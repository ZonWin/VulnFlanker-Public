package collector

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"
)

type fakeFirewallResponse struct {
	output string
	err    error
}

type fakeFirewallRunner struct {
	paths     map[string]bool
	responses map[string]fakeFirewallResponse
}

func (runner fakeFirewallRunner) LookPath(name string) bool {
	return runner.paths[name]
}

func (runner fakeFirewallRunner) Run(name string, args ...string) (string, error) {
	response, ok := runner.responses[name+" "+strings.Join(args, " ")]
	if !ok {
		return "", errors.New("unexpected command")
	}
	return response.output, response.err
}

func TestParseFirewalldZones(t *testing.T) {
	fixture := `public (active)
  target: default
  interfaces: eth0
  sources: 10.0.0.0/8
  services: ssh dhcpv6-client
  ports: 8443/tcp 5353/udp
  protocols:
  forward: no
  masquerade: yes
  rich rules:
    rule family="ipv4" source address="192.0.2.0/24" port port="443" protocol="tcp" accept
`
	rules := parseFirewalldZones(fixture, "runtime")
	if len(rules) != 8 {
		t.Fatalf("expected 8 normalized rules, got %d: %#v", len(rules), rules)
	}
	if rules[0].RuleKind != "interface" || rules[0].InputInterface != "eth0" {
		t.Fatalf("unexpected interface rule: %#v", rules[0])
	}
	rich := rules[len(rules)-1]
	if rich.RuleKind != "rich_rule" || rich.Source != "192.0.2.0/24" || rich.DestinationPort != "443" || rich.Action != "accept" {
		t.Fatalf("unexpected rich rule: %#v", rich)
	}
}

func TestParseUFWStatusAndAdded(t *testing.T) {
	status := `Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere
443/tcp (v6)               DENY IN     2001:db8::/32 (v6)
`
	state, rules := parseUFWStatus(status)
	if state != "active" || len(rules) != 3 {
		t.Fatalf("unexpected UFW status parse: state=%s rules=%#v", state, rules)
	}
	if rules[1].DestinationPort != "22" || rules[1].Protocol != "tcp" || rules[1].Source != "0.0.0.0/0" {
		t.Fatalf("unexpected IPv4 UFW rule: %#v", rules[1])
	}
	if rules[2].Family != "ipv6" || rules[2].Source != "2001:db8::/32" {
		t.Fatalf("unexpected IPv6 UFW rule: %#v", rules[2])
	}
	added := parseUFWAdded("Added user rules (see 'ufw status'):\nufw allow 8080/tcp\nufw deny from 198.51.100.0/24\n")
	if len(added) != 2 || added[0].Scope != "permanent" || added[0].DestinationPort != "8080" {
		t.Fatalf("unexpected UFW added parse: %#v", added)
	}
}

func TestParseIPTablesSaveIPv4AndIPv6(t *testing.T) {
	fixture := `*filter
:INPUT DROP [0:0]
:FORWARD ACCEPT [0:0]
-A INPUT -s 192.0.2.0/24 -p tcp --dport 22 -m conntrack --ctstate NEW -j ACCEPT -m comment --comment "admin ssh"
COMMIT
`
	rules := parseIPTablesSave(fixture, "ipv4")
	if len(rules) != 3 {
		t.Fatalf("expected policies plus rule, got %#v", rules)
	}
	rule := rules[2]
	if rule.Table != "filter" || rule.Chain != "INPUT" || rule.Source != "192.0.2.0/24" || rule.DestinationPort != "22" || rule.Comment != "admin ssh" {
		t.Fatalf("unexpected iptables rule: %#v", rule)
	}
	ipv6 := parseIPTablesSave("*filter\n-A INPUT -p ipv6-icmp -j ACCEPT\nCOMMIT\n", "ipv6")
	if len(ipv6) != 1 || ipv6[0].Family != "ipv6" {
		t.Fatalf("unexpected ip6tables parse: %#v", ipv6)
	}
}

func TestParseNFTablesJSON(t *testing.T) {
	fixture := `{"nftables":[
  {"metainfo":{"version":"1.0.9"}},
  {"chain":{"family":"inet","table":"firewalld","name":"filter_INPUT","policy":"drop"}},
  {"rule":{"family":"inet","table":"firewalld","chain":"filter_INPUT","expr":[
    {"match":{"op":"==","left":{"payload":{"protocol":"tcp","field":"dport"}},"right":8443}},
    {"accept":null}
  ],"comment":"managed rule"}}
]}`
	rules, err := parseNFTablesJSON(fixture)
	if err != nil {
		t.Fatalf("parse nftables: %v", err)
	}
	if len(rules) != 2 || rules[0].RuleKind != "chain_policy" || rules[0].Action != "drop" {
		t.Fatalf("unexpected nftables policies: %#v", rules)
	}
	if rules[1].DestinationPort != "8443" || rules[1].Protocol != "tcp" || rules[1].Action != "accept" {
		t.Fatalf("unexpected nftables rule: %#v", rules[1])
	}
}

func TestCollectFirewallsReportsCoexistingRelationships(t *testing.T) {
	runner := fakeFirewallRunner{
		paths: map[string]bool{"firewall-cmd": true, "iptables": true, "iptables-save": true, "nft": true},
		responses: map[string]fakeFirewallResponse{
			"firewall-cmd --state":                      {output: "running\n"},
			"firewall-cmd --list-all-zones":             {output: "public (active)\n  services: ssh\n"},
			"firewall-cmd --permanent --list-all-zones": {output: "public\n  services: ssh\n"},
			"iptables --version":                        {output: "iptables v1.8.9 (nf_tables)\n"},
			"iptables-save ":                            {output: "*filter\n-A INPUT -j ACCEPT\nCOMMIT\n"},
			"nft -j -s list ruleset":                    {output: `{"nftables":[{"rule":{"family":"inet","table":"firewalld","chain":"filter_INPUT","expr":[{"accept":null}]}}]}`},
		},
	}
	firewalls := collectFirewallsWithRunner(runner)
	if len(firewalls) != 3 {
		t.Fatalf("expected all three engines, got %#v", firewalls)
	}
	if firewalls[0].Engine != "firewalld" || firewalls[0].Backend != "nftables" || !firewalls[0].Effective {
		t.Fatalf("unexpected firewalld relationship: %#v", firewalls[0])
	}
	if firewalls[1].Engine != "iptables" || firewalls[1].Role != "compatibility" || firewalls[1].Effective {
		t.Fatalf("unexpected iptables compatibility relationship: %#v", firewalls[1])
	}
	if firewalls[2].Engine != "nftables" || firewalls[2].ManagedBy != "firewalld" || !firewalls[2].Effective {
		t.Fatalf("unexpected nftables relationship: %#v", firewalls[2])
	}
}

func TestCollectionFailureAndOutputBounds(t *testing.T) {
	runner := fakeFirewallRunner{
		paths: map[string]bool{"ufw": true},
		responses: map[string]fakeFirewallResponse{
			"ufw status verbose": {output: "ERROR: You need to be root to run this script\n", err: errors.New("exit status 1")},
			"ufw show added":     {output: "permission denied\n", err: errors.New("exit status 1")},
		},
	}
	firewalls := collectFirewallsWithRunner(runner)
	if len(firewalls) != 1 || firewalls[0].CollectionStatus != "permission_denied" || firewalls[0].RuntimeState != "unknown" {
		t.Fatalf("unexpected permission failure: %#v", firewalls)
	}
	if classifyFirewallError("", context.DeadlineExceeded) != "timeout" {
		t.Fatal("deadline should be classified as timeout")
	}

	buffer := &limitedFirewallBuffer{limit: 4}
	_, _ = buffer.Write([]byte("abcdefgh"))
	if buffer.String() != "abcd" || !buffer.truncated {
		t.Fatalf("unexpected bounded buffer: value=%q truncated=%v", buffer.String(), buffer.truncated)
	}

	snapshotJSON, err := json.Marshal(Snapshot{Firewalls: []Firewall{}})
	if err != nil || !strings.Contains(string(snapshotJSON), `"firewalls":[]`) {
		t.Fatalf("new agent must send an explicit empty firewall list: %s, %v", snapshotJSON, err)
	}
}

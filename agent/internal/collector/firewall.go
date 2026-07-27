package collector

import (
	"bytes"
	"context"
	"errors"
	"os/exec"
	"sort"
	"strings"
	"time"
)

const (
	firewallCommandTimeout = 5 * time.Second
	firewallOutputLimit    = 1024 * 1024
)

var errFirewallOutputTooLarge = errors.New("firewall command output exceeded limit")

// Firewall represents one logical host-firewall engine. ip6tables is folded
// into iptables and distinguished by each rule's family field.
type Firewall struct {
	Engine           string         `json:"engine"`
	Role             string         `json:"role"`
	Backend          string         `json:"backend,omitempty"`
	ManagedBy        string         `json:"managed_by,omitempty"`
	Effective        bool           `json:"effective"`
	Installed        bool           `json:"installed"`
	RuntimeState     string         `json:"runtime_state"`
	ServiceEnabled   *bool          `json:"service_enabled,omitempty"`
	CollectionStatus string         `json:"collection_status"`
	ErrorCode        string         `json:"error_code,omitempty"`
	ErrorMessage     string         `json:"error_message,omitempty"`
	RawRuntime       string         `json:"raw_runtime,omitempty"`
	RawPermanent     string         `json:"raw_permanent,omitempty"`
	Rules            []FirewallRule `json:"rules"`

	collectionSuccess int
	collectionFailure int
}

type FirewallRule struct {
	Scope           string `json:"scope"`
	Family          string `json:"family,omitempty"`
	Table           string `json:"table,omitempty"`
	Chain           string `json:"chain,omitempty"`
	Zone            string `json:"zone,omitempty"`
	Order           int    `json:"order"`
	RuleKind        string `json:"rule_kind"`
	Action          string `json:"action,omitempty"`
	Protocol        string `json:"protocol,omitempty"`
	Source          string `json:"source,omitempty"`
	Destination     string `json:"destination,omitempty"`
	SourcePort      string `json:"source_port,omitempty"`
	DestinationPort string `json:"destination_port,omitempty"`
	InputInterface  string `json:"in_interface,omitempty"`
	OutputInterface string `json:"out_interface,omitempty"`
	ConnectionState string `json:"state_match,omitempty"`
	Comment         string `json:"comment,omitempty"`
	RawRule         string `json:"raw_rule,omitempty"`
}

type firewallRunner interface {
	LookPath(name string) bool
	Run(name string, args ...string) (string, error)
}

type systemFirewallRunner struct{}

func (systemFirewallRunner) LookPath(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

func (systemFirewallRunner) Run(name string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), firewallCommandTimeout)
	defer cancel()

	output := &limitedFirewallBuffer{limit: firewallOutputLimit}
	command := exec.CommandContext(ctx, name, args...)
	command.Stdout = output
	command.Stderr = output
	err := command.Run()
	if errors.Is(ctx.Err(), context.DeadlineExceeded) {
		return output.String(), context.DeadlineExceeded
	}
	if output.truncated {
		return output.String(), errFirewallOutputTooLarge
	}
	return output.String(), err
}

type limitedFirewallBuffer struct {
	buffer    bytes.Buffer
	limit     int
	truncated bool
}

func (buffer *limitedFirewallBuffer) Write(input []byte) (int, error) {
	written := len(input)
	remaining := buffer.limit - buffer.buffer.Len()
	if remaining <= 0 {
		buffer.truncated = true
		return written, nil
	}
	if len(input) > remaining {
		_, _ = buffer.buffer.Write(input[:remaining])
		buffer.truncated = true
		return written, nil
	}
	_, _ = buffer.buffer.Write(input)
	return written, nil
}

func (buffer *limitedFirewallBuffer) String() string {
	return buffer.buffer.String()
}

// CollectFirewalls returns every installed supported engine. Installed engines
// that cannot be read are included with an error status instead of disappearing.
func CollectFirewalls() []Firewall {
	return collectFirewallsWithRunner(systemFirewallRunner{})
}

func collectFirewallsWithRunner(runner firewallRunner) []Firewall {
	firewalls := make([]Firewall, 0, 4)
	if runner.LookPath("firewall-cmd") {
		firewalls = append(firewalls, collectFirewalld(runner))
	}
	if runner.LookPath("ufw") {
		firewalls = append(firewalls, collectUFW(runner))
	}
	if runner.LookPath("iptables-save") || runner.LookPath("ip6tables-save") {
		firewalls = append(firewalls, collectIPTables(runner))
	}
	if runner.LookPath("nft") {
		firewalls = append(firewalls, collectNFTables(runner))
	}

	inferFirewallRelationships(firewalls)
	for index := range firewalls {
		finalizeFirewall(&firewalls[index])
	}
	sort.SliceStable(firewalls, func(left, right int) bool {
		return firewallEngineOrder(firewalls[left].Engine) < firewallEngineOrder(firewalls[right].Engine)
	})
	return firewalls
}

func newFirewall(engine, role string) Firewall {
	return Firewall{
		Engine:           engine,
		Role:             role,
		Installed:        true,
		RuntimeState:     "unknown",
		CollectionStatus: "success",
		Rules:            make([]FirewallRule, 0),
	}
}

func recordFirewallFailure(firewall *Firewall, output string, err error) {
	firewall.collectionFailure++
	code := classifyFirewallError(output, err)
	if firewall.ErrorCode == "" || code == "permission_denied" || code == "timeout" {
		firewall.ErrorCode = code
		message := strings.TrimSpace(output)
		if message == "" && err != nil {
			message = err.Error()
		}
		if len(message) > 1024 {
			message = message[:1024]
		}
		firewall.ErrorMessage = message
	}
}

func classifyFirewallError(output string, err error) string {
	if errors.Is(err, context.DeadlineExceeded) {
		return "timeout"
	}
	if errors.Is(err, errFirewallOutputTooLarge) {
		return "output_too_large"
	}
	message := strings.ToLower(output)
	for _, marker := range []string{
		"permission denied",
		"operation not permitted",
		"must be root",
		"insufficient privileges",
		"you need to be root",
	} {
		if strings.Contains(message, marker) {
			return "permission_denied"
		}
	}
	return "command_failed"
}

func finalizeFirewall(firewall *Firewall) {
	for index := range firewall.Rules {
		firewall.Rules[index].Order = index
	}
	if firewall.collectionFailure == 0 {
		firewall.CollectionStatus = "success"
	} else if firewall.collectionSuccess > 0 {
		firewall.CollectionStatus = "partial"
	} else {
		switch firewall.ErrorCode {
		case "permission_denied", "timeout":
			firewall.CollectionStatus = firewall.ErrorCode
		default:
			firewall.CollectionStatus = "error"
		}
	}
	if firewall.CollectionStatus == "success" {
		firewall.ErrorCode = ""
		firewall.ErrorMessage = ""
	}
}

func inferFirewallRelationships(firewalls []Firewall) {
	byEngine := make(map[string]*Firewall, len(firewalls))
	for index := range firewalls {
		byEngine[firewalls[index].Engine] = &firewalls[index]
	}

	nft, hasNFT := byEngine["nftables"]
	if hasNFT {
		content := strings.ToLower(nft.RawRuntime)
		switch {
		case strings.Contains(content, "firewalld"):
			nft.ManagedBy = "firewalld"
		case strings.Contains(content, "ufw"):
			nft.ManagedBy = "ufw"
		}
	}

	if firewalld, ok := byEngine["firewalld"]; ok {
		if hasNFT && nft.ManagedBy == "firewalld" {
			firewalld.Backend = "nftables"
		} else if iptables, exists := byEngine["iptables"]; exists && iptables.Backend == "iptables" {
			firewalld.Backend = "iptables"
		}
	}
	if ufw, ok := byEngine["ufw"]; ok {
		if iptables, exists := byEngine["iptables"]; exists && iptables.Backend == "nftables" {
			ufw.Backend = "nftables"
		} else {
			ufw.Backend = "iptables"
		}
	}
	if iptables, ok := byEngine["iptables"]; ok {
		content := strings.ToLower(iptables.RawRuntime)
		switch {
		case strings.Contains(content, "firewalld"):
			iptables.ManagedBy = "firewalld"
		case strings.Contains(content, "ufw"):
			iptables.ManagedBy = "ufw"
		}
	}
}

func firewallEngineOrder(engine string) int {
	switch engine {
	case "firewalld":
		return 0
	case "ufw":
		return 1
	case "iptables":
		return 2
	case "nftables":
		return 3
	default:
		return 99
	}
}

package collector

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

const maxFirewallRules = 20000

var multiSpacePattern = regexp.MustCompile(`\s{2,}`)

func parseFirewalldZones(output, scope string) []FirewallRule {
	rules := make([]FirewallRule, 0)
	zone := ""
	scanner := bufio.NewScanner(strings.NewReader(output))
	scanner.Buffer(make([]byte, 4096), firewallOutputLimit)
	for scanner.Scan() && len(rules) < maxFirewallRules {
		line := scanner.Text()
		trimmed := strings.TrimSpace(line)
		if trimmed == "" {
			continue
		}
		if line[0] != ' ' && line[0] != '\t' {
			zone = strings.TrimSpace(strings.TrimSuffix(trimmed, "(active)"))
			continue
		}
		if zone != "" && strings.HasPrefix(trimmed, "rule ") {
			rules = append(rules, parseFirewalldRichRule(scope, zone, trimmed))
			continue
		}
		key, value, found := strings.Cut(trimmed, ":")
		if !found || zone == "" {
			continue
		}
		key = strings.TrimSpace(key)
		value = strings.TrimSpace(value)
		switch key {
		case "target":
			if value != "" && value != "default" {
				rules = append(rules, FirewallRule{Scope: scope, Family: "inet", Zone: zone, RuleKind: "zone_target", Action: value, RawRule: trimmed})
			}
		case "interfaces":
			for _, item := range strings.Fields(value) {
				rules = append(rules, FirewallRule{Scope: scope, Family: "inet", Zone: zone, RuleKind: "interface", InputInterface: item, RawRule: item})
			}
		case "sources":
			for _, item := range strings.Fields(value) {
				rules = append(rules, FirewallRule{Scope: scope, Family: familyForAddress(item), Zone: zone, RuleKind: "source", Source: item, RawRule: item})
			}
		case "services":
			for _, item := range strings.Fields(value) {
				rules = append(rules, FirewallRule{Scope: scope, Family: "inet", Zone: zone, RuleKind: "service", Action: "accept", DestinationPort: item, RawRule: item})
			}
		case "ports", "source-ports":
			for _, item := range strings.Fields(value) {
				port, protocol := splitPortProtocol(item)
				rule := FirewallRule{Scope: scope, Family: "inet", Zone: zone, RuleKind: strings.TrimSuffix(key, "s"), Action: "accept", Protocol: protocol, RawRule: item}
				if key == "source-ports" {
					rule.SourcePort = port
				} else {
					rule.DestinationPort = port
				}
				rules = append(rules, rule)
			}
		case "protocols":
			for _, item := range strings.Fields(value) {
				rules = append(rules, FirewallRule{Scope: scope, Family: "inet", Zone: zone, RuleKind: "protocol", Action: "accept", Protocol: item, RawRule: item})
			}
		case "forward", "masquerade":
			if value == "yes" {
				rules = append(rules, FirewallRule{Scope: scope, Family: "inet", Zone: zone, RuleKind: key, Action: key, RawRule: trimmed})
			}
		case "forward-ports":
			if value != "" {
				rules = append(rules, FirewallRule{Scope: scope, Family: "inet", Zone: zone, RuleKind: "forward_port", Action: "dnat", RawRule: value})
			}
		case "icmp-blocks":
			for _, item := range strings.Fields(value) {
				rules = append(rules, FirewallRule{Scope: scope, Family: "inet", Zone: zone, RuleKind: "icmp_block", Action: "reject", Protocol: "icmp", RawRule: item})
			}
		case "rich rules":
			if value != "" {
				rules = append(rules, parseFirewalldRichRule(scope, zone, value))
			}
		}
	}
	return rules
}

func parseFirewalldRichRule(scope, zone, raw string) FirewallRule {
	rule := FirewallRule{Scope: scope, Family: "inet", Zone: zone, RuleKind: "rich_rule", RawRule: raw}
	fields := splitQuotedFields(raw)
	for index := 0; index < len(fields); index++ {
		field := fields[index]
		switch {
		case strings.HasPrefix(field, "family="):
			rule.Family = strings.Trim(strings.TrimPrefix(field, "family="), `"`)
		case strings.HasPrefix(field, "address=") && index > 0 && fields[index-1] == "source":
			rule.Source = strings.Trim(strings.TrimPrefix(field, "address="), `"`)
		case strings.HasPrefix(field, "address=") && index > 0 && fields[index-1] == "destination":
			rule.Destination = strings.Trim(strings.TrimPrefix(field, "address="), `"`)
		case strings.HasPrefix(field, "port="):
			rule.DestinationPort = strings.Trim(strings.TrimPrefix(field, "port="), `"`)
		case strings.HasPrefix(field, "protocol="):
			rule.Protocol = strings.Trim(strings.TrimPrefix(field, "protocol="), `"`)
		case field == "accept" || field == "drop" || field == "reject" || field == "masquerade" || field == "mark":
			rule.Action = field
		}
	}
	return rule
}

func parseUFWStatus(output string) (string, []FirewallRule) {
	state := "unknown"
	rules := make([]FirewallRule, 0)
	inRules := false
	scanner := bufio.NewScanner(strings.NewReader(output))
	scanner.Buffer(make([]byte, 4096), firewallOutputLimit)
	for scanner.Scan() && len(rules) < maxFirewallRules {
		trimmed := strings.TrimSpace(scanner.Text())
		lower := strings.ToLower(trimmed)
		if strings.HasPrefix(lower, "status:") {
			if strings.Contains(lower, "inactive") {
				state = "inactive"
			} else if strings.Contains(lower, "active") {
				state = "active"
			}
			continue
		}
		if strings.HasPrefix(lower, "default:") {
			rules = append(rules, FirewallRule{Scope: "runtime", Family: "inet", RuleKind: "default_policy", RawRule: trimmed, Action: strings.TrimSpace(strings.TrimPrefix(lower, "default:"))})
			continue
		}
		if strings.HasPrefix(trimmed, "--") {
			inRules = true
			continue
		}
		if !inRules || trimmed == "" || strings.HasPrefix(lower, "to ") {
			continue
		}
		columns := multiSpacePattern.Split(trimmed, 3)
		if len(columns) < 3 {
			continue
		}
		to, action, from := columns[0], columns[1], columns[2]
		family := "ipv4"
		if strings.Contains(to, "(v6)") || strings.Contains(from, "(v6)") {
			family = "ipv6"
		}
		to = strings.TrimSpace(strings.ReplaceAll(to, "(v6)", ""))
		from = strings.TrimSpace(strings.ReplaceAll(from, "(v6)", ""))
		port, protocol := splitPortProtocol(to)
		rules = append(rules, FirewallRule{
			Scope: "runtime", Family: family, RuleKind: "rule", Action: strings.ToLower(strings.Fields(action)[0]),
			Protocol: protocol, Source: normalizeUFWAnywhere(from, family), DestinationPort: port, RawRule: trimmed,
		})
	}
	return state, rules
}

func parseUFWAdded(output string) []FirewallRule {
	rules := make([]FirewallRule, 0)
	scanner := bufio.NewScanner(strings.NewReader(output))
	for scanner.Scan() && len(rules) < maxFirewallRules {
		trimmed := strings.TrimSpace(scanner.Text())
		if !strings.HasPrefix(strings.ToLower(trimmed), "ufw ") {
			continue
		}
		fields := splitQuotedFields(trimmed)
		rule := FirewallRule{Scope: "permanent", Family: "inet", RuleKind: "rule", RawRule: trimmed}
		for index, field := range fields {
			lower := strings.ToLower(field)
			if lower == "allow" || lower == "deny" || lower == "reject" || lower == "limit" {
				rule.Action = lower
			}
			if index > 0 && fields[index-1] == "from" {
				rule.Source = field
			}
			if index > 0 && fields[index-1] == "to" {
				rule.Destination = field
			}
			if index > 0 && fields[index-1] == "port" {
				rule.DestinationPort = field
			}
			if index > 0 && fields[index-1] == "proto" {
				rule.Protocol = field
			}
			if index == len(fields)-1 && strings.Contains(field, "/") && rule.DestinationPort == "" {
				rule.DestinationPort, rule.Protocol = splitPortProtocol(field)
			}
		}
		rules = append(rules, rule)
	}
	return rules
}

func parseIPTablesSave(output, family string) []FirewallRule {
	rules := make([]FirewallRule, 0)
	table := ""
	scanner := bufio.NewScanner(strings.NewReader(output))
	scanner.Buffer(make([]byte, 4096), firewallOutputLimit)
	for scanner.Scan() && len(rules) < maxFirewallRules {
		trimmed := strings.TrimSpace(scanner.Text())
		if trimmed == "" || strings.HasPrefix(trimmed, "#") || strings.HasPrefix(trimmed, "COMMIT") {
			continue
		}
		if strings.HasPrefix(trimmed, "*") {
			table = strings.TrimPrefix(trimmed, "*")
			continue
		}
		if strings.HasPrefix(trimmed, ":") {
			fields := strings.Fields(strings.TrimPrefix(trimmed, ":"))
			if len(fields) >= 2 && fields[1] != "-" {
				rules = append(rules, FirewallRule{Scope: "runtime", Family: family, Table: table, Chain: fields[0], RuleKind: "chain_policy", Action: strings.ToLower(fields[1]), RawRule: trimmed})
			}
			continue
		}
		if !strings.HasPrefix(trimmed, "-A ") {
			continue
		}
		fields := splitQuotedFields(trimmed)
		rule := FirewallRule{Scope: "runtime", Family: family, Table: table, RuleKind: "rule", RawRule: trimmed}
		for index := 0; index < len(fields); index++ {
			value := func() string {
				if index+1 < len(fields) {
					return fields[index+1]
				}
				return ""
			}()
			switch fields[index] {
			case "-A":
				rule.Chain = value
			case "-p", "--protocol":
				rule.Protocol = value
			case "-s", "--source":
				rule.Source = value
			case "-d", "--destination":
				rule.Destination = value
			case "--sport", "--source-port", "--sports", "--source-ports":
				rule.SourcePort = value
			case "--dport", "--destination-port", "--dports", "--destination-ports":
				rule.DestinationPort = value
			case "-i", "--in-interface":
				rule.InputInterface = value
			case "-o", "--out-interface":
				rule.OutputInterface = value
			case "--state", "--ctstate":
				rule.ConnectionState = value
			case "-j", "--jump", "-g", "--goto":
				rule.Action = strings.ToLower(value)
			case "--comment":
				rule.Comment = value
			}
		}
		rules = append(rules, rule)
	}
	return rules
}

func parseNFTablesJSON(output string) ([]FirewallRule, error) {
	var document struct {
		NFTables []map[string]json.RawMessage `json:"nftables"`
	}
	if err := json.Unmarshal([]byte(output), &document); err != nil {
		return nil, fmt.Errorf("parse nftables JSON: %w", err)
	}
	rules := make([]FirewallRule, 0)
	for _, item := range document.NFTables {
		if len(rules) >= maxFirewallRules {
			break
		}
		for _, kind := range []string{"chain", "rule", "set", "map", "flowtable"} {
			raw, found := item[kind]
			if !found {
				continue
			}
			var detail map[string]any
			if err := json.Unmarshal(raw, &detail); err != nil {
				return nil, fmt.Errorf("parse nftables %s: %w", kind, err)
			}
			rule := FirewallRule{
				Scope: "runtime", Family: anyString(detail["family"]), Table: anyString(detail["table"]),
				Chain: anyString(detail["chain"]), RuleKind: kind, Comment: anyString(detail["comment"]), RawRule: compactJSON(raw),
			}
			if kind == "chain" {
				rule.Chain = anyString(detail["name"])
				rule.Action = strings.ToLower(anyString(detail["policy"]))
				if rule.Action == "" {
					continue
				}
				rule.RuleKind = "chain_policy"
			} else if kind == "set" || kind == "map" || kind == "flowtable" {
				rule.Chain = anyString(detail["name"])
			} else {
				extractNFTExpressions(&rule, detail["expr"])
			}
			rules = append(rules, rule)
		}
	}
	return rules, nil
}

func extractNFTExpressions(rule *FirewallRule, expressions any) {
	items, ok := expressions.([]any)
	if !ok {
		return
	}
	for _, item := range items {
		object, ok := item.(map[string]any)
		if !ok {
			continue
		}
		for _, action := range []string{"accept", "drop", "reject", "return", "continue", "masquerade", "redirect", "dnat", "snat", "jump", "goto"} {
			if value, found := object[action]; found {
				rule.Action = action
				if action == "jump" || action == "goto" {
					rule.Action += ":" + anyString(value)
				}
			}
		}
		match, ok := object["match"].(map[string]any)
		if !ok {
			continue
		}
		leftJSON, _ := json.Marshal(match["left"])
		left := strings.ToLower(string(leftJSON))
		right := anyString(match["right"])
		switch {
		case strings.Contains(left, `"field":"dport"`):
			rule.DestinationPort = right
		case strings.Contains(left, `"field":"sport"`):
			rule.SourcePort = right
		case strings.Contains(left, `"field":"saddr"`):
			rule.Source = right
		case strings.Contains(left, `"field":"daddr"`):
			rule.Destination = right
		case strings.Contains(left, `"key":"iifname"`):
			rule.InputInterface = right
		case strings.Contains(left, `"key":"oifname"`):
			rule.OutputInterface = right
		case strings.Contains(left, `"key":"ct state"`):
			rule.ConnectionState = right
		}
		for _, protocol := range []string{"tcp", "udp", "sctp", "icmp", "icmpv6"} {
			if strings.Contains(left, `"protocol":"`+protocol+`"`) {
				rule.Protocol = protocol
			}
		}
	}
}

func splitPortProtocol(value string) (string, string) {
	parts := strings.SplitN(value, "/", 2)
	if len(parts) == 2 {
		return parts[0], parts[1]
	}
	return value, ""
}

func familyForAddress(value string) string {
	if strings.Contains(value, ":") {
		return "ipv6"
	}
	return "ipv4"
}

func normalizeUFWAnywhere(value, family string) string {
	if strings.EqualFold(strings.TrimSpace(value), "anywhere") {
		if family == "ipv6" {
			return "::/0"
		}
		return "0.0.0.0/0"
	}
	return value
}

func splitQuotedFields(input string) []string {
	fields := make([]string, 0)
	var current strings.Builder
	quote := rune(0)
	escaped := false
	flush := func() {
		if current.Len() > 0 {
			fields = append(fields, current.String())
			current.Reset()
		}
	}
	for _, character := range input {
		if escaped {
			current.WriteRune(character)
			escaped = false
			continue
		}
		if character == '\\' {
			escaped = true
			continue
		}
		if quote != 0 {
			if character == quote {
				quote = 0
			} else {
				current.WriteRune(character)
			}
			continue
		}
		if character == '\'' || character == '"' {
			quote = character
			continue
		}
		if character == ' ' || character == '\t' || character == '\n' {
			flush()
			continue
		}
		current.WriteRune(character)
	}
	flush()
	return fields
}

func compactJSON(raw json.RawMessage) string {
	buffer := &bytes.Buffer{}
	if err := json.Compact(buffer, raw); err != nil {
		return string(raw)
	}
	return buffer.String()
}

func anyString(value any) string {
	switch typed := value.(type) {
	case nil:
		return ""
	case string:
		return typed
	case float64:
		return strconv.FormatFloat(typed, 'f', -1, 64)
	case []any:
		parts := make([]string, 0, len(typed))
		for _, item := range typed {
			parts = append(parts, anyString(item))
		}
		return strings.Join(parts, ",")
	default:
		return fmt.Sprint(typed)
	}
}

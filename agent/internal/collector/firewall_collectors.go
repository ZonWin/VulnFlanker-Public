package collector

import "strings"

func collectFirewalld(runner firewallRunner) Firewall {
	firewall := newFirewall("firewalld", "manager")
	stateOutput, stateErr := runner.Run("firewall-cmd", "--state")
	lowerState := strings.ToLower(stateOutput)
	if stateErr == nil || strings.Contains(lowerState, "not running") {
		firewall.collectionSuccess++
		if strings.Contains(lowerState, "running") && !strings.Contains(lowerState, "not running") {
			firewall.RuntimeState = "active"
			firewall.Effective = true
		} else {
			firewall.RuntimeState = "inactive"
		}
	} else {
		recordFirewallFailure(&firewall, stateOutput, stateErr)
	}

	if runner.LookPath("systemctl") {
		serviceOutput, serviceErr := runner.Run("systemctl", "is-enabled", "firewalld")
		serviceState := strings.TrimSpace(serviceOutput)
		if serviceErr == nil || serviceState == "disabled" {
			enabled := serviceState == "enabled"
			firewall.ServiceEnabled = &enabled
		}
	}

	if firewall.RuntimeState == "active" {
		runtimeOutput, runtimeErr := runner.Run("firewall-cmd", "--list-all-zones")
		if runtimeErr == nil {
			firewall.collectionSuccess++
			firewall.RawRuntime = runtimeOutput
			firewall.Rules = append(firewall.Rules, parseFirewalldZones(runtimeOutput, "runtime")...)
		} else {
			recordFirewallFailure(&firewall, runtimeOutput, runtimeErr)
		}
	}

	permanentOutput, permanentErr := runner.Run("firewall-cmd", "--permanent", "--list-all-zones")
	if permanentErr == nil {
		firewall.collectionSuccess++
		firewall.RawPermanent = permanentOutput
		firewall.Rules = append(firewall.Rules, parseFirewalldZones(permanentOutput, "permanent")...)
		if firewall.RuntimeState == "unknown" && strings.TrimSpace(permanentOutput) != "" {
			firewall.RuntimeState = "configured"
		}
	} else {
		recordFirewallFailure(&firewall, permanentOutput, permanentErr)
	}
	return firewall
}

func collectUFW(runner firewallRunner) Firewall {
	firewall := newFirewall("ufw", "manager")
	firewall.Backend = "iptables"
	statusOutput, statusErr := runner.Run("ufw", "status", "verbose")
	if statusErr == nil {
		firewall.collectionSuccess++
		firewall.RawRuntime = statusOutput
		firewall.RuntimeState, firewall.Rules = parseUFWStatus(statusOutput)
		firewall.Effective = firewall.RuntimeState == "active"
	} else {
		recordFirewallFailure(&firewall, statusOutput, statusErr)
	}

	permanentOutput, permanentErr := runner.Run("ufw", "show", "added")
	if permanentErr == nil {
		firewall.collectionSuccess++
		firewall.RawPermanent = permanentOutput
		firewall.Rules = append(firewall.Rules, parseUFWAdded(permanentOutput)...)
		if firewall.RuntimeState == "unknown" && strings.TrimSpace(permanentOutput) != "" {
			firewall.RuntimeState = "configured"
		}
	} else {
		recordFirewallFailure(&firewall, permanentOutput, permanentErr)
	}
	return firewall
}

func collectIPTables(runner firewallRunner) Firewall {
	firewall := newFirewall("iptables", "backend")
	versionCommand := "iptables"
	if !runner.LookPath(versionCommand) {
		versionCommand = "iptables-save"
	}
	versionOutput, _ := runner.Run(versionCommand, "--version")
	if strings.Contains(strings.ToLower(versionOutput), "nf_tables") {
		firewall.Role = "compatibility"
		firewall.Backend = "nftables"
		firewall.Effective = false
	} else {
		firewall.Backend = "iptables"
	}

	parts := make([]string, 0, 2)
	if runner.LookPath("iptables-save") {
		output, err := runner.Run("iptables-save")
		if err == nil {
			firewall.collectionSuccess++
			parts = append(parts, "# IPv4\n"+output)
			firewall.Rules = append(firewall.Rules, parseIPTablesSave(output, "ipv4")...)
		} else {
			recordFirewallFailure(&firewall, output, err)
		}
	}
	if runner.LookPath("ip6tables-save") {
		output, err := runner.Run("ip6tables-save")
		if err == nil {
			firewall.collectionSuccess++
			parts = append(parts, "# IPv6\n"+output)
			firewall.Rules = append(firewall.Rules, parseIPTablesSave(output, "ipv6")...)
		} else {
			recordFirewallFailure(&firewall, output, err)
		}
	}
	firewall.RawRuntime = strings.Join(parts, "\n")
	if len(firewall.Rules) > 0 {
		firewall.RuntimeState = "active"
		if firewall.Role != "compatibility" {
			firewall.Effective = true
		}
	} else if firewall.collectionSuccess > 0 {
		firewall.RuntimeState = "inactive"
	}
	return firewall
}

func collectNFTables(runner firewallRunner) Firewall {
	firewall := newFirewall("nftables", "backend")
	output, err := runner.Run("nft", "-j", "-s", "list", "ruleset")
	if err != nil {
		recordFirewallFailure(&firewall, output, err)
		return firewall
	}
	firewall.collectionSuccess++
	firewall.RawRuntime = output
	rules, parseErr := parseNFTablesJSON(output)
	if parseErr != nil {
		recordFirewallFailure(&firewall, parseErr.Error(), parseErr)
		return firewall
	}
	firewall.Rules = rules
	if len(rules) > 0 {
		firewall.RuntimeState = "active"
		firewall.Effective = true
	} else {
		firewall.RuntimeState = "inactive"
	}
	return firewall
}

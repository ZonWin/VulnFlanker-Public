package config

import "testing"

func TestCurrentAgentVersion(t *testing.T) {
	cfg := Load(nil)

	if cfg.AgentVersion != "0.2.0" {
		t.Fatalf("expected Agent version 0.2.0, got %q", cfg.AgentVersion)
	}
}

func TestAgentIngressURLTakesPriorityOverServerURL(t *testing.T) {
	t.Setenv("VULNFLANKER_AGENT_INGRESS_URL", "http://agent.example.test")
	t.Setenv("VULNFLANKER_SERVER_URL", "http://legacy.example.test")

	cfg := Load(nil)

	if cfg.ServerURL != "http://agent.example.test" {
		t.Fatalf("expected agent ingress URL, got %q", cfg.ServerURL)
	}
}

func TestServerURLFallbackIsKept(t *testing.T) {
	t.Setenv("VULNFLANKER_AGENT_INGRESS_URL", "")
	t.Setenv("VULNFLANKER_SERVER_URL", "http://legacy.example.test")

	cfg := Load(nil)

	if cfg.ServerURL != "http://legacy.example.test" {
		t.Fatalf("expected legacy server URL fallback, got %q", cfg.ServerURL)
	}
}

func TestAgentIngressURLFlag(t *testing.T) {
	cfg := Load([]string{"-agent-ingress-url", "http://flag.example.test"})

	if cfg.ServerURL != "http://flag.example.test" {
		t.Fatalf("expected flag URL, got %q", cfg.ServerURL)
	}
}

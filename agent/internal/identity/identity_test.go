package identity

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadOrCreateReusesAgentID(t *testing.T) {
	path := filepath.Join(t.TempDir(), "agent-id")

	first, err := LoadOrCreate(path)
	if err != nil {
		t.Fatalf("first LoadOrCreate failed: %v", err)
	}
	second, err := LoadOrCreate(path)
	if err != nil {
		t.Fatalf("second LoadOrCreate failed: %v", err)
	}

	if first != second {
		t.Fatalf("expected stable agent id, got %q then %q", first, second)
	}
	if !strings.HasPrefix(first, "vf-agent-") {
		t.Fatalf("unexpected agent id prefix: %q", first)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("agent id file was not written: %v", err)
	}
	if strings.TrimSpace(string(data)) != first {
		t.Fatalf("agent id file contains %q, want %q", strings.TrimSpace(string(data)), first)
	}
}

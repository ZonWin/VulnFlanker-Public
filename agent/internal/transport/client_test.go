package transport

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"vulnflanker-agent/internal/collector"
	"vulnflanker-agent/internal/taskrunner"
)

func TestClientUsesAgentIngressPaths(t *testing.T) {
	seen := make(map[string]int)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen[r.Method+" "+r.URL.String()]++
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/agent/v1/heartbeat", "/agent/v1/snapshots", "/agent/v1/tasks/task-1/results":
			w.WriteHeader(http.StatusAccepted)
			_, _ = w.Write([]byte(`{"status":"accepted","task_id":"task-1","evidence_count":0}`))
		case "/agent/v1/tasks/next":
			_, _ = w.Write([]byte(`{"task":null}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	client, err := New(server.URL, time.Second, "secret-1")
	if err != nil {
		t.Fatal(err)
	}

	if err := client.SubmitHeartbeat(Heartbeat{AgentID: "agent-1", Hostname: "host-1", Platform: "linux", Version: "0.1.0"}); err != nil {
		t.Fatal(err)
	}
	if err := client.SubmitSnapshot(collector.Snapshot{AgentID: "agent-1"}); err != nil {
		t.Fatal(err)
	}
	if _, err := client.PollTask("agent-1"); err != nil {
		t.Fatal(err)
	}
	if err := client.SubmitTaskResult("agent-1", "task-1", taskrunner.TaskResult{Status: "completed"}); err != nil {
		t.Fatal(err)
	}

	expected := []string{
		"POST /agent/v1/heartbeat",
		"POST /agent/v1/snapshots",
		"GET /agent/v1/tasks/next",
		"POST /agent/v1/tasks/task-1/results",
	}
	for _, key := range expected {
		if seen[key] != 1 {
			t.Fatalf("expected request %q once, saw %d; all requests: %#v", key, seen[key], seen)
		}
	}
}

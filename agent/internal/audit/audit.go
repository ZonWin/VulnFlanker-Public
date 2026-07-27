package audit

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

type Logger struct {
	path string
}

type Event struct {
	Timestamp time.Time      `json:"timestamp"`
	EventType string         `json:"event_type"`
	Details   map[string]any `json:"details,omitempty"`
}

func New(logDir string) (*Logger, error) {
	if err := os.MkdirAll(logDir, 0o755); err != nil {
		return nil, err
	}
	return &Logger{path: filepath.Join(logDir, "agent-audit.jsonl")}, nil
}

func (l *Logger) Record(eventType string, details map[string]any) error {
	event := Event{
		Timestamp: time.Now().UTC(),
		EventType: eventType,
		Details:   details,
	}
	line, err := json.Marshal(event)
	if err != nil {
		return err
	}
	file, err := os.OpenFile(l.path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o600)
	if err != nil {
		return err
	}
	defer file.Close()
	_, err = file.Write(append(line, '\n'))
	return err
}

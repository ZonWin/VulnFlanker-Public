package identity

import (
	"crypto/rand"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func LoadOrCreate(path string) (string, error) {
	if data, err := os.ReadFile(path); err == nil {
		agentID := strings.TrimSpace(string(data))
		if agentID != "" {
			return agentID, nil
		}
	}

	agentID, err := newAgentID()
	if err != nil {
		return "", err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", err
	}
	if err := os.WriteFile(path, []byte(agentID+"\n"), 0o600); err != nil {
		return "", err
	}
	return agentID, nil
}

func Save(path string, value string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(strings.TrimSpace(value)+"\n"), 0o600)
}

func LoadSecret(path string) (string, bool, error) {
	data, err := os.ReadFile(path)
	if err == nil {
		secret := strings.TrimSpace(string(data))
		return secret, secret != "", nil
	}
	if os.IsNotExist(err) {
		return "", false, nil
	}
	return "", false, err
}

func SaveSecret(path string, secret string) error {
	return Save(path, secret)
}

func newAgentID() (string, error) {
	var buf [16]byte
	if _, err := rand.Read(buf[:]); err != nil {
		return "", err
	}
	return fmt.Sprintf(
		"vf-agent-%x-%x-%x-%x-%x",
		buf[0:4],
		buf[4:6],
		buf[6:8],
		buf[8:10],
		buf[10:16],
	), nil
}

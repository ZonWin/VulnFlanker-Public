package main

import (
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"time"

	"vulnflanker-agent/internal/audit"
	"vulnflanker-agent/internal/collector"
	"vulnflanker-agent/internal/config"
	"vulnflanker-agent/internal/identity"
	"vulnflanker-agent/internal/taskrunner"
	"vulnflanker-agent/internal/transport"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(args []string) error {
	cfg := config.Load(args)
	agentID, err := identity.LoadOrCreate(cfg.AgentIDFile)
	if err != nil {
		return err
	}
	agentSecret, err := ensureAgentSecret(cfg, agentID)
	if err != nil {
		return err
	}
	auditLog, err := audit.New(cfg.LogDir)
	if err != nil {
		return err
	}
	client, err := transport.New(cfg.ServerURL, cfg.RequestTimeout, agentSecret)
	if err != nil {
		return err
	}

	if cfg.Once {
		return runCycle(cfg, agentID, auditLog, client)
	}

	heartbeatTicker := time.NewTicker(cfg.HeartbeatEvery)
	snapshotTicker := time.NewTicker(cfg.SnapshotEvery)
	taskTicker := time.NewTicker(cfg.TaskPollEvery)
	defer heartbeatTicker.Stop()
	defer snapshotTicker.Stop()
	defer taskTicker.Stop()

	if err := runCycle(cfg, agentID, auditLog, client); err != nil {
		_ = auditLog.Record("cycle_failed", map[string]any{"error": err.Error()})
	}
	for {
		select {
		case <-heartbeatTicker.C:
			if err := submitHeartbeat(cfg, agentID, client); err != nil {
				_ = auditLog.Record("heartbeat_failed", map[string]any{"error": err.Error()})
			}
		case <-snapshotTicker.C:
			if err := submitSnapshot(cfg, agentID, client); err != nil {
				_ = auditLog.Record("snapshot_failed", map[string]any{"error": err.Error()})
			}
		case <-taskTicker.C:
			if err := pollAndRunTask(agentID, auditLog, client); err != nil {
				_ = auditLog.Record("task_cycle_failed", map[string]any{"error": err.Error()})
			}
		}
	}
}

func ensureAgentSecret(cfg config.Config, agentID string) (string, error) {
	secret, ok, err := identity.LoadSecret(cfg.AgentSecretFile)
	if err != nil {
		return "", err
	}
	if ok {
		return secret, nil
	}
	if cfg.EnrollmentToken == "" {
		return "", fmt.Errorf("agent secret missing at %s and VULNFLANKER_AGENT_ENROLLMENT_TOKEN is not set", cfg.AgentSecretFile)
	}
	hostname, _ := os.Hostname()
	client, err := transport.New(cfg.ServerURL, cfg.RequestTimeout, "")
	if err != nil {
		return "", err
	}
	response, err := client.Enroll(transport.EnrollRequest{
		EnrollmentToken: cfg.EnrollmentToken,
		AgentID:         agentID,
		Hostname:        hostname,
		Platform:        runtime.GOOS,
		Version:         cfg.AgentVersion,
	})
	if err != nil {
		return "", err
	}
	if response.AgentID != "" && response.AgentID != agentID {
		agentID = response.AgentID
		if err := identity.Save(cfg.AgentIDFile, agentID); err != nil {
			return "", err
		}
	}
	if response.AgentSecret == "" {
		return "", fmt.Errorf("agent enrollment response did not include agent_secret")
	}
	if err := identity.SaveSecret(cfg.AgentSecretFile, response.AgentSecret); err != nil {
		return "", err
	}
	return response.AgentSecret, nil
}

func runCycle(
	cfg config.Config,
	agentID string,
	auditLog *audit.Logger,
	client *transport.Client,
) error {
	if cfg.PrintSnapshot {
		return printSnapshot(cfg, agentID)
	}
	if err := submitHeartbeat(cfg, agentID, client); err != nil {
		return err
	}
	if err := submitSnapshot(cfg, agentID, client); err != nil {
		return err
	}
	return pollAndRunTask(agentID, auditLog, client)
}

func submitHeartbeat(cfg config.Config, agentID string, client *transport.Client) error {
	hostname, _ := os.Hostname()
	return client.SubmitHeartbeat(transport.Heartbeat{
		AgentID:  agentID,
		Hostname: hostname,
		Platform: runtime.GOOS,
		Version:  cfg.AgentVersion,
	})
}

func submitSnapshot(cfg config.Config, agentID string, client *transport.Client) error {
	snapshot, err := collectSnapshot(cfg, agentID)
	if err != nil {
		return err
	}
	return client.SubmitSnapshot(snapshot)
}

func printSnapshot(cfg config.Config, agentID string) error {
	snapshot, err := collectSnapshot(cfg, agentID)
	if err != nil {
		return err
	}
	encoded, err := json.MarshalIndent(snapshot, "", "  ")
	if err != nil {
		return err
	}
	fmt.Println(string(encoded))
	return nil
}

func collectSnapshot(cfg config.Config, agentID string) (collector.Snapshot, error) {
	return collector.Collect(agentID, cfg.AgentVersion, collector.ProfileOptions{
		EnvironmentType:    cfg.EnvironmentType,
		ExposureType:       cfg.ExposureType,
		BusinessSystem:     cfg.BusinessSystem,
		OwnerTeam:          cfg.OwnerTeam,
		OwnerPerson:        cfg.OwnerPerson,
		Criticality:        cfg.Criticality,
		AllowAutoVerify:    cfg.AllowAutoVerify,
		AllowAutoRemediate: cfg.AllowAutoRemediate,
	})
}

func pollAndRunTask(
	agentID string,
	auditLog *audit.Logger,
	client *transport.Client,
) error {
	task, err := client.PollTask(agentID)
	if err != nil {
		return err
	}
	if task == nil {
		return auditLog.Record("task_poll_empty", nil)
	}

	_ = auditLog.Record("task_received", map[string]any{
		"task_id":   task.ID,
		"task_type": task.TaskType,
	})
	result := taskrunner.RunWithPlatform(
		*task,
		collector.InstalledPackages(),
		collector.CurrentPlatformInfo(),
	)
	if result.Status == "rejected" {
		_ = auditLog.Record("task_rejected", map[string]any{
			"task_id":    task.ID,
			"error_code": result.ErrorCode,
		})
	} else {
		_ = auditLog.Record("task_completed", map[string]any{
			"task_id": task.ID,
			"status":  result.Status,
		})
	}
	return client.SubmitTaskResult(agentID, task.ID, result)
}

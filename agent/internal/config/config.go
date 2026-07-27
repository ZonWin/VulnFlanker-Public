package config

import (
	"flag"
	"os"
	"path/filepath"
	"strconv"
	"time"
)

type Config struct {
	ServerURL          string
	AgentIDFile        string
	AgentSecretFile    string
	EnrollmentToken    string
	StateDir           string
	LogDir             string
	AgentVersion       string
	Once               bool
	PrintSnapshot      bool
	HeartbeatEvery     time.Duration
	SnapshotEvery      time.Duration
	TaskPollEvery      time.Duration
	RequestTimeout     time.Duration
	EnvironmentType    string
	ExposureType       string
	Criticality        string
	BusinessSystem     string
	OwnerTeam          string
	OwnerPerson        string
	AllowAutoVerify    bool
	AllowAutoRemediate bool
}

func Load(args []string) Config {
	stateDir := envString("VULNFLANKER_AGENT_STATE_DIR", defaultStateDir())
	logDir := envString("VULNFLANKER_AGENT_LOG_DIR", defaultLogDir())
	cfg := Config{
		ServerURL:          envString("VULNFLANKER_AGENT_INGRESS_URL", envString("VULNFLANKER_SERVER_URL", "http://127.0.0.1:8001")),
		StateDir:           stateDir,
		LogDir:             logDir,
		AgentIDFile:        envString("VULNFLANKER_AGENT_ID_FILE", filepath.Join(stateDir, "agent-id")),
		AgentSecretFile:    envString("VULNFLANKER_AGENT_SECRET_FILE", filepath.Join(stateDir, "agent-secret")),
		EnrollmentToken:    envString("VULNFLANKER_AGENT_ENROLLMENT_TOKEN", ""),
		AgentVersion:       "0.2.0",
		Once:               true,
		PrintSnapshot:      false,
		HeartbeatEvery:     envDuration("VULNFLANKER_AGENT_HEARTBEAT_SECONDS", 60*time.Second),
		SnapshotEvery:      envDuration("VULNFLANKER_AGENT_SNAPSHOT_SECONDS", time.Hour),
		TaskPollEvery:      envDuration("VULNFLANKER_AGENT_TASK_POLL_SECONDS", 30*time.Second),
		RequestTimeout:     envDuration("VULNFLANKER_AGENT_REQUEST_TIMEOUT_SECONDS", 10*time.Second),
		EnvironmentType:    envString("VULNFLANKER_AGENT_ENVIRONMENT_TYPE", "production"),
		ExposureType:       envString("VULNFLANKER_AGENT_EXPOSURE_TYPE", "internal"),
		Criticality:        envString("VULNFLANKER_AGENT_CRITICALITY", "medium"),
		BusinessSystem:     envString("VULNFLANKER_AGENT_BUSINESS_SYSTEM", ""),
		OwnerTeam:          envString("VULNFLANKER_AGENT_OWNER_TEAM", ""),
		OwnerPerson:        envString("VULNFLANKER_AGENT_OWNER_PERSON", ""),
		AllowAutoVerify:    envBool("VULNFLANKER_AGENT_ALLOW_AUTO_VERIFY", true),
		AllowAutoRemediate: envBool("VULNFLANKER_AGENT_ALLOW_AUTO_REMEDIATE", false),
	}

	fs := flag.NewFlagSet("vulnflanker-agent", flag.ExitOnError)
	fs.StringVar(&cfg.ServerURL, "agent-ingress-url", cfg.ServerURL, "VulnFlanker Agent Ingress URL")
	fs.StringVar(&cfg.ServerURL, "server-url", cfg.ServerURL, "deprecated alias for -agent-ingress-url")
	fs.StringVar(&cfg.AgentIDFile, "agent-id-file", cfg.AgentIDFile, "agent id state file")
	fs.StringVar(&cfg.AgentSecretFile, "agent-secret-file", cfg.AgentSecretFile, "agent secret state file")
	fs.StringVar(&cfg.EnrollmentToken, "enrollment-token", cfg.EnrollmentToken, "Agent enrollment token")
	fs.StringVar(&cfg.StateDir, "state-dir", cfg.StateDir, "agent state directory")
	fs.StringVar(&cfg.LogDir, "log-dir", cfg.LogDir, "agent log directory")
	fs.BoolVar(&cfg.Once, "once", cfg.Once, "run one heartbeat/snapshot/task cycle and exit")
	fs.BoolVar(&cfg.PrintSnapshot, "print-snapshot", cfg.PrintSnapshot, "print collected snapshot JSON")
	_ = fs.Parse(args)
	return cfg
}

func envString(name string, fallback string) string {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	return value
}

func envBool(name string, fallback bool) bool {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	parsed, err := strconv.ParseBool(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func envDuration(name string, fallback time.Duration) time.Duration {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	seconds, err := strconv.Atoi(value)
	if err != nil || seconds <= 0 {
		return fallback
	}
	return time.Duration(seconds) * time.Second
}

func defaultStateDir() string {
	if os.Geteuid() == 0 {
		return "/var/lib/vulnflanker"
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return ".vulnflanker"
	}
	return filepath.Join(home, ".vulnflanker")
}

func defaultLogDir() string {
	if os.Geteuid() == 0 {
		return "/var/log/vulnflanker"
	}
	return defaultStateDir()
}

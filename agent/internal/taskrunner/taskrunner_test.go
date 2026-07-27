package taskrunner

import (
	"testing"

	"vulnflanker-agent/internal/collector"
)

func TestRunPackageVersionCheck(t *testing.T) {
	result := Run(Task{
		TaskType: "package_version_check",
		Parameters: map[string]any{
			"package_name": "nginx",
		},
	}, []collector.PackageInfo{
		{Name: "nginx", Version: "1.24.0", Source: "dpkg"},
	})

	if result.Status != "completed" {
		t.Fatalf("status = %q", result.Status)
	}
	if len(result.Evidence) != 1 {
		t.Fatalf("len(evidence) = %d", len(result.Evidence))
	}
	if result.Evidence[0].Details["observed_version"] != "1.24.0" {
		t.Fatalf("unexpected details: %#v", result.Evidence[0].Details)
	}
}

func TestRunPackageVersionCheckCompletesWhenPackageIsAbsent(t *testing.T) {
	result := Run(Task{
		TaskType: "package_version_check",
		Parameters: map[string]any{
			"package_name": "missing-package",
		},
	}, []collector.PackageInfo{
		{Name: "nginx", Version: "1.24.0", Source: "dpkg"},
	})

	if result.Status != "completed" {
		t.Fatalf("status = %q", result.Status)
	}
	if result.ErrorCode != "" || result.ErrorMessage != "" {
		t.Fatalf("unexpected error: %q %q", result.ErrorCode, result.ErrorMessage)
	}
	if len(result.Evidence) != 1 {
		t.Fatalf("len(evidence) = %d", len(result.Evidence))
	}
	if result.Evidence[0].EvidenceType != "package_absence" {
		t.Fatalf("evidence type = %q", result.Evidence[0].EvidenceType)
	}
	if result.Evidence[0].Details["observed"] != false {
		t.Fatalf("unexpected details: %#v", result.Evidence[0].Details)
	}
}

func TestRunKernelVersionCheckUsesPlatformFacts(t *testing.T) {
	result := RunWithPlatform(Task{
		TaskType: "package_version_check",
		Parameters: map[string]any{
			"package_name": "Linux Kernel",
		},
	}, nil, collector.PlatformInfo{
		KernelVersion: "5.15.0-119-generic",
	})

	if result.Status != "completed" {
		t.Fatalf("status = %q", result.Status)
	}
	if len(result.Evidence) != 1 {
		t.Fatalf("len(evidence) = %d", len(result.Evidence))
	}
	if result.Evidence[0].EvidenceType != "kernel_version" {
		t.Fatalf("evidence type = %q", result.Evidence[0].EvidenceType)
	}
	if result.Evidence[0].Details["observed_version"] != "5.15.0-119-generic" {
		t.Fatalf("unexpected details: %#v", result.Evidence[0].Details)
	}
}

func TestRunOSVersionCheckUsesPlatformFacts(t *testing.T) {
	result := RunWithPlatform(Task{
		TaskType: "package_version_check",
		Parameters: map[string]any{
			"package_name":   "Ubuntu",
			"component_type": "operating_system",
		},
	}, nil, collector.PlatformInfo{
		Platform:  "linux",
		OSFamily:  "ubuntu",
		OSVersion: "22.04",
	})

	if result.Status != "completed" {
		t.Fatalf("status = %q", result.Status)
	}
	if len(result.Evidence) != 1 {
		t.Fatalf("len(evidence) = %d", len(result.Evidence))
	}
	if result.Evidence[0].EvidenceType != "os_version" {
		t.Fatalf("evidence type = %q", result.Evidence[0].EvidenceType)
	}
	if result.Evidence[0].Details["observed_version"] != "22.04" {
		t.Fatalf("unexpected details: %#v", result.Evidence[0].Details)
	}
}

func TestRunRejectsUnsupportedTaskType(t *testing.T) {
	result := Run(Task{TaskType: "shell_command"}, nil)

	if result.Status != "rejected" {
		t.Fatalf("status = %q", result.Status)
	}
	if result.ErrorCode != "unsupported_task_type" {
		t.Fatalf("error code = %q", result.ErrorCode)
	}
}

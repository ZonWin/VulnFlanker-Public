package taskrunner

import (
	"fmt"
	"strings"
	"time"

	"vulnflanker-agent/internal/collector"
)

type Task struct {
	ID            string         `json:"id"`
	TaskType      string         `json:"task_type"`
	MatchResultID string         `json:"match_result_id"`
	Parameters    map[string]any `json:"parameters"`
	CreatedAt     time.Time      `json:"created_at"`
}

type TaskResult struct {
	Status       string     `json:"status"`
	Evidence     []Evidence `json:"evidence,omitempty"`
	ErrorCode    string     `json:"error_code,omitempty"`
	ErrorMessage string     `json:"error_message,omitempty"`
	CompletedAt  time.Time  `json:"completed_at"`
}

type Evidence struct {
	EvidenceType string         `json:"evidence_type"`
	Summary      string         `json:"summary"`
	RawRef       string         `json:"raw_ref,omitempty"`
	Confidence   float64        `json:"confidence"`
	Details      map[string]any `json:"details,omitempty"`
}

func Run(task Task, packages []collector.PackageInfo) TaskResult {
	return RunWithPlatform(task, packages, collector.PlatformInfo{})
}

func RunWithPlatform(
	task Task,
	packages []collector.PackageInfo,
	platform collector.PlatformInfo,
) TaskResult {
	switch task.TaskType {
	case "package_version_check":
		return runPackageVersionCheck(task, packages, platform)
	default:
		return TaskResult{
			Status:       "rejected",
			ErrorCode:    "unsupported_task_type",
			ErrorMessage: fmt.Sprintf("unsupported task type %q", task.TaskType),
			CompletedAt:  time.Now().UTC(),
		}
	}
}

func runPackageVersionCheck(
	task Task,
	packages []collector.PackageInfo,
	platform collector.PlatformInfo,
) TaskResult {
	packageName := stringParameter(task.Parameters, "package_name")
	if packageName == "" {
		return TaskResult{
			Status:       "failed",
			ErrorCode:    "missing_package_name",
			ErrorMessage: "package_version_check requires package_name",
			CompletedAt:  time.Now().UTC(),
		}
	}

	switch componentType(task.Parameters, packageName) {
	case "kernel":
		return runKernelVersionCheck(packageName, platform)
	case "operating_system":
		return runOSVersionCheck(packageName, platform)
	}

	pkg, ok := collector.FindPackage(packages, packageName)
	if !ok {
		return TaskResult{
			Status: "completed",
			Evidence: []Evidence{
				{
					EvidenceType: "package_absence",
					Summary:      fmt.Sprintf("Package %s was not observed in the asset package inventory.", packageName),
					Confidence:   0.95,
					Details: map[string]any{
						"package_name":   packageName,
						"component_type": "package",
						"observed":       false,
						"source":         "agent_package_inventory",
					},
				},
			},
			CompletedAt: time.Now().UTC(),
		}
	}

	return TaskResult{
		Status: "completed",
		Evidence: []Evidence{
			{
				EvidenceType: "package_version",
				Summary:      fmt.Sprintf("Observed %s %s from %s.", pkg.Name, pkg.Version, pkg.Source),
				Confidence:   0.95,
				Details: map[string]any{
					"package_name":     pkg.Name,
					"observed_version": pkg.Version,
					"source":           pkg.Source,
				},
			},
		},
		CompletedAt: time.Now().UTC(),
	}
}

func runKernelVersionCheck(packageName string, platform collector.PlatformInfo) TaskResult {
	if strings.TrimSpace(platform.KernelVersion) == "" {
		return TaskResult{
			Status:       "failed",
			ErrorCode:    "missing_kernel_version",
			ErrorMessage: "package_version_check requires kernel_version for kernel verification",
			CompletedAt:  time.Now().UTC(),
		}
	}

	name := firstNonEmpty(packageName, "Linux Kernel")
	return TaskResult{
		Status: "completed",
		Evidence: []Evidence{
			{
				EvidenceType: "kernel_version",
				Summary:      fmt.Sprintf("Observed %s %s from uname.", name, platform.KernelVersion),
				Confidence:   0.95,
				Details: map[string]any{
					"package_name":     name,
					"component_type":   "kernel",
					"observed_version": platform.KernelVersion,
					"source":           "uname",
				},
			},
		},
		CompletedAt: time.Now().UTC(),
	}
}

func runOSVersionCheck(packageName string, platform collector.PlatformInfo) TaskResult {
	if strings.TrimSpace(platform.OSVersion) == "" {
		return TaskResult{
			Status:       "failed",
			ErrorCode:    "missing_os_version",
			ErrorMessage: "package_version_check requires os_version for operating system verification",
			CompletedAt:  time.Now().UTC(),
		}
	}

	name := firstNonEmpty(packageName, platform.OSFamily, platform.Platform, "operating system")
	return TaskResult{
		Status: "completed",
		Evidence: []Evidence{
			{
				EvidenceType: "os_version",
				Summary:      fmt.Sprintf("Observed %s %s from os-release.", name, platform.OSVersion),
				Confidence:   0.92,
				Details: map[string]any{
					"package_name":     name,
					"component_type":   "operating_system",
					"observed_version": platform.OSVersion,
					"os_family":        platform.OSFamily,
					"platform":         platform.Platform,
					"source":           "os-release",
				},
			},
		},
		CompletedAt: time.Now().UTC(),
	}
}

func componentType(parameters map[string]any, packageName string) string {
	explicit := normalizedToken(stringParameter(parameters, "component_type"))
	switch explicit {
	case "kernel":
		return "kernel"
	case "operatingsystem", "os":
		return "operating_system"
	}

	name := normalizedToken(packageName)
	switch name {
	case "linuxkernel", "kernel", "linuximage", "linuximagegeneric", "linuxheaders":
		return "kernel"
	case "ubuntu", "ubuntulinux", "debian", "debianlinux", "rhel", "redhat",
		"redhatenterpriselinux", "centos", "centoslinux", "rockylinux",
		"rocky", "almalinux", "amazonlinux", "amzn", "amzn2":
		return "operating_system"
	}
	return ""
}

func stringParameter(parameters map[string]any, key string) string {
	value, _ := parameters[key].(string)
	return strings.TrimSpace(value)
}

func normalizedToken(value string) string {
	var builder strings.Builder
	for _, item := range strings.ToLower(strings.TrimSpace(value)) {
		if item >= 'a' && item <= 'z' || item >= '0' && item <= '9' {
			builder.WriteRune(item)
		}
	}
	return builder.String()
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		trimmed := strings.TrimSpace(value)
		if trimmed != "" {
			return trimmed
		}
	}
	return ""
}

import { request } from "@/api/client";
import type {
  CisaKevMonitorConfig,
  CisaKevMonitorConfigUpdate,
  IntelCollectionResult,
  IntelCollectionRun,
  IntelCollectRequest,
  IntelRawEvent,
  IntelRawEventNormalizeResult,
  IntelSourceVulnerabilityCleanupResult,
  IntelSourceStatus,
  WatchVulnMonitorConfig,
  WatchVulnMonitorConfigUpdate
} from "@/api/types";

export type IntelManualSourceName = "cisa-kev" | "aliyun-avd" | "watchvuln";

export function collectIntelSource(sourceName: IntelManualSourceName, body: IntelCollectRequest) {
  return request<IntelCollectionResult>(`/api/v1/intel/${sourceName}/collect`, {
    method: "POST",
    body
  });
}

export function getCisaKevMonitorConfig() {
  return request<CisaKevMonitorConfig>("/api/v1/intel/cisa-kev/monitor");
}

export function updateCisaKevMonitorConfig(body: CisaKevMonitorConfigUpdate) {
  return request<CisaKevMonitorConfig>("/api/v1/intel/cisa-kev/monitor", {
    method: "PATCH",
    body
  });
}

export function getWatchVulnMonitorConfig() {
  return request<WatchVulnMonitorConfig>("/api/v1/intel/watchvuln/monitor");
}

export function updateWatchVulnMonitorConfig(body: WatchVulnMonitorConfigUpdate) {
  return request<WatchVulnMonitorConfig>("/api/v1/intel/watchvuln/monitor", {
    method: "PATCH",
    body
  });
}

export function getIntelSources() {
  return request<IntelSourceStatus[]>("/api/v1/intel/sources");
}

export function clearIntelSourceVulnerabilities(sourceName: string) {
  return request<IntelSourceVulnerabilityCleanupResult>(
    `/api/v1/intel/sources/${encodeURIComponent(sourceName)}/vulnerabilities`,
    {
      method: "DELETE",
      body: { confirmed: true }
    }
  );
}

export function getIntelRuns() {
  return request<IntelCollectionRun[]>("/api/v1/intel/runs", {
    query: { limit: 20 }
  });
}

export function getIntelRawEvents() {
  return request<IntelRawEvent[]>("/api/v1/intel/raw-events", {
    query: { limit: 20 }
  });
}

export function normalizeIntelRawEvent(rawEventId: string) {
  return request<IntelRawEventNormalizeResult>(
    `/api/v1/intel/raw-events/${rawEventId}/normalize`,
    {
      method: "POST"
    }
  );
}

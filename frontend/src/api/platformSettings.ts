import { request } from "@/api/client";
import type { PlatformSettings, PlatformSettingsUpdate } from "@/api/types";

export function getPlatformSettings() {
  return request<PlatformSettings>("/api/v1/platform-settings");
}

export function updatePlatformSettings(body: PlatformSettingsUpdate) {
  return request<PlatformSettings>("/api/v1/platform-settings", {
    method: "PATCH",
    body
  });
}

export function resetPlatformSettings() {
  return request<PlatformSettings>("/api/v1/platform-settings/reset", {
    method: "POST"
  });
}

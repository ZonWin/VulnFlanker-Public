import { request } from "@/api/client";
import type { HealthCheckResponse } from "@/api/types";

export function getLiveHealth() {
  return request<HealthCheckResponse>("/api/v1/health/live");
}

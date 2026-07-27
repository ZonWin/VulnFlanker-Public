import { request } from "@/api/client";
import type {
  AIEnrichmentStats,
  AIProfile,
  AIProfileCreate,
  AIProfileTestResult,
  AIProfileUpdate
} from "@/api/types";

export const aiProfilesQueryKey = ["ai", "profiles"] as const;
export const aiEnrichmentStatsQueryKey = ["ai", "enrichment-stats"] as const;

export function getAIProfiles() {
  return request<AIProfile[]>("/api/v1/ai/profiles");
}

export function getAIEnrichmentStats() {
  return request<AIEnrichmentStats>("/api/v1/ai/enrichment-stats");
}

export function createAIProfile(payload: AIProfileCreate) {
  return request<AIProfile>("/api/v1/ai/profiles", {
    method: "POST",
    body: payload
  });
}

export function updateAIProfile(profileId: string, payload: AIProfileUpdate) {
  return request<AIProfile>(`/api/v1/ai/profiles/${profileId}`, {
    method: "PATCH",
    body: payload
  });
}

export function deleteAIProfile(profileId: string) {
  return request<AIProfile>(`/api/v1/ai/profiles/${profileId}`, {
    method: "DELETE"
  });
}

export function testAIProfile(profileId: string) {
  return request<AIProfileTestResult>(`/api/v1/ai/profiles/${profileId}/test`, {
    method: "POST"
  });
}

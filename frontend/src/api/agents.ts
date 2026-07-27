import { request } from "@/api/client";
import type {
  AgentDetail,
  AgentEnrollmentToken,
  AgentEnrollmentTokenCreateRequest,
  AgentEnrollmentTokenCreateResponse,
  AgentSummary,
  LifecycleActionResult
} from "@/api/types";

export async function getAgents() {
  return request<AgentSummary[]>("/api/v1/agents");
}

export async function getAgent(agentId: string) {
  return request<AgentDetail>(`/api/v1/agents/${agentId}`);
}

export async function getAgentEnrollmentTokens() {
  return request<AgentEnrollmentToken[]>("/api/v1/agents/enrollment-tokens");
}

export async function createAgentEnrollmentToken(payload: AgentEnrollmentTokenCreateRequest) {
  return request<AgentEnrollmentTokenCreateResponse>("/api/v1/agents/enrollment-tokens", {
    method: "POST",
    body: payload
  });
}

export async function revokeAgentEnrollmentToken(tokenId: string) {
  return request<AgentEnrollmentToken>(`/api/v1/agents/enrollment-tokens/${tokenId}/revoke`, {
    method: "POST"
  });
}

export async function disableAgent(agentId: string) {
  return request<LifecycleActionResult>(`/api/v1/agents/${agentId}/disable`, {
    method: "POST"
  });
}

export async function deleteAgent(agentId: string) {
  return request<LifecycleActionResult>(`/api/v1/agents/${agentId}`, {
    method: "DELETE"
  });
}

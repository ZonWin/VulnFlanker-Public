import { request } from "@/api/client";
import type {
  VulnerabilityAIEnrichmentStatus,
  VulnerabilityAIEnrichmentAcceptRequest,
  VulnerabilityAIEnrichmentAcceptResponse,
  VulnerabilityAIEnrichmentBatchRequest,
  VulnerabilityAIEnrichmentBatchDetail,
  VulnerabilityAIEnrichmentBatchResponse,
  VulnerabilityAIEnrichment,
  VulnerabilityAIEnrichmentRejectRequest,
  VulnerabilityAIEnrichmentRunResponse,
  VulnerabilityAIEnrichmentTriggerRequest,
  VulnerabilityCreate,
  VulnerabilityDetail,
  VulnerabilityInformationCompleteness,
  VulnerabilityListPage,
  VulnerabilityMatchReadiness,
  VulnerabilityReadinessStats,
  VulnerabilityReviewDetail,
  VulnerabilityReviewListPage,
  VulnerabilityReviewQueue,
  VulnerabilityReviewResolution,
  VulnerabilityReviewResolutionCreate,
  VulnerabilityUpdate
} from "@/api/types";

export interface VulnerabilityListParams {
  match_readiness?: VulnerabilityMatchReadiness;
  information_completeness?: VulnerabilityInformationCompleteness;
  search?: string;
  severity_labels?: string;
  kev_status?: boolean;
  ai_enrichment_status?: VulnerabilityAIEnrichmentStatus;
  offset?: number;
  limit?: number;
}

export function getVulnerabilities(params: VulnerabilityListParams = {}) {
  return request<VulnerabilityListPage>("/api/v1/vulnerabilities", {
    query: {
      match_readiness: params.match_readiness,
      information_completeness: params.information_completeness,
      search: params.search,
      severity_labels: params.severity_labels,
      kev_status: params.kev_status,
      ai_enrichment_status: params.ai_enrichment_status,
      offset: params.offset,
      limit: params.limit
    }
  });
}

export function getVulnerabilityReadinessStats() {
  return request<VulnerabilityReadinessStats>("/api/v1/vulnerabilities/readiness/stats");
}

export function getVulnerabilityReviews(
  queue: VulnerabilityReviewQueue = "open",
  limit = 60,
  offset = 0
) {
  return request<VulnerabilityReviewListPage>("/api/v1/vulnerability-reviews", {
    query: { queue, limit, offset }
  });
}

export function getVulnerabilityReview(vulnerabilityId: string) {
  return request<VulnerabilityReviewDetail>(`/api/v1/vulnerability-reviews/${vulnerabilityId}`);
}

export function createVulnerabilityReviewResolution(
  vulnerabilityId: string,
  body: VulnerabilityReviewResolutionCreate
) {
  return request<VulnerabilityReviewResolution>(
    `/api/v1/vulnerability-reviews/${vulnerabilityId}/resolutions`,
    { method: "POST", body }
  );
}

export function getVulnerability(vulnerabilityId: string) {
  return request<VulnerabilityDetail>(`/api/v1/vulnerabilities/${vulnerabilityId}`);
}

export function createVulnerability(body: VulnerabilityCreate) {
  return request<VulnerabilityDetail>("/api/v1/vulnerabilities", {
    method: "POST",
    body
  });
}

export function updateVulnerability(
  vulnerabilityId: string,
  body: VulnerabilityUpdate
) {
  return request<VulnerabilityDetail>(`/api/v1/vulnerabilities/${vulnerabilityId}`, {
    method: "PATCH",
    body
  });
}

export function getVulnerabilityAIEnrichments(vulnerabilityId: string) {
  return request<VulnerabilityAIEnrichment[]>(
    `/api/v1/vulnerabilities/${vulnerabilityId}/ai-enrichments`
  );
}

export function triggerVulnerabilityAIEnrichment(
  vulnerabilityId: string,
  body: VulnerabilityAIEnrichmentTriggerRequest = {
    layer: "existing_data_extraction",
    async_mode: false
  }
) {
  return request<VulnerabilityAIEnrichmentRunResponse>(
    `/api/v1/vulnerabilities/${vulnerabilityId}/ai-enrichments`,
    {
      method: "POST",
      body
    }
  );
}

export function acceptVulnerabilityAIEnrichment(
  enrichmentId: string,
  body: VulnerabilityAIEnrichmentAcceptRequest
) {
  return request<VulnerabilityAIEnrichmentAcceptResponse>(
    `/api/v1/vulnerability-ai-enrichments/${enrichmentId}/accept`,
    {
      method: "POST",
      body
    }
  );
}

export function rejectVulnerabilityAIEnrichment(
  enrichmentId: string,
  body: VulnerabilityAIEnrichmentRejectRequest
) {
  return request<VulnerabilityAIEnrichment>(
    `/api/v1/vulnerability-ai-enrichments/${enrichmentId}/reject`,
    {
      method: "POST",
      body
    }
  );
}

export function createVulnerabilityAIEnrichmentBatch(
  body: VulnerabilityAIEnrichmentBatchRequest
) {
  return request<VulnerabilityAIEnrichmentBatchResponse>(
    "/api/v1/vulnerability-ai-enrichments/batch",
    {
      method: "POST",
      body
    }
  );
}

export function getVulnerabilityAIEnrichmentBatchDetail(batchRunId: string) {
  return request<VulnerabilityAIEnrichmentBatchDetail>(
    `/api/v1/vulnerability-ai-enrichments/batch/${batchRunId}`
  );
}

import { request } from "@/api/client";
import type {
  VerificationEvidenceQuery,
  VerificationEvidenceSummary,
  VerificationTask,
  VerificationTaskActionRequest,
  VerificationTaskDetail,
  VerificationTaskListPage,
  VerificationTasksQuery,
} from "@/api/types";

export function getVerificationTasks(query: VerificationTasksQuery = {}) {
  return request<VerificationTaskListPage>("/api/v1/verification-tasks", {
    query: { ...query, paged: true }
  });
}

export function getVerificationTask(taskId: string) {
  return request<VerificationTaskDetail>(`/api/v1/verification-tasks/${taskId}`);
}

export function cancelVerificationTask(
  taskId: string,
  body: VerificationTaskActionRequest = {}
) {
  return request<VerificationTaskDetail>(
    `/api/v1/verification-tasks/${taskId}/cancel`,
    {
      method: "POST",
      body
    }
  );
}

export function retryVerificationTask(
  taskId: string,
  body: VerificationTaskActionRequest = {}
) {
  return request<VerificationTask>(
    `/api/v1/verification-tasks/${taskId}/retry`,
    {
      method: "POST",
      body
    }
  );
}

export function getVerificationEvidence(query: VerificationEvidenceQuery = {}) {
  return request<VerificationEvidenceSummary[]>("/api/v1/verification-evidence", {
    query: { ...query }
  });
}

import { request } from "@/api/client";
import type {
  AuditLog,
  AuditLogsQuery,
  HandlingAuditRecord,
  HandlingAuditRecordsQuery
} from "@/api/types";

export function getAuditLogs(query: AuditLogsQuery = {}) {
  return request<AuditLog[]>("/api/v1/audit/logs", {
    query: { ...query }
  });
}

export function getHandlingAuditRecords(query: HandlingAuditRecordsQuery = {}) {
  return request<HandlingAuditRecord[]>("/api/v1/audit/handling-records", {
    query: { ...query }
  });
}

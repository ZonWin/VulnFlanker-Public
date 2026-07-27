import { request } from "@/api/client";
import type {
  TaskCenterItem,
  TaskCenterItemsQuery,
  TaskCenterSummary
} from "@/api/types";

export function getTaskCenterSummary() {
  return request<TaskCenterSummary>("/api/v1/task-center/summary");
}

export function getTaskCenterItems(query: TaskCenterItemsQuery = {}) {
  return request<TaskCenterItem[]>("/api/v1/task-center/items", {
    query: { ...query }
  });
}

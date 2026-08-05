import { request } from "@/api/client";
import type {
  AdminNotification,
  NotificationHistoryQuery,
  NotificationListPage,
  SystemEventListPage
} from "@/api/types";

export function getNotifications(query: {
  unread_only?: boolean;
  offset?: number;
  limit?: number;
} = {}) {
  return request<NotificationListPage>("/api/v1/notifications", { query });
}

export function getUnreadNotificationCount() {
  return request<{ count: number }>("/api/v1/notifications/unread-count");
}

export function markNotificationRead(notificationId: string) {
  return request<AdminNotification>(`/api/v1/notifications/${notificationId}/read`, {
    method: "POST"
  });
}

export function markAllNotificationsRead() {
  return request<{ updated_count: number }>("/api/v1/notifications/read-all", {
    method: "POST"
  });
}

export function getNotificationHistory(query: NotificationHistoryQuery = {}) {
  return request<SystemEventListPage>("/api/v1/notifications/history", {
    query: { ...query }
  });
}

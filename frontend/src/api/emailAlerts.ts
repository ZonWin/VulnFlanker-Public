import { request } from "@/api/client";
import type {
  EmailAction,
  EmailDeliveryDetail,
  EmailDeliveryListPage,
  EmailDeliveryQuery,
  EmailSettings,
  EmailSettingsUpdate,
  EmailTemplatePreview
} from "@/api/types";

export function getEmailSettings() {
  return request<EmailSettings>("/api/v1/email-settings");
}

export function updateEmailSettings(body: EmailSettingsUpdate) {
  return request<EmailSettings>("/api/v1/email-settings", {
    method: "PATCH",
    body
  });
}

export function previewEmailTemplates(body: {
  subject_template: string;
  text_body_template: string;
  html_body_template: string;
}) {
  return request<EmailTemplatePreview>("/api/v1/email-settings/preview", {
    method: "POST",
    body
  });
}

export function sendTestEmail(recipient_email: string) {
  return request<EmailAction>("/api/v1/email-settings/test", {
    method: "POST",
    body: { recipient_email }
  });
}

export function getEmailDeliveries(query: EmailDeliveryQuery = {}) {
  return request<EmailDeliveryListPage>("/api/v1/email-deliveries", {
    query: { ...query }
  });
}

export function getEmailDelivery(deliveryId: string) {
  return request<EmailDeliveryDetail>(`/api/v1/email-deliveries/${deliveryId}`);
}

export function resendEmailDelivery(deliveryId: string) {
  return request<EmailAction>(`/api/v1/email-deliveries/${deliveryId}/resend`, {
    method: "POST"
  });
}

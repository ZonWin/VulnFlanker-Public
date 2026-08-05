import { t } from "@/app/i18n";
import { Tag } from "antd";

import { severityColor, severityDisplayValue } from "@/utils/severity";

function displayValue(value?: string | number | null) {
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

function criticalityColor(value?: string | null) {
  if (value === "critical" || value === "high") {
    return "red";
  }
  if (value === "medium") {
    return "orange";
  }
  if (value === "low") {
    return "blue";
  }
  return "default";
}

function exposureColor(value?: string | null) {
  if (value && ["internet", "public", "external"].includes(value)) {
    return "red";
  }
  if (value === "dmz") {
    return "orange";
  }
  return "blue";
}

function outcomeColor(value?: string | null) {
  if (value && ["success", "completed"].includes(value)) {
    return "green";
  }
  if (value && ["failed", "rejected", "not_found"].includes(value)) {
    return "red";
  }
  return "blue";
}

function agentStatusColor(value?: string | null) {
  if (value === "online") {
    return "green";
  }
  if (value === "offline") {
    return "red";
  }
  if (value === "disabled") {
    return "default";
  }
  if (value === "unknown") {
    return "default";
  }
  return "blue";
}

function verificationTaskStatusColor(value?: string | null) {
  if (value === "completed") {
    return "green";
  }
  if (value === "failed" || value === "rejected") {
    return "red";
  }
  if (value === "cancelled") {
    return "default";
  }
  if (value === "cancel_requested") {
    return "orange";
  }
  if (value === "in_progress") {
    return "blue";
  }
  return "cyan";
}

function verificationTaskStatusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    queued: t("排队中"),
    in_progress: t("执行中"),
    cancel_requested: t("请求取消"),
    cancelled: t("已取消"),
    completed: t("已完成"),
    failed: t("失败"),
    rejected: t("已拒绝")
  };
  return value ? labels[value] ?? value : t("未知");
}

export function SeverityTag({ value }: { value?: string | null }) {
  return <Tag color={severityColor(value)}>{severityDisplayValue(value)}</Tag>;
}

export function CriticalityTag({ value }: { value?: string | null }) {
  return <Tag color={criticalityColor(value)}>{displayValue(value)}</Tag>;
}

export function ExposureTag({ value }: { value?: string | null }) {
  return <Tag color={exposureColor(value)}>{displayValue(value)}</Tag>;
}

export function OutcomeTag({ value }: { value?: string | null }) {
  return <Tag color={outcomeColor(value)}>{displayValue(value)}</Tag>;
}

export function AgentStatusTag({ value }: { value?: string | null }) {
  const labels: Record<string, string> = {
    online: t("在线"),
    offline: t("离线"),
    unknown: t("未知"),
    disabled: t("已禁用")
  };
  return <Tag color={agentStatusColor(value)}>{value ? labels[value] ?? value : "-"}</Tag>;
}

export function VerificationTaskStatusTag({ value }: { value?: string | null }) {
  return (
    <Tag color={verificationTaskStatusColor(value)}>
      {verificationTaskStatusLabel(value)}
    </Tag>
  );
}

interface BooleanTagProps {
  value: boolean;
  trueColor?: string;
  falseColor?: string;
}

export function BooleanTag({
  value,
  trueColor = "green",
  falseColor = "default"
}: BooleanTagProps) {
  return <Tag color={value ? trueColor : falseColor}>{value ? t("是") : t("否")}</Tag>;
}

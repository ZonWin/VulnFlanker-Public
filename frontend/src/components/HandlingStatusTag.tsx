import { t } from "@/app/i18n";
import { Tag } from "antd";

import type {
  MatchHandlingScope,
  MatchHandlingStatus
} from "@/api/types";

const statusMap: Record<MatchHandlingStatus, { color: string; label: string }> = {
  unprocessed: { color: "default", label: t("未处理") },
  notified: { color: "blue", label: t("已通知") },
  remediating: { color: "gold", label: t("整改中") },
  pending_review: { color: "cyan", label: t("待复核") },
  resolved: { color: "green", label: t("已处理") },
  false_positive: { color: "purple", label: t("确认误报") },
  risk_accepted: { color: "volcano", label: t("接受风险") }
};

export const handlingStatusOptions = Object.entries(statusMap).map(
  ([value, meta]) => ({
    value: value as MatchHandlingStatus,
    label: meta.label
  })
);

export const handlingScopeOptions: Array<{
  value: MatchHandlingScope;
  label: string;
}> = [
  { value: "open", label: t("未闭环") },
  { value: "closed", label: t("已闭环") },
  { value: "all", label: t("全部") }
];

export function handlingStatusLabel(value?: MatchHandlingStatus | null) {
  return value ? statusMap[value]?.label ?? t("未知") : t("未知");
}

export function isClosedHandlingStatus(value?: MatchHandlingStatus | null) {
  return value === "resolved" || value === "false_positive" || value === "risk_accepted";
}

interface HandlingStatusTagProps {
  value?: MatchHandlingStatus | null;
}

export default function HandlingStatusTag({ value }: HandlingStatusTagProps) {
  const meta = value ? statusMap[value] : undefined;

  return <Tag color={meta?.color ?? "default"}>{meta?.label ?? t("未知")}</Tag>;
}

import { Tag } from "antd";

import type {
  MatchHandlingScope,
  MatchHandlingStatus
} from "@/api/types";

const statusMap: Record<MatchHandlingStatus, { color: string; label: string }> = {
  unprocessed: { color: "default", label: "未处理" },
  notified: { color: "blue", label: "已通知" },
  remediating: { color: "gold", label: "整改中" },
  pending_review: { color: "cyan", label: "待复核" },
  resolved: { color: "green", label: "已处理" },
  false_positive: { color: "purple", label: "确认误报" },
  risk_accepted: { color: "volcano", label: "接受风险" }
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
  { value: "open", label: "未闭环" },
  { value: "closed", label: "已闭环" },
  { value: "all", label: "全部" }
];

export function handlingStatusLabel(value?: MatchHandlingStatus | null) {
  return value ? statusMap[value]?.label ?? "未知" : "未知";
}

export function isClosedHandlingStatus(value?: MatchHandlingStatus | null) {
  return value === "resolved" || value === "false_positive" || value === "risk_accepted";
}

interface HandlingStatusTagProps {
  value?: MatchHandlingStatus | null;
}

export default function HandlingStatusTag({ value }: HandlingStatusTagProps) {
  const meta = value ? statusMap[value] : undefined;

  return <Tag color={meta?.color ?? "default"}>{meta?.label ?? "未知"}</Tag>;
}

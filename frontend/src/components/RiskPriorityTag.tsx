import { Tag } from "antd";

import type { RiskPriority } from "@/api/types";

const priorityMap: Record<RiskPriority, { color: string; label: string }> = {
  critical: { color: "red", label: "严重" },
  high: { color: "volcano", label: "高危" },
  medium: { color: "orange", label: "中危" },
  low: { color: "blue", label: "低危" },
  none: { color: "default", label: "无风险" }
};

interface RiskPriorityTagProps {
  value?: RiskPriority | null;
}

export default function RiskPriorityTag({ value }: RiskPriorityTagProps) {
  const meta = priorityMap[value ?? "none"] ?? priorityMap.none;

  return <Tag color={meta.color}>{meta.label}</Tag>;
}

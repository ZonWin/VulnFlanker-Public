import { t } from "@/app/i18n";
import { Tag } from "antd";

import type { RiskPriority } from "@/api/types";

const priorityMap: Record<RiskPriority, { color: string; label: string }> = {
  critical: { color: "red", label: t("严重") },
  high: { color: "volcano", label: t("高危") },
  medium: { color: "orange", label: t("中危") },
  low: { color: "blue", label: t("低危") },
  none: { color: "default", label: t("无风险") }
};

interface RiskPriorityTagProps {
  value?: RiskPriority | null;
}

export default function RiskPriorityTag({ value }: RiskPriorityTagProps) {
  const meta = priorityMap[value ?? "none"] ?? priorityMap.none;

  return <Tag color={meta.color}>{meta.label}</Tag>;
}

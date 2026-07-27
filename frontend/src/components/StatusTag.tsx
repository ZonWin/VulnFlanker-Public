import { Tag } from "antd";

import type { MatchStatus } from "@/api/types";

const statusMap: Record<MatchStatus, { color: string; label: string }> = {
  affected: { color: "red", label: "受影响" },
  not_affected: { color: "green", label: "不受影响" },
  needs_review: { color: "orange", label: "待复核" },
  verified: { color: "cyan", label: "已验证" },
  suppressed: { color: "default", label: "已抑制" }
};

interface StatusTagProps {
  value?: MatchStatus | null;
}

export default function StatusTag({ value }: StatusTagProps) {
  const meta = value ? statusMap[value] : undefined;

  return <Tag color={meta?.color ?? "default"}>{meta?.label ?? "未知"}</Tag>;
}

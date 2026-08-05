import { t } from "@/app/i18n";
import { Tag } from "antd";

import type { MatchStatus } from "@/api/types";

const statusMap: Record<MatchStatus, { color: string; label: string }> = {
  affected: { color: "red", label: t("受影响") },
  not_affected: { color: "green", label: t("不受影响") },
  needs_review: { color: "orange", label: t("待复核") },
  verified: { color: "cyan", label: t("已验证") },
  suppressed: { color: "default", label: t("已抑制") }
};

interface StatusTagProps {
  value?: MatchStatus | null;
}

export default function StatusTag({ value }: StatusTagProps) {
  const meta = value ? statusMap[value] : undefined;

  return <Tag color={meta?.color ?? "default"}>{meta?.label ?? t("未知")}</Tag>;
}

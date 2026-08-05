import { t } from "@/app/i18n";
export const severityOptions = [
  { label: t("严重 / Critical"), value: "critical" },
  { label: t("高危 / High"), value: "high" },
  { label: t("中危 / Medium"), value: "medium" },
  { label: t("低危 / Low"), value: "low" },
  { label: t("信息 / Info"), value: "info" }
];

const severityLabels: Record<string, string> = {
  critical: t("严重 / Critical"),
  high: t("高危 / High"),
  medium: t("中危 / Medium"),
  low: t("低危 / Low"),
  info: t("信息 / Info")
};

const severityColors: Record<string, string> = {
  critical: "red",
  high: "volcano",
  medium: "orange",
  low: "blue",
  info: "default"
};

const severityAliases: Record<string, string> = {
  critical: "critical",
  crit: "critical",
  severe: "critical",
  serious: "critical",
  严重: "critical",
  超危: "critical",
  严重critical: "critical",
  critical严重: "critical",
  high: "high",
  important: "high",
  高: "high",
  高危: "high",
  高风险: "high",
  highrisk: "high",
  高危high: "high",
  high高危: "high",
  medium: "medium",
  moderate: "medium",
  中: "medium",
  中危: "medium",
  中风险: "medium",
  mediumrisk: "medium",
  中危medium: "medium",
  medium中危: "medium",
  low: "low",
  低: "low",
  低危: "low",
  低风险: "low",
  lowrisk: "low",
  低危low: "low",
  low低危: "low",
  info: "info",
  informational: "info",
  information: "info",
  信息: "info",
  提示: "info",
  信息info: "info",
  info信息: "info"
};

const knownExploitedMarkers = new Set([
  "knownexploited",
  "knownexploitedvulnerability",
  "knownexploitedvulnerabilities",
  "kev",
  "cisakev",
  t("已知利用"),
  t("已知被利用"),
  t("已知存在利用"),
  t("已知有利用")
]);

const emptySeverityMarkers = new Set([
  "unknown",
  "unk",
  "none",
  "null",
  "na",
  "n/a",
  "-",
  t("未知"),
  t("不详"),
  t("暂无"),
  t("无")
]);

export function normalizeSeverityLabel(value?: string | null) {
  const trimmed = value?.trim();
  if (!trimmed) {
    return null;
  }
  const key = compactKey(trimmed);
  if (
    knownExploitedMarkers.has(key) ||
    emptySeverityMarkers.has(key) ||
    emptySeverityMarkers.has(trimmed.toLowerCase())
  ) {
    return null;
  }
  return severityAliases[key] ?? trimmed.toLowerCase();
}

export function isKnownExploitedSeverity(value?: string | null) {
  const trimmed = value?.trim();
  return Boolean(trimmed && knownExploitedMarkers.has(compactKey(trimmed)));
}

export function severityDisplayValue(value?: string | null) {
  const normalized = normalizeSeverityLabel(value);
  return normalized ? severityLabels[normalized] ?? normalized : "-";
}

export function severityColor(value?: string | null) {
  const normalized = normalizeSeverityLabel(value);
  return normalized ? severityColors[normalized] ?? "default" : "default";
}

export function isHighOrCriticalSeverity(value?: string | null) {
  return ["critical", "high"].includes(normalizeSeverityLabel(value) ?? "");
}

function compactKey(value: string) {
  return value.trim().toLowerCase().replace(/[\s/_\-.]+/g, "");
}

import { t } from "@/app/i18n";
export function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(date);
}

export function formatPercent(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "-";
  }

  return `${Math.round(value * 100)}%`;
}

export function formatScore(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "-";
  }

  return value.toFixed(1);
}

export function formatDurationSeconds(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "-";
  }
  if (value < 60) {
    return t("{{v0}} 秒", { v0: value });
  }
  if (value < 3600) {
    return t("{{v0}} 分钟", { v0: Math.floor(value / 60) });
  }
  if (value < 86400) {
    return t("{{v0}} 小时", { v0: Math.floor(value / 3600) });
  }
  return t("{{v0}} 天", { v0: Math.floor(value / 86400) });
}

export function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

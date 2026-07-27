import { Progress } from "antd";

import { formatPercent } from "@/utils/format";

interface ConfidenceBarProps {
  value?: number | null;
}

export default function ConfidenceBar({ value }: ConfidenceBarProps) {
  const normalizedValue = Math.max(0, Math.min(1, value ?? 0));
  const percent = Math.round(normalizedValue * 100);

  return (
    <div className="confidence-bar">
      <Progress percent={percent} size="small" showInfo={false} />
      <span>{formatPercent(value)}</span>
    </div>
  );
}

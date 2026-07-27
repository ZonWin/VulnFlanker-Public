import { Alert, Card, Col, Row, Statistic, Tag } from "antd";
import { Building2, Database, Users, UserRound } from "lucide-react";
import type { ReactNode } from "react";

import type {
  BusinessSystemStatus,
  OwnershipSummary,
  PersonStatus,
  TeamStatus
} from "@/api/ownership";

type OwnershipStatus = TeamStatus | PersonStatus | BusinessSystemStatus;

const statusPresentation: Record<OwnershipStatus, { color: string; label: string }> = {
  active: { color: "green", label: "启用" },
  inactive: { color: "default", label: "停用" },
  draft: { color: "gold", label: "草稿" }
};

export function LifecycleTag({ status }: { status: OwnershipStatus }) {
  const presentation = statusPresentation[status];
  return <Tag color={presentation.color}>{presentation.label}</Tag>;
}

export function ReadOnlyNotice({ isAdmin }: { isAdmin: boolean }) {
  if (isAdmin) {
    return null;
  }
  return (
    <Alert
      showIcon
      type="info"
      message="当前账号为只读权限"
      description="可查看运营归属数据；新增、编辑、转移和启停操作需要超级管理员权限。"
    />
  );
}

function MetricCard({
  title,
  value,
  icon,
  tone
}: {
  title: string;
  value: number;
  icon: ReactNode;
  tone?: "green" | "red";
}) {
  return (
    <Col xs={24} sm={12} xl={6}>
      <Card className={`metric-card${tone ? ` metric-card-${tone}` : ""}`}>
        <Statistic title={title} value={value} prefix={icon} />
      </Card>
    </Col>
  );
}

export function OwnershipMetrics({ summary }: { summary?: OwnershipSummary }) {
  return (
    <Row gutter={[16, 16]}>
      <MetricCard
        title="责任团队"
        value={summary?.team_count ?? 0}
        icon={<Users size={24} />}
      />
      <MetricCard
        title="责任人员"
        value={summary?.person_count ?? 0}
        icon={<UserRound size={24} />}
      />
      <MetricCard
        title="业务系统"
        value={summary?.business_system_count ?? 0}
        icon={<Building2 size={24} />}
      />
      <MetricCard
        title="完整归属资产"
        value={summary?.complete_asset_count ?? 0}
        icon={<Database size={24} />}
        tone="green"
      />
    </Row>
  );
}

export const lifecycleOptions = [
  { label: "启用", value: "active" },
  { label: "停用", value: "inactive" }
];

export function cleanOptional(value?: string | null) {
  const cleaned = value?.trim();
  return cleaned || null;
}

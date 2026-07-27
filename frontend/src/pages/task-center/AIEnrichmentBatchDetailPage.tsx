import {
  Alert,
  Button,
  Card,
  Collapse,
  Descriptions,
  Empty,
  List,
  Row,
  Col,
  Space,
  Statistic,
  Table,
  Tag,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  ShieldAlert
} from "lucide-react";
import { useMemo } from "react";
import { useNavigate, useParams } from "react-router";

import { getVulnerabilityAIEnrichmentBatchDetail } from "@/api/vulnerabilities";
import type {
  VulnerabilityAIEnrichment,
  VulnerabilityAIEnrichmentBatchItem,
  VulnerabilityAIEnrichmentStatus,
  VulnerabilityDetail,
  VulnerabilityMatchReadiness
} from "@/api/types";
import ErrorState from "@/components/ErrorState";
import LoadingBlock from "@/components/LoadingBlock";
import PageHeader from "@/components/PageHeader";
import { formatDateTime } from "@/utils/format";

const statusLabels: Record<VulnerabilityAIEnrichmentStatus | "not_started", string> = {
  pending_review: "待人工核对",
  insufficient: "建议不足",
  failed: "补全失败",
  accepted: "已采纳",
  rejected: "已拒绝",
  auto_accepted: "自动采纳",
  already_applied: "无需变更",
  not_started: "未开始"
};

const statusColors: Record<VulnerabilityAIEnrichmentStatus | "not_started", string> = {
  pending_review: "processing",
  insufficient: "default",
  failed: "error",
  accepted: "success",
  rejected: "warning",
  auto_accepted: "success",
  already_applied: "success",
  not_started: "default"
};

const readinessLabels: Record<VulnerabilityMatchReadiness, string> = {
  ready: "匹配就绪",
  needs_enrichment: "仍需补全",
  needs_review: "需人工复核",
  not_matchable: "暂不可匹配"
};

const readinessColors: Record<VulnerabilityMatchReadiness, string> = {
  ready: "success",
  needs_enrichment: "processing",
  needs_review: "warning",
  not_matchable: "error"
};

const qualityGateLabels: Record<string, string> = {
  passed: "质量通过",
  needs_review: "需复核",
  failed: "质量失败",
  not_applicable: "不适用"
};

const qualityGateColors: Record<string, string> = {
  passed: "success",
  needs_review: "warning",
  failed: "error",
  not_applicable: "default"
};

const riskLevelLabels: Record<string, string> = {
  none: "低风险",
  low: "低风险",
  medium: "中风险",
  high: "高风险"
};

const fieldRows = [
  { key: "vendor", label: "厂商" },
  { key: "product", label: "产品" },
  { key: "affected_versions", label: "受影响版本" },
  { key: "fixed_versions", label: "修复版本" },
  { key: "remediation", label: "修复建议" }
] as const;

function displayValue(value?: string | number | boolean | null) {
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

function confidenceValue(value?: number | null) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "-";
}

function statusTag(status: VulnerabilityAIEnrichmentStatus | "not_started") {
  return <Tag color={statusColors[status]}>{statusLabels[status] ?? status}</Tag>;
}

function readinessTag(value?: VulnerabilityMatchReadiness | null) {
  if (!value) {
    return <Tag>暂无</Tag>;
  }
  return <Tag color={readinessColors[value]}>{readinessLabels[value]}</Tag>;
}

function qualityGateTag(enrichment?: VulnerabilityAIEnrichment | null) {
  const status = enrichment?.quality_gate?.quality_gate_status;
  if (!status) {
    return <Tag>暂无质量门禁</Tag>;
  }
  return <Tag color={qualityGateColors[status]}>{qualityGateLabels[status] ?? status}</Tag>;
}

function fieldValue(
  vulnerability: VulnerabilityDetail,
  enrichment: VulnerabilityAIEnrichment | null,
  field: (typeof fieldRows)[number]["key"],
  source: "current" | "ai"
) {
  const target = source === "current" ? vulnerability : enrichment;
  return target ? displayValue(target[field]) : "-";
}

function sourceLink(url: string | null, label?: string | null) {
  if (!url) {
    return displayValue(label);
  }
  return (
    <Typography.Link href={url} target="_blank" rel="noreferrer">
      <Space size={4}>
        {label ?? url}
        <ExternalLink size={13} />
      </Space>
    </Typography.Link>
  );
}

export default function AIEnrichmentBatchDetailPage() {
  const navigate = useNavigate();
  const { batchRunId } = useParams();
  const query = useQuery({
    queryKey: ["ai-enrichment-batch", batchRunId],
    queryFn: () => getVulnerabilityAIEnrichmentBatchDetail(batchRunId ?? ""),
    enabled: Boolean(batchRunId)
  });

  const items = query.data?.items ?? [];
  const readyCount = useMemo(
    () => items.filter((item) => item.vulnerability.match_readiness === "ready").length,
    [items]
  );

  const columns: ColumnsType<VulnerabilityAIEnrichmentBatchItem> = [
    {
      title: "漏洞",
      key: "vulnerability",
      minWidth: 300,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link
            onClick={() =>
              navigate(
                `/vulnerabilities/${record.vulnerability.canonical_id || record.vulnerability.id}`
              )
            }
          >
            {record.vulnerability.canonical_id || record.vulnerability.id}
          </Typography.Link>
          <Typography.Text className="table-subtitle" ellipsis>
            {record.vulnerability.title}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "补全状态",
      dataIndex: "result_status",
      width: 150,
      render: (value: VulnerabilityAIEnrichmentStatus | "not_started") => statusTag(value)
    },
    {
      title: "质量门禁",
      key: "quality",
      width: 150,
      render: (_, record) => qualityGateTag(record.enrichment)
    },
    {
      title: "匹配就绪度",
      key: "readiness",
      width: 150,
      render: (_, record) => readinessTag(record.vulnerability.match_readiness)
    },
    {
      title: "AI 候选",
      key: "candidate",
      minWidth: 260,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{displayValue(record.enrichment?.product)}</Typography.Text>
          <Typography.Text className="table-subtitle" ellipsis>
            {displayValue(record.enrichment?.affected_versions)}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "置信度",
      key: "confidence",
      width: 110,
      render: (_, record) => confidenceValue(record.enrichment?.confidence)
    },
    {
      title: "更新时间",
      key: "updated",
      width: 180,
      render: (_, record) =>
        formatDateTime(
          record.enrichment?.updated_at ?? record.vulnerability.readiness_updated_at
        )
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 130,
      render: (_, record) => (
        <Button
          type="link"
          icon={<ExternalLink size={15} />}
          onClick={() =>
            navigate(
              `/vulnerabilities/${record.vulnerability.canonical_id || record.vulnerability.id}`
            )
          }
        >
          处理
        </Button>
      )
    }
  ];

  return (
    <Space className="page-stack ai-batch-detail-page" orientation="vertical" size={16}>
      <PageHeader
        title="AI 补全详情"
        extra={
          <Space wrap>
            <Button icon={<ArrowLeft size={16} />} onClick={() => navigate(-1)}>
              返回
            </Button>
            <Button
              icon={<RefreshCw size={16} />}
              onClick={() => query.refetch()}
              loading={query.isFetching}
            >
              刷新
            </Button>
          </Space>
        }
      />

      {query.isLoading ? <LoadingBlock /> : null}
      {query.isError ? <ErrorState title="AI 补全详情加载失败" error={query.error} /> : null}

      {query.data ? (
        <>
          {query.data.batch.recent_error ? (
            <Alert type="error" showIcon message={query.data.batch.recent_error} />
          ) : null}

          <Row gutter={[16, 16]}>
            <Col xs={24} lg={6}>
              <Card className="metric-card">
                <Statistic
                  title="选中漏洞"
                  value={query.data.batch.selected_count}
                  prefix={<Bot size={28} />}
                />
              </Card>
            </Col>
            <Col xs={24} lg={6}>
              <Card className="metric-card metric-card-green">
                <Statistic
                  title="已处理"
                  value={query.data.batch.processed_count}
                  prefix={<RefreshCw size={28} />}
                />
              </Card>
            </Col>
            <Col xs={24} lg={6}>
              <Card className="metric-card">
                <Statistic
                  title="待核对"
                  value={query.data.batch.pending_review_count}
                  prefix={<ShieldAlert size={28} />}
                />
              </Card>
            </Col>
            <Col xs={24} lg={6}>
              <Card className="metric-card metric-card-green">
                <Statistic
                  title="匹配就绪"
                  value={readyCount}
                  prefix={<CheckCircle2 size={28} />}
                />
              </Card>
            </Col>
          </Row>

          <Card className="content-card" title="批次概览">
            <Descriptions
              size="small"
              bordered
              column={{ xs: 1, md: 2, xl: 4 }}
              items={[
                { key: "status", label: "状态", children: query.data.batch.status },
                { key: "trigger", label: "触发", children: query.data.batch.trigger_type },
                {
                  key: "layer",
                  label: "补全层",
                  children: displayValue(query.data.batch.filters.layer as string | undefined)
                },
                {
                  key: "web",
                  label: "联网补充",
                  children: query.data.batch.allow_web_enrichment ? "允许" : "未允许"
                },
                {
                  key: "started",
                  label: "开始时间",
                  children: formatDateTime(query.data.batch.started_at)
                },
                {
                  key: "finished",
                  label: "结束时间",
                  children: formatDateTime(query.data.batch.finished_at)
                },
                {
                  key: "success",
                  label: "成功/失败",
                  children: `${query.data.batch.success_count} / ${query.data.batch.failed_count}`
                },
                {
                  key: "insufficient",
                  label: "建议不足",
                  children: query.data.batch.insufficient_count
                }
              ]}
            />
          </Card>

          <Card className="content-card" title="补全成果核对">
            <Table<VulnerabilityAIEnrichmentBatchItem>
              rowKey={(record) => record.vulnerability.id}
              columns={columns}
              dataSource={items}
              pagination={{ pageSize: 10, showSizeChanger: true }}
              scroll={{ x: 1420 }}
              locale={{
                emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无补全结果" />
              }}
              expandable={{
                expandedRowRender: renderExpandedItem,
                rowExpandable: () => true
              }}
            />
          </Card>
        </>
      ) : null}
    </Space>
  );
}

function renderExpandedItem(record: VulnerabilityAIEnrichmentBatchItem) {
  const enrichment = record.enrichment;
  const gate = enrichment?.quality_gate;
  return (
    <Space className="page-stack ai-batch-expanded" orientation="vertical" size={12}>
      <div className="ai-batch-field-grid">
        {fieldRows.map((field) => (
          <div className="ai-batch-field-row" key={field.key}>
            <Typography.Text strong>{field.label}</Typography.Text>
            <Typography.Text type="secondary">
              当前：{fieldValue(record.vulnerability, enrichment, field.key, "current")}
            </Typography.Text>
            <Typography.Text>
              AI：{fieldValue(record.vulnerability, enrichment, field.key, "ai")}
            </Typography.Text>
          </div>
        ))}
      </div>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card size="small" title="源信息">
            <List
              size="small"
              dataSource={record.vulnerability.sources}
              locale={{ emptyText: "暂无源信息" }}
              renderItem={(source) => (
                <List.Item>
                  <Space orientation="vertical" size={2}>
                    <Space size={6} wrap>
                      <Tag>{source.source_name}</Tag>
                      <Typography.Text>{source.external_id}</Typography.Text>
                    </Space>
                    {sourceLink(source.source_url, source.source_url)}
                    {source.references.length ? (
                      <Space size={[4, 4]} wrap>
                        {source.references.slice(0, 5).map((reference) => (
                          <Tag key={reference}>{reference}</Tag>
                        ))}
                      </Space>
                    ) : null}
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="匹配就绪度">
            <Descriptions
              size="small"
              column={1}
              items={[
                {
                  key: "readiness",
                  label: "状态",
                  children: readinessTag(record.vulnerability.match_readiness)
                },
                {
                  key: "score",
                  label: "证据分",
                  children: displayValue(record.vulnerability.readiness_evidence_score)
                },
                {
                  key: "missing",
                  label: "缺失字段",
                  children: record.vulnerability.readiness_missing_fields.length
                    ? record.vulnerability.readiness_missing_fields.join(" / ")
                    : "-"
                },
                {
                  key: "reasons",
                  label: "原因",
                  children: record.vulnerability.readiness_reasons.length
                    ? record.vulnerability.readiness_reasons.join(" / ")
                    : "-"
                }
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card size="small" title="AI 证据">
            <List
              size="small"
              dataSource={enrichment?.evidence ?? []}
              locale={{ emptyText: "暂无证据" }}
              renderItem={(item) => (
                <List.Item>
                  <Space orientation="vertical" size={3}>
                    <Space size={6} wrap>
                      <Tag>{item.field}</Tag>
                      <Typography.Text type="secondary">
                        {confidenceValue(item.confidence)}
                      </Typography.Text>
                      {item.source_type ? <Tag>{item.source_type}</Tag> : null}
                    </Space>
                    {item.quote ? <Typography.Text>{item.quote}</Typography.Text> : null}
                    {sourceLink(item.source_url, item.source_url)}
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="质量门禁">
            <Descriptions
              size="small"
              column={1}
              items={[
                {
                  key: "gate",
                  label: "状态",
                  children: qualityGateTag(enrichment)
                },
                {
                  key: "risk",
                  label: "人工采纳风险",
                  children: riskLevelLabels[gate?.manual_accept_risk_level ?? ""] ?? "-"
                },
                {
                  key: "auto",
                  label: "可自动采纳",
                  children: gate?.auto_accept_allowed ? "是" : "否"
                },
                {
                  key: "candidate",
                  label: "候选字段",
                  children: displayValue(gate?.candidate_field_count)
                },
                {
                  key: "reason",
                  label: "原因",
                  children: gate?.quality_gate_reasons.length
                    ? gate.quality_gate_reasons.join(" / ")
                    : "-"
                },
                {
                  key: "warning",
                  label: "提示",
                  children: gate?.quality_gate_warnings.length
                    ? gate.quality_gate_warnings.join(" / ")
                    : "-"
                }
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Collapse
        size="small"
        items={[
          {
            key: "raw",
            label: "AI 原始输出",
            children: (
              <pre className="json-block">
                {JSON.stringify(enrichment?.raw_output ?? {}, null, 2)}
              </pre>
            )
          },
          {
            key: "scopes",
            label: "影响范围",
            children: (
              <List
                size="small"
                dataSource={record.vulnerability.affected_scopes}
                locale={{ emptyText: "暂无影响范围" }}
                renderItem={(scope) => (
                  <List.Item>
                    <Space orientation="vertical" size={2}>
                      <Space size={6} wrap>
                        <Tag>{scope.source_name}</Tag>
                        <Typography.Text>{displayValue(scope.product)}</Typography.Text>
                      </Space>
                      <Typography.Text type="secondary">
                        影响：{displayValue(scope.affected_versions)}
                      </Typography.Text>
                      <Typography.Text type="secondary">
                        修复：{displayValue(scope.fixed_versions)}
                      </Typography.Text>
                      {sourceLink(scope.source_url, scope.source_url)}
                    </Space>
                  </List.Item>
                )}
              />
            )
          }
        ]}
      />
    </Space>
  );
}

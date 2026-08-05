import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Row,
  Segmented,
  Skeleton,
  Space,
  Table
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  Bug,
  CheckCircle2,
  Database,
  RefreshCw,
  ShieldAlert
} from "lucide-react";
import { useNavigate } from "react-router";

import {
  getDashboard,
  type DashboardDistributionItem,
  type DashboardMetric,
  type DashboardQuery,
  type DashboardTopRisk,
  type DashboardTrendPoint
} from "@/api/dashboard";
import type { MatchHandlingStatus } from "@/api/types";
import { t } from "@/app/i18n";
import ErrorState from "@/components/ErrorState";
import HandlingStatusTag, {
  handlingStatusLabel
} from "@/components/HandlingStatusTag";
import PageHeader from "@/components/PageHeader";
import RiskPriorityTag from "@/components/RiskPriorityTag";
import { formatScore } from "@/utils/format";


const { RangePicker } = DatePicker;

const riskPriorityMeta: Record<string, { label: string; color: string }> = {
  critical: { label: t("严重"), color: "#cf1322" },
  high: { label: t("高危"), color: "#fa541c" },
  medium: { label: t("中危"), color: "#d48806" },
  low: { label: t("低危"), color: "#1677ff" },
  none: { label: t("无风险"), color: "#98a2b3" }
};

const closureMeta: Record<string, { label: string; color: string }> = {
  resolved: { label: t("已解决"), color: "#16a34a" },
  false_positive: { label: t("确认误报"), color: "#7c3aed" },
  risk_accepted: { label: t("接受风险"), color: "#d97706" }
};

const handlingColors: Record<string, string> = {
  unprocessed: "#98a2b3",
  notified: "#1677ff",
  remediating: "#d97706",
  pending_review: "#0891b2"
};

function number(value: number) {
  return new Intl.NumberFormat().format(value);
}

function periodDays(startDate: string, endDate: string) {
  const start = new Date(`${startDate}T00:00:00Z`).getTime();
  const end = new Date(`${endDate}T00:00:00Z`).getTime();
  return Math.round((end - start) / 86_400_000) + 1;
}

function formatGeneratedAt(value: string, timezone: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function Comparison({ metric }: { metric: DashboardMetric }) {
  if (metric.change_percent === null) {
    return <span className="dashboard-comparison">{t("上周期无新增")}</span>;
  }
  const sign = metric.change_percent > 0 ? "+" : "";
  return (
    <span className="dashboard-comparison">
      {t("较上周期")} {sign}{metric.change_percent.toFixed(1)}%
    </span>
  );
}

function MetricCard({
  title,
  icon,
  metric,
  days,
  tone
}: {
  title: string;
  icon: ReactNode;
  metric: DashboardMetric;
  days: number;
  tone?: string;
}) {
  return (
    <Card className={`dashboard-metric-card${tone ? ` dashboard-metric-${tone}` : ""}`}>
      <div className="dashboard-metric-heading">
        <span className="dashboard-metric-icon" aria-hidden="true">{icon}</span>
        <span>{title}</span>
      </div>
      <div className="dashboard-metric-value">{number(metric.current_total)}</div>
      <div className="dashboard-metric-caption">{t("当前存量")}</div>
      <div className="dashboard-metric-footer">
        <strong>
          {days === 7 ? t("近 {{v0}} 天新增", { v0: days }) : t("本周期新增")} {number(metric.period_new)}
        </strong>
        <Comparison metric={metric} />
      </div>
    </Card>
  );
}

function DonutChart({
  items,
  meta,
  ariaLabel
}: {
  items: DashboardDistributionItem[];
  meta: Record<string, { label: string; color: string }>;
  ariaLabel: string;
}) {
  const total = items.reduce((sum, item) => sum + item.count, 0);
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  let progress = 0;
  return (
    <div className="dashboard-donut-layout">
      <svg
        className="dashboard-donut"
        viewBox="0 0 100 100"
        role="img"
        aria-label={`${ariaLabel}，${t("共 {{v0}} 条", { v0: total })}`}
      >
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#eef2f7" strokeWidth="13" />
        {total > 0
          ? items.map((item) => {
              const length = (item.count / total) * circumference;
              const offset = progress;
              progress += length;
              return (
                <circle
                  key={item.key}
                  cx="50"
                  cy="50"
                  r={radius}
                  fill="none"
                  stroke={meta[item.key]?.color ?? "#98a2b3"}
                  strokeWidth="13"
                  strokeDasharray={`${length} ${circumference - length}`}
                  strokeDashoffset={-offset}
                  transform="rotate(-90 50 50)"
                >
                  <title>{`${meta[item.key]?.label ?? item.key}: ${item.count}`}</title>
                </circle>
              );
            })
          : null}
        <text x="50" y="47" textAnchor="middle" className="dashboard-donut-total">{number(total)}</text>
        <text x="50" y="61" textAnchor="middle" className="dashboard-donut-label">{t("总数")}</text>
      </svg>
      <div className="dashboard-donut-legend">
        {items.map((item) => {
          const percentage = total ? Math.round((item.count / total) * 100) : 0;
          return (
            <div className="dashboard-legend-row" key={item.key}>
              <span
                className="dashboard-legend-dot"
                style={{ backgroundColor: meta[item.key]?.color ?? "#98a2b3" }}
              />
              <span className="dashboard-legend-name">{meta[item.key]?.label ?? item.key}</span>
              <strong>{number(item.count)}</strong>
              <span className="dashboard-legend-percent">{percentage}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TrendChart({ points }: { points: DashboardTrendPoint[] }) {
  if (!points.length) {
    return <div className="dashboard-chart-empty">{t("暂无风险趋势数据")}</div>;
  }
  const width = 920;
  const height = 300;
  const left = 52;
  const top = 22;
  const right = 18;
  const bottom = 46;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const baseY = top + plotHeight;
  const maxValue = Math.max(
    1,
    ...points.flatMap((point) => [point.open_count, point.new_count, point.closed_count])
  );
  const step = plotWidth / points.length;
  const barWidth = Math.max(2, Math.min(12, step * 0.22));
  const y = (value: number) => baseY - (value / maxValue) * plotHeight;
  const x = (index: number) => left + step * index + step / 2;
  const line = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${x(index)} ${y(point.open_count)}`)
    .join(" ");
  const labelEvery = points.length <= 10 ? 1 : points.length <= 35 ? 5 : 15;
  const summary = `${t("开放风险")} ${points.at(-1)?.open_count ?? 0}，${t("新增风险")} ${points.reduce((sum, item) => sum + item.new_count, 0)}，${t("闭环风险")} ${points.reduce((sum, item) => sum + item.closed_count, 0)}`;

  return (
    <div className="dashboard-trend-wrap">
      <svg className="dashboard-trend" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={summary}>
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const value = Math.round(maxValue * ratio);
          const gridY = y(value);
          return (
            <g key={ratio}>
              <line x1={left} x2={width - right} y1={gridY} y2={gridY} className="dashboard-grid-line" />
              <text x={left - 10} y={gridY + 4} textAnchor="end" className="dashboard-axis-label">{value}</text>
            </g>
          );
        })}
        {points.map((point, index) => (
          <g key={point.date}>
            <rect
              x={x(index) - barWidth - 1}
              y={y(point.new_count)}
              width={barWidth}
              height={baseY - y(point.new_count)}
              rx="2"
              fill="#d97706"
            >
              <title>{`${point.date} ${t("新增风险")}: ${point.new_count}`}</title>
            </rect>
            <rect
              x={x(index) + 1}
              y={y(point.closed_count)}
              width={barWidth}
              height={baseY - y(point.closed_count)}
              rx="2"
              fill="#16a34a"
            >
              <title>{`${point.date} ${t("闭环风险")}: ${point.closed_count}`}</title>
            </rect>
            {index % labelEvery === 0 || index === points.length - 1 ? (
              <text x={x(index)} y={height - 18} textAnchor="middle" className="dashboard-axis-label">
                {point.date.slice(5)}
              </text>
            ) : null}
          </g>
        ))}
        <path d={line} fill="none" stroke="#1668dc" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
        {points.map((point, index) => (
          <circle key={point.date} cx={x(index)} cy={y(point.open_count)} r="3.5" fill="#1668dc">
            <title>{`${point.date} ${t("开放风险")}: ${point.open_count}`}</title>
          </circle>
        ))}
      </svg>
      <div className="dashboard-chart-legend" aria-hidden="true">
        <span><i className="dashboard-line-key" />{t("开放风险")}</span>
        <span><i style={{ background: "#d97706" }} />{t("新增风险")}</span>
        <span><i style={{ background: "#16a34a" }} />{t("闭环风险")}</span>
      </div>
    </div>
  );
}

function HandlingDistribution({ items }: { items: DashboardDistributionItem[] }) {
  const total = items.reduce((sum, item) => sum + item.count, 0);
  return (
    <div className="dashboard-handling-list">
      {items.map((item) => {
        const percentage = total ? (item.count / total) * 100 : 0;
        return (
          <div className="dashboard-handling-row" key={item.key}>
            <div className="dashboard-handling-label">
              <span>{handlingStatusLabel(item.key as MatchHandlingStatus)}</span>
              <strong>{number(item.count)}</strong>
            </div>
            <div className="dashboard-handling-track" aria-label={`${handlingStatusLabel(item.key as MatchHandlingStatus)} ${item.count}`}>
              <span style={{ width: `${percentage}%`, backgroundColor: handlingColors[item.key] ?? "#98a2b3" }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState<DashboardQuery>({ days: 7 });
  const [periodMode, setPeriodMode] = useState<string>("7");
  const dashboardQuery = useQuery({
    queryKey: ["dashboard", query],
    queryFn: () => getDashboard(query)
  });
  const data = dashboardQuery.data;
  const days = data ? periodDays(data.period.start_date, data.period.end_date) : Number(query.days ?? 7);

  const columns = useMemo<ColumnsType<DashboardTopRisk>>(
    () => [
      {
        title: t("优先级"),
        dataIndex: "risk_priority",
        width: 96,
        render: (value: DashboardTopRisk["risk_priority"]) => <RiskPriorityTag value={value} />
      },
      {
        title: t("风险编号"),
        dataIndex: "risk_code",
        width: 180,
        render: (value: string | null) => value ?? "-"
      },
      {
        title: t("漏洞"),
        dataIndex: "vulnerability_title",
        ellipsis: true,
        render: (_: string, record) => (
          <div className="dashboard-risk-primary">
            <strong>{record.vulnerability_canonical_id}</strong>
            <span>{record.vulnerability_title}</span>
          </div>
        )
      },
      {
        title: t("资产"),
        dataIndex: "asset_name",
        width: 190,
        ellipsis: true
      },
      {
        title: t("风险分"),
        dataIndex: "risk_score",
        width: 90,
        align: "right",
        render: (value: number) => <strong>{formatScore(value)}</strong>
      },
      {
        title: t("处置状态"),
        dataIndex: "handling_status",
        width: 110,
        render: (value: DashboardTopRisk["handling_status"]) => <HandlingStatusTag value={value} />
      }
    ],
    []
  );

  if (dashboardQuery.isLoading && !data) {
    return (
      <Space className="page-stack dashboard-page" orientation="vertical" size={16}>
        <PageHeader title={t("总览")} />
        <Skeleton active paragraph={{ rows: 16 }} />
      </Space>
    );
  }

  if (dashboardQuery.isError || !data) {
    return (
      <Space className="page-stack dashboard-page" orientation="vertical" size={16}>
        <PageHeader title={t("总览")} />
        <ErrorState error={dashboardQuery.error} />
        <Button onClick={() => void dashboardQuery.refetch()}>{t("重试")}</Button>
      </Space>
    );
  }

  const closureItems = [
    { key: "resolved", count: data.closure.resolved },
    { key: "false_positive", count: data.closure.false_positive },
    { key: "risk_accepted", count: data.closure.risk_accepted }
  ];

  return (
    <Space className="page-stack dashboard-page" orientation="vertical" size={16}>
      <PageHeader
        title={t("总览")}
        subtitle={
          <Space size={12} wrap>
            <span>{t("统计周期：{{v0}} 至 {{v1}}", { v0: data.period.start_date, v1: data.period.end_date })}</span>
            <span>{t("数据更新于 {{v0}}（{{v1}}）", {
              v0: formatGeneratedAt(data.period.generated_at, data.period.timezone),
              v1: data.period.timezone
            })}</span>
          </Space>
        }
        extra={
          <div className="dashboard-toolbar">
            <Segmented
              value={periodMode}
              options={[
                { label: t("{{v0}} 天", { v0: 7 }), value: "7" },
                { label: t("{{v0}} 天", { v0: 30 }), value: "30" },
                { label: t("{{v0}} 天", { v0: 90 }), value: "90" },
                { label: t("自定义"), value: "custom" }
              ]}
              onChange={(value) => {
                const next = String(value);
                setPeriodMode(next);
                if (next !== "custom") setQuery({ days: Number(next) });
              }}
            />
            {periodMode === "custom" ? (
              <RangePicker
                allowClear={false}
                onChange={(dates) => {
                  const start = dates?.[0]?.format("YYYY-MM-DD");
                  const end = dates?.[1]?.format("YYYY-MM-DD");
                  if (start && end) setQuery({ start_date: start, end_date: end });
                }}
              />
            ) : null}
            <Button
              aria-label={t("刷新")}
              icon={<RefreshCw size={16} />}
              loading={dashboardQuery.isFetching}
              onClick={() => void dashboardQuery.refetch()}
            >
              {t("刷新")}
            </Button>
          </div>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard title={t("风险概览")} icon={<ShieldAlert size={22} />} metric={data.risk} days={days} tone="red" />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard title={t("资产概览")} icon={<Database size={22} />} metric={data.asset} days={days} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard title={t("漏洞概览")} icon={<Bug size={22} />} metric={data.vulnerability} days={days} tone="orange" />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card className="dashboard-metric-card dashboard-metric-green">
            <div className="dashboard-metric-heading">
              <span className="dashboard-metric-icon" aria-hidden="true"><CheckCircle2 size={22} /></span>
              <span>{t("闭环概览")}</span>
            </div>
            <div className="dashboard-metric-value">{number(data.closure.total)}</div>
            <div className="dashboard-metric-caption">{t("本周期闭环总数")}</div>
            <div className="dashboard-closure-breakdown">
              <span>{t("已解决")} <strong>{number(data.closure.resolved)}</strong></span>
              <span>{t("确认误报")} <strong>{number(data.closure.false_positive)}</strong></span>
              <span>{t("接受风险")} <strong>{number(data.closure.risk_accepted)}</strong></span>
            </div>
          </Card>
        </Col>
      </Row>

      <div className="dashboard-primary-grid">
        <Card className="content-card dashboard-chart-card" title={t("风险趋势")}>
          <TrendChart points={data.trend} />
        </Card>
        <Card className="content-card dashboard-chart-card" title={t("风险等级分布")}>
          <DonutChart items={data.risk_priority_distribution} meta={riskPriorityMeta} ariaLabel={t("风险等级分布")} />
        </Card>
      </div>

      <div className="dashboard-secondary-grid">
        <Card className="content-card dashboard-chart-card" title={t("闭环性质分布")}>
          <DonutChart items={closureItems} meta={closureMeta} ariaLabel={t("闭环性质分布")} />
        </Card>
        <Card className="content-card dashboard-chart-card" title={t("风险处置状态")}>
          <HandlingDistribution items={data.handling_status_distribution} />
        </Card>
      </div>

      <Card className="content-card dashboard-top-risk-card" title={t("最高危的五条风险")}>
        <Table<DashboardTopRisk>
          rowKey="id"
          columns={columns}
          dataSource={data.top_risks}
          pagination={false}
          locale={{ emptyText: t("暂无最高危风险") }}
          scroll={{ x: 850 }}
          onRow={(record) => ({
            tabIndex: 0,
            role: "link",
            onClick: () => navigate(`/matching/${record.id}`),
            onKeyDown: (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                navigate(`/matching/${record.id}`);
              }
            }
          })}
        />
      </Card>
    </Space>
  );
}

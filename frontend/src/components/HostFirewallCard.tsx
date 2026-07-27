import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Grid,
  Input,
  Row,
  Segmented,
  Select,
  Space,
  Statistic,
  Tag,
  Tooltip,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useQuery } from "@tanstack/react-query";
import {
  CircleHelp,
  Code2,
  Database,
  RefreshCw,
  Shield,
  ShieldCheck
} from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";

import {
  getAssetFirewallRaw,
  getAssetFirewallRules,
  getAssetFirewalls
} from "@/api/assets";
import type {
  AssetFirewall,
  AssetFirewallRule,
  FirewallEngine,
  FirewallScope
} from "@/api/types";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import LoadingBlock from "@/components/LoadingBlock";
import ResizableTable from "@/components/ResizableTable";
import { formatDateTime } from "@/utils/format";

type FirewallView = "overview" | FirewallEngine;
const FIREWALL_RULE_PAGE_SIZE = 5;
const FIREWALL_RULE_FETCH_LIMIT = 200;

const engineLabels: Record<FirewallEngine, string> = {
  firewalld: "firewalld",
  ufw: "UFW",
  iptables: "iptables",
  nftables: "nftables"
};

const roleLabels: Record<AssetFirewall["role"], string> = {
  manager: "策略管理器",
  backend: "底层引擎",
  compatibility: "兼容层",
  standalone: "独立引擎"
};

const stateLabels: Record<AssetFirewall["runtime_state"], string> = {
  active: "运行中",
  inactive: "未运行",
  configured: "已配置",
  unknown: "未知"
};

const collectionLabels: Record<AssetFirewall["collection_status"], string> = {
  success: "采集成功",
  partial: "部分成功",
  unsupported: "不支持",
  permission_denied: "权限不足",
  timeout: "采集超时",
  error: "采集失败"
};

function collectionColor(status: AssetFirewall["collection_status"]) {
  if (status === "success") return "success";
  if (status === "partial") return "warning";
  return "error";
}

function stateColor(state: AssetFirewall["runtime_state"]) {
  if (state === "active") return "success";
  if (state === "configured") return "processing";
  if (state === "inactive") return "default";
  return "warning";
}

function actionColor(action?: string | null) {
  const normalized = action?.toLowerCase() ?? "";
  if (["accept", "allow"].includes(normalized)) return "success";
  if (["drop", "deny", "reject"].includes(normalized)) return "error";
  if (["dnat", "snat", "masquerade", "redirect"].includes(normalized)) {
    return "processing";
  }
  return "default";
}

function relationshipText(firewall: AssetFirewall) {
  if (firewall.role === "manager") {
    return `策略管理器 → ${firewall.backend || "后端未知"}`;
  }
  if (firewall.role === "compatibility") {
    return `命令兼容层 → ${firewall.backend || "底层未知"}`;
  }
  if (firewall.managed_by) {
    return `${firewall.managed_by} 管理的底层规则集`;
  }
  return firewall.role === "backend" ? "直接生效的底层规则集" : "独立策略来源";
}

function rulePosition(rule: AssetFirewallRule) {
  return [rule.zone, rule.table, rule.chain].filter(Boolean).join(" / ") || "-";
}

function ruleMatch(rule: AssetFirewallRule) {
  const network = [rule.source, rule.destination]
    .filter(Boolean)
    .join(" → ");
  const ports = [
    rule.source_port ? `源端口 ${rule.source_port}` : null,
    rule.destination_port ? `目标端口 ${rule.destination_port}` : null
  ]
    .filter(Boolean)
    .join(" · ");
  const interfaces = [rule.in_interface, rule.out_interface]
    .filter(Boolean)
    .join(" → ");
  return [network, ports, interfaces, rule.state_match]
    .filter(Boolean)
    .join(" · ") || "任意";
}

export interface HostFirewallCardProps {
  assetId: string;
}

export default function HostFirewallCard({ assetId }: HostFirewallCardProps) {
  const screens = Grid.useBreakpoint();
  const compact = !screens.md;
  const [view, setView] = useState<FirewallView>("overview");
  const [scope, setScope] = useState<FirewallScope>("runtime");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim());
  const [page, setPage] = useState(1);
  const [rawOpen, setRawOpen] = useState(false);

  const summaryQuery = useQuery({
    queryKey: ["assets", assetId, "firewalls"],
    queryFn: () => getAssetFirewalls(assetId),
    enabled: Boolean(assetId)
  });
  const firewalls = summaryQuery.data?.items ?? [];
  const selectedEngine = view === "overview" ? undefined : view;
  const selectedFirewall = firewalls.find(
    (firewall) => firewall.engine === selectedEngine
  );

  useEffect(() => {
    if (view !== "overview" && summaryQuery.data && !selectedFirewall) {
      setView("overview");
    }
  }, [selectedFirewall, summaryQuery.data, view]);

  useEffect(() => {
    setPage(1);
    setRawOpen(false);
  }, [scope, view]);

  const rulesQuery = useQuery({
    queryKey: [
      "assets",
      assetId,
      "firewalls",
      selectedEngine,
      "rules",
      scope,
      deferredSearch
    ],
    queryFn: () =>
      getAssetFirewallRules(assetId, selectedEngine as FirewallEngine, {
        scope,
        search: deferredSearch || undefined,
        page: 1,
        page_size: FIREWALL_RULE_FETCH_LIMIT
      }),
    enabled: Boolean(selectedEngine)
  });

  const rawQuery = useQuery({
    queryKey: [
      "assets",
      assetId,
      "firewalls",
      selectedEngine,
      "raw",
      scope
    ],
    queryFn: () =>
      getAssetFirewallRaw(assetId, selectedEngine as FirewallEngine, scope),
    enabled: Boolean(selectedEngine && rawOpen)
  });

  const columns = useMemo<ColumnsType<AssetFirewallRule>>(
    () => [
      {
        key: "order",
        title: "序号",
        dataIndex: "order",
        width: 82,
        render: (value: number) => value + 1
      },
      {
        key: "kind",
        title: "类型",
        dataIndex: "rule_kind",
        width: 130,
        render: (value: string, record) => (
          <Space size={4} wrap>
            <Tag>{value}</Tag>
            {record.family ? <Tag bordered={false}>{record.family}</Tag> : null}
          </Space>
        )
      },
      {
        key: "position",
        title: "位置",
        width: 220,
        render: (_, record) => (
          <Typography.Text ellipsis={{ tooltip: rulePosition(record) }}>
            {rulePosition(record)}
          </Typography.Text>
        )
      },
      {
        key: "protocol",
        title: "协议",
        dataIndex: "protocol",
        width: 100,
        render: (value: string | null) => value || "-"
      },
      {
        key: "match",
        title: "匹配条件",
        width: 330,
        render: (_, record) => (
          <Typography.Text ellipsis={{ tooltip: ruleMatch(record) }}>
            {ruleMatch(record)}
          </Typography.Text>
        )
      },
      {
        key: "action",
        title: "动作",
        dataIndex: "action",
        width: 120,
        render: (value: string | null) =>
          value ? <Tag color={actionColor(value)}>{value}</Tag> : "-"
      },
      {
        key: "comment",
        title: "备注",
        dataIndex: "comment",
        width: 190,
        render: (value: string | null) => value || "-"
      },
      {
        key: "raw",
        title: "原始规则",
        dataIndex: "raw_rule",
        width: 360,
        render: (value: string) => (
          <Typography.Text
            className="firewall-rule-raw"
            copyable
            ellipsis={{ tooltip: value }}
          >
            {value}
          </Typography.Text>
        )
      }
    ],
    []
  );

  const viewOptions: Array<{ label: string; value: FirewallView }> = [
    { label: "总览", value: "overview" },
    ...firewalls.map((firewall) => ({
      label: engineLabels[firewall.engine],
      value: firewall.engine
    }))
  ];
  const effectiveCount = firewalls.filter((firewall) => firewall.effective).length;
  const totalRuleCount = firewalls.reduce(
    (total, firewall) =>
      total + firewall.runtime_rule_count + firewall.permanent_rule_count,
    0
  );

  function refresh() {
    void summaryQuery.refetch();
    if (selectedEngine) void rulesQuery.refetch();
    if (selectedEngine && rawOpen) void rawQuery.refetch();
  }

  function renderOverview() {
    if (firewalls.length === 0) {
      return (
        <EmptyState title="未检测到支持的主机防火墙">
          当前 Agent 未发现 firewalld、UFW、iptables 或 nftables。
        </EmptyState>
      );
    }
    return (
      <Space orientation="vertical" size={16} className="firewall-section-stack">
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6}>
            <Statistic title="检测到的引擎" value={firewalls.length} />
          </Col>
          <Col xs={12} md={6}>
            <Statistic title="标记为实际生效" value={effectiveCount} />
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              title={<Tooltip title="包含各引擎上报条目，兼容层与底层可能描述同一策略">采集规则条目</Tooltip>}
              value={totalRuleCount}
            />
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              title="采集异常"
              value={firewalls.filter((item) => item.collection_status !== "success").length}
            />
          </Col>
        </Row>

        <div className="firewall-engine-grid">
          {firewalls.map((firewall) => (
            <div className="firewall-engine-summary" key={firewall.id}>
              <div className="firewall-engine-heading">
                <Space size={8} wrap>
                  <Database size={17} aria-hidden="true" />
                  <Typography.Text strong>
                    {engineLabels[firewall.engine]}
                  </Typography.Text>
                  <Tag color={firewall.effective ? "success" : "default"}>
                    {firewall.effective ? "实际生效" : "非独立生效"}
                  </Tag>
                </Space>
                <Button type="link" onClick={() => setView(firewall.engine)}>
                  查看策略
                </Button>
              </div>
              <Typography.Text className="firewall-relationship">
                {relationshipText(firewall)}
              </Typography.Text>
              <Space size={[6, 6]} wrap>
                <Tag>{roleLabels[firewall.role]}</Tag>
                <Tag color={stateColor(firewall.runtime_state)}>
                  {stateLabels[firewall.runtime_state]}
                </Tag>
                <Tag color={collectionColor(firewall.collection_status)}>
                  {collectionLabels[firewall.collection_status]}
                </Tag>
              </Space>
              <div className="firewall-rule-counts">
                <span>运行时 {firewall.runtime_rule_count}</span>
                <span>永久配置 {firewall.permanent_rule_count}</span>
              </div>
            </div>
          ))}
        </div>
      </Space>
    );
  }

  function renderEngine() {
    if (!selectedFirewall) return null;
    const failed = selectedFirewall.collection_status !== "success";
    return (
      <Space orientation="vertical" size={16} className="firewall-section-stack">
        {failed ? (
          <Alert
            showIcon
            type={selectedFirewall.collection_status === "partial" ? "warning" : "error"}
            title={`${collectionLabels[selectedFirewall.collection_status]}：${selectedFirewall.error_message || selectedFirewall.error_code || "未获得完整策略"}`}
            description={
              selectedFirewall.last_success_at
                ? `页面保留并展示 ${formatDateTime(selectedFirewall.last_success_at)} 的最后成功策略。`
                : "该引擎还没有完整成功的策略快照。"
            }
          />
        ) : null}

        <Descriptions
          bordered
          size="small"
          column={{ xs: 1, sm: 2, lg: 4 }}
          items={[
            { key: "role", label: "角色", children: roleLabels[selectedFirewall.role] },
            { key: "backend", label: "后端", children: selectedFirewall.backend || "-" },
            { key: "managedBy", label: "管理来源", children: selectedFirewall.managed_by || "-" },
            {
              key: "effective",
              label: "实际生效",
              children: <Tag color={selectedFirewall.effective ? "success" : "default"}>{selectedFirewall.effective ? "是" : "否"}</Tag>
            },
            { key: "state", label: "运行状态", children: stateLabels[selectedFirewall.runtime_state] },
            {
              key: "enabled",
              label: "开机启用",
              children: selectedFirewall.service_enabled === null ? "-" : selectedFirewall.service_enabled ? "是" : "否"
            },
            { key: "attempt", label: "最近尝试", children: formatDateTime(selectedFirewall.last_attempt_at) },
            { key: "success", label: "最后成功", children: formatDateTime(selectedFirewall.last_success_at) }
          ]}
        />

        <div className="firewall-rule-toolbar">
          <Segmented<FirewallScope>
            options={[
              { label: `运行时 (${selectedFirewall.runtime_rule_count})`, value: "runtime" },
              { label: `永久配置 (${selectedFirewall.permanent_rule_count})`, value: "permanent" }
            ]}
            value={scope}
            onChange={setScope}
          />
          <Input.Search
            allowClear
            aria-label="搜索防火墙策略"
            placeholder="搜索链、地址、端口或原始规则"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
          <Button
            icon={<Code2 size={16} />}
            aria-expanded={rawOpen}
            onClick={() => setRawOpen((current) => !current)}
          >
            {rawOpen ? "收起原始策略" : "查看原始策略"}
          </Button>
        </div>

        {rawOpen ? (
          <div className="firewall-raw-panel" role="region" aria-label={`${engineLabels[selectedFirewall.engine]} 原始策略`}>
            {rawQuery.isError ? <ErrorState error={rawQuery.error} /> : null}
            {rawQuery.isLoading ? <LoadingBlock /> : null}
            {!rawQuery.isLoading && !rawQuery.isError ? (
              rawQuery.data?.content ? (
                <pre>{rawQuery.data.content}</pre>
              ) : (
                <EmptyState title={`暂无${scope === "runtime" ? "运行时" : "永久配置"}原始策略`} />
              )
            ) : null}
          </div>
        ) : null}

        {rulesQuery.isError ? <ErrorState error={rulesQuery.error} /> : null}
        <ResizableTable<AssetFirewallRule>
          className="asset-detail-compact-table"
          storageKey={`asset-firewall-${selectedFirewall.engine}`}
          rowKey="id"
          columns={columns}
          dataSource={rulesQuery.data?.items ?? []}
          loading={rulesQuery.isFetching}
          pagination={{
            current: page,
            pageSize: FIREWALL_RULE_PAGE_SIZE,
            showSizeChanger: false,
            showTotal: (total) => `共 ${total} 条`,
            onChange: setPage
          }}
          locale={{
            emptyText: (
              <EmptyState
                title={deferredSearch ? "未找到匹配策略" : `暂无${scope === "runtime" ? "运行时" : "永久配置"}策略`}
              />
            )
          }}
          scroll={{ x: 1532, y: 275 }}
        />
      </Space>
    );
  }

  return (
    <Card
      className="content-card host-firewall-card"
      title={
        <Space size={8}>
          <ShieldCheck size={18} aria-hidden="true" />
          <span>主机防火墙</span>
          <Tooltip title="同一主机可同时出现管理器、底层引擎和兼容层；“实际生效”依据 Agent 识别的管理关系标记，兼容层规则可能与底层规则重复，不应简单相加理解为多套防护。">
            <CircleHelp
              className="inline-help-icon"
              size={15}
              aria-label="主机防火墙说明"
            />
          </Tooltip>
        </Space>
      }
      extra={
        <Button
          aria-label="刷新主机防火墙"
          icon={<RefreshCw size={16} />}
          loading={summaryQuery.isFetching}
          onClick={refresh}
        >
          刷新
        </Button>
      }
    >
      {summaryQuery.isError ? <ErrorState error={summaryQuery.error} /> : null}
      {summaryQuery.isLoading ? <LoadingBlock /> : null}
      {!summaryQuery.isLoading && !summaryQuery.isError ? (
        <Space orientation="vertical" size={16} className="firewall-section-stack">
          <div className="firewall-view-switcher">
            <Space size={8}>
              <Shield size={16} aria-hidden="true" />
              <Typography.Text strong>策略视图</Typography.Text>
            </Space>
            {compact ? (
              <Select<FirewallView>
                aria-label="选择防火墙策略视图"
                options={viewOptions}
                value={view}
                onChange={setView}
              />
            ) : (
              <Segmented<FirewallView>
                options={viewOptions}
                value={view}
                onChange={setView}
              />
            )}
          </div>
          {view === "overview" ? renderOverview() : renderEngine()}
        </Space>
      ) : null}
    </Card>
  );
}

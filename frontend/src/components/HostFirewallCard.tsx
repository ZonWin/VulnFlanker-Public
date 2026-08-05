import { t } from "@/app/i18n";
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
  manager: t("策略管理器"),
  backend: t("底层引擎"),
  compatibility: t("兼容层"),
  standalone: t("独立引擎")
};

const stateLabels: Record<AssetFirewall["runtime_state"], string> = {
  active: t("运行中"),
  inactive: t("未运行"),
  configured: t("已配置"),
  unknown: t("未知")
};

const collectionLabels: Record<AssetFirewall["collection_status"], string> = {
  success: t("采集成功"),
  partial: t("部分成功"),
  unsupported: t("不支持"),
  permission_denied: t("权限不足"),
  timeout: t("采集超时"),
  error: t("采集失败")
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
    return t("策略管理器 → {{v0}}", { v0: firewall.backend || t("后端未知") });
  }
  if (firewall.role === "compatibility") {
    return t("命令兼容层 → {{v0}}", { v0: firewall.backend || t("底层未知") });
  }
  if (firewall.managed_by) {
    return t("{{v0}} 管理的底层规则集", { v0: firewall.managed_by });
  }
  return firewall.role === "backend" ? t("直接生效的底层规则集") : t("独立策略来源");
}

function rulePosition(rule: AssetFirewallRule) {
  return [rule.zone, rule.table, rule.chain].filter(Boolean).join(" / ") || "-";
}

function ruleMatch(rule: AssetFirewallRule) {
  const network = [rule.source, rule.destination]
    .filter(Boolean)
    .join(" → ");
  const ports = [
    rule.source_port ? t("源端口 {{v0}}", { v0: rule.source_port }) : null,
    rule.destination_port ? t("目标端口 {{v0}}", { v0: rule.destination_port }) : null
  ]
    .filter(Boolean)
    .join(" · ");
  const interfaces = [rule.in_interface, rule.out_interface]
    .filter(Boolean)
    .join(" → ");
  return [network, ports, interfaces, rule.state_match]
    .filter(Boolean)
    .join(" · ") || t("任意");
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
        title: t("序号"),
        dataIndex: "order",
        width: 82,
        render: (value: number) => value + 1
      },
      {
        key: "kind",
        title: t("类型"),
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
        title: t("位置"),
        width: 220,
        render: (_, record) => (
          <Typography.Text ellipsis={{ tooltip: rulePosition(record) }}>
            {rulePosition(record)}
          </Typography.Text>
        )
      },
      {
        key: "protocol",
        title: t("协议"),
        dataIndex: "protocol",
        width: 100,
        render: (value: string | null) => value || "-"
      },
      {
        key: "match",
        title: t("匹配条件"),
        width: 330,
        render: (_, record) => (
          <Typography.Text ellipsis={{ tooltip: ruleMatch(record) }}>
            {ruleMatch(record)}
          </Typography.Text>
        )
      },
      {
        key: "action",
        title: t("动作"),
        dataIndex: "action",
        width: 120,
        render: (value: string | null) =>
          value ? <Tag color={actionColor(value)}>{value}</Tag> : "-"
      },
      {
        key: "comment",
        title: t("备注"),
        dataIndex: "comment",
        width: 190,
        render: (value: string | null) => value || "-"
      },
      {
        key: "raw",
        title: t("原始规则"),
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
    { label: t("总览"), value: "overview" },
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
        <EmptyState title={t("未检测到支持的主机防火墙")}>
          {t("当前 Agent 未发现 firewalld、UFW、iptables 或 nftables。")}</EmptyState>
      );
    }
    return (
      <Space orientation="vertical" size={16} className="firewall-section-stack">
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6}>
            <Statistic title={t("检测到的引擎")} value={firewalls.length} />
          </Col>
          <Col xs={12} md={6}>
            <Statistic title={t("标记为实际生效")} value={effectiveCount} />
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              title={<Tooltip title={t("包含各引擎上报条目，兼容层与底层可能描述同一策略")}>{t("采集规则条目")}</Tooltip>}
              value={totalRuleCount}
            />
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              title={t("采集异常")}
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
                    {firewall.effective ? t("实际生效") : t("非独立生效")}
                  </Tag>
                </Space>
                <Button type="link" onClick={() => setView(firewall.engine)}>
                  {t("查看策略")}</Button>
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
                <span>{t("运行时")}{firewall.runtime_rule_count}</span>
                <span>{t("永久配置")}{firewall.permanent_rule_count}</span>
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
            title={t("{{v0}}：{{v1}}", { v0: collectionLabels[selectedFirewall.collection_status], v1: selectedFirewall.error_message || selectedFirewall.error_code || t("未获得完整策略") })}
            description={
              selectedFirewall.last_success_at
                ? t("页面保留并展示 {{v0}} 的最后成功策略。", { v0: formatDateTime(selectedFirewall.last_success_at) })
                : t("该引擎还没有完整成功的策略快照。")
            }
          />
        ) : null}

        <Descriptions
          bordered
          size="small"
          column={{ xs: 1, sm: 2, lg: 4 }}
          items={[
            { key: "role", label: t("角色"), children: roleLabels[selectedFirewall.role] },
            { key: "backend", label: t("后端"), children: selectedFirewall.backend || "-" },
            { key: "managedBy", label: t("管理来源"), children: selectedFirewall.managed_by || "-" },
            {
              key: "effective",
              label: t("实际生效"),
              children: <Tag color={selectedFirewall.effective ? "success" : "default"}>{selectedFirewall.effective ? t("是") : t("否")}</Tag>
            },
            { key: "state", label: t("运行状态"), children: stateLabels[selectedFirewall.runtime_state] },
            {
              key: "enabled",
              label: t("开机启用"),
              children: selectedFirewall.service_enabled === null ? "-" : selectedFirewall.service_enabled ? t("是") : t("否")
            },
            { key: "attempt", label: t("最近尝试"), children: formatDateTime(selectedFirewall.last_attempt_at) },
            { key: "success", label: t("最后成功"), children: formatDateTime(selectedFirewall.last_success_at) }
          ]}
        />

        <div className="firewall-rule-toolbar">
          <Segmented<FirewallScope>
            options={[
              { label: t("运行时 ({{v0}})", { v0: selectedFirewall.runtime_rule_count }), value: "runtime" },
              { label: t("永久配置 ({{v0}})", { v0: selectedFirewall.permanent_rule_count }), value: "permanent" }
            ]}
            value={scope}
            onChange={setScope}
          />
          <Input.Search
            allowClear
            aria-label={t("搜索防火墙策略")}
            placeholder={t("搜索链、地址、端口或原始规则")}
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
            {rawOpen ? t("收起原始策略") : t("查看原始策略")}
          </Button>
        </div>

        {rawOpen ? (
          <div className="firewall-raw-panel" role="region" aria-label={t("{{v0}} 原始策略", { v0: engineLabels[selectedFirewall.engine] })}>
            {rawQuery.isError ? <ErrorState error={rawQuery.error} /> : null}
            {rawQuery.isLoading ? <LoadingBlock /> : null}
            {!rawQuery.isLoading && !rawQuery.isError ? (
              rawQuery.data?.content ? (
                <pre>{rawQuery.data.content}</pre>
              ) : (
                <EmptyState title={t("暂无{{v0}}原始策略", { v0: scope === "runtime" ? t("运行时") : t("永久配置") })} />
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
            showTotal: (total) => t("共 {{v0}} 条", { v0: total }),
            onChange: setPage
          }}
          locale={{
            emptyText: (
              <EmptyState
                title={deferredSearch ? t("未找到匹配策略") : t("暂无{{v0}}策略", { v0: scope === "runtime" ? t("运行时") : t("永久配置") })}
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
          <span>{t("主机防火墙")}</span>
          <Tooltip title={t("同一主机可同时出现管理器、底层引擎和兼容层；“实际生效”依据 Agent 识别的管理关系标记，兼容层规则可能与底层规则重复，不应简单相加理解为多套防护。")}>
            <CircleHelp
              className="inline-help-icon"
              size={15}
              aria-label={t("主机防火墙说明")}
            />
          </Tooltip>
        </Space>
      }
      extra={
        <Button
          aria-label={t("刷新主机防火墙")}
          icon={<RefreshCw size={16} />}
          loading={summaryQuery.isFetching}
          onClick={refresh}
        >
          {t("刷新")}</Button>
      }
    >
      {summaryQuery.isError ? <ErrorState error={summaryQuery.error} /> : null}
      {summaryQuery.isLoading ? <LoadingBlock /> : null}
      {!summaryQuery.isLoading && !summaryQuery.isError ? (
        <Space orientation="vertical" size={16} className="firewall-section-stack">
          <div className="firewall-view-switcher">
            <Space size={8}>
              <Shield size={16} aria-hidden="true" />
              <Typography.Text strong>{t("策略视图")}</Typography.Text>
            </Space>
            {compact ? (
              <Select<FirewallView>
                aria-label={t("选择防火墙策略视图")}
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

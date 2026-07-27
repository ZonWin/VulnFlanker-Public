import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  message,
  Pagination,
  Row,
  Select,
  Space,
  Statistic,
  Tag,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  Eye,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Signal
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import { getLiveHealth } from "@/api/health";
import {
  getRiskConfig,
  getRiskQueue,
  reopenMatchResultHandling,
  updateMatchResultHandling
} from "@/api/matchResults";
import {
  getBusinessSystems,
  getPeople,
  getResponsibilityTeams
} from "@/api/ownership";
import type {
  MatchResultHandlingUpdate,
  MatchResultSummary,
  RiskQueueQuery
} from "@/api/types";
import ConfidenceBar from "@/components/ConfidenceBar";
import ErrorState from "@/components/ErrorState";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import HandlingStatusTag, {
  handlingScopeOptions,
  handlingStatusOptions
} from "@/components/HandlingStatusTag";
import MatchResultHandlingModal from "@/components/MatchResultHandlingModal";
import RiskPriorityTag from "@/components/RiskPriorityTag";
import StatusTag from "@/components/StatusTag";
import {
  AgentStatusTag,
  VerificationTaskStatusTag
} from "@/components/ValueTags";
import { formatDateTime, formatDurationSeconds, formatScore } from "@/utils/format";

const defaultFilters: RiskQueueQuery = {
  handling_scope: "open"
};

const DEFAULT_PAGE_SIZE = 10;

const statusOptions = [
  { label: "受影响", value: "affected" },
  { label: "已验证", value: "verified" },
  { label: "待复核", value: "needs_review" }
];

const priorityOptions = [
  { label: "严重", value: "critical" },
  { label: "高危", value: "high" },
  { label: "中危", value: "medium" },
  { label: "低危", value: "low" },
  { label: "无风险", value: "none" }
];

const criticalityOptions = [
  { label: "极高", value: "critical" },
  { label: "高", value: "high" },
  { label: "中", value: "medium" },
  { label: "低", value: "low" }
];

const exposureOptions = [
  { label: "公网暴露", value: "internet" },
  { label: "内网可达", value: "internal" },
  { label: "DMZ", value: "dmz" },
  { label: "私有", value: "private" }
];

const verificationOptions = [
  { label: "已验证", value: "verified" },
  { label: "未验证", value: "unverified" },
  { label: "已有任务", value: "has_task" },
  { label: "无任务", value: "no_task" }
];

const agentStatusOptions = [
  { label: "在线", value: "online" },
  { label: "离线", value: "offline" },
  { label: "未知", value: "unknown" }
];

const freshnessOptions = [
  { label: "新鲜", value: "fresh" },
  { label: "过期", value: "stale" }
];

function normalizeFilters(values: RiskQueueQuery): RiskQueueQuery {
  return {
    ...(values.risk_code?.trim() ? { risk_code: values.risk_code.trim() } : {}),
    ...(values.status ? { status: values.status } : {}),
    ...(values.min_risk_score !== undefined && values.min_risk_score !== null
      ? { min_risk_score: values.min_risk_score }
      : {}),
    ...(values.risk_priority ? { risk_priority: values.risk_priority } : {}),
    ...(values.asset_criticality
      ? { asset_criticality: values.asset_criticality }
      : {}),
    ...(values.exposure_type ? { exposure_type: values.exposure_type } : {}),
    ...(values.business_system_id
      ? { business_system_id: values.business_system_id }
      : {}),
    ...(values.responsibility_team_id
      ? { responsibility_team_id: values.responsibility_team_id }
      : {}),
    ...(values.responsible_person_id
      ? { responsible_person_id: values.responsible_person_id }
      : {}),
    ...(values.kev_only ? { kev_only: values.kev_only } : {}),
    ...(values.verification_state
      ? { verification_state: values.verification_state }
      : {}),
    ...(values.agent_status ? { agent_status: values.agent_status } : {}),
    ...(values.asset_freshness ? { asset_freshness: values.asset_freshness } : {}),
    ...(values.handling_status ? { handling_status: values.handling_status } : {}),
    ...(values.handling_scope ? { handling_scope: values.handling_scope } : {})
  };
}

export default function RiskQueuePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<RiskQueueQuery>();
  const [messageApi, contextHolder] = message.useMessage();
  const [filters, setFilters] = useState<RiskQueueQuery>(defaultFilters);
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  const [tablePage, setTablePage] = useState(1);
  const [tablePageSize, setTablePageSize] = useState(DEFAULT_PAGE_SIZE);
  const [handlingTarget, setHandlingTarget] = useState<MatchResultSummary | null>(null);

  const healthQuery = useQuery({
    queryKey: ["health", "live"],
    queryFn: getLiveHealth
  });

  const riskConfigQuery = useQuery({
    queryKey: ["match-results", "risk-config"],
    queryFn: getRiskConfig
  });

  const riskQueueQuery = useQuery({
    queryKey: ["match-results", "risk-queue", filters, tablePage, tablePageSize],
    queryFn: () =>
      getRiskQueue({
        ...filters,
        offset: (tablePage - 1) * tablePageSize,
        limit: tablePageSize
      })
  });

  const businessSystemsQuery = useQuery({
    queryKey: ["ownership", "systems", "risk-filter-options"],
    queryFn: () =>
      getBusinessSystems({ page_size: 200, sort_by: "name", sort_order: "asc" })
  });

  const responsibilityTeamsQuery = useQuery({
    queryKey: ["ownership", "teams", "risk-filter-options"],
    queryFn: () =>
      getResponsibilityTeams({ page_size: 200, sort_by: "name", sort_order: "asc" })
  });

  const peopleQuery = useQuery({
    queryKey: ["ownership", "people", "risk-filter-options"],
    queryFn: () => getPeople({ page_size: 200, sort_by: "name", sort_order: "asc" })
  });

  const updateHandlingMutation = useMutation({
    mutationFn: ({
      matchResultId,
      values
    }: {
      matchResultId: string;
      values: MatchResultHandlingUpdate;
    }) => updateMatchResultHandling(matchResultId, values),
    onSuccess: () => {
      messageApi.success("处置状态已更新");
      setHandlingTarget(null);
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
      void queryClient.invalidateQueries({ queryKey: ["task-center"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "处置状态更新失败");
    }
  });

  const reopenHandlingMutation = useMutation({
    mutationFn: ({
      matchResultId,
      note
    }: {
      matchResultId: string;
      note?: string | null;
    }) => reopenMatchResultHandling(matchResultId, { note }),
    onSuccess: () => {
      messageApi.success("风险项已重新打开");
      setHandlingTarget(null);
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
      void queryClient.invalidateQueries({ queryKey: ["task-center"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "重新打开失败");
    }
  });

  useEffect(() => {
    setTablePage(1);
  }, [filters]);

  const riskQueuePage = riskQueueQuery.data;
  const rows = riskQueuePage?.items ?? [];
  const total = riskQueuePage?.total ?? rows.length;
  const businessSystemOptions = useMemo(
    () =>
      (businessSystemsQuery.data?.items ?? []).map((system) => ({
        label: `${system.code} · ${system.name}`,
        value: system.id
      })),
    [businessSystemsQuery.data?.items]
  );
  const responsibilityTeamOptions = useMemo(
    () =>
      (responsibilityTeamsQuery.data?.items ?? []).map((team) => ({
        label: `${team.code} · ${team.name}`,
        value: team.id
      })),
    [responsibilityTeamsQuery.data?.items]
  );
  const personOptions = useMemo(
    () =>
      (peopleQuery.data?.items ?? []).map((person) => ({
        label: `${person.name}${person.employee_no ? ` · ${person.employee_no}` : ""} · ${person.team.name}`,
        value: person.id
      })),
    [peopleQuery.data?.items]
  );
  const ownershipOptionsFailed =
    businessSystemsQuery.isError || responsibilityTeamsQuery.isError || peopleQuery.isError;
  const queueMetrics = {
    total: riskQueuePage?.total ?? rows.length,
    critical:
      riskQueuePage?.critical_count ??
      rows.filter((row) => row.risk_priority === "critical").length,
    unverified:
      riskQueuePage?.unverified_count ??
      rows.filter(
        (row) => row.status !== "verified" && row.verification_evidence_count === 0
      ).length,
    stale:
      riskQueuePage?.stale_asset_count ?? rows.filter((row) => row.asset_is_stale).length
  };

  const columns: ColumnsType<MatchResultSummary> = [
    {
      title: "风险编号",
      dataIndex: "risk_code",
      width: 205,
      render: (value: string | null) =>
        value ? (
          <Typography.Text
            className="risk-business-code"
            copyable={{ text: value }}
          >
            {value}
          </Typography.Text>
        ) : (
          "-"
        )
    },
    {
      title: "优先级",
      dataIndex: "risk_priority",
      width: 100,
      render: (value: MatchResultSummary["risk_priority"]) => (
        <RiskPriorityTag value={value} />
      )
    },
    {
      title: "风险分",
      dataIndex: "risk_score",
      width: 100,
      sorter: (a, b) => a.risk_score - b.risk_score,
      render: (value: number) => <span className="risk-score">{formatScore(value)}</span>
    },
    {
      title: "漏洞",
      dataIndex: "vulnerability_title",
      minWidth: 320,
      render: (_: string, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(`/matching/${record.id}`)}>
            {record.vulnerability_canonical_id}
          </Typography.Link>
          <Tag color={record.vulnerability_kev_status ? "red" : "default"}>
            {record.vulnerability_kev_status ? "KEV" : "非 KEV"}
          </Tag>
          <Typography.Text className="table-subtitle" ellipsis>
            {record.vulnerability_title}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "资产",
      dataIndex: "asset_hostname",
      width: 250,
      render: (_: string, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(`/assets/${record.asset_id}`)}>
            {record.asset_hostname}
          </Typography.Link>
          <Space size={4} wrap>
            <AgentStatusTag value={record.asset_agent_status ?? "unknown"} />
            <Tag color={record.asset_is_stale ? "red" : "green"}>
              {record.asset_is_stale ? "快照过期" : "快照新鲜"}
            </Tag>
          </Space>
          <Typography.Text className="table-subtitle">
            {record.asset_agent_id ?? record.asset_id}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "匹配状态",
      dataIndex: "status",
      width: 120,
      render: (value: MatchResultSummary["status"]) => <StatusTag value={value} />
    },
    {
      title: "处置状态",
      dataIndex: "handling_status",
      width: 160,
      render: (_: MatchResultSummary["handling_status"], record) => (
        <Space orientation="vertical" size={0}>
          <HandlingStatusTag value={record.handling_status} />
          <Typography.Text className="table-subtitle">
            {record.handling_updated_at ? formatDateTime(record.handling_updated_at) : "暂无处置"}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "验证",
      key: "verification",
      width: 150,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          {record.latest_verification_task_status ? (
            <VerificationTaskStatusTag value={record.latest_verification_task_status} />
          ) : (
            <Tag>无任务</Tag>
          )}
          <Typography.Text className="table-subtitle">
            {record.verification_evidence_count} 证据 / {record.verification_task_count} 任务
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "资产线索",
      key: "assetSignals",
      width: 170,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Tag color={record.asset_has_public_exposure ? "red" : "blue"}>
            {record.asset_has_public_exposure ? "公网监听" : record.asset_exposure_type ?? "-"}
          </Tag>
          <Typography.Text className="table-subtitle">
            快照年龄 {formatDurationSeconds(record.asset_snapshot_age_seconds)}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "置信度",
      dataIndex: "confidence",
      width: 150,
      render: (value: number) => <ConfidenceBar value={value} />
    },
    {
      title: "最近评估时间",
      dataIndex: "last_evaluated_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    {
      title: "模型",
      dataIndex: "risk_model_version",
      width: 130
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 200,
      render: (_, record) => (
        <Space className="table-actions" size={2}>
          <Button
            type="link"
            icon={<Eye size={15} />}
            onClick={() => navigate(`/matching/${record.id}`)}
          >
            详情
          </Button>
          <Button
            type="link"
            onClick={() =>
              record.latest_verification_task_id
                ? navigate(`/verification-tasks/${record.latest_verification_task_id}`)
                : navigate(`/matching/${record.id}?verify=1`)
            }
          >
            验证
          </Button>
          <Button
            type="link"
            icon={<ClipboardCheck size={15} />}
            onClick={() => setHandlingTarget(record)}
          >
            处置
          </Button>
        </Space>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title="风险队列"
        extra={
          <Space>
            <Button
              icon={<BookOpen size={16} />}
              onClick={() => navigate("/rules#risk-factors")}
            >
              规则说明
            </Button>
            <Button
              icon={<RefreshCw size={16} />}
              onClick={() => {
                void healthQuery.refetch();
                void riskConfigQuery.refetch();
                void riskQueueQuery.refetch();
              }}
              loading={
                healthQuery.isFetching ||
                riskConfigQuery.isFetching ||
                riskQueueQuery.isFetching
              }
            >
              刷新
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={6}>
          <Card className="metric-card">
            <Statistic title="风险项" value={queueMetrics.total} prefix={<Signal size={28} />} />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-red">
            <Statistic
              title="严重优先级"
              value={queueMetrics.critical}
              prefix={<ShieldAlert size={28} />}
            />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-green">
            <Statistic
              title="未验证"
              value={queueMetrics.unverified}
              prefix={<ShieldCheck size={28} />}
            />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card">
            <Statistic
              title="快照过期"
              value={queueMetrics.stale}
              prefix={<ShieldAlert size={28} />}
            />
          </Card>
        </Col>
      </Row>

      {healthQuery.isError ? (
        <ErrorState title="后端存活检查失败" error={healthQuery.error} />
      ) : null}

      {riskConfigQuery.data?.warnings.length ? (
        <Alert
          type="warning"
          showIcon
          message={`风险模型 ${riskConfigQuery.data.model_version}`}
          description={riskConfigQuery.data.warnings.join(" ")}
        />
      ) : null}

      <Card className="content-card filter-card">
        {ownershipOptionsFailed ? (
          <Alert
            className="filter-options-alert"
            type="warning"
            showIcon
            title="部分责任归属选项加载失败"
            description="可刷新页面后重试；其他风险筛选仍可正常使用。"
          />
        ) : null}
        <Form
          className="risk-filter-form"
          form={form}
          layout="inline"
          initialValues={defaultFilters}
          onFinish={(values) => {
            setTablePage(1);
            setFilters(normalizeFilters(values));
          }}
        >
          <div className="filter-row filter-row-primary">
            <Form.Item label="风险编号" name="risk_code">
              <Input allowClear placeholder="RISK-260717-000001" />
            </Form.Item>
            <Form.Item label="状态" name="status">
              <Select allowClear options={statusOptions} placeholder="全部状态" />
            </Form.Item>
            <Form.Item label="优先级" name="risk_priority">
              <Select allowClear options={priorityOptions} placeholder="全部优先级" />
            </Form.Item>
            <Form.Item label="最低风险分" name="min_risk_score">
              <InputNumber min={0} max={10} step={0.1} placeholder="0-10" />
            </Form.Item>
            <Form.Item label="资产关键性" name="asset_criticality">
              <Select allowClear options={criticalityOptions} placeholder="全部关键性" />
            </Form.Item>
            <Form.Item className="filter-actions">
              <Space>
                <Button
                  onClick={() => {
                    form.resetFields();
                    setTablePage(1);
                    setFilters(defaultFilters);
                  }}
                >
                  重置
                </Button>
                <Button
                  icon={filtersExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  onClick={() => setFiltersExpanded((current) => !current)}
                >
                  {filtersExpanded ? "收起筛选" : "更多筛选"}
                </Button>
                <Button type="primary" htmlType="submit">
                  查询
                </Button>
              </Space>
            </Form.Item>
          </div>
          {filtersExpanded ? (
            <div className="filter-row filter-row-extra">
              <Form.Item label="暴露类型" name="exposure_type">
                <Select allowClear options={exposureOptions} placeholder="全部暴露" />
              </Form.Item>
              <Form.Item label="业务系统" name="business_system_id">
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  loading={businessSystemsQuery.isLoading}
                  options={businessSystemOptions}
                  placeholder="全部业务系统"
                  notFoundContent={businessSystemsQuery.isError ? "业务系统加载失败" : undefined}
                />
              </Form.Item>
              <Form.Item label="责任团队" name="responsibility_team_id">
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  loading={responsibilityTeamsQuery.isLoading}
                  options={responsibilityTeamOptions}
                  placeholder="全部责任团队"
                  notFoundContent={responsibilityTeamsQuery.isError ? "责任团队加载失败" : undefined}
                />
              </Form.Item>
              <Form.Item label="责任人员" name="responsible_person_id">
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  loading={peopleQuery.isLoading}
                  options={personOptions}
                  placeholder="全部责任人员"
                  notFoundContent={peopleQuery.isError ? "责任人员加载失败" : undefined}
                />
              </Form.Item>
              <Form.Item label="KEV" name="kev_only">
                <Select
                  allowClear
                  options={[{ label: "仅 KEV", value: true }]}
                  placeholder="全部漏洞"
                />
              </Form.Item>
              <Form.Item label="验证状态" name="verification_state">
                <Select allowClear options={verificationOptions} placeholder="全部验证" />
              </Form.Item>
              <Form.Item label="Agent" name="agent_status">
                <Select allowClear options={agentStatusOptions} placeholder="全部 Agent" />
              </Form.Item>
              <Form.Item label="资产新鲜度" name="asset_freshness">
                <Select allowClear options={freshnessOptions} placeholder="全部新鲜度" />
              </Form.Item>
              <Form.Item label="处置范围" name="handling_scope">
                <Select options={handlingScopeOptions} />
              </Form.Item>
              <Form.Item label="处置状态" name="handling_status">
                <Select allowClear options={handlingStatusOptions} placeholder="全部处置" />
              </Form.Item>
            </div>
          ) : null}
        </Form>
      </Card>

      <Card className="content-card" title="风险队列表格">
        {riskQueueQuery.isError ? <ErrorState error={riskQueueQuery.error} /> : null}
        <ResizableTable<MatchResultSummary>
          storageKey="risk-queue"
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={riskQueueQuery.isFetching}
          pagination={false}
          locale={{
            emptyText: (
              <EmptyState title="暂无风险项">
                <Button type="primary" onClick={() => navigate("/matching")}>
                  去触发匹配
                </Button>
              </EmptyState>
            )
          }}
          scroll={{ x: 1800 }}
        />
        <Space style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
          <Pagination
            current={tablePage}
            pageSize={tablePageSize}
            total={total}
            showSizeChanger
            showTotal={(value) => `共 ${value} 条`}
            onChange={(nextPage, nextPageSize) => {
              if (nextPageSize !== tablePageSize) {
                setTablePageSize(nextPageSize);
                setTablePage(1);
                return;
              }
              setTablePage(nextPage);
            }}
          />
        </Space>
      </Card>
      <MatchResultHandlingModal
        open={Boolean(handlingTarget)}
        result={handlingTarget}
        saving={updateHandlingMutation.isPending}
        reopening={reopenHandlingMutation.isPending}
        onCancel={() => setHandlingTarget(null)}
        onSave={(values) => {
          if (!handlingTarget) {
            return;
          }
          updateHandlingMutation.mutate({
            matchResultId: handlingTarget.id,
            values
          });
        }}
        onReopen={(note) => {
          if (!handlingTarget) {
            return;
          }
          reopenHandlingMutation.mutate({
            matchResultId: handlingTarget.id,
            note
          });
        }}
      />
    </Space>
  );
}

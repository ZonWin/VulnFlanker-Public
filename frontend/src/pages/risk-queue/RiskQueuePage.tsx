import { t } from "@/app/i18n";
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
  Popconfirm,
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
  Mail,
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
  sendMatchResultEmailAlert,
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
  { label: t("受影响"), value: "affected" },
  { label: t("已验证"), value: "verified" },
  { label: t("待复核"), value: "needs_review" }
];

const priorityOptions = [
  { label: t("严重"), value: "critical" },
  { label: t("高危"), value: "high" },
  { label: t("中危"), value: "medium" },
  { label: t("低危"), value: "low" },
  { label: t("无风险"), value: "none" }
];

const criticalityOptions = [
  { label: t("极高"), value: "critical" },
  { label: t("高"), value: "high" },
  { label: t("中"), value: "medium" },
  { label: t("低"), value: "low" }
];

const exposureOptions = [
  { label: t("公网暴露"), value: "internet" },
  { label: t("内网可达"), value: "internal" },
  { label: "DMZ", value: "dmz" },
  { label: t("私有"), value: "private" }
];

const verificationOptions = [
  { label: t("已验证"), value: "verified" },
  { label: t("未验证"), value: "unverified" },
  { label: t("已有任务"), value: "has_task" },
  { label: t("无任务"), value: "no_task" }
];

const agentStatusOptions = [
  { label: t("在线"), value: "online" },
  { label: t("离线"), value: "offline" },
  { label: t("未知"), value: "unknown" }
];

const freshnessOptions = [
  { label: t("新鲜"), value: "fresh" },
  { label: t("过期"), value: "stale" }
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
      messageApi.success(t("处置状态已更新"));
      setHandlingTarget(null);
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
      void queryClient.invalidateQueries({ queryKey: ["task-center"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("处置状态更新失败"));
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
      messageApi.success(t("风险项已重新打开"));
      setHandlingTarget(null);
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
      void queryClient.invalidateQueries({ queryKey: ["task-center"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("重新打开失败"));
    }
  });

  const emailAlertMutation = useMutation({
    mutationFn: sendMatchResultEmailAlert,
    onSuccess: (result) => {
      if (result.status === "skipped") {
        messageApi.warning(result.message);
      } else {
        messageApi.success(result.message);
      }
      void queryClient.invalidateQueries({ queryKey: ["email-deliveries"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("邮件告警发起失败"));
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
      title: t("风险编号"),
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
      title: t("优先级"),
      dataIndex: "risk_priority",
      width: 100,
      render: (value: MatchResultSummary["risk_priority"]) => (
        <RiskPriorityTag value={value} />
      )
    },
    {
      title: t("风险分"),
      dataIndex: "risk_score",
      width: 100,
      sorter: (a, b) => a.risk_score - b.risk_score,
      render: (value: number) => <span className="risk-score">{formatScore(value)}</span>
    },
    {
      title: t("漏洞"),
      dataIndex: "vulnerability_title",
      minWidth: 320,
      render: (_: string, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(`/matching/${record.id}`)}>
            {record.vulnerability_canonical_id}
          </Typography.Link>
          <Tag color={record.vulnerability_kev_status ? "red" : "default"}>
            {record.vulnerability_kev_status ? "KEV" : t("非 KEV")}
          </Tag>
          <Typography.Text className="table-subtitle" ellipsis>
            {record.vulnerability_title}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("资产"),
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
              {record.asset_is_stale ? t("快照过期") : t("快照新鲜")}
            </Tag>
          </Space>
          <Typography.Text className="table-subtitle">
            {record.asset_agent_id ?? record.asset_id}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("匹配状态"),
      dataIndex: "status",
      width: 120,
      render: (value: MatchResultSummary["status"]) => <StatusTag value={value} />
    },
    {
      title: t("处置状态"),
      dataIndex: "handling_status",
      width: 160,
      render: (_: MatchResultSummary["handling_status"], record) => (
        <Space orientation="vertical" size={0}>
          <HandlingStatusTag value={record.handling_status} />
          <Typography.Text className="table-subtitle">
            {record.handling_updated_at ? formatDateTime(record.handling_updated_at) : t("暂无处置")}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("验证"),
      key: "verification",
      width: 150,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          {record.latest_verification_task_status ? (
            <VerificationTaskStatusTag value={record.latest_verification_task_status} />
          ) : (
            <Tag>{t("无任务")}</Tag>
          )}
          <Typography.Text className="table-subtitle">
            {record.verification_evidence_count} {t("证据 /")}{record.verification_task_count} {t("任务")}</Typography.Text>
        </Space>
      )
    },
    {
      title: t("资产线索"),
      key: "assetSignals",
      width: 170,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Tag color={record.asset_has_public_exposure ? "red" : "blue"}>
            {record.asset_has_public_exposure ? t("公网监听") : record.asset_exposure_type ?? "-"}
          </Tag>
          <Typography.Text className="table-subtitle">
            {t("快照年龄")}{formatDurationSeconds(record.asset_snapshot_age_seconds)}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("置信度"),
      dataIndex: "confidence",
      width: 150,
      render: (value: number) => <ConfidenceBar value={value} />
    },
    {
      title: t("最近评估时间"),
      dataIndex: "last_evaluated_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    {
      title: t("模型"),
      dataIndex: "risk_model_version",
      width: 130
    },
    {
      title: t("操作"),
      key: "actions",
      fixed: "right",
      width: 290,
      render: (_, record) => (
        <Space className="table-actions" size={2}>
          <Button
            type="link"
            icon={<Eye size={15} />}
            onClick={() => navigate(`/matching/${record.id}`)}
          >
            {t("详情")}</Button>
          <Button
            type="link"
            onClick={() =>
              record.latest_verification_task_id
                ? navigate(`/verification-tasks/${record.latest_verification_task_id}`)
                : navigate(`/matching/${record.id}?verify=1`)
            }
          >
            {t("验证")}</Button>
          <Button
            type="link"
            icon={<ClipboardCheck size={15} />}
            onClick={() => setHandlingTarget(record)}
          >
            {t("处置")}</Button>
          <Popconfirm
            title={t("确认发送风险邮件告警？")}
            description={t("手动发送受风险阈值和邮件总开关限制，允许重复发送。")}
            okText={t("确认发送")}
            cancelText={t("取消")}
            onConfirm={() => emailAlertMutation.mutate(record.id)}
          >
            <Button type="link" icon={<Mail size={15} />} loading={emailAlertMutation.isPending}>
              {t("邮件告警")}
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title={t("风险队列")}
        extra={
          <Space>
            <Button
              icon={<BookOpen size={16} />}
              onClick={() => navigate("/rules#risk-factors")}
            >
              {t("规则说明")}</Button>
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
              {t("刷新")}</Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={6}>
          <Card className="metric-card">
            <Statistic title={t("风险项")} value={queueMetrics.total} prefix={<Signal size={28} />} />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-red">
            <Statistic
              title={t("严重优先级")}
              value={queueMetrics.critical}
              prefix={<ShieldAlert size={28} />}
            />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-green">
            <Statistic
              title={t("未验证")}
              value={queueMetrics.unverified}
              prefix={<ShieldCheck size={28} />}
            />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card">
            <Statistic
              title={t("快照过期")}
              value={queueMetrics.stale}
              prefix={<ShieldAlert size={28} />}
            />
          </Card>
        </Col>
      </Row>

      {healthQuery.isError ? (
        <ErrorState title={t("后端存活检查失败")} error={healthQuery.error} />
      ) : null}

      {riskConfigQuery.data?.warnings.length ? (
        <Alert
          type="warning"
          showIcon
          message={t("风险模型 {{v0}}", { v0: riskConfigQuery.data.model_version })}
          description={riskConfigQuery.data.warnings.join(" ")}
        />
      ) : null}

      <Card className="content-card filter-card">
        {ownershipOptionsFailed ? (
          <Alert
            className="filter-options-alert"
            type="warning"
            showIcon
            title={t("部分责任归属选项加载失败")}
            description={t("可刷新页面后重试；其他风险筛选仍可正常使用。")}
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
            <Form.Item label={t("风险编号")} name="risk_code">
              <Input allowClear placeholder="RISK-260717-000001" />
            </Form.Item>
            <Form.Item label={t("状态")} name="status">
              <Select allowClear options={statusOptions} placeholder={t("全部状态")} />
            </Form.Item>
            <Form.Item label={t("优先级")} name="risk_priority">
              <Select allowClear options={priorityOptions} placeholder={t("全部优先级")} />
            </Form.Item>
            <Form.Item label={t("最低风险分")} name="min_risk_score">
              <InputNumber min={0} max={10} step={0.1} placeholder="0-10" />
            </Form.Item>
            <Form.Item label={t("资产关键性")} name="asset_criticality">
              <Select allowClear options={criticalityOptions} placeholder={t("全部关键性")} />
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
                  {t("重置")}</Button>
                <Button
                  icon={filtersExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  onClick={() => setFiltersExpanded((current) => !current)}
                >
                  {filtersExpanded ? t("收起筛选") : t("更多筛选")}
                </Button>
                <Button type="primary" htmlType="submit">
                  {t("查询")}</Button>
              </Space>
            </Form.Item>
          </div>
          {filtersExpanded ? (
            <div className="filter-row filter-row-extra">
              <Form.Item label={t("暴露类型")} name="exposure_type">
                <Select allowClear options={exposureOptions} placeholder={t("全部暴露")} />
              </Form.Item>
              <Form.Item label={t("业务系统")} name="business_system_id">
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  loading={businessSystemsQuery.isLoading}
                  options={businessSystemOptions}
                  placeholder={t("全部业务系统")}
                  notFoundContent={businessSystemsQuery.isError ? t("业务系统加载失败") : undefined}
                />
              </Form.Item>
              <Form.Item label={t("责任团队")} name="responsibility_team_id">
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  loading={responsibilityTeamsQuery.isLoading}
                  options={responsibilityTeamOptions}
                  placeholder={t("全部责任团队")}
                  notFoundContent={responsibilityTeamsQuery.isError ? t("责任团队加载失败") : undefined}
                />
              </Form.Item>
              <Form.Item label={t("责任人员")} name="responsible_person_id">
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  loading={peopleQuery.isLoading}
                  options={personOptions}
                  placeholder={t("全部责任人员")}
                  notFoundContent={peopleQuery.isError ? t("责任人员加载失败") : undefined}
                />
              </Form.Item>
              <Form.Item label="KEV" name="kev_only">
                <Select
                  allowClear
                  options={[{ label: t("仅 KEV"), value: true }]}
                  placeholder={t("全部漏洞")}
                />
              </Form.Item>
              <Form.Item label={t("验证状态")} name="verification_state">
                <Select allowClear options={verificationOptions} placeholder={t("全部验证")} />
              </Form.Item>
              <Form.Item label="Agent" name="agent_status">
                <Select allowClear options={agentStatusOptions} placeholder={t("全部 Agent")} />
              </Form.Item>
              <Form.Item label={t("资产新鲜度")} name="asset_freshness">
                <Select allowClear options={freshnessOptions} placeholder={t("全部新鲜度")} />
              </Form.Item>
              <Form.Item label={t("处置范围")} name="handling_scope">
                <Select options={handlingScopeOptions} />
              </Form.Item>
              <Form.Item label={t("处置状态")} name="handling_status">
                <Select allowClear options={handlingStatusOptions} placeholder={t("全部处置")} />
              </Form.Item>
            </div>
          ) : null}
        </Form>
      </Card>

      <Card className="content-card" title={t("风险队列表格")}>
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
              <EmptyState title={t("暂无风险项")}>
                <Button type="primary" onClick={() => navigate("/matching")}>
                  {t("去触发匹配")}</Button>
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
            showTotal={(value) => t("共 {{v0}} 条", { v0: value })}
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

import { t } from "@/app/i18n";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  message,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Switch,
  Tag,
  Tooltip,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRightLeft,
  Boxes,
  Eye,
  Globe2,
  Pencil,
  RefreshCw,
  Search,
  SearchCheck,
  ServerCog,
  Trash2
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { bindAssetBusinessSystem, deleteAsset, getAsset, updateAsset } from "@/api/assets";
import { getMatchResults } from "@/api/matchResults";
import { getBusinessSystems } from "@/api/ownership";
import type {
  AssetComponent,
  AssetMetadataUpdate,
  AssetExposure,
  MatchResultSummary
} from "@/api/types";
import ConfidenceBar from "@/components/ConfidenceBar";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import HostFirewallCard from "@/components/HostFirewallCard";
import LoadingBlock from "@/components/LoadingBlock";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import RiskPriorityTag from "@/components/RiskPriorityTag";
import StatusTag from "@/components/StatusTag";
import {
  AgentStatusTag,
  BooleanTag,
  CriticalityTag,
  ExposureTag,
  VerificationTaskStatusTag
} from "@/components/ValueTags";
import { formatDateTime, formatDurationSeconds, formatScore } from "@/utils/format";
import { useAuth } from "@/app/auth";

function displayValue(value?: string | number | null) {
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

function matchesKeyword(keyword: string, values: unknown[]) {
  const normalizedKeyword = keyword.trim().toLocaleLowerCase();
  if (!normalizedKeyword) {
    return true;
  }
  return values.some((value) =>
    String(value ?? "")
      .toLocaleLowerCase()
      .includes(normalizedKeyword)
  );
}

function nullableText(value?: string | null) {
  const normalized = String(value ?? "").trim();
  return normalized || null;
}

function optionalText(value?: string | null) {
  const normalized = String(value ?? "").trim();
  return normalized || undefined;
}

function normalizeAssetMetadata(values: AssetMetadataUpdate): AssetMetadataUpdate {
  return {
    display_name: nullableText(values.display_name),
    environment_type: optionalText(values.environment_type),
    exposure_type: optionalText(values.exposure_type),
    criticality: optionalText(values.criticality),
    allow_auto_verify: values.allow_auto_verify,
    allow_auto_remediate: values.allow_auto_remediate
  };
}

const criticalityOptions = ["critical", "high", "medium", "low"].map((value) => ({
  label: value,
  value
}));

const environmentOptions = ["production", "staging", "test", "development"].map(
  (value) => ({
    label: value,
    value
  })
);

const exposureOptions = ["internet", "dmz", "internal", "isolated"].map((value) => ({
  label: value,
  value
}));
const DETAIL_TABLE_PAGE_SIZE = 5;

export default function AssetDetailPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_superuser);
  const { assetId } = useParams<{ assetId: string }>();
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [metadataForm] = Form.useForm<AssetMetadataUpdate>();
  const [ownershipForm] = Form.useForm<{ business_system_id: string }>();
  const selectedOwnershipSystemId = Form.useWatch("business_system_id", ownershipForm);
  const [componentKeyword, setComponentKeyword] = useState("");
  const [exposureKeyword, setExposureKeyword] = useState("");
  const [matchKeyword, setMatchKeyword] = useState("");
  const [metadataOpen, setMetadataOpen] = useState(false);
  const [ownershipOpen, setOwnershipOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteLinkedAgent, setDeleteLinkedAgent] = useState(false);

  const assetQuery = useQuery({
    queryKey: ["assets", "detail", assetId],
    queryFn: () => getAsset(assetId ?? ""),
    enabled: Boolean(assetId)
  });

  const detail = assetQuery.data;
  const matchResultsQuery = useQuery({
    queryKey: ["match-results", "asset", detail?.id],
    queryFn: () => getMatchResults({ asset_id: detail?.id ?? "", limit: 30 }),
    enabled: Boolean(detail?.id)
  });
  const systemsQuery = useQuery({
    queryKey: ["ownership", "systems", "asset-detail-options"],
    queryFn: () =>
      getBusinessSystems({
        status: "active",
        page_size: 200,
        sort_by: "name",
        sort_order: "asc"
      }),
    enabled: ownershipOpen
  });
  const selectedOwnershipSystem = systemsQuery.data?.items.find(
    (system) => system.id === selectedOwnershipSystemId
  );

  const updateMetadataMutation = useMutation({
    mutationFn: (values: AssetMetadataUpdate) =>
      updateAsset(detail?.id ?? assetId ?? "", normalizeAssetMetadata(values)),
    onSuccess: (updated) => {
      messageApi.success(t("资产元数据已更新"));
      setMetadataOpen(false);
      queryClient.setQueryData(["assets", "detail", assetId], updated);
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
      void queryClient.invalidateQueries({ queryKey: ["task-center"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("保存资产元数据失败"));
    }
  });

  const updateOwnershipMutation = useMutation({
    mutationFn: (value: string) =>
      bindAssetBusinessSystem(
        detail?.id ?? assetId ?? "",
        value === "__unassign__" ? null : value
      ),
    onSuccess: (updated) => {
      messageApi.success(t("资产运营归属已更新"));
      setOwnershipOpen(false);
      queryClient.setQueryData(["assets", "detail", assetId], updated);
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      void queryClient.invalidateQueries({ queryKey: ["ownership"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("更新资产运营归属失败"));
    }
  });
  const deleteAssetMutation = useMutation({
    mutationFn: (deleteAgentWithAsset: boolean) => {
      const targetAssetId = detail?.id ?? assetId;
      if (!targetAssetId) {
        throw new Error(t("资产 ID 不存在"));
      }
      return deleteAsset(targetAssetId, deleteAgentWithAsset);
    },
    onSuccess: (result) => {
      messageApi.success(result.agent_deleted ? t("资产和 Agent 已删除") : t("资产已删除，Agent 已保留"));
      setDeleteOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
      void queryClient.invalidateQueries({ queryKey: ["verification-tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["task-center"] });
      navigate("/assets");
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("删除资产失败"));
    }
  });

  function openMetadataModal() {
    if (!detail) {
      return;
    }
    metadataForm.setFieldsValue({
      display_name: detail.display_name ?? "",
      environment_type: detail.environment_type,
      exposure_type: detail.exposure_type,
      criticality: detail.criticality,
      allow_auto_verify: detail.allow_auto_verify,
      allow_auto_remediate: detail.allow_auto_remediate
    });
    setMetadataOpen(true);
  }

  function openOwnershipModal() {
    if (!detail) return;
    ownershipForm.setFieldsValue({
      business_system_id: detail.ownership.business_system?.id ?? "__unassign__"
    });
    setOwnershipOpen(true);
  }

  function openDeleteModal() {
    setDeleteLinkedAgent(false);
    setDeleteOpen(true);
  }

  const filteredComponents = useMemo(
    () =>
      (detail?.components ?? []).filter((component) =>
        matchesKeyword(componentKeyword, [
          component.component_name,
          component.component_type,
          component.version,
          component.source_type,
          component.install_path,
          component.evidence_ref
        ])
      ),
    [componentKeyword, detail?.components]
  );

  const filteredExposures = useMemo(
    () =>
      (detail?.exposures ?? []).filter((exposure) =>
        matchesKeyword(exposureKeyword, [
          exposure.exposure_kind,
          exposure.address,
          exposure.port,
          exposure.protocol,
          exposure.service_name,
          exposure.product,
          exposure.version,
          exposure.state,
          exposure.is_public ? t("公网 是 true") : t("非公网 否 false"),
          exposure.banner,
          exposure.evidence_ref
        ])
      ),
    [detail?.exposures, exposureKeyword]
  );

  const filteredMatchResults = useMemo(
    () =>
      (matchResultsQuery.data?.items ?? []).filter((matchResult) =>
        matchesKeyword(matchKeyword, [
          matchResult.risk_code,
          matchResult.vulnerability_canonical_id,
          matchResult.vulnerability_title,
          matchResult.vulnerability_product,
          matchResult.asset_hostname,
          matchResult.asset_agent_id,
          matchResult.status,
          matchResult.risk_priority,
          matchResult.handling_status,
          matchResult.latest_verification_task_status,
          matchResult.match_reason,
          matchResult.risk_explanation
        ])
      ),
    [matchKeyword, matchResultsQuery.data?.items]
  );

  const componentColumns: ColumnsType<AssetComponent> = useMemo(
    () => [
      { title: t("组件"), dataIndex: "component_name", minWidth: 180 },
      { title: t("类型"), dataIndex: "component_type", width: 120 },
      { title: t("版本"), dataIndex: "version", width: 150, render: displayValue },
      { title: t("来源"), dataIndex: "source_type", width: 130, render: displayValue },
      {
        title: t("安装路径"),
        dataIndex: "install_path",
        minWidth: 220,
        render: (value: string | null) => (
          <Typography.Text className="table-subtitle" ellipsis>
            {displayValue(value)}
          </Typography.Text>
        )
      },
      {
        title: t("证据引用"),
        dataIndex: "evidence_ref",
        width: 160,
        render: displayValue
      }
    ],
    []
  );

  const exposureColumns: ColumnsType<AssetExposure> = useMemo(
    () => [
      { title: t("类型"), dataIndex: "exposure_kind", width: 150 },
      {
        title: t("地址"),
        key: "address",
        width: 190,
        render: (_, record) => {
          const port = record.port === null ? "" : `:${record.port}`;
          return `${displayValue(record.address)}${port}`;
        }
      },
      {
        title: t("协议"),
        dataIndex: "protocol",
        width: 100,
        render: (value: string) => value.toUpperCase()
      },
      { title: t("服务"), dataIndex: "service_name", width: 130, render: displayValue },
      {
        title: t("产品"),
        key: "product",
        width: 190,
        render: (_, record) =>
          [record.product, record.version].filter(Boolean).join(" ") || "-"
      },
      { title: t("状态"), dataIndex: "state", width: 100 },
      {
        title: t("公网"),
        dataIndex: "is_public",
        width: 90,
        render: (value: boolean) => <BooleanTag value={value} trueColor="red" />
      },
      {
        title: "Banner",
        dataIndex: "banner",
        minWidth: 220,
        render: (value: string | null) => (
          <Typography.Text className="table-subtitle" ellipsis>
            {displayValue(value)}
          </Typography.Text>
        )
      }
    ],
    []
  );

  const matchColumns: ColumnsType<MatchResultSummary> = [
    {
      title: t("漏洞"),
      dataIndex: "vulnerability_title",
      minWidth: 280,
      render: (_: string, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(`/matching/${record.id}`)}>
            {record.vulnerability_canonical_id}
          </Typography.Link>
          <Typography.Text className="table-subtitle" ellipsis>
            {record.vulnerability_title}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("状态"),
      dataIndex: "status",
      width: 120,
      render: (value: MatchResultSummary["status"]) => <StatusTag value={value} />
    },
    {
      title: t("风险分"),
      dataIndex: "risk_score",
      width: 100,
      render: (value: number) => <span className="risk-score">{formatScore(value)}</span>
    },
    {
      title: t("优先级"),
      dataIndex: "risk_priority",
      width: 110,
      render: (value: MatchResultSummary["risk_priority"]) => (
        <RiskPriorityTag value={value} />
      )
    },
    {
      title: t("验证"),
      key: "verification",
      width: 140,
      render: (_, record) =>
        record.latest_verification_task_status ? (
          <VerificationTaskStatusTag value={record.latest_verification_task_status} />
        ) : (
          "-"
        )
    },
    {
      title: t("置信度"),
      dataIndex: "confidence",
      width: 150,
      render: (value: number) => <ConfidenceBar value={value} />
    },
    {
      title: t("最近评估"),
      dataIndex: "last_evaluated_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    {
      title: t("操作"),
      key: "actions",
      fixed: "right",
      width: 100,
      render: (_, record) => (
        <Button
          className="table-action-button"
          type="link"
          icon={<Eye size={15} />}
          onClick={() => navigate(`/matching/${record.id}`)}
        >
          {t("详情")}</Button>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title={t("资产详情")}
        extra={
          <Space>
            <Button icon={<ArrowLeft size={16} />} onClick={() => navigate(-1)}>
              {t("返回")}</Button>
            <Button
              icon={<SearchCheck size={16} />}
              onClick={() =>
                navigate(`/matching?asset_id=${encodeURIComponent(assetId ?? "")}`)
              }
              disabled={!assetId}
            >
              {t("漏洞比对")}</Button>
            <Button
              icon={<ServerCog size={16} />}
              onClick={() =>
                detail?.agent_id
                  ? navigate(`/agents?agent_id=${encodeURIComponent(detail.agent_id)}`)
                  : navigate("/agents")
              }
            >
              Agent
            </Button>
            <Button
              icon={<RefreshCw size={16} />}
              onClick={() => assetQuery.refetch()}
              loading={assetQuery.isFetching}
            >
              {t("刷新")}</Button>
            <Tooltip title={!isAdmin ? t("需要超级管理员权限") : t("删除资产及关联风险数据")}>
              <Button
                danger
                icon={<Trash2 size={16} />}
                disabled={!isAdmin || !detail}
                onClick={openDeleteModal}
              >
                {t("删除资产")}</Button>
            </Tooltip>
          </Space>
        }
      />

      {assetQuery.isLoading ? <LoadingBlock /> : null}
      {assetQuery.isError ? <ErrorState error={assetQuery.error} /> : null}

      {detail ? (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={6}>
              <Card className="metric-card">
                <Statistic title={t("组件")} value={detail.component_count} prefix={<Boxes size={24} />} />
              </Card>
            </Col>
            <Col xs={24} lg={6}>
              <Card className="metric-card metric-card-red">
                <Statistic
                  title={t("暴露面")}
                  value={detail.exposure_count}
                  prefix={<Globe2 size={24} />}
                />
              </Card>
            </Col>
            <Col xs={24} lg={6}>
              <Card className="metric-card metric-card-green">
                <Statistic title={t("快照")} value={detail.snapshots_count} />
              </Card>
            </Col>
            <Col xs={24} lg={6}>
              <Card className="metric-card">
                <Statistic
                  title={t("Agent 状态")}
                  valueRender={() =>
                    detail.agent_status ? (
                      <AgentStatusTag value={detail.agent_status.status} />
                    ) : (
                      "-"
                    )
                  }
                />
              </Card>
            </Col>
          </Row>

          <Card
            className="content-card"
            title={t("资产概览")}
            extra={
              <Button icon={<Pencil size={15} />} onClick={openMetadataModal}>
                {t("编辑")}</Button>
            }
          >
            <Descriptions
              bordered
              size="small"
              column={{ xs: 1, md: 3 }}
              items={[
                {
                  key: "displayName",
                  label: t("资产名称"),
                  children: displayValue(detail.display_name ?? detail.hostname)
                },
                {
                  key: "hostname",
                  label: t("资产Hostname"),
                  children: displayValue(detail.hostname)
                },
                { key: "agent", label: "Agent ID", children: displayValue(detail.agent_id) },
                { key: "ip", label: "IP", children: displayValue(detail.primary_ip) },
                { key: "platform", label: t("平台"), children: displayValue(detail.platform) },
                {
                  key: "os",
                  label: "OS",
                  children:
                    [detail.os_family, detail.os_version].filter(Boolean).join(" ") || "-"
                },
                {
                  key: "kernel",
                  label: t("内核"),
                  children: displayValue(detail.kernel_version)
                },
                {
                  key: "arch",
                  label: t("架构"),
                  children: displayValue(detail.architecture)
                },
                {
                  key: "criticality",
                  label: t("关键性"),
                  children: <CriticalityTag value={detail.criticality} />
                },
                {
                  key: "lastSeen",
                  label: t("最近上报"),
                  children: formatDateTime(detail.last_seen_at)
                },
                {
                  key: "assetId",
                  label: t("资产 ID"),
                  children: <Typography.Text copyable>{detail.id}</Typography.Text>
                }
              ]}
            />
          </Card>

          <Card
            className="content-card"
            title={t("运营归属")}
            extra={
              <Space>
                <Button
                  icon={<Pencil size={15} />}
                  disabled={!isAdmin}
                  onClick={openMetadataModal}
                >
                  {t("编辑元数据")}</Button>
                <Button
                  type="primary"
                  icon={<ArrowRightLeft size={15} />}
                  disabled={!isAdmin}
                  onClick={openOwnershipModal}
                >
                  {t("设置归属")}</Button>
              </Space>
            }
          >
            <Descriptions
              bordered
              size="small"
              column={{ xs: 1, md: 3 }}
              items={[
                {
                  key: "business",
                  label: t("业务系统"),
                  children: detail.ownership.business_system ? (
                    <Typography.Link
                      onClick={() =>
                        navigate(
                          `/business-systems?keyword=${encodeURIComponent(detail.ownership.business_system?.code ?? "")}`
                        )
                      }
                    >
                      {detail.ownership.business_system.name}
                    </Typography.Link>
                  ) : (
                    <Typography.Text type="secondary">{t("未分配")}</Typography.Text>
                  )
                },
                {
                  key: "team",
                  label: t("责任团队"),
                  children: detail.ownership.responsibility_team ? (
                    <Typography.Link
                      onClick={() =>
                        navigate(
                          `/responsibility-teams?keyword=${encodeURIComponent(detail.ownership.responsibility_team?.code ?? "")}`
                        )
                      }
                    >
                      {detail.ownership.responsibility_team.name}
                    </Typography.Link>
                  ) : "-"
                },
                {
                  key: "owner",
                  label: t("责任人"),
                  children: detail.ownership.responsible_person ? (
                    <Space orientation="vertical" size={0}>
                      <Typography.Link
                        onClick={() =>
                          navigate(
                            `/people?keyword=${encodeURIComponent(detail.ownership.responsible_person?.name ?? "")}`
                          )
                        }
                      >
                        {detail.ownership.responsible_person.name}
                      </Typography.Link>
                      <Typography.Text className="table-subtitle">
                        {detail.ownership.responsible_person.email || t("未设置邮箱")}
                      </Typography.Text>
                    </Space>
                  ) : "-"
                },
                {
                  key: "ownershipStatus",
                  label: t("归属状态"),
                  children:
                    detail.ownership.status === "complete" ? (
                      <Tag color="green">{t("归属完整")}</Tag>
                    ) : detail.ownership.status === "system_incomplete" ? (
                      <Tag color="gold">{t("链路不完整")}</Tag>
                    ) : (
                      <Tag>{t("未分配")}</Tag>
                    )
                },
                {
                  key: "ownershipSource",
                  label: t("归属来源"),
                  children: displayValue(detail.ownership.source)
                },
                {
                  key: "ownershipUpdatedAt",
                  label: t("归属更新时间"),
                  children: formatDateTime(detail.ownership.updated_at)
                },
                {
                  key: "environment",
                  label: t("环境"),
                  children: detail.environment_type
                },
                {
                  key: "exposure",
                  label: t("暴露类型"),
                  children: <ExposureTag value={detail.exposure_type} />
                },
                {
                  key: "autoVerify",
                  label: t("自动验证"),
                  children: (
                    <BooleanTag value={detail.allow_auto_verify} trueColor="blue" />
                  )
                },
                {
                  key: "autoRemediate",
                  label: t("自动修复"),
                  children: (
                    <BooleanTag value={detail.allow_auto_remediate} trueColor="orange" />
                  )
                }
              ]}
            />
          </Card>

          <Card className="content-card" title={t("Agent 状态")}>
            {detail.agent_status ? (
              <Descriptions
                bordered
                size="small"
                column={{ xs: 1, md: 3 }}
                items={[
                  {
                    key: "agentStatus",
                    label: t("状态"),
                    children: <AgentStatusTag value={detail.agent_status.status} />
                  },
                  {
                    key: "agentVersion",
                    label: t("Agent 版本"),
                    children: displayValue(detail.agent_status.version)
                  },
                  {
                    key: "heartbeat",
                    label: t("最近心跳"),
                    children: formatDateTime(detail.agent_status.last_heartbeat_at)
                  },
                  {
                    key: "snapshot",
                    label: t("最近快照"),
                    children: formatDateTime(detail.agent_status.last_snapshot_at)
                  },
                  {
                    key: "taskPoll",
                    label: t("最近取任务"),
                    children: formatDateTime(detail.agent_status.last_task_poll_at)
                  },
                  {
                    key: "snapshotAge",
                    label: t("快照年龄"),
                    children: formatDurationSeconds(detail.freshness.snapshot_age_seconds)
                  },
                  {
                    key: "stale",
                    label: t("快照过期"),
                    children: <BooleanTag value={detail.freshness.is_stale} trueColor="red" />
                  },
                  {
                    key: "lastError",
                    label: t("最近错误"),
                    children: displayValue(detail.agent_status.last_error)
                  }
                ]}
              />
            ) : (
              <EmptyState title={t("暂无 Agent 状态")} />
            )}
          </Card>

          <Card className="content-card" title={t("最新快照")}>
            {detail.latest_snapshot ? (
              <Descriptions
                bordered
                size="small"
                column={{ xs: 1, md: 3 }}
                items={[
                  {
                    key: "agentVersion",
                    label: t("Agent 版本"),
                    children: displayValue(detail.latest_snapshot.agent_version)
                  },
                  {
                    key: "platform",
                    label: t("平台"),
                    children: displayValue(detail.latest_snapshot.platform)
                  },
                  {
                    key: "collected",
                    label: t("采集时间"),
                    children: formatDateTime(detail.latest_snapshot.collected_at)
                  },
                  {
                    key: "received",
                    label: t("接收时间"),
                    children: formatDateTime(detail.latest_snapshot.received_at)
                  },
                  {
                    key: "counts",
                    label: t("内容"),
                    children: t("{{v0}} 组件 / {{v1}} 暴露面 / {{v2}} 防火墙 / {{v3}} 规则", { v0: detail.latest_snapshot.component_count, v1: detail.latest_snapshot.exposure_count, v2: detail.latest_snapshot.firewall_count ?? 0, v3: detail.latest_snapshot.firewall_rule_count ?? 0 })
                  },
                  {
                    key: "hash",
                    label: "Payload Hash",
                    children: (
                      <Typography.Text copyable className="table-subtitle" ellipsis>
                        {detail.latest_snapshot.payload_hash}
                      </Typography.Text>
                    )
                  }
                ]}
              />
            ) : (
              <EmptyState title={t("暂无快照")} />
            )}
          </Card>

          <Row className="asset-detail-data-grid" gutter={[16, 16]} align="stretch">
            <Col xs={24} xl={12}>
              <Card
                className="content-card"
                title={t("组件")}
                extra={
                  <Input
                    allowClear
                    aria-label={t("搜索组件")}
                    className="asset-detail-table-search"
                    placeholder={t("搜索组件关键字")}
                    prefix={<Search size={15} />}
                    value={componentKeyword}
                    onChange={(event) => setComponentKeyword(event.target.value)}
                  />
                }
              >
                <ResizableTable<AssetComponent>
                  className="asset-detail-compact-table"
                  storageKey="asset-detail-components"
                  rowKey="id"
                  columns={componentColumns}
                  dataSource={filteredComponents}
                  pagination={{
                    pageSize: DETAIL_TABLE_PAGE_SIZE,
                    showSizeChanger: false,
                    showTotal: (total) => t("共 {{v0}} 条", { v0: total })
                  }}
                  locale={{
                    emptyText: (
                      <EmptyState
                        title={componentKeyword.trim() ? t("未找到匹配组件") : t("暂无组件")}
                      />
                    )
                  }}
                  scroll={{ x: 980, y: 275 }}
                />
              </Card>
            </Col>
            <Col xs={24} xl={12}>
              <Card
                className="content-card"
                title={t("暴露面")}
                extra={
                  <Input
                    allowClear
                    aria-label={t("搜索暴露面")}
                    className="asset-detail-table-search"
                    placeholder={t("搜索暴露面关键字")}
                    prefix={<Search size={15} />}
                    value={exposureKeyword}
                    onChange={(event) => setExposureKeyword(event.target.value)}
                  />
                }
              >
                <ResizableTable<AssetExposure>
                  className="asset-detail-compact-table"
                  storageKey="asset-detail-exposures"
                  rowKey="id"
                  columns={exposureColumns}
                  dataSource={filteredExposures}
                  pagination={{
                    pageSize: DETAIL_TABLE_PAGE_SIZE,
                    showSizeChanger: false,
                    showTotal: (total) => t("共 {{v0}} 条", { v0: total })
                  }}
                  locale={{
                    emptyText: (
                      <EmptyState
                        title={exposureKeyword.trim() ? t("未找到匹配暴露面") : t("暂无暴露面")}
                      />
                    )
                  }}
                  scroll={{ x: 1160, y: 275 }}
                />
              </Card>
            </Col>
          </Row>

          <HostFirewallCard assetId={detail.id} />

          <Card
            className="content-card"
            title={t("关联匹配结果")}
            extra={
              <Input
                allowClear
                aria-label={t("搜索关联匹配结果")}
                className="asset-detail-table-search"
                placeholder={t("搜索匹配结果关键字")}
                prefix={<Search size={15} />}
                value={matchKeyword}
                onChange={(event) => setMatchKeyword(event.target.value)}
              />
            }
          >
            {matchResultsQuery.isError ? (
              <ErrorState error={matchResultsQuery.error} />
            ) : null}
            <ResizableTable<MatchResultSummary>
              storageKey="asset-detail-match-results"
              rowKey="id"
              columns={matchColumns}
              dataSource={filteredMatchResults}
              loading={matchResultsQuery.isFetching}
              pagination={{ defaultPageSize: 5, showSizeChanger: true }}
              locale={{
                emptyText: (
                  matchKeyword.trim() ? (
                    <EmptyState title={t("未找到匹配结果")} />
                  ) : (
                    <EmptyState title={t("暂无关联匹配结果")}>
                      <Button
                        type="primary"
                        onClick={() =>
                          navigate(`/matching?asset_id=${encodeURIComponent(detail.id)}`)
                        }
                      >
                        {t("去执行匹配")}</Button>
                    </EmptyState>
                  )
                )
              }}
              scroll={{ x: 1280 }}
            />
          </Card>

          <Modal
            title={t("删除资产")}
            open={deleteOpen}
            okText={t("确认删除")}
            cancelText={t("取消")}
            okButtonProps={{ danger: true }}
            confirmLoading={deleteAssetMutation.isPending}
            onCancel={() => setDeleteOpen(false)}
            onOk={() => deleteAssetMutation.mutate(deleteLinkedAgent)}
            destroyOnHidden
          >
            <Space className="page-stack" orientation="vertical" size={14}>
              <Alert
                showIcon
                type="warning"
                message={t("将删除资产及对应风险数据")}
                description={t("资产关联的匹配结果、风险处理记录、验证任务、证据、组件、暴露面、快照和防火墙数据会一并删除。此操作不可恢复。")}
              />
              {detail.agent_id ? (
                <Space orientation="vertical" size={8}>
                  <Typography.Text strong>{t("Agent 处理")}</Typography.Text>
                  <Switch
                    checked={deleteLinkedAgent}
                    onChange={setDeleteLinkedAgent}
                    checkedChildren={t("一并删除 Agent")}
                    unCheckedChildren={t("保留 Agent")}
                  />
                  <Typography.Text type="secondary">
                    {t("保留 Agent 时，若该 Agent 后续继续上传数据，资产会重新加入并继续更新；一并删除时会删除 Agent 凭证和状态。")}</Typography.Text>
                </Space>
              ) : (
                <Typography.Text type="secondary">
                  {t("该资产未绑定 Agent，只会删除资产及关联风险数据。")}</Typography.Text>
              )}
            </Space>
          </Modal>

          <Modal
            title={t("编辑资产元数据")}
            open={metadataOpen}
            onCancel={() => setMetadataOpen(false)}
            onOk={() => void metadataForm.submit()}
            confirmLoading={updateMetadataMutation.isPending}
            destroyOnHidden
            width={760}
          >
            <Form<AssetMetadataUpdate>
              form={metadataForm}
              layout="vertical"
              onFinish={(values) => updateMetadataMutation.mutate(values)}
            >
              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item
                    label={t("资产名称")}
                    name="display_name"
                    extra={t("为空时页面会使用资产Hostname展示。")}
                  >
                    <Input maxLength={255} placeholder={t("例如：支付业务生产服务器")} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label={t("资产Hostname")}>
                    <Input value={detail.hostname} disabled />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label={t("关键性")} name="criticality">
                    <Select options={criticalityOptions} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label={t("环境")} name="environment_type">
                    <Select options={environmentOptions} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label={t("暴露类型")} name="exposure_type">
                    <Select options={exposureOptions} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item
                    label={t("自动验证")}
                    name="allow_auto_verify"
                    valuePropName="checked"
                  >
                    <Switch />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item
                    label={t("自动修复")}
                    name="allow_auto_remediate"
                    valuePropName="checked"
                  >
                    <Switch />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </Modal>

          <Modal
            title={t("设置资产运营归属")}
            open={ownershipOpen}
            okText={t("确认更新")}
            confirmLoading={updateOwnershipMutation.isPending}
            onCancel={() => setOwnershipOpen(false)}
            onOk={() => ownershipForm.submit()}
          >
            <Alert
              showIcon
              type="info"
              message={t("只选择业务系统")}
              description={t("专门责任人、责任团队和邮箱将由业务关系自动带出，不能在资产上分别修改。")}
            />
            <Form
              form={ownershipForm}
              layout="vertical"
              className="ownership-binding-form"
              onFinish={({ business_system_id }) =>
                updateOwnershipMutation.mutate(business_system_id)
              }
            >
              <Form.Item
                label={t("业务系统")}
                name="business_system_id"
                rules={[{ required: true, message: t("请选择业务系统或解除归属") }]}
              >
                <Select
                  showSearch
                  optionFilterProp="label"
                  loading={systemsQuery.isLoading}
                  options={[
                    { value: "__unassign__", label: t("解除归属（进入待分配）") },
                    ...(systemsQuery.data?.items ?? []).map((system) => ({
                      value: system.id,
                      label: `${system.name} · ${system.code}`
                    }))
                  ]}
                  placeholder={t("选择启用业务系统")}
                />
              </Form.Item>
              {selectedOwnershipSystem?.responsible_person ? (
                <Alert
                  showIcon
                  type="success"
                  message={`${selectedOwnershipSystem.responsible_person.name} · ${selectedOwnershipSystem.responsible_person.team.name}`}
                  description={
                    selectedOwnershipSystem.responsible_person.email ||
                    t("责任人未设置邮箱")
                  }
                />
              ) : selectedOwnershipSystemId === "__unassign__" ? (
                <Alert
                  showIcon
                  type="warning"
                  message={t("确认后该资产将进入待分配状态")}
                />
              ) : null}
            </Form>
          </Modal>
        </>
      ) : null}
    </Space>
  );
}

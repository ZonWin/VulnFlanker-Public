import { t } from "@/app/i18n";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  InputNumber,
  message,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, DownloadCloud, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import {
  collectIntelSource,
  clearIntelSourceVulnerabilities,
  getCisaKevMonitorConfig,
  getIntelRawEvents,
  getIntelRuns,
  getIntelSources,
  getWatchVulnMonitorConfig,
  normalizeIntelRawEvent,
  updateCisaKevMonitorConfig,
  updateWatchVulnMonitorConfig
} from "@/api/intel";
import type { IntelManualSourceName } from "@/api/intel";
import type {
  CisaKevMonitorConfigUpdate,
  IntelCollectionRun,
  IntelRawEvent,
  IntelSourceVulnerabilityCleanupResult,
  IntelSourceStatus,
  WatchVulnMonitorConfigUpdate
} from "@/api/types";
import ErrorState from "@/components/ErrorState";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import { formatDateTime, formatDurationSeconds } from "@/utils/format";

interface IntelCollectFormValues {
  source_name: IntelManualSourceName;
  limit?: number | null;
  min_score?: number | null;
}

interface MonitorDraft {
  enabled: boolean;
  interval_seconds: number;
  limit?: number | null;
  latest_only?: boolean;
}

const defaultValues: IntelCollectFormValues = {
  source_name: "cisa-kev",
  limit: 100,
  min_score: 7
};

const defaultCisaMonitorDraft: MonitorDraft = {
  enabled: true,
  interval_seconds: 86400,
  limit: null,
  latest_only: false
};

const defaultWatchVulnMonitorDraft: MonitorDraft = {
  enabled: false,
  interval_seconds: 1800,
  limit: null
};

const sourceOptions: Array<{ label: string; value: IntelManualSourceName }> = [
  { label: "CISA KEV", value: "cisa-kev" },
  { label: t("阿里云漏洞库"), value: "aliyun-avd" },
  { label: "WatchVuln", value: "watchvuln" }
];

const watchVulnScopeRows = [
  {
    source: t("阿里云漏洞库"),
    level: t("高危、严重"),
    rule: t("WatchVuln 有价值记录")
  },
  {
    source: t("长亭漏洞库"),
    level: t("高危、严重"),
    rule: t("中文漏洞通告")
  },
  {
    source: "OSCS",
    level: t("高危、严重"),
    rule: t("发布预警")
  },
  {
    source: t("奇安信威胁情报"),
    level: t("高危、严重"),
    rule: t("CERT 验证、POC/EXP 或技术细节公开")
  },
  {
    source: t("微步在线"),
    level: t("严重"),
    rule: t("近期披露，且有 POC 与漏洞分析")
  },
  {
    source: "Seebug",
    level: t("高危、严重"),
    rule: t("WatchVuln 有价值记录")
  },
  {
    source: t("Struts2 公告"),
    level: "Important、Critical",
    rule: t("官方安全公告")
  },
  {
    source: "CISA KEV",
    level: t("严重"),
    rule: t("已知在野利用")
  },
  {
    source: t("启明星辰"),
    level: t("高危、严重"),
    rule: t("WatchVuln 有价值记录")
  }
];

function statusColor(status?: string | null) {
  if (!status) {
    return "default";
  }
  if (["completed", "processed"].includes(status)) {
    return "green";
  }
  if (["failed", "rejected"].includes(status)) {
    return "red";
  }
  if (["queued", "pending", "running"].includes(status)) {
    return "blue";
  }
  if (status === "skipped") {
    return "orange";
  }
  return "default";
}

function intervalSecondsToHours(value: number) {
  return Number((Math.max(60, value) / 3600).toFixed(2));
}

function intervalHoursToSeconds(value: number) {
  return Math.max(60, Math.round(value * 3600));
}

function singleCollectLimitTooltip(sourceName: IntelManualSourceName) {
  if (sourceName === "cisa-kev") {
    return t("CISA KEV 手动采集默认仅采集本地最新 dateAdded 水位之后的新增漏洞；本地无水位时按此数量采集最新窗口。填 0 表示全量采集历史目录。");
  }
  return t("填 0 表示不限制数量，采集器会尽可能拉取当前来源可返回的记录。");
}

function qualityTags(record: IntelRawEvent) {
  if (!record.quality) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }
  const items = [
    ["CVE", record.quality.has_canonical_id],
    [t("产品"), record.quality.has_product],
    [t("版本"), record.quality.has_fixed_version],
    [t("严重度"), record.quality.has_severity],
    [t("利用信号"), record.quality.has_exploitation_signal]
  ] as const;
  return (
    <Space size={[4, 4]} wrap>
      {items.map(([label, ok]) => (
        <Tag key={label} color={ok ? "green" : "default"}>
          {label}
        </Tag>
      ))}
    </Space>
  );
}

interface MonitorStatusData {
  enabled: boolean;
  interval_seconds: number;
  limit: number | null;
  latest_only?: boolean;
  last_status: string | null;
  last_started_at: string | null;
  last_error: string | null;
  next_run_at: string | null;
}

interface MonitorSettingsPanelProps {
  hint?: ReactNode;
  data?: MonitorStatusData;
  isError: boolean;
  error: unknown;
  isFetching: boolean;
  isSaving: boolean;
  draft: MonitorDraft;
  minInterval: number;
  maxInterval: number;
  latestOnlyLabel?: string;
  latestOnlyHint?: ReactNode;
  onDraftChange: (updater: (current: MonitorDraft) => MonitorDraft) => void;
  onSave: () => void;
  onRefresh: () => void;
  actions?: ReactNode;
  extra?: ReactNode;
}

function MonitorSettingsPanel({
  hint,
  data,
  isError,
  error,
  isFetching,
  isSaving,
  draft,
  minInterval,
  maxInterval,
  latestOnlyLabel,
  latestOnlyHint,
  onDraftChange,
  onSave,
  onRefresh,
  actions,
  extra
}: MonitorSettingsPanelProps) {
  const minIntervalHours = intervalSecondsToHours(minInterval);
  const maxIntervalHours = intervalSecondsToHours(maxInterval);
  const settingsColMd = latestOnlyLabel ? 6 : 8;

  return (
    <Space className="page-stack" orientation="vertical" size={12}>
      {isError ? <ErrorState error={error} /> : null}
      <Row className="monitor-settings-row" gutter={[12, 12]} align="bottom">
        <Col xs={24} sm={12} md={settingsColMd}>
          <Space direction="vertical" size={4}>
            <Typography.Text type="secondary">{t("自动采集")}</Typography.Text>
            <Switch
              checked={draft.enabled}
              loading={isFetching}
              disabled={isSaving}
              onChange={(checked) =>
                onDraftChange((current) => ({
                  ...current,
                  enabled: checked
                }))
              }
            />
          </Space>
        </Col>
        {latestOnlyLabel ? (
          <Col xs={24} sm={12} md={settingsColMd}>
            <Space direction="vertical" size={4}>
              <Space className="monitor-field-label" size={4}>
                <Typography.Text type="secondary">{latestOnlyLabel}</Typography.Text>
                {latestOnlyHint ? (
                  <Tooltip title={latestOnlyHint}>
                    <CircleAlert size={14} />
                  </Tooltip>
                ) : null}
              </Space>
              <Switch
                checked={Boolean(draft.latest_only)}
                loading={isFetching}
                disabled={isSaving}
                onChange={(checked) =>
                  onDraftChange((current) => ({
                    ...current,
                    latest_only: checked
                  }))
                }
              />
            </Space>
          </Col>
        ) : null}
        <Col xs={24} sm={12} md={settingsColMd}>
          <Space className="page-stack" direction="vertical" size={4}>
            <Typography.Text type="secondary">{t("自动采集间隔")}</Typography.Text>
            <InputNumber
              min={minIntervalHours}
              max={maxIntervalHours}
              step={0.5}
              addonAfter={t("小时")}
              value={intervalSecondsToHours(draft.interval_seconds)}
              disabled={isSaving}
              style={{ width: "100%" }}
              onChange={(value) =>
                onDraftChange((current) => ({
                  ...current,
                  interval_seconds: intervalHoursToSeconds(
                    Number(value ?? minIntervalHours)
                  )
                }))
              }
            />
          </Space>
        </Col>
        <Col xs={24} sm={12} md={settingsColMd}>
          <Space className="page-stack" direction="vertical" size={4}>
            <Space className="monitor-field-label" size={4}>
              <Typography.Text type="secondary">{t("定时采集数量")}</Typography.Text>
              {hint ? (
                <Tooltip title={hint}>
                  <CircleAlert size={14} />
                </Tooltip>
              ) : null}
            </Space>
            <InputNumber
              min={1}
              max={5000}
              placeholder={t("不限制")}
              value={draft.limit ?? undefined}
              disabled={isSaving}
              style={{ width: "100%" }}
              onChange={(value) =>
                onDraftChange((current) => ({
                  ...current,
                  limit: value === null ? null : Number(value)
                }))
              }
            />
          </Space>
        </Col>
      </Row>
      <div className="monitor-summary-grid">
        <div className="monitor-summary-item">
          <Typography.Text type="secondary">{t("上次运行时间")}</Typography.Text>
          <Typography.Text>{formatDateTime(data?.last_started_at)}</Typography.Text>
        </div>
        <div className="monitor-summary-item">
          <Typography.Text type="secondary">{t("上次采集结果")}</Typography.Text>
          <Tag color={statusColor(data?.last_status)}>{data?.last_status ?? "-"}</Tag>
        </div>
        <div className="monitor-summary-item">
          <Typography.Text type="secondary">{t("下次预计运行时间")}</Typography.Text>
          <Typography.Text>{formatDateTime(data?.next_run_at)}</Typography.Text>
        </div>
      </div>
      {data?.last_error ? (
        <Alert type="warning" showIcon message={t("最近自动采集错误")} description={data.last_error} />
      ) : null}
      {extra}
      <div className="monitor-action-bar">
        <Space className="form-actions" size={8} wrap>
          {actions}
          <Button htmlType="button" onClick={onSave} loading={isSaving}>
            {t("保存定时设置")}</Button>
          <Button
            htmlType="button"
            icon={<RefreshCw size={16} />}
            onClick={onRefresh}
            loading={isFetching}
          >
            {t("刷新状态")}</Button>
        </Space>
      </div>
    </Space>
  );
}

export default function IntelCollectionPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<IntelCollectFormValues>();
  const selectedSource = Form.useWatch("source_name", form) ?? defaultValues.source_name;
  const [messageApi, contextHolder] = message.useMessage();
  const queryClient = useQueryClient();
  const [cisaMonitorDraft, setCisaMonitorDraft] =
    useState<MonitorDraft>(defaultCisaMonitorDraft);
  const [watchVulnMonitorDraft, setWatchVulnMonitorDraft] =
    useState<MonitorDraft>(defaultWatchVulnMonitorDraft);

  const sourcesQuery = useQuery({
    queryKey: ["intel", "sources"],
    queryFn: getIntelSources
  });

  const cisaMonitorQuery = useQuery({
    queryKey: ["intel", "cisa-kev", "monitor"],
    queryFn: getCisaKevMonitorConfig
  });

  const watchVulnMonitorQuery = useQuery({
    queryKey: ["intel", "watchvuln", "monitor"],
    queryFn: getWatchVulnMonitorConfig
  });

  useEffect(() => {
    if (!cisaMonitorQuery.data) {
      return;
    }
    setCisaMonitorDraft({
      enabled: cisaMonitorQuery.data.enabled,
      interval_seconds: cisaMonitorQuery.data.interval_seconds,
      limit: cisaMonitorQuery.data.limit,
      latest_only: cisaMonitorQuery.data.latest_only
    });
  }, [cisaMonitorQuery.data]);

  useEffect(() => {
    if (!watchVulnMonitorQuery.data) {
      return;
    }
    setWatchVulnMonitorDraft({
      enabled: watchVulnMonitorQuery.data.enabled,
      interval_seconds: watchVulnMonitorQuery.data.interval_seconds,
      limit: watchVulnMonitorQuery.data.limit
    });
  }, [watchVulnMonitorQuery.data]);

  const runsQuery = useQuery({
    queryKey: ["intel", "runs"],
    queryFn: getIntelRuns
  });

  const rawEventsQuery = useQuery({
    queryKey: ["intel", "raw-events"],
    queryFn: getIntelRawEvents
  });

  const collectMutation = useMutation({
    mutationFn: (values: IntelCollectFormValues) => {
      const sourceName = values.source_name ?? defaultValues.source_name;
      return collectIntelSource(sourceName, {
        limit: sourceName === "watchvuln" ? null : values.limit ?? null,
        min_score: sourceName === "aliyun-avd" ? values.min_score ?? null : null,
        async_mode: false,
        latest_only: sourceName === "cisa-kev" && values.limit !== 0
      });
    },
    onSuccess: (result) => {
      if (result.status === "failed") {
        messageApi.error(result.error_message ?? result.message ?? t("情报采集失败"));
      } else {
        messageApi.success(result.message ?? t("情报采集请求已完成"));
      }
      void queryClient.invalidateQueries({ queryKey: ["vulnerabilities"] });
      void queryClient.invalidateQueries({ queryKey: ["intel"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("情报采集失败"));
    }
  });

  const cisaMonitorMutation = useMutation({
    mutationFn: (values: CisaKevMonitorConfigUpdate) =>
      updateCisaKevMonitorConfig(values),
    onSuccess: (result) => {
      messageApi.success(t("CISA KEV 定时采集设置已更新"));
      setCisaMonitorDraft({
        enabled: result.enabled,
        interval_seconds: result.interval_seconds,
        limit: result.limit,
        latest_only: result.latest_only
      });
      queryClient.setQueryData(["intel", "cisa-kev", "monitor"], result);
      void queryClient.invalidateQueries({ queryKey: ["intel", "sources"] });
      void queryClient.invalidateQueries({ queryKey: ["intel", "runs"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("定时采集设置更新失败"));
    }
  });

  const watchVulnMonitorMutation = useMutation({
    mutationFn: (values: WatchVulnMonitorConfigUpdate) =>
      updateWatchVulnMonitorConfig(values),
    onSuccess: (result) => {
      messageApi.success(t("WatchVuln 自动监测设置已更新"));
      setWatchVulnMonitorDraft({
        enabled: result.enabled,
        interval_seconds: result.interval_seconds,
        limit: result.limit
      });
      queryClient.setQueryData(["intel", "watchvuln", "monitor"], result);
      void queryClient.invalidateQueries({ queryKey: ["intel", "sources"] });
      void queryClient.invalidateQueries({ queryKey: ["intel", "runs"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("自动监测设置更新失败"));
    }
  });

  const normalizeMutation = useMutation({
    mutationFn: normalizeIntelRawEvent,
    onSuccess: (result) => {
      messageApi.success(t("归一化完成：{{v0}}", { v0: result.status }));
      void queryClient.invalidateQueries({ queryKey: ["intel"] });
      void queryClient.invalidateQueries({ queryKey: ["vulnerabilities"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("归一化重试失败"));
    }
  });

  const clearSourceMutation = useMutation({
    mutationFn: clearIntelSourceVulnerabilities,
    onSuccess: (result: IntelSourceVulnerabilityCleanupResult) => {
      messageApi.success(
        t("已清除 {{v0}}：删除 {{v1}} 条漏洞，保留 {{v2}} 条共享漏洞。", { v0: result.source_label ?? result.source_name, v1: result.vulnerabilities_deleted, v2: result.shared_vulnerabilities_retained })
      );
      void queryClient.invalidateQueries({ queryKey: ["intel"] });
      void queryClient.invalidateQueries({ queryKey: ["vulnerabilities"] });
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
      void queryClient.invalidateQueries({ queryKey: ["verification"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("清除采集漏洞失败"));
    }
  });

  function confirmClearSource(record: IntelSourceStatus) {
    const sourceLabel = record.source_label ?? record.source_name;
    Modal.confirm({
      title: t("确认清除“{{v0}}”采集的漏洞？", { v0: sourceLabel }),
      content: (
        <Space direction="vertical" size={4}>
          <Typography.Text>
            {t("将删除该引擎的来源链接、原始情报和采集记录。")}</Typography.Text>
          <Typography.Text type="danger">
            {t("最多")}{record.vulnerability_count} {t("条没有其他来源的漏洞及其匹配、验证、AI 补全信息也会被删除，操作不可恢复。")}</Typography.Text>
          <Typography.Text type="secondary">
            {t("有其他来源的同一漏洞会被保留。")}</Typography.Text>
        </Space>
      ),
      okText: t("确认清除"),
      okButtonProps: { danger: true },
      cancelText: t("取消"),
      onOk: () =>
        new Promise<void>((resolve, reject) => {
          clearSourceMutation.mutate(record.source_name, {
            onSuccess: () => resolve(),
            onError: reject
          });
        })
    });
  }

  const collectActions = (
    <>
      <Button
        icon={<RefreshCw size={16} />}
        onClick={() => {
          form.setFieldsValue(defaultValues);
        }}
        disabled={collectMutation.isPending}
      >
        {t("重置")}</Button>
      <Button
        type="primary"
        htmlType="submit"
        icon={<DownloadCloud size={16} />}
        loading={collectMutation.isPending}
      >
        {t("单次采集")}</Button>
    </>
  );

  const sourceColumns: ColumnsType<IntelSourceStatus> = [
    {
      title: t("来源"),
      dataIndex: "source_name",
      width: 190,
      render: (value: string, record) => (
        <Typography.Text strong>{record.source_label ?? value}</Typography.Text>
      )
    },
    {
      title: t("最近状态"),
      dataIndex: "last_status",
      width: 120,
      render: (value: string | null) => <Tag color={statusColor(value)}>{value ?? "-"}</Tag>
    },
    {
      title: t("最近采集"),
      dataIndex: "last_started_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    { title: t("原始事件"), dataIndex: "raw_event_count", width: 100 },
    { title: t("已处理"), dataIndex: "processed_event_count", width: 100 },
    { title: t("失败"), dataIndex: "failed_event_count", width: 90 },
    { title: t("漏洞数"), dataIndex: "vulnerability_count", width: 100 },
    {
      title: t("最近错误"),
      dataIndex: "last_error",
      render: (value: string | null) => value || "-"
    },
    {
      title: t("操作"),
      key: "actions",
      fixed: "right",
      width: 140,
      render: (_, record) => (
        <Button
          className="table-action-button"
          danger
          type="link"
          icon={<Trash2 size={15} />}
          onClick={() => confirmClearSource(record)}
          loading={clearSourceMutation.isPending}
        >
          {t("清除漏洞")}</Button>
      )
    }
  ];

  const runColumns: ColumnsType<IntelCollectionRun> = [
    {
      title: t("来源"),
      dataIndex: "source_name",
      width: 120
    },
    {
      title: t("触发"),
      dataIndex: "trigger_type",
      width: 100
    },
    {
      title: t("状态"),
      dataIndex: "status",
      width: 110,
      render: (value: string) => <Tag color={statusColor(value)}>{value}</Tag>
    },
    {
      title: t("开始时间"),
      dataIndex: "started_at",
      width: 190,
      render: (value: string) => formatDateTime(value)
    },
    { title: t("获取"), dataIndex: "fetched_count", width: 80 },
    { title: t("入库"), dataIndex: "stored_count", width: 80 },
    { title: t("处理"), dataIndex: "processed_count", width: 80 },
    { title: t("跳过"), dataIndex: "skipped_count", width: 80 },
    { title: t("失败"), dataIndex: "failed_count", width: 80 },
    {
      title: t("错误"),
      dataIndex: "error_message",
      render: (value: string | null) => value || "-"
    }
  ];

  const rawEventColumns: ColumnsType<IntelRawEvent> = [
    {
      title: t("来源"),
      dataIndex: "provider",
      width: 120
    },
    {
      title: t("状态"),
      dataIndex: "processing_status",
      width: 110,
      render: (value: string) => <Tag color={statusColor(value)}>{value}</Tag>
    },
    {
      title: t("外部键"),
      dataIndex: "external_key",
      minWidth: 180,
      render: (value: string) => <Typography.Text copyable>{value}</Typography.Text>
    },
    {
      title: t("漏洞"),
      dataIndex: "vulnerability_canonical_id",
      width: 160,
      render: (value: string | null) =>
        value ? (
          <Typography.Link onClick={() => navigate(`/vulnerabilities/${value}`)}>
            {value}
          </Typography.Link>
        ) : (
          "-"
        )
    },
    {
      title: t("质量"),
      key: "quality",
      width: 280,
      render: (_, record) => qualityTags(record)
    },
    {
      title: t("接收时间"),
      dataIndex: "received_at",
      width: 190,
      render: (value: string) => formatDateTime(value)
    },
    {
      title: t("错误"),
      dataIndex: "last_error",
      render: (value: string | null) => value || "-"
    },
    {
      title: t("操作"),
      key: "actions",
      fixed: "right",
      width: 120,
      render: (_, record) => (
        <Button
          className="table-action-button"
          type="link"
          icon={<RotateCcw size={15} />}
          onClick={() => normalizeMutation.mutate(record.id)}
          loading={normalizeMutation.isPending}
        >
          {t("重跑")}</Button>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader title={t("情报采集")} />

      <Card className="content-card" title={t("情报采集")}>
        <Form
          form={form}
          layout="vertical"
          initialValues={defaultValues}
          onFinish={(values) => collectMutation.mutate(values)}
        >
          <Row gutter={[16, 12]} align="bottom">
            <Col xs={24} md={8} xl={6}>
              <Form.Item label={t("情报来源")} name="source_name">
                <Select options={sourceOptions} />
              </Form.Item>
            </Col>
            {selectedSource !== "watchvuln" ? (
              <Col xs={24} sm={12} md={8} xl={5}>
                <Form.Item
                  label={t("单次采集数量")}
                  name="limit"
                  tooltip={singleCollectLimitTooltip(selectedSource)}
                  rules={[
                    {
                      type: "number",
                      min: 0,
                      max: 5000,
                      message: t("单次采集数量必须在 0 到 5000 之间")
                    }
                  ]}
                >
                  <InputNumber min={0} max={5000} style={{ width: "100%" }} />
                </Form.Item>
              </Col>
            ) : null}
            {selectedSource === "aliyun-avd" ? (
              <Col xs={24} sm={12} md={8} xl={5}>
                <Form.Item
                  label={t("最低评分")}
                  name="min_score"
                  rules={[
                    {
                      type: "number",
                      min: 0,
                      max: 10,
                      message: t("评分必须在 0 到 10 之间")
                    }
                  ]}
                >
                  <InputNumber min={0} max={10} step={0.1} style={{ width: "100%" }} />
                </Form.Item>
              </Col>
            ) : null}
          </Row>
          {selectedSource === "cisa-kev" ? (
            <MonitorSettingsPanel
              hint={t("CISA KEV 定时采集默认全量拉取 CISA KEV 官方目录，并按 CVE 与已有漏洞库比对；已存在条目会更新同一来源记录，新条目会补入。")}
              data={cisaMonitorQuery.data}
              isError={cisaMonitorQuery.isError}
              error={cisaMonitorQuery.error}
              isFetching={cisaMonitorQuery.isFetching}
              isSaving={cisaMonitorMutation.isPending}
              draft={cisaMonitorDraft}
              minInterval={300}
              maxInterval={604800}
              latestOnlyLabel={t("仅采集新增漏洞")}
              latestOnlyHint={t("打开后定时任务按本地 CISA KEV 最新 dateAdded 水位采集新增条目；首次无水位时只采集当前数量窗口。")}
              onDraftChange={setCisaMonitorDraft}
              actions={collectActions}
              onSave={() =>
                cisaMonitorMutation.mutate({
                  enabled: cisaMonitorDraft.enabled,
                  interval_seconds: cisaMonitorDraft.interval_seconds,
                  limit: cisaMonitorDraft.limit ?? null,
                  latest_only: Boolean(cisaMonitorDraft.latest_only)
                })
              }
              onRefresh={() => void cisaMonitorQuery.refetch()}
            />
          ) : null}
          {selectedSource === "watchvuln" ? (
            <MonitorSettingsPanel
              hint={t("WatchVuln 当前只接入各子源的新漏洞告警与高价值记录，不作为历史漏洞全量拉取入口。")}
              data={watchVulnMonitorQuery.data}
              isError={watchVulnMonitorQuery.isError}
              error={watchVulnMonitorQuery.error}
              isFetching={watchVulnMonitorQuery.isFetching}
              isSaving={watchVulnMonitorMutation.isPending}
              draft={watchVulnMonitorDraft}
              minInterval={60}
              maxInterval={86400}
              onDraftChange={setWatchVulnMonitorDraft}
              actions={collectActions}
              onSave={() =>
                watchVulnMonitorMutation.mutate({
                  enabled: watchVulnMonitorDraft.enabled,
                  interval_seconds: watchVulnMonitorDraft.interval_seconds,
                  limit: watchVulnMonitorDraft.limit ?? null
                })
              }
              onRefresh={() => void watchVulnMonitorQuery.refetch()}
              extra={
                <Table
                  rowKey="source"
                  size="small"
                  columns={[
                    {
                      title: t("子源"),
                      dataIndex: "source",
                      width: 130
                    },
                    {
                      title: t("告警级别"),
                      dataIndex: "level",
                      width: 120
                    },
                    {
                      title: t("进入条件"),
                      dataIndex: "rule"
                    }
                  ]}
                  dataSource={watchVulnScopeRows}
                  pagination={false}
                  scroll={{ x: 520 }}
                />
              }
            />
          ) : null}
          {selectedSource === "aliyun-avd" ? (
            <div className="intel-collect-action-bar">
              <Space className="form-actions" size={8} wrap>
                {collectActions}
              </Space>
            </div>
          ) : null}
        </Form>
      </Card>

      <Card className="content-card" title={t("情报来源状态")}>
        {sourcesQuery.isError ? <ErrorState error={sourcesQuery.error} /> : null}
        <ResizableTable<IntelSourceStatus>
          storageKey="intel-sources"
          rowKey="source_name"
          columns={sourceColumns}
          dataSource={sourcesQuery.data ?? []}
          loading={sourcesQuery.isFetching}
          pagination={false}
          scroll={{ x: 1180 }}
        />
      </Card>

      <Card className="content-card" title={t("采集历史")}>
        {runsQuery.isError ? <ErrorState error={runsQuery.error} /> : null}
        <ResizableTable<IntelCollectionRun>
          storageKey="intel-runs"
          rowKey="id"
          columns={runColumns}
          dataSource={runsQuery.data ?? []}
          loading={runsQuery.isFetching}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1120 }}
        />
      </Card>

      <Card className="content-card" title={t("原始情报事件")}>
        {rawEventsQuery.isError ? <ErrorState error={rawEventsQuery.error} /> : null}
        <ResizableTable<IntelRawEvent>
          storageKey="intel-raw-events"
          rowKey="id"
          columns={rawEventColumns}
          dataSource={rawEventsQuery.data ?? []}
          loading={rawEventsQuery.isFetching}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1380 }}
        />
      </Card>
    </Space>
  );
}

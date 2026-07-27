import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Tag,
  Typography,
  message
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  DownloadCloud,
  Eye,
  ListChecks,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  SearchCheck,
  ShieldAlert
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";

import type { IntelManualSourceName } from "@/api/intel";
import { collectIntelSource } from "@/api/intel";
import { createVerificationTask, reevaluateMatchResult } from "@/api/matchResults";
import { getTaskCenterItems, getTaskCenterSummary } from "@/api/taskCenter";
import type {
  RiskPriority,
  TaskCenterItem,
  TaskCenterItemsQuery,
  TaskCenterItemType,
  TaskCenterStatusGroup
} from "@/api/types";
import {
  cancelVerificationTask,
  retryVerificationTask
} from "@/api/verification";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import RiskPriorityTag from "@/components/RiskPriorityTag";
import { formatDateTime, formatScore } from "@/utils/format";

const defaultFilters: TaskCenterItemsQuery = {
  limit: 100
};

const itemTypeOptions: Array<{ label: string; value: TaskCenterItemType }> = [
  { label: "验证任务", value: "verification" },
  { label: "情报采集", value: "intel_collection" },
  { label: "风险待处理项", value: "risk_queue_item" },
  { label: "AI 补全", value: "ai_enrichment" }
];

const statusGroupOptions: Array<{ label: string; value: TaskCenterStatusGroup }> = [
  { label: "待处理", value: "pending" },
  { label: "运行中", value: "running" },
  { label: "已完成", value: "success" },
  { label: "失败", value: "failed" },
  { label: "已取消", value: "cancelled" },
  { label: "需关注", value: "attention" }
];

const sourceOptions = [
  { label: "验证任务", value: "verification" },
  { label: "风险队列", value: "risk-queue" },
  { label: "AI 补全", value: "ai-enrichment" },
  { label: "CISA KEV", value: "cisa-kev" },
  { label: "阿里云漏洞库", value: "aliyun-avd" },
  { label: "WatchVuln", value: "watchvuln" }
];

const triggerOptions = [
  { label: "手动", value: "manual" },
  { label: "定时", value: "scheduled" },
  { label: "Webhook", value: "webhook" },
  { label: "系统", value: "system" }
];

const manualIntelSources: IntelManualSourceName[] = [
  "cisa-kev",
  "aliyun-avd",
  "watchvuln"
];

function normalizeFilters(values: TaskCenterItemsQuery): TaskCenterItemsQuery {
  return {
    ...(values.item_type ? { item_type: values.item_type } : {}),
    ...(values.status_group ? { status_group: values.status_group } : {}),
    ...(values.status?.trim() ? { status: values.status.trim() } : {}),
    ...(values.source ? { source: values.source } : {}),
    ...(values.trigger_type ? { trigger_type: values.trigger_type } : {}),
    ...(values.keyword?.trim() ? { keyword: values.keyword.trim() } : {}),
    limit: values.limit ?? 100
  };
}

function itemTypeLabel(value: TaskCenterItemType) {
  const labels: Record<TaskCenterItemType, string> = {
    verification: "验证任务",
    intel_collection: "情报采集",
    risk_queue_item: "风险项",
    ai_enrichment: "AI 补全"
  };
  return labels[value];
}

function statusGroupColor(value: TaskCenterStatusGroup) {
  const colors: Record<TaskCenterStatusGroup, string> = {
    pending: "cyan",
    running: "blue",
    success: "green",
    failed: "red",
    cancelled: "default",
    attention: "orange"
  };
  return colors[value];
}

function statusGroupLabel(value: TaskCenterStatusGroup) {
  const labels: Record<TaskCenterStatusGroup, string> = {
    pending: "待处理",
    running: "运行中",
    success: "已完成",
    failed: "失败",
    cancelled: "已取消",
    attention: "需关注"
  };
  return labels[value];
}

function canCollectSource(source?: string | null): source is IntelManualSourceName {
  return manualIntelSources.includes(source as IntelManualSourceName);
}

function riskPriorityValue(value?: string | null): RiskPriority {
  if (["critical", "high", "medium", "low", "none"].includes(value ?? "")) {
    return value as RiskPriority;
  }
  return "none";
}

function metricValue(item: TaskCenterItem, key: string) {
  return item.metrics[key] ?? 0;
}

export default function TaskCenterPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<TaskCenterItemsQuery>();
  const [filters, setFilters] = useState<TaskCenterItemsQuery>(defaultFilters);
  const [messageApi, contextHolder] = message.useMessage();
  const queryClient = useQueryClient();

  const summaryQuery = useQuery({
    queryKey: ["task-center", "summary"],
    queryFn: getTaskCenterSummary
  });

  const itemsQuery = useQuery({
    queryKey: ["task-center", "items", filters],
    queryFn: () => getTaskCenterItems(filters)
  });

  function invalidateTaskData() {
    void queryClient.invalidateQueries({ queryKey: ["task-center"] });
    void queryClient.invalidateQueries({ queryKey: ["verification-tasks"] });
    void queryClient.invalidateQueries({ queryKey: ["match-results"] });
    void queryClient.invalidateQueries({ queryKey: ["intel"] });
  }

  const cancelMutation = useMutation({
    mutationFn: (taskId: string) => cancelVerificationTask(taskId),
    onSuccess: () => {
      messageApi.success("验证任务已更新");
      invalidateTaskData();
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "取消任务失败");
    }
  });

  const retryMutation = useMutation({
    mutationFn: (taskId: string) => retryVerificationTask(taskId),
    onSuccess: (task) => {
      messageApi.success("重试任务已创建");
      invalidateTaskData();
      navigate(`/verification-tasks/${task.id}`);
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "重试任务失败");
    }
  });

  const collectMutation = useMutation({
    mutationFn: (sourceName: IntelManualSourceName) =>
      collectIntelSource(sourceName, {
        async_mode: true,
        limit: sourceName === "watchvuln" ? null : 100,
        min_score: sourceName === "aliyun-avd" ? 7 : null
      }),
    onSuccess: (result) => {
      messageApi.success(result.message ?? "情报采集任务已提交");
      invalidateTaskData();
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "情报采集失败");
    }
  });

  const createVerificationMutation = useMutation({
    mutationFn: (matchResultId: string) =>
      createVerificationTask(matchResultId, {
        task_type: "package_version_check",
        parameters: {},
        requested_by: null
      }),
    onSuccess: (task) => {
      messageApi.success("验证任务已创建");
      invalidateTaskData();
      navigate(`/verification-tasks/${task.id}`);
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "验证任务创建失败");
    }
  });

  const reevaluateMutation = useMutation({
    mutationFn: (matchResultId: string) => reevaluateMatchResult(matchResultId),
    onSuccess: () => {
      messageApi.success("匹配结果已重评估");
      invalidateTaskData();
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "重评估失败");
    }
  });

  const summary = summaryQuery.data;
  const rows = itemsQuery.data ?? [];
  const localMetrics = useMemo(
    () => ({
      total: rows.length,
      pending: rows.filter((item) => item.status_group === "pending").length,
      running: rows.filter((item) => item.status_group === "running").length,
      failed: rows.filter((item) => item.status_group === "failed").length,
      attention: rows.filter((item) => item.status_group === "attention").length
    }),
    [rows]
  );

  const columns: ColumnsType<TaskCenterItem> = [
    {
      title: "类型",
      dataIndex: "item_type",
      width: 120,
      render: (value: TaskCenterItemType) => <Tag>{itemTypeLabel(value)}</Tag>
    },
    {
      title: "任务",
      dataIndex: "title",
      minWidth: 280,
      render: (_: string, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(record.detail_path)}>
            {record.title}
          </Typography.Link>
          <Typography.Text className="table-subtitle" copyable>
            {record.raw_id}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "状态",
      key: "status",
      width: 150,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Tag color={statusGroupColor(record.status_group)}>
            {statusGroupLabel(record.status_group)}
          </Tag>
          <Typography.Text className="table-subtitle">{record.status}</Typography.Text>
        </Space>
      )
    },
    {
      title: "来源/触发",
      key: "source",
      width: 160,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{record.source ?? "-"}</Typography.Text>
          <Typography.Text className="table-subtitle">
            {record.trigger_type ?? "-"}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "资产",
      key: "asset",
      width: 210,
      render: (_, record) =>
        record.asset_id ? (
          <Space orientation="vertical" size={0}>
            <Typography.Link onClick={() => navigate(`/assets/${record.asset_id}`)}>
              {record.asset_name ?? record.asset_id}
            </Typography.Link>
            <Typography.Text className="table-subtitle">
              {record.agent_id ?? "-"}
            </Typography.Text>
          </Space>
        ) : (
          "-"
        )
    },
    {
      title: "漏洞",
      key: "vulnerability",
      minWidth: 240,
      render: (_, record) =>
        record.vulnerability_id ? (
          <Space orientation="vertical" size={0}>
            <Typography.Link
              onClick={() => navigate(`/vulnerabilities/${record.vulnerability_id}`)}
            >
              {record.vulnerability_id}
            </Typography.Link>
            <Typography.Text className="table-subtitle" ellipsis>
              {record.vulnerability_title ?? "-"}
            </Typography.Text>
          </Space>
        ) : (
          "-"
        )
    },
    {
      title: "风险",
      key: "risk",
      width: 140,
      render: (_, record) =>
        record.risk_priority ? (
          <Space orientation="vertical" size={0}>
            <RiskPriorityTag value={riskPriorityValue(record.risk_priority)} />
            <Typography.Text className="table-subtitle">
              {record.risk_score === null ? "-" : formatScore(record.risk_score)}
            </Typography.Text>
          </Space>
        ) : (
          "-"
        )
    },
    {
      title: "计数",
      key: "metrics",
      width: 170,
      render: (_, record) => {
        if (record.item_type === "verification") {
          return `${metricValue(record, "evidence_count")} 证据 / ${metricValue(
            record,
            "retry_count"
          )} 重试`;
        }
        if (record.item_type === "intel_collection") {
          return `${metricValue(record, "processed_count")} 处理 / ${metricValue(
            record,
            "failed_count"
          )} 失败`;
        }
        if (record.item_type === "ai_enrichment") {
          return `${metricValue(record, "processed_count")} 处理 / ${metricValue(
            record,
            "pending_review_count"
          )} 待审 / ${metricValue(record, "failed_count")} 失败`;
        }
        return `${metricValue(record, "verification_task_count")} 验证 / ${metricValue(
          record,
          "verification_evidence_count"
        )} 证据`;
      }
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      width: 190,
      render: (value: string) => formatDateTime(value)
    },
    {
      title: "错误",
      dataIndex: "error_message",
      minWidth: 220,
      render: (value: string | null) => (
        <Typography.Text className="table-subtitle" ellipsis>
          {value ?? "-"}
        </Typography.Text>
      )
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 300,
      render: (_, record) => (
        <Space className="table-actions" size={2} wrap>
          <Button
            type="link"
            icon={<Eye size={15} />}
            onClick={() => navigate(record.detail_path)}
          >
            详情
          </Button>
          {record.item_type === "verification" ? (
            <>
              <Popconfirm
                title="取消验证任务"
                onConfirm={() => cancelMutation.mutate(record.raw_id)}
                disabled={!record.available_actions.includes("cancel")}
              >
                <Button
                  type="link"
                  danger
                  icon={<Ban size={15} />}
                  disabled={!record.available_actions.includes("cancel")}
                  loading={cancelMutation.isPending}
                >
                  取消
                </Button>
              </Popconfirm>
              <Button
                type="link"
                icon={<RotateCcw size={15} />}
                disabled={!record.available_actions.includes("retry")}
                loading={retryMutation.isPending}
                onClick={() => retryMutation.mutate(record.raw_id)}
              >
                重试
              </Button>
            </>
          ) : null}
          {record.item_type === "risk_queue_item" ? (
            <>
              <Button
                type="link"
                icon={<PlayCircle size={15} />}
                loading={createVerificationMutation.isPending}
                onClick={() => createVerificationMutation.mutate(record.raw_id)}
              >
                验证
              </Button>
              <Button
                type="link"
                icon={<SearchCheck size={15} />}
                loading={reevaluateMutation.isPending}
                onClick={() => reevaluateMutation.mutate(record.raw_id)}
              >
                重评估
              </Button>
            </>
          ) : null}
          {record.item_type === "intel_collection" && canCollectSource(record.source) ? (
            <Button
              type="link"
              icon={<DownloadCloud size={15} />}
              loading={collectMutation.isPending}
              onClick={() => {
                if (canCollectSource(record.source)) {
                  collectMutation.mutate(record.source);
                }
              }}
            >
              重采集
            </Button>
          ) : null}
        </Space>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title="任务中心"
        extra={
          <Space wrap>
            <Button
              icon={<DownloadCloud size={16} />}
              onClick={() => collectMutation.mutate("watchvuln")}
              loading={collectMutation.isPending}
            >
              采集 WatchVuln
            </Button>
            <Button
              icon={<RefreshCw size={16} />}
              onClick={() => {
                void summaryQuery.refetch();
                void itemsQuery.refetch();
              }}
              loading={summaryQuery.isFetching || itemsQuery.isFetching}
            >
              刷新
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={6}>
          <Card className="metric-card">
            <Statistic
              title="任务条目"
              value={summary?.total ?? localMetrics.total}
              prefix={<ListChecks size={28} />}
            />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card">
            <Statistic
              title="待处理"
              value={summary?.pending ?? localMetrics.pending}
              prefix={<PlayCircle size={28} />}
            />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-green">
            <Statistic
              title="运行中"
              value={summary?.running ?? localMetrics.running}
              prefix={<RefreshCw size={28} />}
            />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-red">
            <Statistic
              title="失败/需关注"
              value={(summary?.failed ?? localMetrics.failed) + (summary?.attention ?? localMetrics.attention)}
              prefix={<ShieldAlert size={28} />}
            />
          </Card>
        </Col>
      </Row>

      <Card className="content-card filter-card">
        <Form
          form={form}
          layout="inline"
          initialValues={defaultFilters}
          onFinish={(values) => setFilters(normalizeFilters(values))}
        >
          <Form.Item label="类型" name="item_type">
            <Select allowClear options={itemTypeOptions} placeholder="全部类型" />
          </Form.Item>
          <Form.Item label="状态组" name="status_group">
            <Select allowClear options={statusGroupOptions} placeholder="全部状态组" />
          </Form.Item>
          <Form.Item label="原始状态" name="status">
            <Input placeholder="queued / affected" />
          </Form.Item>
          <Form.Item label="来源" name="source">
            <Select allowClear options={sourceOptions} placeholder="全部来源" />
          </Form.Item>
          <Form.Item label="触发" name="trigger_type">
            <Select allowClear options={triggerOptions} placeholder="全部触发" />
          </Form.Item>
          <Form.Item label="关键字" name="keyword">
            <Input placeholder="任务、资产、漏洞、Agent" />
          </Form.Item>
          <Form.Item label="返回数量" name="limit">
            <InputNumber min={1} max={500} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button
                onClick={() => {
                  form.resetFields();
                  setFilters(defaultFilters);
                }}
              >
                重置
              </Button>
              <Button type="primary" htmlType="submit">
                查询
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Card className="content-card" title="任务条目">
        {summaryQuery.isError ? <ErrorState title="任务统计加载失败" error={summaryQuery.error} /> : null}
        {itemsQuery.isError ? <ErrorState error={itemsQuery.error} /> : null}
        <ResizableTable<TaskCenterItem>
          storageKey="task-center-items"
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={
            itemsQuery.isFetching ||
            cancelMutation.isPending ||
            retryMutation.isPending ||
            createVerificationMutation.isPending ||
            reevaluateMutation.isPending
          }
          pagination={{ pageSize: 10, showSizeChanger: true }}
          locale={{
            emptyText: (
              <EmptyState title="暂无任务条目">
                <Button type="primary" onClick={() => navigate("/risk-queue")}>
                  去风险队列
                </Button>
              </EmptyState>
            )
          }}
          scroll={{ x: 2180 }}
        />
      </Card>
    </Space>
  );
}

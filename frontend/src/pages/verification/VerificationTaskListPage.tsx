import { t } from "@/app/i18n";
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  Pagination,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Typography,
  message
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  Eye,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import {
  cancelVerificationTask,
  getVerificationTasks,
  retryVerificationTask
} from "@/api/verification";
import type { VerificationTasksQuery, VerificationTaskSummary } from "@/api/types";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import { VerificationTaskStatusTag } from "@/components/ValueTags";
import { formatDateTime } from "@/utils/format";

const defaultFilters: VerificationTasksQuery = {};

const DEFAULT_PAGE_SIZE = 10;

const statusOptions = [
  { label: t("排队中"), value: "queued" },
  { label: t("执行中"), value: "in_progress" },
  { label: t("请求取消"), value: "cancel_requested" },
  { label: t("已取消"), value: "cancelled" },
  { label: t("已完成"), value: "completed" },
  { label: t("失败"), value: "failed" },
  { label: t("已拒绝"), value: "rejected" }
];

const taskTypeOptions = [{ label: "package_version_check", value: "package_version_check" }];

function normalizeFilters(values: VerificationTasksQuery): VerificationTasksQuery {
  return {
    ...(values.status ? { status: values.status } : {}),
    ...(values.task_type ? { task_type: values.task_type.trim() } : {}),
    ...(values.agent_id ? { agent_id: values.agent_id.trim() } : {}),
    ...(values.asset_id ? { asset_id: values.asset_id.trim() } : {}),
    ...(values.vulnerability_id ? { vulnerability_id: values.vulnerability_id.trim() } : {}),
    ...(values.match_result_id ? { match_result_id: values.match_result_id.trim() } : {})
  };
}

function canCancel(task: VerificationTaskSummary) {
  return task.status === "queued" || task.status === "in_progress";
}

function canRetry(task: VerificationTaskSummary) {
  return ["failed", "rejected", "cancelled"].includes(task.status);
}

export default function VerificationTaskListPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<VerificationTasksQuery>();
  const [filters, setFilters] = useState<VerificationTasksQuery>(defaultFilters);
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [messageApi, contextHolder] = message.useMessage();
  const queryClient = useQueryClient();

  const tasksQuery = useQuery({
    queryKey: ["verification-tasks", "list", filters, currentPage, pageSize],
    queryFn: () =>
      getVerificationTasks({
        ...filters,
        offset: (currentPage - 1) * pageSize,
        limit: pageSize
      })
  });

  const cancelMutation = useMutation({
    mutationFn: (taskId: string) => cancelVerificationTask(taskId),
    onSuccess: () => {
      messageApi.success(t("验证任务已更新"));
      void queryClient.invalidateQueries({ queryKey: ["verification-tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("取消任务失败"));
    }
  });

  const retryMutation = useMutation({
    mutationFn: (taskId: string) => retryVerificationTask(taskId),
    onSuccess: (task) => {
      messageApi.success(t("重试任务已创建"));
      void queryClient.invalidateQueries({ queryKey: ["verification-tasks"] });
      navigate(`/verification-tasks/${task.id}`);
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("重试任务失败"));
    }
  });

  useEffect(() => {
    setCurrentPage(1);
  }, [filters]);

  const tasksPage = tasksQuery.data;
  const rows = tasksPage?.items ?? [];
  const total = tasksPage?.total ?? rows.length;
  const metrics = {
    total: tasksPage?.total ?? rows.length,
    active:
      tasksPage?.active_count ??
      rows.filter((task) => ["queued", "in_progress"].includes(task.status)).length,
    failed:
      tasksPage?.failed_count ??
      rows.filter((task) => ["failed", "rejected"].includes(task.status)).length,
    evidence:
      tasksPage?.evidence_count ??
      rows.reduce((sum, task) => sum + task.evidence_count, 0)
  };

  const columns: ColumnsType<VerificationTaskSummary> = [
    {
      title: t("任务"),
      dataIndex: "id",
      minWidth: 270,
      render: (_: string, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(`/verification-tasks/${record.id}`)}>
            {record.id}
          </Typography.Link>
          <Typography.Text className="table-subtitle">{record.task_type}</Typography.Text>
        </Space>
      )
    },
    {
      title: t("状态"),
      dataIndex: "status",
      width: 120,
      render: (value: string) => <VerificationTaskStatusTag value={value} />
    },
    {
      title: t("漏洞"),
      key: "vulnerability",
      minWidth: 260,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link
            onClick={() =>
              record.vulnerability_canonical_id
                ? navigate(`/vulnerabilities/${record.vulnerability_canonical_id}`)
                : undefined
            }
          >
            {record.vulnerability_canonical_id ?? "-"}
          </Typography.Link>
          <Typography.Text className="table-subtitle" ellipsis>
            {record.vulnerability_title ?? "-"}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("资产"),
      key: "asset",
      width: 180,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(`/assets/${record.asset_id}`)}>
            {record.asset_hostname ?? record.asset_id}
          </Typography.Link>
          <Typography.Text className="table-subtitle">
            {record.asset_agent_id ?? "-"}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("证据"),
      dataIndex: "evidence_count",
      width: 90
    },
    {
      title: t("创建时间"),
      dataIndex: "created_at",
      width: 190,
      render: (value: string) => formatDateTime(value)
    },
    {
      title: t("完成时间"),
      dataIndex: "completed_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    {
      title: t("错误"),
      key: "error",
      minWidth: 240,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{record.error_code ?? "-"}</Typography.Text>
          <Typography.Text className="table-subtitle" ellipsis>
            {record.error_message ?? "-"}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("操作"),
      key: "actions",
      fixed: "right",
      width: 220,
      render: (_, record) => (
        <Space className="table-actions" size={2}>
          <Button
            type="link"
            icon={<Eye size={15} />}
            onClick={() => navigate(`/verification-tasks/${record.id}`)}
          >
            {t("详情")}</Button>
          <Popconfirm
            title={t("取消验证任务")}
            onConfirm={() => cancelMutation.mutate(record.id)}
            disabled={!canCancel(record)}
          >
            <Button
              type="link"
              danger
              icon={<Ban size={15} />}
              disabled={!canCancel(record)}
            >
              {t("取消")}</Button>
          </Popconfirm>
          <Button
            type="link"
            icon={<RotateCcw size={15} />}
            onClick={() => retryMutation.mutate(record.id)}
            disabled={!canRetry(record)}
          >
            {t("重试")}</Button>
        </Space>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title={t("验证中心")}
        extra={
          <Button
            icon={<RefreshCw size={16} />}
            onClick={() => tasksQuery.refetch()}
            loading={tasksQuery.isFetching}
          >
            {t("刷新")}</Button>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={6}>
          <Card className="metric-card">
            <Statistic title={t("任务数")} value={metrics.total} prefix={<ClipboardCheck size={26} />} />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card">
            <Statistic
              title={t("排队/执行")}
              value={metrics.active}
              prefix={<RefreshCw size={26} />}
            />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-red">
            <Statistic
              title={t("失败/拒绝")}
              value={metrics.failed}
              prefix={<ShieldAlert size={26} />}
            />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-green">
            <Statistic
              title={t("证据数")}
              value={metrics.evidence}
              prefix={<ShieldCheck size={26} />}
            />
          </Card>
        </Col>
      </Row>

      <Card className="content-card filter-card">
        <Form
          className="verification-filter-form"
          form={form}
          layout="inline"
          initialValues={defaultFilters}
          onFinish={(values) => setFilters(normalizeFilters(values))}
        >
          <div className="filter-row filter-row-primary">
            <Form.Item label={t("状态")} name="status">
              <Select allowClear options={statusOptions} placeholder={t("全部状态")} />
            </Form.Item>
            <Form.Item label={t("任务类型")} name="task_type">
              <Select allowClear options={taskTypeOptions} placeholder={t("全部类型")} />
            </Form.Item>
            <Form.Item label="Agent" name="agent_id">
              <Input placeholder="agent_id" />
            </Form.Item>
            <Form.Item label={t("资产")} name="asset_id">
              <Input placeholder="asset_id" />
            </Form.Item>
            <Form.Item className="filter-actions">
              <Space>
                <Button
                  onClick={() => {
                    form.resetFields();
                    setCurrentPage(1);
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
              <Form.Item label={t("漏洞")} name="vulnerability_id">
                <Input placeholder={t("CVE 或漏洞 ID")} />
              </Form.Item>
              <Form.Item label={t("匹配结果")} name="match_result_id">
                <Input placeholder="match_result_id" />
              </Form.Item>
            </div>
          ) : null}
        </Form>
      </Card>

      <Card className="content-card" title={t("验证任务")}>
        {tasksQuery.isError ? <ErrorState error={tasksQuery.error} /> : null}
        <ResizableTable<VerificationTaskSummary>
          storageKey="verification-tasks"
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={tasksQuery.isFetching || cancelMutation.isPending}
          pagination={false}
          locale={{
            emptyText: (
              <EmptyState title={t("暂无验证任务")}>
                <Button type="primary" onClick={() => navigate("/risk-queue")}>
                  {t("去风险队列")}</Button>
              </EmptyState>
            )
          }}
          scroll={{ x: 1760 }}
        />
        <Space style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
          <Pagination
            current={currentPage}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            showTotal={(value) => t("共 {{v0}} 条", { v0: value })}
            onChange={(nextPage, nextPageSize) => {
              if (nextPageSize !== pageSize) {
                setPageSize(nextPageSize);
                setCurrentPage(1);
                return;
              }
              setCurrentPage(nextPage);
            }}
          />
        </Space>
      </Card>
    </Space>
  );
}

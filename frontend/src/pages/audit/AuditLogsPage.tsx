import { t } from "@/app/i18n";
import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Tag,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useQuery } from "@tanstack/react-query";
import { Eye, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { getAuditLogs } from "@/api/audit";
import type { AuditLog, AuditLogsQuery } from "@/api/types";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import JsonDetails from "@/components/JsonDetails";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import { OutcomeTag } from "@/components/ValueTags";
import { formatDateTime } from "@/utils/format";

const actionOptions = [
  { label: t("验证任务创建"), value: "verification_task.created" },
  { label: t("验证任务分配"), value: "verification_task.assigned" },
  { label: t("验证结果回传"), value: "verification_task.result_received" },
  { label: t("验证任务拒绝"), value: "verification_task.rejected" },
  { label: t("验证任务创建失败"), value: "verification_task.create_failed" },
  { label: t("匹配结果回写"), value: "match_result.verification_updated" }
];

const resourceTypeOptions = [
  { label: "verification_task", value: "verification_task" },
  { label: "match_result", value: "match_result" }
];

const outcomeOptions = [
  { label: "success", value: "success" },
  { label: "completed", value: "completed" },
  { label: "failed", value: "failed" },
  { label: "rejected", value: "rejected" },
  { label: "not_found", value: "not_found" }
];

function displayValue(value?: string | number | null) {
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

function normalizeFilters(values: AuditLogsQuery): AuditLogsQuery {
  return {
    ...(values.action ? { action: values.action.trim() } : {}),
    ...(values.actor_id ? { actor_id: values.actor_id.trim() } : {}),
    ...(values.resource_type ? { resource_type: values.resource_type.trim() } : {}),
    ...(values.resource_id ? { resource_id: values.resource_id.trim() } : {}),
    ...(values.outcome ? { outcome: values.outcome.trim() } : {}),
    limit: values.limit ?? 100
  };
}

function filtersFromSearchParams(searchParams: URLSearchParams): AuditLogsQuery {
  const limitValue = Number(searchParams.get("limit") ?? 100);
  return normalizeFilters({
    action: searchParams.get("action") ?? undefined,
    actor_id: searchParams.get("actor_id") ?? undefined,
    resource_type: searchParams.get("resource_type") ?? undefined,
    resource_id: searchParams.get("resource_id") ?? undefined,
    outcome: searchParams.get("outcome") ?? undefined,
    limit: Number.isNaN(limitValue) ? 100 : limitValue
  });
}

export default function AuditLogsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialFilters = useMemo(
    () => filtersFromSearchParams(searchParams),
    [searchParams]
  );
  const [form] = Form.useForm<AuditLogsQuery>();
  const [filters, setFilters] = useState<AuditLogsQuery>(initialFilters);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  const auditLogsQuery = useQuery({
    queryKey: ["audit-logs", filters],
    queryFn: () => getAuditLogs(filters)
  });

  function applyFilters(values: AuditLogsQuery) {
    const normalized = normalizeFilters(values);
    const nextParams = new URLSearchParams();
    Object.entries(normalized).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        nextParams.set(key, String(value));
      }
    });
    setSearchParams(nextParams);
    setFilters(normalized);
  }

  function resetFilters() {
    const defaults = { limit: 100 };
    form.setFieldsValue({
      action: undefined,
      actor_id: undefined,
      resource_type: undefined,
      resource_id: undefined,
      outcome: undefined,
      limit: 100
    });
    setSearchParams(new URLSearchParams());
    setFilters(defaults);
  }

  const columns: ColumnsType<AuditLog> = [
    {
      title: t("时间"),
      dataIndex: "created_at",
      width: 190,
      render: (value: string) => formatDateTime(value)
    },
    {
      title: t("发起方"),
      key: "actor",
      width: 200,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Tag>{record.actor_type}</Tag>
          <Typography.Text className="table-subtitle" ellipsis>
            {displayValue(record.actor_id)}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("动作"),
      dataIndex: "action",
      minWidth: 240,
      render: (value: string) => <Typography.Text copyable>{value}</Typography.Text>
    },
    {
      title: t("资源"),
      key: "resource",
      minWidth: 240,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Tag>{record.resource_type}</Tag>
          {record.resource_type === "match_result" && record.resource_id ? (
            <Typography.Link
              className="table-subtitle"
              onClick={() => navigate(`/matching/${record.resource_id}`)}
            >
              {record.resource_id}
            </Typography.Link>
          ) : (
            <Typography.Text className="table-subtitle" ellipsis copyable>
              {displayValue(record.resource_id)}
            </Typography.Text>
          )}
        </Space>
      )
    },
    {
      title: t("结果"),
      dataIndex: "outcome",
      width: 120,
      render: (value: string) => <OutcomeTag value={value} />
    },
    {
      title: t("摘要"),
      dataIndex: "summary",
      minWidth: 320,
      render: (value: string) => (
        <Typography.Text className="table-subtitle" ellipsis>
          {value}
        </Typography.Text>
      )
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
          onClick={() => setSelectedLog(record)}
        >
          {t("详情")}</Button>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      <PageHeader
        title={t("审计日志")}
        extra={
          <Button
            icon={<RefreshCw size={16} />}
            onClick={() => auditLogsQuery.refetch()}
            loading={auditLogsQuery.isFetching}
          >
            {t("刷新")}</Button>
        }
      />

      <Card className="content-card filter-card">
        <Form
          form={form}
          layout="inline"
          initialValues={initialFilters}
          onFinish={applyFilters}
        >
          <Form.Item label={t("动作")} name="action">
            <Select
              allowClear
              showSearch
              options={actionOptions}
              placeholder={t("全部动作")}
            />
          </Form.Item>
          <Form.Item label={t("发起方")} name="actor_id">
            <Input allowClear placeholder="actor id" />
          </Form.Item>
          <Form.Item label={t("资源类型")} name="resource_type">
            <Select
              allowClear
              showSearch
              options={resourceTypeOptions}
              placeholder={t("全部资源")}
            />
          </Form.Item>
          <Form.Item label={t("资源 ID")} name="resource_id">
            <Input allowClear placeholder="resource id" />
          </Form.Item>
          <Form.Item label={t("结果")} name="outcome">
            <Select
              allowClear
              showSearch
              options={outcomeOptions}
              placeholder={t("全部结果")}
            />
          </Form.Item>
          <Form.Item label={t("数量")} name="limit">
            <InputNumber min={1} max={500} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={resetFilters}>{t("重置")}</Button>
              <Button type="primary" htmlType="submit">
                {t("查询")}</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Card className="content-card" title={t("审计记录")}>
        {auditLogsQuery.isError ? <ErrorState error={auditLogsQuery.error} /> : null}
        <ResizableTable<AuditLog>
          storageKey="audit-logs"
          rowKey="id"
          columns={columns}
          dataSource={auditLogsQuery.data ?? []}
          loading={auditLogsQuery.isFetching}
          pagination={{ pageSize: 10, showSizeChanger: true }}
          locale={{ emptyText: <EmptyState title={t("暂无审计记录")} /> }}
          scroll={{ x: 1410 }}
        />
      </Card>

      <Drawer
        title={t("审计详情")}
        width={720}
        open={Boolean(selectedLog)}
        onClose={() => setSelectedLog(null)}
      >
        {selectedLog ? (
          <Space className="page-stack" orientation="vertical" size={16}>
            <Descriptions
              bordered
              size="small"
              column={1}
              items={[
                { key: "id", label: t("日志 ID"), children: selectedLog.id },
                {
                  key: "time",
                  label: t("时间"),
                  children: formatDateTime(selectedLog.created_at)
                },
                {
                  key: "actor",
                  label: t("发起方"),
                  children: `${selectedLog.actor_type} / ${displayValue(
                    selectedLog.actor_id
                  )}`
                },
                { key: "action", label: t("动作"), children: selectedLog.action },
                {
                  key: "resource",
                  label: t("资源"),
                  children: `${selectedLog.resource_type} / ${displayValue(
                    selectedLog.resource_id
                  )}`
                },
                {
                  key: "outcome",
                  label: t("结果"),
                  children: <OutcomeTag value={selectedLog.outcome} />
                },
                { key: "summary", label: t("摘要"), children: selectedLog.summary }
              ]}
            />
            <Card className="content-card" title="Details JSON">
              <JsonDetails value={selectedLog.details} />
            </Card>
          </Space>
        ) : null}
      </Drawer>
    </Space>
  );
}

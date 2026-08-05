import { t } from "@/app/i18n";
import {
  Button,
  Card,
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
import { ExternalLink, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { getHandlingAuditRecords } from "@/api/audit";
import type {
  HandlingAuditRecord,
  HandlingAuditRecordsQuery
} from "@/api/types";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import HandlingStatusTag, {
  handlingStatusLabel,
  handlingStatusOptions
} from "@/components/HandlingStatusTag";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import { formatDateTime } from "@/utils/format";

const actionOptions = [
  { label: t("状态变更"), value: "status_changed" },
  { label: t("重新打开"), value: "reopened" }
];

function actionLabel(value: string) {
  return actionOptions.find((option) => option.value === value)?.label ?? value;
}

function displayValue(value?: string | number | null) {
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

function actorName(record: HandlingAuditRecord) {
  return (
    record.actor_display_name ||
    record.actor_username ||
    record.actor_id ||
    "-"
  );
}

function normalizeFilters(
  values: HandlingAuditRecordsQuery
): HandlingAuditRecordsQuery {
  return {
    ...(values.actor_id ? { actor_id: values.actor_id.trim() } : {}),
    ...(values.match_result_id
      ? { match_result_id: values.match_result_id.trim() }
      : {}),
    ...(values.to_status ? { to_status: values.to_status } : {}),
    ...(values.action ? { action: values.action.trim() } : {}),
    limit: values.limit ?? 100
  };
}

function filtersFromSearchParams(
  searchParams: URLSearchParams
): HandlingAuditRecordsQuery {
  const limitValue = Number(searchParams.get("limit") ?? 100);
  return normalizeFilters({
    actor_id: searchParams.get("actor_id") ?? undefined,
    match_result_id: searchParams.get("match_result_id") ?? undefined,
    to_status:
      (searchParams.get("to_status") as HandlingAuditRecordsQuery["to_status"]) ??
      undefined,
    action: searchParams.get("action") ?? undefined,
    limit: Number.isNaN(limitValue) ? 100 : limitValue
  });
}

export default function HandlingRecordsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialFilters = useMemo(
    () => filtersFromSearchParams(searchParams),
    [searchParams]
  );
  const [form] = Form.useForm<HandlingAuditRecordsQuery>();
  const [filters, setFilters] =
    useState<HandlingAuditRecordsQuery>(initialFilters);

  const recordsQuery = useQuery({
    queryKey: ["audit", "handling-records", filters],
    queryFn: () => getHandlingAuditRecords(filters)
  });

  function applyFilters(values: HandlingAuditRecordsQuery) {
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
      actor_id: undefined,
      match_result_id: undefined,
      to_status: undefined,
      action: undefined,
      limit: 100
    });
    setSearchParams(new URLSearchParams());
    setFilters(defaults);
  }

  const columns: ColumnsType<HandlingAuditRecord> = [
    {
      title: t("时间"),
      dataIndex: "created_at",
      width: 190,
      render: (value: string) => formatDateTime(value)
    },
    {
      title: t("风险项"),
      key: "risk",
      minWidth: 300,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(`/matching/${record.match_result_id}`)}>
            {record.risk_code || record.match_result_id}
          </Typography.Link>
          <Typography.Text className="table-subtitle" ellipsis>
            {record.vulnerability_canonical_id} · {record.vulnerability_title}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("资产"),
      key: "asset",
      width: 220,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(`/assets/${record.asset_id}`)}>
            {record.asset_hostname}
          </Typography.Link>
          <Typography.Text className="table-subtitle" ellipsis>
            {record.asset_id}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("处置动作"),
      key: "status",
      width: 250,
      render: (_, record) => (
        <Space orientation="vertical" size={4}>
          <Tag>{actionLabel(record.action)}</Tag>
          <Space size={4} wrap>
            {record.from_status ? (
              <HandlingStatusTag value={record.from_status} />
            ) : (
              <Tag>{t("起始")}</Tag>
            )}
            <Typography.Text type="secondary">{t("到")}</Typography.Text>
            <HandlingStatusTag value={record.to_status} />
          </Space>
        </Space>
      )
    },
    {
      title: t("操作者"),
      key: "actor",
      width: 180,
      render: (_, record) => actorName(record)
    },
    {
      title: t("说明"),
      dataIndex: "note",
      minWidth: 280,
      render: (value: string | null) => (
        <Typography.Text className="table-subtitle" ellipsis>
          {displayValue(value)}
        </Typography.Text>
      )
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
          icon={<ExternalLink size={15} />}
          onClick={() => navigate(`/matching/${record.match_result_id}`)}
        >
          {t("查看风险")}</Button>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      <PageHeader
        title={t("处置记录")}
        subtitle={t("记录各风险项的人工处置状态变更和重新打开操作")}
        extra={
          <Button
            icon={<RefreshCw size={16} />}
            onClick={() => recordsQuery.refetch()}
            loading={recordsQuery.isFetching}
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
            <Select allowClear options={actionOptions} placeholder={t("全部动作")} />
          </Form.Item>
          <Form.Item label={t("处置状态")} name="to_status">
            <Select
              allowClear
              options={handlingStatusOptions}
              placeholder={t("全部状态")}
            />
          </Form.Item>
          <Form.Item label={t("风险项 ID")} name="match_result_id">
            <Input allowClear placeholder="match result id" />
          </Form.Item>
          <Form.Item label={t("操作者")} name="actor_id">
            <Input allowClear placeholder="actor id" />
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

      <Card className="content-card" title={t("处置记录")}>
        {recordsQuery.isError ? <ErrorState error={recordsQuery.error} /> : null}
        <ResizableTable<HandlingAuditRecord>
          storageKey="handling-audit-records"
          rowKey="id"
          columns={columns}
          dataSource={recordsQuery.data ?? []}
          loading={recordsQuery.isFetching}
          pagination={{ pageSize: 10, showSizeChanger: true }}
          locale={{ emptyText: <EmptyState title={t("暂无处置记录")} /> }}
          scroll={{ x: 1540 }}
        />
      </Card>
    </Space>
  );
}

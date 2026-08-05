import { t } from "@/app/i18n";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Form,
  Input,
  Pagination,
  Select,
  Space,
  Tag,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { ExternalLink, Eye, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { getNotificationHistory } from "@/api/notifications";
import type {
  NotificationHistoryQuery,
  SystemEvent,
  SystemEventCategory
} from "@/api/types";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import JsonDetails from "@/components/JsonDetails";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import { systemEventTarget } from "@/utils/eventTargets";
import { formatDateTime } from "@/utils/format";

const PAGE_SIZE = 20;
const categoryLabels: Record<string, string> = {
  asset: t("资产"),
  intel: t("情报"),
  risk: t("风险")
};
const levelColors: Record<string, string> = {
  info: "blue",
  success: "green",
  warning: "orange",
  error: "red"
};

export default function NotificationHistoryPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<NotificationHistoryQuery>();
  const [filters, setFilters] = useState<NotificationHistoryQuery>({});
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<SystemEvent | null>(null);
  const query = useQuery({
    queryKey: ["notifications", "history", filters, page],
    queryFn: () =>
      getNotificationHistory({
        ...filters,
        offset: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE
      })
  });

  const columns: ColumnsType<SystemEvent> = [
    {
      title: t("发生时间"),
      dataIndex: "occurred_at",
      width: 190,
      render: (value: string) => formatDateTime(value)
    },
    {
      title: t("类别"),
      dataIndex: "category",
      width: 100,
      render: (value: string, record) => (
        <Tag color={levelColors[record.level]}>{categoryLabels[value] ?? value}</Tag>
      )
    },
    { title: t("事件类型"), dataIndex: "event_type", width: 210 },
    { title: t("标题"), dataIndex: "title", width: 220 },
    {
      title: t("摘要"),
      dataIndex: "summary",
      minWidth: 360,
      render: (value: string) => (
        <Typography.Text className="table-subtitle" ellipsis>{value}</Typography.Text>
      )
    },
    {
      title: t("操作"),
      key: "actions",
      fixed: "right",
      width: 100,
      render: (_, record) => (
        <Button type="link" icon={<Eye size={15} />} onClick={() => setSelected(record)}>
          {t("详情")}
        </Button>
      )
    }
  ];
  const target = selected ? systemEventTarget(selected) : null;

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      <PageHeader
        title={t("历史消息")}
        extra={
          <Button icon={<RefreshCw size={16} />} loading={query.isFetching} onClick={() => query.refetch()}>
            {t("刷新")}
          </Button>
        }
      />
      <Card className="content-card filter-card">
        <Form
          form={form}
          layout="inline"
          onFinish={(values) => {
            setFilters({
              ...(values.category ? { category: values.category } : {}),
              ...(values.event_type?.trim() ? { event_type: values.event_type.trim() } : {})
            });
            setPage(1);
          }}
        >
          <Form.Item label={t("类别")} name="category">
            <Select
              allowClear
              placeholder={t("全部类别")}
              options={(Object.keys(categoryLabels) as SystemEventCategory[]).map((value) => ({
                value,
                label: categoryLabels[value]
              }))}
            />
          </Form.Item>
          <Form.Item label={t("事件类型")} name="event_type">
            <Input allowClear placeholder={t("输入事件类型")} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={() => { form.resetFields(); setFilters({}); setPage(1); }}>
                {t("重置")}
              </Button>
              <Button type="primary" htmlType="submit">{t("查询")}</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
      {query.isError ? <ErrorState error={query.error} /> : null}
      <Card className="content-card">
        <ResizableTable<SystemEvent>
          storageKey="notification-history"
          rowKey="id"
          columns={columns}
          dataSource={query.data?.items ?? []}
          loading={query.isLoading}
          pagination={false}
          locale={{ emptyText: <EmptyState title={t("暂无历史消息")} /> }}
          scroll={{ x: 1180 }}
        />
        <Pagination
          className="table-pagination"
          current={page}
          pageSize={PAGE_SIZE}
          total={query.data?.total ?? 0}
          showSizeChanger={false}
          showTotal={(total) => t("共 {{v0}} 条", { v0: total })}
          onChange={setPage}
        />
      </Card>
      <Drawer title={t("历史消息详情")} size={640} open={Boolean(selected)} onClose={() => setSelected(null)}>
        {selected ? (
          <Space orientation="vertical" size={16} style={{ width: "100%" }}>
            <Typography.Title level={4}>{selected.title}</Typography.Title>
            <Typography.Paragraph>{selected.summary}</Typography.Paragraph>
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label={t("发生时间")}>{formatDateTime(selected.occurred_at)}</Descriptions.Item>
              <Descriptions.Item label={t("类别")}>{categoryLabels[selected.category]}</Descriptions.Item>
              <Descriptions.Item label={t("事件类型")}>{selected.event_type}</Descriptions.Item>
              <Descriptions.Item label={t("事件 ID")}><Typography.Text copyable>{selected.id}</Typography.Text></Descriptions.Item>
            </Descriptions>
            <JsonDetails value={selected.details} />
            {target ? (
              <Button type="primary" icon={<ExternalLink size={16} />} onClick={() => navigate(target)}>
                {t("前往对应页面")}
              </Button>
            ) : null}
          </Space>
        ) : null}
      </Drawer>
    </Space>
  );
}

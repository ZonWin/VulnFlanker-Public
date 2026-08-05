import { t } from "@/app/i18n";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Form,
  Input,
  message,
  Pagination,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { Eye, RefreshCw, RotateCcw } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";

import {
  getEmailDeliveries,
  getEmailDelivery,
  resendEmailDelivery
} from "@/api/emailAlerts";
import type {
  EmailDelivery,
  EmailDeliveryQuery,
  EmailDeliveryStatus,
  EmailTriggerType
} from "@/api/types";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import JsonDetails from "@/components/JsonDetails";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import { formatDateTime } from "@/utils/format";

const PAGE_SIZE = 20;
const statusMeta: Record<EmailDeliveryStatus, { label: string; color: string }> = {
  queued: { label: t("排队中"), color: "blue" },
  sending: { label: t("发送中"), color: "processing" },
  retry_scheduled: { label: t("等待重试"), color: "orange" },
  sent: { label: t("已发送"), color: "green" },
  failed: { label: t("发送失败"), color: "red" },
  skipped: { label: t("已跳过"), color: "default" }
};
const triggerLabels: Record<EmailTriggerType, string> = {
  automatic: t("自动告警"),
  manual: t("手动告警"),
  test: t("测试邮件"),
  manual_retry: t("手动重发")
};
const skipReasonLabels: Record<string, string> = {
  missing_business_system: t("资产未绑定业务系统"),
  inactive_business_system: t("业务系统已停用"),
  missing_responsible_person: t("未设置主责任人"),
  inactive_responsible_person: t("主责任人已停用"),
  missing_recipient_email: t("主责任人邮箱为空"),
  invalid_recipient_email: t("主责任人邮箱格式无效"),
  below_threshold: t("风险等级低于告警阈值"),
  delivery_preparation_failed: t("邮件准备失败")
};

function deliveryReason(delivery: EmailDelivery) {
  return delivery.skip_reason
    ? skipReasonLabels[delivery.skip_reason] ?? delivery.skip_reason
    : delivery.last_error || "-";
}

export default function EmailDeliveryLogsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm<EmailDeliveryQuery>();
  const [filters, setFilters] = useState<EmailDeliveryQuery>({});
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const listQuery = useQuery({
    queryKey: ["email-deliveries", filters, page],
    queryFn: () => getEmailDeliveries({ ...filters, offset: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE })
  });
  const detailQuery = useQuery({
    queryKey: ["email-deliveries", "detail", selectedId],
    queryFn: () => getEmailDelivery(selectedId ?? ""),
    enabled: Boolean(selectedId)
  });
  const resendMutation = useMutation({
    mutationFn: resendEmailDelivery,
    onSuccess: (result) => {
      messageApi.success(result.message);
      void queryClient.invalidateQueries({ queryKey: ["email-deliveries"] });
      setSelectedId(result.delivery_id);
    },
    onError: (error) => messageApi.error(error instanceof Error ? error.message : t("重新发送失败"))
  });

  const columns: ColumnsType<EmailDelivery> = [
    { title: t("创建时间"), dataIndex: "created_at", width: 190, render: formatDateTime },
    {
      title: t("状态"), dataIndex: "status", width: 120,
      render: (value: EmailDeliveryStatus) => <Tag color={statusMeta[value].color}>{statusMeta[value].label}</Tag>
    },
    {
      title: t("触发方式"), dataIndex: "trigger_type", width: 130,
      render: (value: EmailTriggerType) => triggerLabels[value]
    },
    {
      title: t("收件人"), key: "recipient", width: 260,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{record.recipient_name || "-"}</Typography.Text>
          <Typography.Text type="secondary">{record.recipient_email || "-"}</Typography.Text>
        </Space>
      )
    },
    { title: t("主题"), dataIndex: "subject", minWidth: 320, ellipsis: true },
    { title: t("风险数"), dataIndex: "risk_count", width: 90 },
    {
      title: t("尝试"), key: "attempts", width: 100,
      render: (_, record) => `${record.attempt_count}/${record.max_retries + 1}`
    },
    { title: t("下次重试"), dataIndex: "next_attempt_at", width: 190, render: formatDateTime },
    { title: t("发送时间"), dataIndex: "sent_at", width: 190, render: formatDateTime },
    {
      title: t("说明"), key: "reason", minWidth: 260,
      render: (_, record) => deliveryReason(record)
    },
    {
      title: t("操作"), key: "actions", fixed: "right", width: 170,
      render: (_, record) => (
        <Space size={2}>
          <Button type="link" icon={<Eye size={15} />} onClick={() => setSelectedId(record.id)}>{t("详情")}</Button>
          {record.status === "failed" ? (
            <Popconfirm
              title={t("确认重新发送此邮件？")}
              description={t("将生成一条新的邮件投递记录。")}
              onConfirm={() => resendMutation.mutate(record.id)}
            >
              <Button type="link" icon={<RotateCcw size={15} />}>{t("重发")}</Button>
            </Popconfirm>
          ) : null}
        </Space>
      )
    }
  ];
  const detail = detailQuery.data;

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader title={t("邮件日志")} extra={<Button icon={<RefreshCw size={16} />} loading={listQuery.isFetching} onClick={() => listQuery.refetch()}>{t("刷新")}</Button>} />
      <Card className="content-card filter-card">
        <Form form={form} layout="inline" onFinish={(values) => { setFilters(values); setPage(1); }}>
          <Form.Item label={t("状态")} name="status">
            <Select allowClear placeholder={t("全部状态")} options={(Object.keys(statusMeta) as EmailDeliveryStatus[]).map((value) => ({ value, label: statusMeta[value].label }))} />
          </Form.Item>
          <Form.Item label={t("触发方式")} name="trigger_type">
            <Select allowClear placeholder={t("全部方式")} options={(Object.keys(triggerLabels) as EmailTriggerType[]).map((value) => ({ value, label: triggerLabels[value] }))} />
          </Form.Item>
          <Form.Item label={t("收件邮箱")} name="recipient_email"><Input allowClear /></Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={() => { form.resetFields(); setFilters({}); setPage(1); }}>{t("重置")}</Button>
              <Button type="primary" htmlType="submit">{t("查询")}</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
      {listQuery.isError ? <ErrorState error={listQuery.error} /> : null}
      <Card className="content-card">
        <ResizableTable<EmailDelivery> storageKey="email-delivery-logs" rowKey="id" columns={columns} dataSource={listQuery.data?.items ?? []} loading={listQuery.isLoading} pagination={false} locale={{ emptyText: <EmptyState title={t("暂无邮件日志")} /> }} scroll={{ x: 1840 }} />
        <Pagination className="table-pagination" current={page} pageSize={PAGE_SIZE} total={listQuery.data?.total ?? 0} showSizeChanger={false} showTotal={(total) => t("共 {{v0}} 条", { v0: total })} onChange={setPage} />
      </Card>
      <Drawer title={t("邮件投递详情")} size={720} open={Boolean(selectedId)} onClose={() => setSelectedId(null)}>
        {detailQuery.isError ? <ErrorState error={detailQuery.error} /> : null}
        {detail ? (
          <Space orientation="vertical" size={16} style={{ width: "100%" }}>
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label={t("状态")}><Tag color={statusMeta[detail.status].color}>{statusMeta[detail.status].label}</Tag></Descriptions.Item>
              <Descriptions.Item label={t("收件人")}>{detail.recipient_name || "-"} · {detail.recipient_email || "-"}</Descriptions.Item>
              <Descriptions.Item label={t("主题")}>{detail.subject}</Descriptions.Item>
              <Descriptions.Item label={t("创建时间")}>{formatDateTime(detail.created_at)}</Descriptions.Item>
              <Descriptions.Item label={t("发送时间")}>{formatDateTime(detail.sent_at)}</Descriptions.Item>
              <Descriptions.Item label={t("跳过原因")}>{detail.skip_reason ? skipReasonLabels[detail.skip_reason] ?? detail.skip_reason : "-"}</Descriptions.Item>
              <Descriptions.Item label={t("最后错误")}>{detail.last_error || "-"}</Descriptions.Item>
            </Descriptions>
            {detail.match_result_ids.length ? <Space wrap>{detail.match_result_ids.map((id) => <Button key={id} size="small" onClick={() => navigate(`/matching/${id}`)}>{t("风险详情")} · {id.slice(0, 8)}</Button>)}</Space> : null}
            <div><Typography.Text strong>{t("纯文本正文")}</Typography.Text><pre className="json-block">{detail.text_body}</pre></div>
            <div><Typography.Text strong>{t("HTML 正文")}</Typography.Text><iframe className="email-preview-frame" title={t("HTML 邮件预览")} sandbox="" srcDoc={detail.html_body} /></div>
            <div>
              <Typography.Text strong>{t("发送尝试")}</Typography.Text>
              <Table rowKey="id" size="small" pagination={false} dataSource={detail.attempts} columns={[
                { title: t("次数"), dataIndex: "attempt_number", width: 80 },
                { title: t("状态"), dataIndex: "status", width: 100 },
                { title: t("开始时间"), dataIndex: "started_at", width: 190, render: formatDateTime },
                { title: t("错误"), dataIndex: "error_message" }
              ]} />
            </div>
            <div><Typography.Text strong>{t("上下文")}</Typography.Text><JsonDetails value={detail.context} /></div>
          </Space>
        ) : null}
      </Drawer>
    </Space>
  );
}

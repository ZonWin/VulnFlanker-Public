import { t } from "@/app/i18n";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Descriptions,
  Drawer,
  message,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography
} from "antd";
import { Bell, CheckCheck, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import {
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead
} from "@/api/notifications";
import type { AdminNotification, SystemEvent } from "@/api/types";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import JsonDetails from "@/components/JsonDetails";
import { systemEventTarget } from "@/utils/eventTargets";
import { formatDateTime } from "@/utils/format";

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

export default function NotificationCenter() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [open, setOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<SystemEvent | null>(null);

  const countQuery = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: getUnreadNotificationCount,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true
  });
  const notificationsQuery = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: async () => {
      const firstPage = await getNotifications({ unread_only: true, limit: 500 });
      const items = [...firstPage.items];
      while (items.length < firstPage.total) {
        const nextPage = await getNotifications({
          unread_only: true,
          offset: items.length,
          limit: 500
        });
        if (!nextPage.items.length) break;
        items.push(...nextPage.items);
      }
      return { ...firstPage, items };
    },
    enabled: open,
    refetchInterval: open ? 30_000 : false,
    refetchOnWindowFocus: true
  });
  const items = notificationsQuery.data?.items ?? [];

  useEffect(() => {
    if (open && !selectedEvent && items[0]) {
      setSelectedEvent(items[0].event);
    }
  }, [items, open, selectedEvent]);

  const invalidateNotifications = () => {
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  const readMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: invalidateNotifications,
    onError: (error) =>
      messageApi.error(error instanceof Error ? error.message : t("标记已读失败"))
  });
  const readAllMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: (result) => {
      invalidateNotifications();
      messageApi.success(t("已将 {{v0}} 条消息标记为已读", { v0: result.updated_count }));
    },
    onError: (error) =>
      messageApi.error(error instanceof Error ? error.message : t("全部已读失败"))
  });

  function selectNotification(notification: AdminNotification) {
    setSelectedEvent(notification.event);
    readMutation.mutate(notification.id);
  }

  const target = selectedEvent ? systemEventTarget(selectedEvent) : null;

  return (
    <>
      {contextHolder}
      <Tooltip title={t("站内消息")}>
        <Badge count={countQuery.data?.count ?? 0} overflowCount={99} size="small">
          <Button
            className="notification-trigger"
            aria-label={t("站内消息，{{v0}} 条未读", { v0: countQuery.data?.count ?? 0 })}
            icon={<Bell size={18} />}
            onClick={() => setOpen(true)}
          />
        </Badge>
      </Tooltip>

      <Drawer
        className="notification-drawer"
        title={t("站内消息")}
        size={860}
        open={open}
        onClose={() => setOpen(false)}
        extra={
          <Button
            icon={<CheckCheck size={16} />}
            disabled={!items.length}
            loading={readAllMutation.isPending}
            onClick={() => readAllMutation.mutate()}
          >
            {t("全部已读")}
          </Button>
        }
      >
        {notificationsQuery.isError ? <ErrorState error={notificationsQuery.error} /> : null}
        <div className="notification-center-grid">
          <div className="notification-list-panel" aria-label={t("未读消息列表")}>
            {notificationsQuery.isLoading ? (
              <div className="notification-list-loading"><Spin /></div>
            ) : !items.length ? (
              <EmptyState title={t("暂无未读消息")} />
            ) : (
              <div className="notification-list">
                {items.map((item) => (
                  <div
                    key={item.id}
                    className={`notification-list-item${selectedEvent?.id === item.event.id ? " is-selected" : ""}`}
                  >
                    <button type="button" className="notification-list-button" onClick={() => selectNotification(item)}>
                      <Space orientation="vertical" size={4}>
                        <Space size={6} wrap>
                          <Tag color={levelColors[item.event.level]}>
                            {categoryLabels[item.event.category] ?? item.event.category}
                          </Tag>
                          <Typography.Text strong>{item.event.title}</Typography.Text>
                        </Space>
                        <Typography.Text type="secondary" ellipsis>
                          {item.event.summary}
                        </Typography.Text>
                        <Typography.Text className="table-subtitle">
                          {formatDateTime(item.event.occurred_at)}
                        </Typography.Text>
                      </Space>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="notification-detail-panel" aria-live="polite">
            {selectedEvent ? (
              <Space orientation="vertical" size={16} style={{ width: "100%" }}>
                <div>
                  <Space size={6} wrap>
                    <Tag color={levelColors[selectedEvent.level]}>
                      {categoryLabels[selectedEvent.category] ?? selectedEvent.category}
                    </Tag>
                    <Typography.Title level={4}>{selectedEvent.title}</Typography.Title>
                  </Space>
                  <Typography.Paragraph>{selectedEvent.summary}</Typography.Paragraph>
                </div>
                <Descriptions column={1} size="small" bordered>
                  <Descriptions.Item label={t("发生时间")}>
                    {formatDateTime(selectedEvent.occurred_at)}
                  </Descriptions.Item>
                  <Descriptions.Item label={t("事件类型")}>
                    {selectedEvent.event_type}
                  </Descriptions.Item>
                </Descriptions>
                <div>
                  <Typography.Text strong>{t("事件详情")}</Typography.Text>
                  <JsonDetails value={selectedEvent.details} />
                </div>
                {target ? (
                  <Button
                    type="primary"
                    icon={<ExternalLink size={16} />}
                    onClick={() => {
                      setOpen(false);
                      navigate(target);
                    }}
                  >
                    {t("前往对应页面")}
                  </Button>
                ) : null}
              </Space>
            ) : (
              <EmptyState title={t("请选择一条消息查看详情")} />
            )}
          </div>
        </div>
      </Drawer>
    </>
  );
}

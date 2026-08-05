import { t } from "@/app/i18n";
import {
  Button,
  Card,
  Col,
  Descriptions,
  Popconfirm,
  Row,
  Space,
  Statistic,
  Timeline,
  Typography,
  message
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban, FileClock, RefreshCw, RotateCcw } from "lucide-react";
import { useNavigate, useParams } from "react-router";

import {
  cancelVerificationTask,
  getVerificationTask,
  retryVerificationTask
} from "@/api/verification";
import type { VerificationTaskDetail } from "@/api/types";
import ErrorState from "@/components/ErrorState";
import EvidenceList from "@/components/EvidenceList";
import JsonDetails from "@/components/JsonDetails";
import LoadingBlock from "@/components/LoadingBlock";
import PageHeader from "@/components/PageHeader";
import { VerificationTaskStatusTag } from "@/components/ValueTags";
import { formatDateTime } from "@/utils/format";

function canCancel(task?: VerificationTaskDetail) {
  return task?.status === "queued" || task?.status === "in_progress";
}

function canRetry(task?: VerificationTaskDetail) {
  return task ? ["failed", "rejected", "cancelled"].includes(task.status) : false;
}

export default function VerificationTaskDetailPage() {
  const navigate = useNavigate();
  const { taskId } = useParams<{ taskId: string }>();
  const [messageApi, contextHolder] = message.useMessage();
  const queryClient = useQueryClient();

  const taskQuery = useQuery({
    queryKey: ["verification-tasks", "detail", taskId],
    queryFn: () => getVerificationTask(taskId ?? ""),
    enabled: Boolean(taskId)
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelVerificationTask(taskId ?? ""),
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
    mutationFn: () => retryVerificationTask(taskId ?? ""),
    onSuccess: (task) => {
      messageApi.success(t("重试任务已创建"));
      void queryClient.invalidateQueries({ queryKey: ["verification-tasks"] });
      navigate(`/verification-tasks/${task.id}`);
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("重试任务失败"));
    }
  });

  const task = taskQuery.data;

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title={t("验证任务详情")}
        extra={
          <Space>
            <Button icon={<ArrowLeft size={16} />} onClick={() => navigate(-1)}>
              {t("返回")}</Button>
            <Button
              icon={<FileClock size={16} />}
              onClick={() =>
                navigate(
                  `/audit?resource_type=verification_task&resource_id=${encodeURIComponent(
                    taskId ?? ""
                  )}`
                )
              }
              disabled={!taskId}
            >
              {t("相关审计")}</Button>
            <Button
              icon={<RefreshCw size={16} />}
              onClick={() => taskQuery.refetch()}
              loading={taskQuery.isFetching}
            >
              {t("刷新")}</Button>
            <Popconfirm
              title={t("取消验证任务")}
              onConfirm={() => cancelMutation.mutate()}
              disabled={!canCancel(task)}
            >
              <Button
                danger
                icon={<Ban size={16} />}
                disabled={!canCancel(task)}
                loading={cancelMutation.isPending}
              >
                {t("取消")}</Button>
            </Popconfirm>
            <Button
              icon={<RotateCcw size={16} />}
              disabled={!canRetry(task)}
              loading={retryMutation.isPending}
              onClick={() => retryMutation.mutate()}
            >
              {t("重试")}</Button>
          </Space>
        }
      />

      {taskQuery.isLoading ? <LoadingBlock /> : null}
      {taskQuery.isError ? <ErrorState error={taskQuery.error} /> : null}

      {task ? (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={6}>
              <Card className="metric-card">
                <Statistic
                  title={t("当前状态")}
                  valueRender={() => <VerificationTaskStatusTag value={task.status} />}
                />
              </Card>
            </Col>
            <Col xs={24} lg={6}>
              <Card className="metric-card metric-card-green">
                <Statistic title={t("证据数")} value={task.evidence_count} />
              </Card>
            </Col>
            <Col xs={24} lg={6}>
              <Card className="metric-card">
                <Statistic title={t("重试次数")} value={task.retry_count} />
              </Card>
            </Col>
            <Col xs={24} lg={6}>
              <Card className="metric-card metric-card-red">
                <Statistic title={t("错误码")} value={task.error_code ?? "-"} />
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]}>
            <Col xs={24} xl={14}>
              <Card className="content-card" title={t("任务上下文")}>
                <Descriptions
                  bordered
                  size="small"
                  column={{ xs: 1, md: 2 }}
                  items={[
                    { key: "id", label: t("任务 ID"), children: task.id },
                    { key: "type", label: t("任务类型"), children: task.task_type },
                    {
                      key: "match",
                      label: t("匹配结果"),
                      children: (
                        <Typography.Link
                          onClick={() => navigate(`/matching/${task.match_result_id}`)}
                        >
                          {task.match_result_id}
                        </Typography.Link>
                      )
                    },
                    {
                      key: "previous",
                      label: t("前序任务"),
                      children: task.previous_task_id ? (
                        <Typography.Link
                          onClick={() =>
                            navigate(`/verification-tasks/${task.previous_task_id}`)
                          }
                        >
                          {task.previous_task_id}
                        </Typography.Link>
                      ) : (
                        "-"
                      )
                    },
                    {
                      key: "vuln",
                      label: t("漏洞"),
                      children: (
                        <Space orientation="vertical" size={0}>
                          <Typography.Link
                            onClick={() =>
                              task.vulnerability_canonical_id
                                ? navigate(
                                    `/vulnerabilities/${task.vulnerability_canonical_id}`
                                  )
                                : undefined
                            }
                          >
                            {task.vulnerability_canonical_id ?? "-"}
                          </Typography.Link>
                          <Typography.Text className="table-subtitle" ellipsis>
                            {task.vulnerability_title ?? "-"}
                          </Typography.Text>
                        </Space>
                      )
                    },
                    {
                      key: "asset",
                      label: t("资产"),
                      children: (
                        <Space orientation="vertical" size={0}>
                          <Typography.Link
                            onClick={() => navigate(`/assets/${task.asset_id}`)}
                          >
                            {task.asset_hostname ?? task.asset_id}
                          </Typography.Link>
                          <Typography.Text className="table-subtitle">
                            {task.asset_agent_id ?? "-"}
                          </Typography.Text>
                        </Space>
                      )
                    },
                    { key: "requested", label: t("请求人"), children: task.requested_by ?? "-" },
                    { key: "created", label: t("创建时间"), children: formatDateTime(task.created_at) },
                    { key: "assigned", label: t("分配时间"), children: formatDateTime(task.assigned_at) },
                    {
                      key: "cancel",
                      label: t("取消请求"),
                      children: formatDateTime(task.cancel_requested_at)
                    },
                    { key: "completed", label: t("完成时间"), children: formatDateTime(task.completed_at) },
                    { key: "updated", label: t("更新时间"), children: formatDateTime(task.updated_at) }
                  ]}
                />
              </Card>
            </Col>
            <Col xs={24} xl={10}>
              <Card className="content-card" title={t("状态时间线")}>
                <Timeline
                  items={task.timeline.map((event) => ({
                    children: (
                      <Space orientation="vertical" size={0}>
                        <Space>
                          <VerificationTaskStatusTag value={event.status} />
                          <Typography.Text>{formatDateTime(event.occurred_at)}</Typography.Text>
                        </Space>
                        <Typography.Text className="table-subtitle">
                          {event.summary}
                        </Typography.Text>
                      </Space>
                    )
                  }))}
                />
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]}>
            <Col xs={24} xl={12}>
              <Card className="content-card" title={t("任务参数")}>
                <JsonDetails value={task.parameters} />
              </Card>
            </Col>
            <Col xs={24} xl={12}>
              <Card className="content-card" title={t("错误信息")}>
                <Space orientation="vertical" size={8}>
                  <Typography.Text>{task.error_code ?? "-"}</Typography.Text>
                  <Typography.Text className="table-subtitle">
                    {task.error_message ?? "-"}
                  </Typography.Text>
                </Space>
              </Card>
            </Col>
          </Row>

          <Card className="content-card" title={t("验证发现")}>
            <EvidenceList
              items={task.evidence}
              emptyText={t("暂无验证证据")}
              mode="verification"
            />
          </Card>
        </>
      ) : null}
    </Space>
  );
}

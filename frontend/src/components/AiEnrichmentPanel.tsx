import { t } from "@/app/i18n";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Descriptions,
  Empty,
  Input,
  List,
  Modal,
  Select,
  Space,
  Tag,
  Typography,
  message
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Check, RefreshCw, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getAIProfiles } from "@/api/ai";
import {
  acceptVulnerabilityAIEnrichment,
  getVulnerabilityAIEnrichments,
  rejectVulnerabilityAIEnrichment,
  triggerVulnerabilityAIEnrichment
} from "@/api/vulnerabilities";
import type {
  VulnerabilityAIEnrichment,
  VulnerabilityAIEnrichmentAcceptField,
  VulnerabilityAIEnrichmentEvidence,
  VulnerabilityAIEnrichmentStatus,
  VulnerabilityDetail
} from "@/api/types";
import ErrorState from "@/components/ErrorState";
import LoadingBlock from "@/components/LoadingBlock";
import { formatDateTime } from "@/utils/format";

const statusLabels: Record<VulnerabilityAIEnrichmentStatus, string> = {
  pending_review: t("有 AI 建议待处理"),
  insufficient: t("未形成有效建议"),
  failed: t("AI 任务失败"),
  accepted: t("已人工采纳"),
  rejected: t("建议已忽略"),
  auto_accepted: t("已自动采纳"),
  already_applied: t("无需变更")
};

const statusColors: Record<VulnerabilityAIEnrichmentStatus, string> = {
  pending_review: "processing",
  insufficient: "default",
  failed: "error",
  accepted: "success",
  rejected: "warning",
  auto_accepted: "success",
  already_applied: "success"
};

const fieldRows: Array<{
  field: VulnerabilityAIEnrichmentAcceptField;
  label: string;
}> = [
  { field: "vendor", label: t("厂商") },
  { field: "product", label: t("产品") },
  { field: "affected_versions", label: t("受影响版本") },
  { field: "fixed_versions", label: t("修复版本") },
  { field: "remediation", label: t("修复建议") }
];

const rejectReasonOptions = [
  { label: t("证据不足"), value: t("证据不足") },
  { label: t("来源不可信"), value: t("来源不可信") },
  { label: t("版本范围疑似错误"), value: t("版本范围疑似错误") },
  { label: t("与官方公告冲突"), value: t("与官方公告冲突") }
];

function displayValue(value?: string | number | null) {
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

function hasValue(value?: string | null) {
  return Boolean(value?.trim());
}

function confidenceValue(value?: number | null) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "-";
}

function statusTag(status: VulnerabilityAIEnrichmentStatus) {
  return <Tag color={statusColors[status]}>{statusLabels[status] ?? status}</Tag>;
}

function evidenceTitle(item: VulnerabilityAIEnrichmentEvidence) {
  const label = fieldRows.find((row) => row.field === item.field)?.label ?? item.field;
  return (
    <Space size={6} wrap>
      <Tag>{label}</Tag>
      {item.source_type ? (
        <Typography.Text type="secondary">{item.source_type}</Typography.Text>
      ) : null}
      {typeof item.confidence === "number" ? (
        <Typography.Text type="secondary">{confidenceValue(item.confidence)}</Typography.Text>
      ) : null}
    </Space>
  );
}

function vulnerabilityValue(
  vulnerability: VulnerabilityDetail,
  field: VulnerabilityAIEnrichmentAcceptField
) {
  return vulnerability[field];
}

function aiValue(
  enrichment: VulnerabilityAIEnrichment,
  field: VulnerabilityAIEnrichmentAcceptField
) {
  return enrichment[field];
}

function defaultSelectedFields(
  vulnerability: VulnerabilityDetail,
  enrichment?: VulnerabilityAIEnrichment
) {
  if (!enrichment || enrichment.status !== "pending_review") {
    return [];
  }
  return fieldRows
    .filter(
      (row) =>
        !hasValue(vulnerabilityValue(vulnerability, row.field)) &&
        hasValue(aiValue(enrichment, row.field))
    )
    .map((row) => row.field);
}

function enrichmentItems(enrichment: VulnerabilityAIEnrichment) {
  return [
    { key: "status", label: t("状态"), children: statusTag(enrichment.status) },
    {
      key: "confidence",
      label: t("置信度"),
      children: confidenceValue(enrichment.confidence)
    },
    {
      key: "created",
      label: t("生成时间"),
      children: formatDateTime(enrichment.created_at)
    },
    { key: "model", label: t("模型"), children: displayValue(enrichment.model) }
  ];
}

interface AiEnrichmentPanelProps {
  vulnerability: VulnerabilityDetail;
}

export default function AiEnrichmentPanel({ vulnerability }: AiEnrichmentPanelProps) {
  const [messageApi, contextHolder] = message.useMessage();
  const queryClient = useQueryClient();
  const vulnerabilityId = vulnerability.canonical_id || vulnerability.id;
  const queryKey = ["vulnerabilities", "ai-enrichments", vulnerabilityId] as const;
  const [selectedFields, setSelectedFields] = useState<
    VulnerabilityAIEnrichmentAcceptField[]
  >([]);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectPreset, setRejectPreset] = useState<string | undefined>();
  const [rejectCustomReason, setRejectCustomReason] = useState("");

  const enrichmentsQuery = useQuery({
    queryKey,
    queryFn: () => getVulnerabilityAIEnrichments(vulnerabilityId),
    enabled: Boolean(vulnerabilityId)
  });
  const enrichments = enrichmentsQuery.data ?? [];
  const latest = enrichments[0];
  const profilesQuery = useQuery({
    queryKey: ["ai", "profiles"],
    queryFn: getAIProfiles
  });
  const webProfile = profilesQuery.data?.find(
    (profile) => profile.profile_key === "web_enrichment_profile"
  );
  const canUseWebProfile = Boolean(
    webProfile?.enabled && (webProfile.supports_web_search || webProfile.allow_external_network)
  );

  useEffect(() => {
    setSelectedFields(defaultSelectedFields(vulnerability, latest));
  }, [latest?.id, latest?.status, vulnerability.id]);

  const canReject =
    latest &&
    !["accepted", "auto_accepted", "already_applied", "rejected"].includes(latest.status);
  const rejectReason = (rejectCustomReason.trim() || rejectPreset || "").trim();

  const comparisonRows = useMemo(
    () =>
      fieldRows.map((row) => ({
        ...row,
        currentValue: vulnerabilityValue(vulnerability, row.field),
        aiValue: latest ? aiValue(latest, row.field) : null
      })),
    [latest, vulnerability]
  );

  const triggerMutation = useMutation({
    mutationFn: () =>
      triggerVulnerabilityAIEnrichment(vulnerabilityId, {
        layer: "existing_data_extraction",
        async_mode: false
      }),
    onSuccess: (payload) => {
      if (payload.enrichment) {
        messageApi.success(t("AI 补全候选已生成"));
      } else if (payload.async_queued) {
        messageApi.success(t("AI 补全任务已提交"));
      }
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("AI 补全失败"));
    }
  });

  const webMutation = useMutation({
    mutationFn: () =>
      triggerVulnerabilityAIEnrichment(vulnerabilityId, {
        layer: "web_enrichment",
        async_mode: false,
        allow_web_enrichment: true
      }),
    onSuccess: (payload) => {
      if (payload.enrichment?.status === "pending_review") {
        messageApi.success(t("联网补充候选已生成"));
      } else {
        messageApi.info(t("联网补充已完成"));
      }
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("联网补充失败"));
    }
  });

  const acceptMutation = useMutation({
    mutationFn: () =>
      acceptVulnerabilityAIEnrichment(latest?.id ?? "", {
        fields: selectedFields,
        allow_overwrite: false
      }),
    onSuccess: (payload) => {
      messageApi.success(t("AI 补全结果已采纳"));
      if (payload.matching_reevaluation_recommended) {
        messageApi.info(t("建议重新评估相关匹配结果"));
      }
      void queryClient.invalidateQueries({ queryKey });
      void queryClient.invalidateQueries({ queryKey: ["vulnerabilities"] });
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("采纳失败"));
    }
  });

  const rejectMutation = useMutation({
    mutationFn: () =>
      rejectVulnerabilityAIEnrichment(latest?.id ?? "", {
        reason: rejectReason
      }),
    onSuccess: () => {
      messageApi.success(t("AI 补全结果已拒绝"));
      setRejectOpen(false);
      setRejectPreset(undefined);
      setRejectCustomReason("");
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("拒绝失败"));
    }
  });

  function toggleField(field: VulnerabilityAIEnrichmentAcceptField, checked: boolean) {
    setSelectedFields((current) =>
      checked
        ? [...current.filter((item) => item !== field), field]
        : current.filter((item) => item !== field)
    );
  }

  return (
    <Card
      className="content-card"
      title={
        <Space>
          <Bot size={18} />
          {t("AI 补全")}</Space>
      }
      extra={
        <Space>
          <Button
            icon={<Sparkles size={16} />}
            type="primary"
            onClick={() => triggerMutation.mutate()}
            loading={triggerMutation.isPending}
          >
            {t("从已有情报补全")}</Button>
          <Button
            icon={<Sparkles size={16} />}
            onClick={() => webMutation.mutate()}
            loading={webMutation.isPending}
            disabled={!canUseWebProfile}
          >
            {t("联网补充")}</Button>
          <Button
            icon={<RefreshCw size={16} />}
            onClick={() => enrichmentsQuery.refetch()}
            loading={enrichmentsQuery.isFetching}
          >
            {t("刷新")}</Button>
        </Space>
      }
    >
      {contextHolder}
      {enrichmentsQuery.isLoading ? <LoadingBlock /> : null}
      {enrichmentsQuery.isError ? <ErrorState error={enrichmentsQuery.error} /> : null}
      {!enrichmentsQuery.isLoading && !latest ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t("暂无 AI 补全结果")} />
      ) : null}
      {latest ? (
        <Space className="page-stack" orientation="vertical" size={14}>
          {latest.status === "failed" && latest.error_message ? (
            <Alert type="error" showIcon message={latest.error_message} />
          ) : null}
          <Descriptions
            bordered
            size="small"
            column={{ xs: 1, md: 2 }}
            items={enrichmentItems(latest)}
          />
          {latest.status === "already_applied" ? (
            <Alert
              type="success"
              showIcon
              message={t("无需变更")}
              description={t("候选字段已由正式来源写入漏洞主记录，未产生新的待处理变更。")}
            />
          ) : null}
          <List
            size="small"
            header={<Typography.Text strong>{t("字段对比")}</Typography.Text>}
            dataSource={comparisonRows}
            renderItem={(row) => {
              const selectable =
                latest.status === "pending_review" && hasValue(row.aiValue);
              return (
                <List.Item>
                  <Space align="start" size={12}>
                    <Checkbox
                      checked={selectedFields.includes(row.field)}
                      disabled={!selectable}
                      onChange={(event) => toggleField(row.field, event.target.checked)}
                    />
                    <Space orientation="vertical" size={3}>
                      <Typography.Text strong>{row.label}</Typography.Text>
                      <Typography.Text type="secondary">
                        {t("当前：")}{displayValue(row.currentValue)}
                      </Typography.Text>
                      <Typography.Text>AI：{displayValue(row.aiValue)}</Typography.Text>
                    </Space>
                  </Space>
                </List.Item>
              );
            }}
          />
          <List
            size="small"
            header={<Typography.Text strong>{t("证据")}</Typography.Text>}
            dataSource={latest.evidence}
            locale={{ emptyText: t("暂无证据") }}
            renderItem={(item) => (
              <List.Item>
                <Space orientation="vertical" size={4}>
                  {evidenceTitle(item)}
                  {item.quote ? <Typography.Text>{item.quote}</Typography.Text> : null}
                  {item.source_url ? (
                    <Typography.Link href={item.source_url} target="_blank" rel="noreferrer">
                      {item.source_url}
                    </Typography.Link>
                  ) : null}
                </Space>
              </List.Item>
            )}
          />
          {latest.source_urls.length ? (
            <Space size={[6, 6]} wrap>
              {latest.source_urls.map((url) => (
                <Typography.Link key={url} href={url} target="_blank" rel="noreferrer">
                  <Tag color="blue">{url}</Tag>
                </Typography.Link>
              ))}
            </Space>
          ) : null}
          <Space>
            <Button
              type="primary"
              icon={<Check size={16} />}
              disabled={latest.status !== "pending_review" || !selectedFields.length}
              loading={acceptMutation.isPending}
              onClick={() => acceptMutation.mutate()}
            >
              {t("采纳所选字段")}</Button>
            <Button
              icon={<X size={16} />}
              disabled={!canReject}
              onClick={() => setRejectOpen(true)}
            >
              {t("拒绝")}</Button>
          </Space>
        </Space>
      ) : null}
      <Modal
        title={t("拒绝 AI 补全结果")}
        open={rejectOpen}
        okText={t("确认拒绝")}
        cancelText={t("取消")}
        okButtonProps={{
          danger: true,
          disabled: !rejectReason,
          loading: rejectMutation.isPending
        }}
        onOk={() => rejectMutation.mutate()}
        onCancel={() => setRejectOpen(false)}
        destroyOnHidden
      >
        <Space className="page-stack" orientation="vertical" size={12}>
          <Select
            allowClear
            placeholder={t("选择拒绝原因")}
            options={rejectReasonOptions}
            value={rejectPreset}
            onChange={setRejectPreset}
            style={{ width: "100%" }}
          />
          <Input.TextArea
            rows={4}
            placeholder={t("补充说明")}
            value={rejectCustomReason}
            onChange={(event) => setRejectCustomReason(event.target.value)}
          />
        </Space>
      </Modal>
    </Card>
  );
}

import { t } from "@/app/i18n";
import { useEffect, useMemo, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  Activity,
  Bot,
  CheckCircle2,
  CircleAlert,
  FlaskConical,
  RefreshCw,
  Save,
  Settings2,
  Trash2
} from "lucide-react";

import {
  aiEnrichmentStatsQueryKey,
  aiProfilesQueryKey,
  deleteAIProfile,
  getAIEnrichmentStats,
  getAIProfiles,
  testAIProfile,
  updateAIProfile
} from "@/api/ai";
import { getPlatformSettings, updatePlatformSettings } from "@/api/platformSettings";
import { createVulnerabilityAIEnrichmentBatch } from "@/api/vulnerabilities";
import type {
  AIEnrichmentProfileStats,
  AIProfile,
  AIProfileUpdate,
  PlatformSettingsUpdate
} from "@/api/types";
import { platformSettingsQueryKey } from "@/app/platformSettings";
import ErrorState from "@/components/ErrorState";
import PageHeader from "@/components/PageHeader";
import { formatDateTime } from "@/utils/format";

type AIProfileFormValues = AIProfileUpdate & {
  profile_key: string;
  display_name: string;
  provider: string;
  model_vendor: string;
  model: string;
  enabled: boolean;
  supports_web_search: boolean;
  allow_external_network: boolean;
  json_mode: boolean;
  timeout_seconds: number;
  temperature: number;
  api_key?: string | null;
};

const providerOptions = [
  { label: t("Fake 测试 Provider"), value: "fake" },
  { label: "OpenAI Compatible", value: "openai_compatible" }
];

const modelVendorOptions = [
  { label: "OpenAI", value: "openai" },
  { label: "KIMI", value: "kimi" }
];

const profileLayerOptions = [
  { label: t("AI识别补全"), value: "basic_extraction_profile" },
  { label: t("AI联网补全"), value: "web_enrichment_profile" }
];

const profileLayerLabelMap = new Map(
  profileLayerOptions.map((option) => [option.value, option.label])
);
const profileLayerDescriptionMap = new Map([
  [
    "basic_extraction_profile",
    t("由大模型对已获取的漏洞信息进行进一步结构化提取，对没有标准格式的漏洞信息源效果较佳。")
  ],
  [
    "web_enrichment_profile",
    t("由大模型结合联网搜索补充漏洞信息，适合本地情报缺少影响版本、修复版本或厂商公告证据时使用。")
  ]
]);
const profileDescriptionSourceValues = new Set([
  "由大模型对已获取的漏洞信息进行进一步结构化提取，对没有标准格式的漏洞信息源效果较佳。",
  "由大模型结合联网搜索补充漏洞信息，适合本地情报缺少影响版本、修复版本或厂商公告证据时使用。"
]);

function profileDisplayName(value: string) {
  return profileDescriptionSourceValues.has(value) ? t(value) : value;
}

const modelVendorLabelMap = new Map(
  modelVendorOptions.map((option) => [option.value, option.label])
);
const aiSettingsHint =
  t("AI Profile 是 AI 能力层的底座配置。第一层和第二层可以绑定不同模型，后续漏洞补全不会向 AI 发送资产清单或匹配结果。");

const defaultFormValues: AIProfileFormValues = {
  profile_key: "basic_extraction_profile",
  display_name:
    profileLayerDescriptionMap.get("basic_extraction_profile") ?? t("源信息快速提取"),
  provider: "fake",
  model_vendor: "openai",
  base_url: null,
  api_key: null,
  model: "fake-json-model",
  enabled: true,
  supports_web_search: false,
  allow_external_network: false,
  json_mode: true,
  timeout_seconds: 30,
  max_tokens: null,
  temperature: 0,
  daily_call_limit: null,
  daily_token_limit: null
};

const defaultAutomationValues: PlatformSettingsUpdate = {
  ai_enabled: true,
  ai_auto_enrich_enabled: false,
  ai_auto_accept_enabled: false,
  ai_auto_accept_policy: "moderate",
  ai_auto_accept_confidence: 0.85,
  ai_web_auto_accept_confidence: 0.8,
  ai_layer2_daily_limit: 50,
  ai_batch_max_size: 100,
  ai_allow_web_enrichment_default: false
};

function formatRate(value?: number | null) {
  return value === null || value === undefined ? "-" : `${Math.round(value * 100)}%`;
}

function profileLayerLabel(profileKey: string) {
  return profileLayerLabelMap.get(profileKey) ?? t("未绑定能力层");
}

function modelVendorLabel(modelVendor: string) {
  return modelVendorLabelMap.get(modelVendor) ?? modelVendor;
}

function profileToForm(profile: AIProfile): AIProfileFormValues {
  return {
    profile_key: profile.profile_key,
    display_name: profile.display_name,
    provider: profile.provider,
    model_vendor: profile.model_vendor,
    base_url: profile.base_url,
    api_key: null,
    model: profile.model,
    enabled: profile.enabled,
    supports_web_search: profile.supports_web_search,
    allow_external_network: profile.allow_external_network,
    json_mode: profile.json_mode,
    timeout_seconds: profile.timeout_seconds,
    max_tokens: profile.max_tokens,
    temperature: profile.temperature,
    daily_call_limit: profile.daily_call_limit,
    daily_token_limit: profile.daily_token_limit,
    prompt_template: profile.prompt_template
      ? {
          system_prompt: profile.prompt_template.system_prompt,
          user_prompt_template: profile.prompt_template.user_prompt_template,
          output_contract: profile.prompt_template.output_contract
        }
      : undefined
  };
}

function promptTemplatePayload(values: AIProfileFormValues): AIProfileUpdate["prompt_template"] {
  const promptTemplate = values.prompt_template;
  if (!promptTemplate) {
    return null;
  }
  return {
    system_prompt: promptTemplate.system_prompt.trim(),
    user_prompt_template: promptTemplate.user_prompt_template.trim(),
    output_contract: promptTemplate.output_contract.trim()
  };
}

function promptTemplateRules(label: string) {
  return [
    {
      validator: async (_: unknown, value?: string | null) => {
        if (!value || !value.trim()) {
          throw new Error(t("请输入{{v0}}", { v0: label }));
        }
      }
    }
  ];
}

function compactUpdatePayload(values: AIProfileFormValues): AIProfileUpdate {
  const payload: AIProfileUpdate = {
    profile_key: values.profile_key,
    display_name: values.display_name,
    provider: values.provider,
    model_vendor: values.model_vendor,
    base_url: values.base_url || null,
    model: values.model,
    enabled: values.enabled,
    supports_web_search: values.supports_web_search,
    allow_external_network: values.allow_external_network,
    json_mode: values.json_mode,
    timeout_seconds: values.timeout_seconds,
    max_tokens: values.max_tokens || null,
    temperature: values.temperature,
    daily_call_limit: values.daily_call_limit || null,
    daily_token_limit: values.daily_token_limit || null,
    prompt_template: promptTemplatePayload(values)
  };
  if (values.api_key && values.api_key.trim()) {
    payload.api_key = values.api_key.trim();
  }
  return payload;
}

export default function AiSettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<AIProfileFormValues>();
  const [automationForm] = Form.useForm<PlatformSettingsUpdate>();
  const [messageApi, contextHolder] = message.useMessage();
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [profileSettingsOpen, setProfileSettingsOpen] = useState(false);
  const [testResult, setTestResult] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const profilesQuery = useQuery({
    queryKey: aiProfilesQueryKey,
    queryFn: getAIProfiles
  });
  const platformSettingsQuery = useQuery({
    queryKey: platformSettingsQueryKey,
    queryFn: getPlatformSettings
  });
  const statsQuery = useQuery({
    queryKey: aiEnrichmentStatsQueryKey,
    queryFn: getAIEnrichmentStats,
    refetchInterval: 60_000
  });
  const profiles = useMemo(() => profilesQuery.data ?? [], [profilesQuery.data]);
  const selectedProfile = profiles.find((profile) => profile.id === selectedProfileId);
  const stats = statsQuery.data;
  const selectedPromptTemplate = selectedProfile?.prompt_template ?? null;

  useEffect(() => {
    if (selectedProfile) {
      form.setFieldsValue(profileToForm(selectedProfile));
      return;
    }
    form.setFieldsValue(defaultFormValues);
  }, [form, selectedProfile]);

  useEffect(() => {
    automationForm.setFieldsValue({
      ...defaultAutomationValues,
      ...(platformSettingsQuery.data ?? {})
    });
  }, [automationForm, platformSettingsQuery.data]);

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AIProfileUpdate }) =>
      updateAIProfile(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aiProfilesQueryKey });
      messageApi.success(t("AI Profile 已保存"));
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("保存 AI Profile 失败"));
    }
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAIProfile,
    onSuccess: () => {
      setSelectedProfileId(null);
      setProfileSettingsOpen(false);
      setTestResult(null);
      form.setFieldsValue(defaultFormValues);
      queryClient.invalidateQueries({ queryKey: aiProfilesQueryKey });
      queryClient.invalidateQueries({ queryKey: aiEnrichmentStatsQueryKey });
      messageApi.success(t("AI Profile 已删除"));
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("删除 AI Profile 失败"));
    }
  });

  const testMutation = useMutation({
    mutationFn: testAIProfile,
    onSuccess: (result) => {
      setTestResult({
        type: result.success ? "success" : "error",
        text: result.success
          ? t("连接测试成功，模型 {{v0}}，耗时 {{v1}} ms", { v0: result.model, v1: result.latency_ms ?? 0 })
          : t("连接测试失败：{{v0}}", { v0: result.error_message || result.status })
      });
      if (result.success) {
        messageApi.success(t("AI Profile 连接测试成功"));
      } else {
        messageApi.error(t("AI Profile 连接测试失败"));
      }
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("连接测试失败"));
    }
  });

  const automationMutation = useMutation({
    mutationFn: updatePlatformSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(platformSettingsQueryKey, data);
      messageApi.success(t("AI 自动化设置已保存"));
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("保存 AI 自动化设置失败"));
    }
  });

  const forceWebBatchMutation = useMutation({
    mutationFn: () =>
      createVulnerabilityAIEnrichmentBatch({
        filters: {
          match_readiness: "needs_enrichment",
          missing_affected_versions: true,
          missing_fixed_versions: false
        },
        layer: "web_enrichment",
        limit: 100,
        allow_web_enrichment: true,
        async_mode: true,
        force_refresh: true
      }),
    onSuccess: (result) => {
      messageApi.success(t("强制联网补全任务已创建，选中 {{v0}} 条", { v0: result.selected_count }));
      void queryClient.invalidateQueries({ queryKey: ["task-center"] });
      void queryClient.invalidateQueries({ queryKey: ["vulnerabilities"] });
      void queryClient.invalidateQueries({ queryKey: aiEnrichmentStatsQueryKey });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("强制联网补全任务创建失败"));
    }
  });

  const statsColumns: ColumnsType<AIEnrichmentProfileStats> = [
    {
      title: "Profile",
      dataIndex: "profile_key",
      render: (value: string | null, record) => value || record.model || "-"
    },
    {
      title: t("调用"),
      dataIndex: "call_count",
      width: 86
    },
    {
      title: "Token",
      dataIndex: "token_count",
      width: 96
    },
    {
      title: t("失败"),
      dataIndex: "failed_count",
      width: 76,
      render: (value: number) => (value ? <Tag color="red">{value}</Tag> : <Tag>0</Tag>)
    }
  ];

  const columns: ColumnsType<AIProfile> = [
    {
      title: t("配置能力层"),
      dataIndex: "profile_key",
      width: 170,
      render: (_, profile) => (
        <Space direction="vertical" size={2}>
          <Typography.Text strong>{profileLayerLabel(profile.profile_key)}</Typography.Text>
          {!profileLayerLabelMap.has(profile.profile_key) ? (
            <Typography.Text type="secondary">{profile.profile_key}</Typography.Text>
          ) : null}
        </Space>
      )
    },
    {
      title: t("功能解释"),
      dataIndex: "display_name",
      render: (value: string) => (
        <Typography.Text type="secondary">
          {value ? profileDisplayName(value) : "-"}
        </Typography.Text>
      )
    },
    {
      title: "Provider",
      dataIndex: "model_vendor",
      width: 140,
      render: (modelVendor: string) => (
        <Tag color={modelVendor === "kimi" ? "blue" : undefined}>
          {modelVendorLabel(modelVendor)}
        </Tag>
      )
    },
    {
      title: t("实际模型"),
      dataIndex: "model",
      width: 190,
      render: (model: string) => (
        <Typography.Text type="secondary">{model || "-"}</Typography.Text>
      )
    },
    {
      title: t("能力"),
      width: 180,
      render: (_, profile) => (
        <Space wrap size={4}>
          {profile.enabled ? <Tag color="green">{t("启用")}</Tag> : <Tag>{t("停用")}</Tag>}
          {profile.json_mode && <Tag color="blue">JSON</Tag>}
          {profile.supports_web_search && <Tag color="purple">{t("联网")}</Tag>}
        </Space>
      )
    },
    {
      title: t("更新时间"),
      dataIndex: "updated_at",
      width: 190,
      render: (value: string) => formatDateTime(value)
    },
    {
      title: t("操作"),
      width: 96,
      align: "right",
      render: (_, profile) => (
        <Button
          size="small"
          icon={<Settings2 size={15} />}
          onClick={(event) => {
            event.stopPropagation();
            setSelectedProfileId(profile.id);
            setProfileSettingsOpen(true);
            setTestResult(null);
          }}
        >
          {t("设置")}</Button>
      )
    }
  ];

  function applyProfileLayerSelection(profileKey: string) {
    const layerDescription = profileLayerDescriptionMap.get(profileKey);
    const currentDisplayName = form.getFieldValue("display_name");
    const generatedNames = new Set([
      ...profileLayerOptions.map((option) => option.label),
      ...profileLayerDescriptionMap.values(),
      t("基础漏洞情报抽取"),
      t("源信息快速提取"),
      t("联网漏洞情报补全"),
      t("联网搜索补充"),
      t("联网搜索")
    ]);
    if (layerDescription && (!currentDisplayName || generatedNames.has(currentDisplayName))) {
      form.setFieldValue("display_name", layerDescription);
    }
    if (profileKey === "web_enrichment_profile") {
      form.setFieldsValue({ supports_web_search: true });
    }
    if (profileKey === "basic_extraction_profile") {
      form.setFieldsValue({
        supports_web_search: false,
        allow_external_network: false
      });
    }
  }

  function submit(values: AIProfileFormValues) {
    setTestResult(null);
    if (selectedProfileId) {
      updateMutation.mutate({
        id: selectedProfileId,
        payload: compactUpdatePayload(values)
      });
    }
  }

  function submitAutomation(values: PlatformSettingsUpdate) {
    automationMutation.mutate(values);
  }

  return (
    <Space className="page-stack ai-settings-page" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title={t("AI 补全设置")}
        titleExtra={
          <Tooltip title={aiSettingsHint} placement="right">
            <Button
              aria-label={t("AI 补全设置说明")}
              className="page-title-help-button"
              icon={<CircleAlert size={16} />}
              shape="circle"
              type="text"
            />
          </Tooltip>
        }
      />

      <div className="ai-ops-grid">
        <Card
          className="content-card"
          title={
            <Space size={8}>
              <Settings2 size={18} />
              <span>{t("AI功能设置")}</span>
            </Space>
          }
          extra={
            <Button
              icon={<RefreshCw size={16} />}
              onClick={() => platformSettingsQuery.refetch()}
              loading={platformSettingsQuery.isFetching}
            />
          }
        >
          <Form<PlatformSettingsUpdate>
            form={automationForm}
            layout="vertical"
            requiredMark={false}
            initialValues={defaultAutomationValues}
            onFinish={submitAutomation}
          >
            <div className="ai-automation-switches">
              <Form.Item label={t("AI 总开关")} name="ai_enabled" valuePropName="checked">
                <Switch checkedChildren={t("启用")} unCheckedChildren={t("停用")} />
              </Form.Item>
              <Form.Item
                label={t("采集后自动投递")}
                name="ai_auto_enrich_enabled"
                valuePropName="checked"
              >
                <Switch checkedChildren={t("启用")} unCheckedChildren={t("停用")} />
              </Form.Item>
              <Form.Item
                label={t("默认联网兜底")}
                name="ai_allow_web_enrichment_default"
                valuePropName="checked"
              >
                <Switch checkedChildren={t("允许")} unCheckedChildren={t("禁止")} />
              </Form.Item>
              <Form.Item
                label={t("高置信自动采纳")}
                name="ai_auto_accept_enabled"
                valuePropName="checked"
              >
                <Switch checkedChildren={t("启用")} unCheckedChildren={t("停用")} />
              </Form.Item>
            </div>
            <div className="form-inline-grid">
              <Form.Item label={t("自动采纳策略")} name="ai_auto_accept_policy">
                <Select
                  options={[
                    { label: t("严格模式（字段证据完整）"), value: "strict" },
                    { label: t("适中模式（产品与版本）"), value: "moderate" },
                    { label: t("宽松模式（仅产品即可匹配）"), value: "relaxed" }
                  ]}
                />
              </Form.Item>
              <Form.Item label={t("自动采纳阈值")} name="ai_auto_accept_confidence">
                <InputNumber min={0} max={1} step={0.01} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item label={t("联网自动采纳阈值")} name="ai_web_auto_accept_confidence">
                <InputNumber min={0} max={1} step={0.01} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item label={t("二层日上限")} name="ai_layer2_daily_limit">
                <InputNumber min={1} max={10000} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item label={t("批量最大数")} name="ai_batch_max_size">
                <InputNumber min={1} max={500} style={{ width: "100%" }} />
              </Form.Item>
            </div>
            <Space className="ai-settings-actions" wrap>
              <Button
                type="primary"
                htmlType="submit"
                icon={<Save size={16} />}
                loading={automationMutation.isPending}
              >
                {t("保存AI设置")}</Button>
              <Popconfirm
                title={t("强制重新联网补全")}
                description={t("会跳过已有 AI 补全缓存，对当前待补全漏洞重新发起联网补全，可能消耗较多 Token。")}
                okText={t("开始")}
                cancelText={t("取消")}
                okButtonProps={{
                  danger: true,
                  loading: forceWebBatchMutation.isPending
                }}
                onConfirm={() => forceWebBatchMutation.mutate()}
              >
                <Button
                  danger
                  icon={<RefreshCw size={16} />}
                  loading={forceWebBatchMutation.isPending}
                >
                  {t("强制重新联网补全")}</Button>
              </Popconfirm>
            </Space>
          </Form>
        </Card>

        <Card
          className="content-card"
          title={
            <Space size={8}>
              <Activity size={18} />
              <span>{t("今日 AI 概览")}</span>
            </Space>
          }
          extra={
            <Button
              icon={<RefreshCw size={16} />}
              onClick={() => statsQuery.refetch()}
              loading={statsQuery.isFetching}
            />
          }
        >
          {statsQuery.isError ? <ErrorState error={statsQuery.error} /> : null}
          <Row gutter={[12, 12]} className="ai-stats-grid">
            <Col xs={12} md={6}>
              <Statistic title={t("调用")} value={stats?.today_call_count ?? 0} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title="Token" value={stats?.today_token_count ?? 0} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title={t("一层成功率")} value={formatRate(stats?.layer1_success_rate)} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title={t("二层成功率")} value={formatRate(stats?.layer2_success_rate)} />
            </Col>
          </Row>
          <Space className="ai-status-strip" wrap size={8}>
            <Tag color="blue" icon={<CircleAlert size={13} />}>
              {t("待复核")}{stats?.pending_review_count ?? 0}
            </Tag>
            <Tag color="green" icon={<CheckCircle2 size={13} />}>
              {t("已采纳")}{stats?.accepted_count ?? 0}
            </Tag>
            <Tag color="cyan" icon={<CheckCircle2 size={13} />}>
              {t("自动采纳")}{stats?.auto_accepted_count ?? 0}
            </Tag>
            <Tag color="red">{t("失败")}{stats?.failed_count ?? 0}</Tag>
            <Tag>{t("不足")}{stats?.insufficient_count ?? 0}</Tag>
          </Space>
          <Table<AIEnrichmentProfileStats>
            className="ai-stats-profile-table"
            rowKey={(record) => record.profile_id || record.profile_key || record.model || "unknown"}
            size="small"
            columns={statsColumns}
            dataSource={stats?.by_profile ?? []}
            loading={statsQuery.isLoading}
            pagination={false}
          />
        </Card>
      </div>

      {profilesQuery.isError ? (
        <ErrorState
          title={t("AI Profile 加载失败")}
          error={profilesQuery.error}
        />
      ) : (
        <div className="settings-grid">
          <Card
            className="content-card"
            title={
              <Space size={8}>
                <Bot size={18} />
                <span>{t("AI能力设置")}</span>
              </Space>
            }
            extra={
              <Space>
                <Button
                  icon={<RefreshCw size={16} />}
                  onClick={() => profilesQuery.refetch()}
                />
              </Space>
            }
          >
            <Table<AIProfile>
              rowKey="id"
              size="middle"
              columns={columns}
              dataSource={profiles}
              loading={profilesQuery.isLoading}
              pagination={false}
            />
          </Card>
        </div>
      )}

      {selectedProfile ? (
        <Modal
          className="profile-settings-modal"
          width={980}
          footer={null}
          open={profileSettingsOpen}
          onCancel={() => setProfileSettingsOpen(false)}
          title={
            <Space size={8} wrap>
              <Settings2 size={18} />
              <span>{t("配置 AI 能力")}</span>
              <Tag>{profileLayerLabel(selectedProfile.profile_key)}</Tag>
            </Space>
          }
        >
          <Form<AIProfileFormValues>
            form={form}
            layout="vertical"
            requiredMark={false}
            initialValues={defaultFormValues}
            onFinish={submit}
          >
            <div className="profile-settings-section">
              <Typography.Text className="profile-settings-section-title" strong>
                {t("基础信息")}</Typography.Text>
              <div className="profile-settings-main-grid">
                <Form.Item
                  label={t("配置能力层")}
                  name="profile_key"
                  rules={[{ required: true, message: t("请选择配置能力层") }]}
                >
                  <Select
                    options={profileLayerOptions}
                    onChange={applyProfileLayerSelection}
                  />
                </Form.Item>

                <Form.Item
                  label={t("展示名称")}
                  name="display_name"
                  rules={[{ required: true, message: t("请输入展示名称") }]}
                >
                  <Input maxLength={128} />
                </Form.Item>

                <Form.Item
                  label="Provider"
                  name="provider"
                  rules={[{ required: true, message: t("请选择 Provider") }]}
                >
                  <Select options={providerOptions} />
                </Form.Item>

                <Form.Item
                  label={t("大模型厂商")}
                  name="model_vendor"
                  rules={[{ required: true, message: t("请选择大模型厂商") }]}
                >
                  <Select options={modelVendorOptions} />
                </Form.Item>

                <Form.Item
                  className="profile-field-wide"
                  label={t("模型")}
                  name="model"
                  rules={[{ required: true, message: t("请输入模型名") }]}
                >
                  <Input maxLength={128} />
                </Form.Item>
              </div>
            </div>

            <div className="profile-settings-section">
              <Typography.Text className="profile-settings-section-title" strong>
                {t("连接信息")}</Typography.Text>
              <div className="profile-settings-main-grid">
                <Form.Item
                  className="profile-field-wide"
                  label="Base URL"
                  name="base_url"
                  tooltip={t("OpenAI Compatible Provider 使用，例如 https://api.example.com/v1")}
                >
                  <Input placeholder={t("仅 OpenAI Compatible 需要")} />
                </Form.Item>

                <Form.Item
                  className="profile-field-wide"
                  label={selectedProfile.has_api_key ? t("API Key（留空则保持不变）") : "API Key"}
                  name="api_key"
                >
                  <Input.Password autoComplete="new-password" />
                </Form.Item>
              </div>
            </div>

            <div className="profile-settings-section">
              <Typography.Text className="profile-settings-section-title" strong>
                {t("运行限制")}</Typography.Text>
              <div className="profile-settings-limit-grid">
                <Form.Item label={t("超时（秒）")} name="timeout_seconds">
                  <InputNumber min={1} max={300} />
                </Form.Item>
                <Form.Item label={t("输出上限")} name="max_tokens">
                  <InputNumber min={1} max={100000} placeholder={t("不限")} />
                </Form.Item>
                <Form.Item label={t("温度")} name="temperature">
                  <InputNumber min={0} max={2} step={0.1} />
                </Form.Item>
                <Form.Item label={t("日调用上限")} name="daily_call_limit">
                  <InputNumber min={1} placeholder={t("不限")} />
                </Form.Item>
                <Form.Item label={t("日 Token 上限")} name="daily_token_limit">
                  <InputNumber min={1} placeholder={t("不限")} />
                </Form.Item>
              </div>
            </div>

            <Divider className="profile-settings-divider" />
            <div className="profile-settings-section">
              <Space className="profile-prompt-title-row" size={8} wrap>
                <Typography.Text className="profile-settings-section-title" strong>
                  {t("当前 Profile 提示词")}</Typography.Text>
                {selectedPromptTemplate?.customized ? <Tag color="blue">{t("已自定义")}</Tag> : <Tag>{t("默认模板")}</Tag>}
              </Space>
              {selectedPromptTemplate ? (
                <div className="profile-prompt-edit-grid">
                  <Form.Item
                    label="System Prompt"
                    name={["prompt_template", "system_prompt"]}
                    rules={promptTemplateRules("System Prompt")}
                  >
                    <Input.TextArea className="prompt-edit-textarea" rows={7} />
                  </Form.Item>
                  <Form.Item
                    label={t("User Prompt 模板")}
                    name={["prompt_template", "user_prompt_template"]}
                    rules={promptTemplateRules(t("User Prompt 模板"))}
                    tooltip={t("可使用 {output_contract} 和 {enrichment_input_json} 占位符")}
                  >
                    <Input.TextArea className="prompt-edit-textarea" rows={8} />
                  </Form.Item>
                  <Form.Item
                    className="profile-field-wide"
                    label={t("输出契约")}
                    name={["prompt_template", "output_contract"]}
                    rules={promptTemplateRules(t("输出契约"))}
                  >
                    <Input.TextArea className="prompt-edit-textarea" rows={8} />
                  </Form.Item>
                </div>
              ) : (
                <Alert
                  type="info"
                  showIcon
                  message={t("当前 Profile 暂未绑定平台内置提示词模板")}
                />
              )}
            </div>

            <div className="profile-settings-control-row">
              <div className="profile-settings-switch-panel">
                <Typography.Text className="profile-settings-section-title" strong>
                  {t("能力开关")}</Typography.Text>
                <Space className="profile-settings-switch-row" wrap size={18}>
                  <Form.Item name="enabled" valuePropName="checked">
                    <Switch checkedChildren={t("启用")} unCheckedChildren={t("停用")} />
                  </Form.Item>
                  <Form.Item name="json_mode" valuePropName="checked">
                    <Switch checkedChildren="JSON" unCheckedChildren={t("普通")} />
                  </Form.Item>
                  <Form.Item name="supports_web_search" valuePropName="checked">
                    <Switch checkedChildren={t("支持联网")} unCheckedChildren={t("无联网")} />
                  </Form.Item>
                  <Form.Item name="allow_external_network" valuePropName="checked">
                    <Switch checkedChildren={t("允许外联")} unCheckedChildren={t("禁止外联")} />
                  </Form.Item>
                </Space>
              </div>

              <Space wrap className="profile-action-row">
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<Save size={16} />}
                  loading={
                    updateMutation.isPending ||
                    deleteMutation.isPending
                  }
                >
                  {t("保存 Profile")}</Button>
                <Button
                  icon={<FlaskConical size={16} />}
                  disabled={!selectedProfileId}
                  loading={testMutation.isPending}
                  onClick={() => {
                    if (selectedProfileId) {
                      testMutation.mutate(selectedProfileId);
                    }
                  }}
                >
                  {t("测试连接")}</Button>
                <Popconfirm
                  title={t("删除 AI Profile")}
                  description={t("删除后会保留历史调用和补全记录，但这条 Profile 配置会被移除。")}
                  okText={t("确认删除")}
                  cancelText={t("取消")}
                  okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
                  onConfirm={() => {
                    if (selectedProfileId) {
                      deleteMutation.mutate(selectedProfileId);
                    }
                  }}
                >
                  <Button
                    danger
                    icon={<Trash2 size={16} />}
                    disabled={!selectedProfileId}
                    loading={deleteMutation.isPending}
                  >
                    {t("删除 Profile")}</Button>
                </Popconfirm>
              </Space>
            </div>

            {testResult && (
              <Alert className="profile-settings-result" showIcon message={testResult.text} type={testResult.type} />
            )}
          </Form>
        </Modal>
      ) : null}
    </Space>
  );
}

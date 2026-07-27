import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  message,
  Modal,
  Pagination,
  Select,
  Space,
  Switch,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Eye, PlayCircle, RefreshCw, RotateCcw, Settings } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import {
  evaluateMatchResults,
  getMatchResults,
  reevaluateMatchResult
} from "@/api/matchResults";
import { getPlatformSettings, updatePlatformSettings } from "@/api/platformSettings";
import type {
  MatchEvaluationResponse,
  MatchResultsQuery,
  MatchResultSummary,
  PlatformSettingsUpdate
} from "@/api/types";
import { platformSettingsQueryKey } from "@/app/platformSettings";
import ConfidenceBar from "@/components/ConfidenceBar";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import RiskPriorityTag from "@/components/RiskPriorityTag";
import StatusTag from "@/components/StatusTag";
import { VerificationTaskStatusTag } from "@/components/ValueTags";
import { formatDateTime, formatScore } from "@/utils/format";

const statusOptions = [
  { label: "受影响", value: "affected" },
  { label: "不受影响", value: "not_affected" },
  { label: "待复核", value: "needs_review" },
  { label: "已验证", value: "verified" },
  { label: "已抑制", value: "suppressed" }
];

const DEFAULT_PAGE_SIZE = 10;

function normalizeFilters(values: MatchResultsQuery): MatchResultsQuery {
  return {
    ...(values.risk_code?.trim() ? { risk_code: values.risk_code.trim() } : {}),
    ...(values.status ? { status: values.status } : {}),
    ...(values.asset_id ? { asset_id: values.asset_id.trim() } : {}),
    ...(values.vulnerability_id
      ? { vulnerability_id: values.vulnerability_id.trim() }
      : {})
  };
}

interface EvaluateFormValues {
  asset_id?: string;
  vulnerability_id?: string;
}

interface AutoMatchSettingsFormValues {
  auto_match_on_new_asset: boolean;
  auto_match_on_new_vulnerability: boolean;
}

function normalizeEvaluation(values: EvaluateFormValues) {
  return {
    asset_id: values.asset_id?.trim() || null,
    vulnerability_id: values.vulnerability_id?.trim() || null
  };
}

export default function MatchResultsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [filterForm] = Form.useForm<MatchResultsQuery>();
  const [evaluateForm] = Form.useForm<EvaluateFormValues>();
  const [autoMatchForm] = Form.useForm<AutoMatchSettingsFormValues>();
  const initialFilters: MatchResultsQuery = {
    ...(searchParams.get("risk_code")
      ? { risk_code: searchParams.get("risk_code") ?? undefined }
      : {}),
    ...(searchParams.get("asset_id")
      ? { asset_id: searchParams.get("asset_id") ?? undefined }
      : {}),
    ...(searchParams.get("vulnerability_id")
      ? { vulnerability_id: searchParams.get("vulnerability_id") ?? undefined }
      : {})
  };
  const [filters, setFilters] = useState<MatchResultsQuery>(initialFilters);
  const [evaluationResult, setEvaluationResult] =
    useState<MatchEvaluationResponse | null>(null);
  const [autoSettingsOpen, setAutoSettingsOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const matchResultsQuery = useQuery({
    queryKey: ["match-results", "list", filters, currentPage, pageSize],
    queryFn: () =>
      getMatchResults({
        ...filters,
        offset: (currentPage - 1) * pageSize,
        limit: pageSize
      })
  });
  const platformSettingsQuery = useQuery({
    queryKey: platformSettingsQueryKey,
    queryFn: getPlatformSettings
  });

  useEffect(() => {
    setCurrentPage(1);
  }, [filters]);

  const matchResultsPage = matchResultsQuery.data;
  const rows = matchResultsPage?.items ?? [];
  const total = matchResultsPage?.total ?? rows.length;

  const evaluateMutation = useMutation({
    mutationFn: (values: EvaluateFormValues) =>
      evaluateMatchResults(normalizeEvaluation(values)),
    onSuccess: (result) => {
      setEvaluationResult(result);
      messageApi.success(`匹配评估完成，生成 ${result.evaluated_count} 条结果`);
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "匹配评估失败");
    }
  });

  const reevaluateMutation = useMutation({
    mutationFn: reevaluateMatchResult,
    onSuccess: (result) => {
      messageApi.success(`已重评估 ${result.vulnerability_canonical_id}`);
      void queryClient.invalidateQueries({ queryKey: ["match-results"] });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "重评估失败");
    }
  });

  const updateAutoSettingsMutation = useMutation({
    mutationFn: (values: AutoMatchSettingsFormValues) =>
      updatePlatformSettings({
        auto_match_on_new_asset: values.auto_match_on_new_asset,
        auto_match_on_new_vulnerability: values.auto_match_on_new_vulnerability
      } satisfies PlatformSettingsUpdate),
    onSuccess: (settings) => {
      messageApi.success("自动比对设置已保存");
      setAutoSettingsOpen(false);
      queryClient.setQueryData(platformSettingsQueryKey, settings);
      void queryClient.invalidateQueries({ queryKey: platformSettingsQueryKey });
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "自动比对设置保存失败");
    }
  });

  function openAutoSettings() {
    const settings = platformSettingsQuery.data;
    autoMatchForm.setFieldsValue({
      auto_match_on_new_asset: Boolean(settings?.auto_match_on_new_asset),
      auto_match_on_new_vulnerability: Boolean(settings?.auto_match_on_new_vulnerability)
    });
    setAutoSettingsOpen(true);
  }

  function submitEvaluation(values: EvaluateFormValues) {
    const normalized = normalizeEvaluation(values);
    if (!normalized.asset_id && !normalized.vulnerability_id) {
      Modal.confirm({
        title: "确认执行全量匹配评估？",
        content: "未填写资产或漏洞范围时，后端会对当前资产和漏洞进行全量评估。",
        okText: "执行评估",
        cancelText: "取消",
        onOk: () => evaluateMutation.mutate(values)
      });
      return;
    }

    evaluateMutation.mutate(values);
  }

  const columns: ColumnsType<MatchResultSummary> = [
    {
      title: "风险编号",
      dataIndex: "risk_code",
      width: 205,
      render: (value: string | null) =>
        value ? (
          <Typography.Text
            className="risk-business-code"
            copyable={{ text: value }}
          >
            {value}
          </Typography.Text>
        ) : (
          <Typography.Text type="secondary">未进入风险队列</Typography.Text>
        )
    },
    {
      title: "漏洞",
      dataIndex: "vulnerability_title",
      minWidth: 280,
      render: (_: string, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(`/matching/${record.id}`)}>
            {record.vulnerability_canonical_id}
          </Typography.Link>
          <Typography.Text className="table-subtitle" ellipsis>
            {record.vulnerability_title}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "资产",
      dataIndex: "asset_hostname",
      width: 190,
      render: (_: string, record) => (
        <Typography.Link onClick={() => navigate(`/assets/${record.asset_id}`)}>
          {record.asset_hostname}
        </Typography.Link>
      )
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 120,
      render: (value: MatchResultSummary["status"]) => <StatusTag value={value} />
    },
    {
      title: "置信度",
      dataIndex: "confidence",
      width: 150,
      render: (value: number) => <ConfidenceBar value={value} />
    },
    {
      title: "风险分",
      dataIndex: "risk_score",
      width: 100,
      sorter: (a, b) => a.risk_score - b.risk_score,
      render: (value: number) => <span className="risk-score">{formatScore(value)}</span>
    },
    {
      title: "优先级",
      dataIndex: "risk_priority",
      width: 110,
      render: (value: MatchResultSummary["risk_priority"]) => (
        <RiskPriorityTag value={value} />
      )
    },
    {
      title: "验证",
      key: "verification",
      width: 140,
      render: (_, record) =>
        record.latest_verification_task_status ? (
          <VerificationTaskStatusTag value={record.latest_verification_task_status} />
        ) : (
          "-"
        )
    },
    {
      title: "最近评估",
      dataIndex: "last_evaluated_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 170,
      render: (_, record) => (
        <Space className="table-actions" size={2}>
          <Button
            type="link"
            icon={<Eye size={15} />}
            onClick={() => navigate(`/matching/${record.id}`)}
          >
            详情
          </Button>
          <Button
            type="link"
            icon={<RotateCcw size={15} />}
            onClick={() => reevaluateMutation.mutate(record.id)}
            loading={reevaluateMutation.isPending}
          >
            重评估
          </Button>
        </Space>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title="漏洞比对"
        extra={
          <Space>
            <Button
              icon={<Settings size={16} />}
              onClick={openAutoSettings}
              loading={platformSettingsQuery.isFetching}
            >
              自动比对设置
            </Button>
            <Button icon={<BookOpen size={16} />} onClick={() => navigate("/rules#rules")}>
              规则说明
            </Button>
            <Button
              icon={<RefreshCw size={16} />}
              onClick={() => matchResultsQuery.refetch()}
              loading={matchResultsQuery.isFetching}
            >
              刷新
            </Button>
          </Space>
        }
      />

      <Card className="content-card filter-card" title="手动评估">
        <Form
          className="matching-inline-form"
          form={evaluateForm}
          layout="inline"
          initialValues={initialFilters}
          onFinish={submitEvaluation}
        >
          <Form.Item label="资产" name="asset_id">
            <Input allowClear placeholder="资产 ID 或 Agent ID" />
          </Form.Item>
          <Form.Item label="漏洞" name="vulnerability_id">
            <Input allowClear placeholder="漏洞 ID 或 CVE" />
          </Form.Item>
          <Form.Item className="matching-form-actions">
            <Space>
              <Button
                onClick={() => {
                  evaluateForm.resetFields();
                  setEvaluationResult(null);
                }}
                disabled={evaluateMutation.isPending}
              >
                重置
              </Button>
              <Button
                type="primary"
                htmlType="submit"
                icon={<PlayCircle size={16} />}
                loading={evaluateMutation.isPending}
              >
                触发评估
              </Button>
            </Space>
          </Form.Item>
        </Form>

        {evaluationResult ? (
          <Alert
            className="task-alert"
            type={evaluationResult.status === "completed" ? "success" : "info"}
            showIcon
            title={`评估状态：${evaluationResult.status}`}
            description={
              <Space orientation="vertical" size={4}>
                <Typography.Text>
                  评估结果数：{evaluationResult.evaluated_count}
                </Typography.Text>
                {evaluationResult.result_ids.length ? (
                  <Space size={[8, 4]} wrap>
                    {evaluationResult.result_ids.slice(0, 8).map((id) => (
                      <Typography.Link
                        key={id}
                        onClick={() => navigate(`/matching/${id}`)}
                      >
                        {id.slice(0, 8)}
                      </Typography.Link>
                    ))}
                    {evaluationResult.result_ids.length > 8 ? (
                      <Typography.Text type="secondary">
                        +{evaluationResult.result_ids.length - 8}
                      </Typography.Text>
                    ) : null}
                  </Space>
                ) : null}
              </Space>
            }
          />
        ) : null}
      </Card>

      <Card className="content-card filter-card">
        <Form
          className="matching-inline-form"
          form={filterForm}
          layout="inline"
          initialValues={initialFilters}
          onFinish={(values) => setFilters(normalizeFilters(values))}
        >
          <Form.Item label="风险编号" name="risk_code">
            <Input allowClear placeholder="RISK-260717-000001" />
          </Form.Item>
          <Form.Item label="状态" name="status">
            <Select allowClear options={statusOptions} placeholder="全部状态" />
          </Form.Item>
          <Form.Item label="资产" name="asset_id">
            <Input allowClear placeholder="资产 ID 或 Agent ID" />
          </Form.Item>
          <Form.Item label="漏洞" name="vulnerability_id">
            <Input allowClear placeholder="漏洞 ID 或 CVE" />
          </Form.Item>
          <Form.Item className="matching-form-actions">
            <Space>
              <Button
                onClick={() => {
                  filterForm.resetFields();
                  setFilters({});
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

      <Card className="content-card" title="匹配结果列表">
        {matchResultsQuery.isError ? <ErrorState error={matchResultsQuery.error} /> : null}
        <ResizableTable<MatchResultSummary>
          storageKey="match-results"
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={matchResultsQuery.isFetching}
          pagination={false}
          locale={{
            emptyText: (
              <EmptyState title="暂无匹配结果">
                <Button
                  type="primary"
                  icon={<PlayCircle size={16} />}
                  onClick={() => submitEvaluation(evaluateForm.getFieldsValue())}
                  loading={evaluateMutation.isPending}
                >
                  执行匹配评估
                </Button>
              </EmptyState>
            )
          }}
          scroll={{ x: 1320 }}
        />
        <Space style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
          <Pagination
            current={currentPage}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            showTotal={(value) => `共 ${value} 条`}
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
      <Modal
        title="自动比对设置"
        open={autoSettingsOpen}
        okText="保存"
        cancelText="取消"
        confirmLoading={updateAutoSettingsMutation.isPending}
        onCancel={() => setAutoSettingsOpen(false)}
        onOk={() => autoMatchForm.submit()}
      >
        {platformSettingsQuery.isError ? (
          <ErrorState title="自动比对设置加载失败" error={platformSettingsQuery.error} />
        ) : null}
        <Form<AutoMatchSettingsFormValues>
          form={autoMatchForm}
          layout="vertical"
          initialValues={{
            auto_match_on_new_asset: false,
            auto_match_on_new_vulnerability: false
          }}
          onFinish={(values) => updateAutoSettingsMutation.mutate(values)}
        >
          <Form.Item
            label="新增资产时自动进行全漏洞比对"
            name="auto_match_on_new_asset"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
          <Form.Item
            label="新增可开始匹配漏洞时自动进行全资产比对"
            name="auto_match_on_new_vulnerability"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

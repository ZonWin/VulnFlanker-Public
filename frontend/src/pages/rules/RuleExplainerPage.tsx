import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  message,
  Space,
  Table,
  Tag,
  Timeline,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  Boxes,
  Calculator,
  CheckCircle2,
  Database,
  ExternalLink,
  FileSearch,
  Filter,
  Flag,
  GitBranch,
  HelpCircle,
  Layers3,
  Network,
  PackageSearch,
  Puzzle,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router";

import {
  getRuleNumericConfig,
  resetRuleNumericConfig,
  updateRuleNumericConfig
} from "@/api/ruleConfig";
import type { NestedNumericMap, RuleNumericConfig } from "@/api/types";
import PageHeader from "@/components/PageHeader";

interface RuleConfidenceRow {
  key: string;
  scenario: string;
  status: string;
  confidenceKey: string;
  defaultConfidence: number;
  confidence?: string;
}

interface MatchingRule {
  name: string;
  ruleName: string;
  codeName: string;
  codePath: string;
  icon: typeof PackageSearch;
  color: string;
  summary: string;
  rows: RuleConfidenceRow[];
}

interface FactorRow {
  key: string;
  factor: string;
  source: string;
  value: string;
  weight: string;
}

interface EditableNestedRow {
  key: string;
  group: string;
  field: string;
  label: string;
  codePath: string;
}

interface EditableFlatRow {
  key: string;
  field: string;
  label: string;
  codePath: string;
}

const statusColorMap: Record<string, string> = {
  affected: "red",
  not_affected: "green",
  needs_review: "orange",
  not_applicable: "default",
  verified: "blue"
};

const defaultMatchingConfidences: NestedNumericMap = {
  product_rule: {
    missing_product: 0.2,
    no_candidate: 0.82,
    matched: 0.78
  },
  version_rule: {
    no_observed_version: 0.35,
    exact_affected: 0.78,
    no_machine_readable_range: 0.45,
    affected_range: 0.82,
    uncertain_comparison: 0.5,
    safe_range: 0.86
  },
  os_rule: {
    not_applicable: 0,
    matched: 0.72,
    not_matched: 0.84
  },
  feature_rule: {
    not_applicable: 0,
    matched: 0.62,
    missing_observed: 0.42
  },
  exposure_rule: {
    not_applicable: 0,
    local_listening: 0.55,
    no_public_exposure: 0.8,
    public_exposure: 0.76
  },
  pipeline: {
    no_conclusive_result: 0.3
  }
};

const defaultRiskFactorValues: NestedNumericMap = {
  exploitability: {
    kev: 8,
    poc: 6.5,
    wild_exploitation: 9,
    epss_multiplier: 10,
    default: 0
  },
  exposure: {
    public_exposure: 10,
    internet: 8,
    public: 8,
    external: 8,
    dmz: 6,
    default: 0
  },
  business_criticality: {
    low: 2,
    medium: 5,
    high: 8,
    critical: 10,
    default: 5
  },
  verification: {
    verified: 10,
    verification_pending: 5,
    verification_failed: 3,
    affected: 2,
    needs_review: 1,
    unverified: 1,
    default: 1
  },
  asset_freshness: {
    fresh: 10,
    stale: 6,
    critical: 2,
    unknown: 0
  }
};

const defaultRiskWeights: Record<string, number> = {
  severity: 0.3,
  exploitability: 0.18,
  exposure: 0.15,
  business_criticality: 0.17,
  confidence: 0.08,
  verification: 0.07,
  asset_freshness: 0.05
};

const defaultPriorityThresholds: Record<string, number> = {
  critical: 8.5,
  high: 7,
  medium: 4,
  low: 0.01
};

const matchingRules: MatchingRule[] = [
  {
    name: "产品匹配",
    ruleName: "product_rule",
    codeName: "ProductRule",
    codePath: "backend/app/matching/product_rule.py",
    icon: PackageSearch,
    color: "blue",
    summary: "先确认资产组件、服务或系统信息中，是否出现漏洞影响的产品或常见别名。",
    rows: [
      {
        key: "product-missing",
        scenario: "漏洞缺少产品字段",
        status: "needs_review",
        confidenceKey: "missing_product",
        defaultConfidence: 0.2
      },
      {
        key: "product-none",
        scenario: "资产没有匹配产品",
        status: "not_affected",
        confidenceKey: "no_candidate",
        defaultConfidence: 0.82
      },
      {
        key: "product-hit",
        scenario: "命中产品或别名",
        status: "affected",
        confidenceKey: "matched",
        defaultConfidence: 0.78
      }
    ]
  },
  {
    name: "版本匹配",
    ruleName: "version_rule",
    codeName: "VersionRule",
    codePath: "backend/app/matching/version_rule.py",
    icon: FileSearch,
    color: "cyan",
    summary: "在产品命中后比较资产版本、影响版本和修复版本，判断是否落入影响范围。",
    rows: [
      {
        key: "version-no-observed",
        scenario: "没有观测版本",
        status: "needs_review",
        confidenceKey: "no_observed_version",
        defaultConfidence: 0.35
      },
      {
        key: "version-no-range",
        scenario: "没有机器可读版本范围",
        status: "needs_review",
        confidenceKey: "no_machine_readable_range",
        defaultConfidence: 0.45
      },
      {
        key: "version-exact-affected",
        scenario: "影响文本精确点名资产 OS/Kernel 版本",
        status: "affected",
        confidenceKey: "exact_affected",
        defaultConfidence: 0.78
      },
      {
        key: "version-affected",
        scenario: "版本在影响范围内",
        status: "affected",
        confidenceKey: "affected_range",
        defaultConfidence: 0.82
      },
      {
        key: "version-safe",
        scenario: "版本在影响范围外",
        status: "not_affected",
        confidenceKey: "safe_range",
        defaultConfidence: 0.86
      },
      {
        key: "version-uncertain",
        scenario: "发行版回补等导致比较不可靠",
        status: "needs_review",
        confidenceKey: "uncertain_comparison",
        defaultConfidence: 0.5
      }
    ]
  },
  {
    name: "OS 条件",
    ruleName: "os_rule",
    codeName: "OperatingSystemRule",
    codePath: "backend/app/matching/os_rule.py",
    icon: Layers3,
    color: "green",
    summary: "当漏洞声明受影响 OS 时，检查资产平台、系统族和系统版本是否命中。",
    rows: [
      {
        key: "os-none",
        scenario: "漏洞未定义 OS 条件",
        status: "not_applicable",
        confidenceKey: "not_applicable",
        defaultConfidence: 0
      },
      {
        key: "os-hit",
        scenario: "资产 OS 命中",
        status: "affected",
        confidenceKey: "matched",
        defaultConfidence: 0.72
      },
      {
        key: "os-miss",
        scenario: "资产 OS 不在影响范围",
        status: "not_affected",
        confidenceKey: "not_matched",
        defaultConfidence: 0.84
      }
    ]
  },
  {
    name: "功能/模块",
    ruleName: "feature_rule",
    codeName: "FeatureRule",
    codePath: "backend/app/matching/feature_rule.py",
    icon: Puzzle,
    color: "gold",
    summary: "检查资产证据中是否出现漏洞要求的模块或功能开关，例如特定插件、协议或配置。",
    rows: [
      {
        key: "feature-none",
        scenario: "未定义模块/功能条件",
        status: "not_applicable",
        confidenceKey: "not_applicable",
        defaultConfidence: 0
      },
      {
        key: "feature-hit",
        scenario: "观测到必需模块或功能",
        status: "affected",
        confidenceKey: "matched",
        defaultConfidence: 0.62
      },
      {
        key: "feature-unknown",
        scenario: "未观测到，无法确认",
        status: "needs_review",
        confidenceKey: "missing_observed",
        defaultConfidence: 0.42
      }
    ]
  },
  {
    name: "暴露面",
    ruleName: "exposure_rule",
    codeName: "ExposureRule",
    codePath: "backend/app/matching/exposure_rule.py",
    icon: Network,
    color: "purple",
    summary: "当漏洞需要公网可达时，检查匹配服务是否真的暴露在公网。",
    rows: [
      {
        key: "exposure-none",
        scenario: "漏洞不要求公网访问",
        status: "not_applicable",
        confidenceKey: "not_applicable",
        defaultConfidence: 0
      },
      {
        key: "exposure-local",
        scenario: "只有本地监听",
        status: "needs_review",
        confidenceKey: "local_listening",
        defaultConfidence: 0.55
      },
      {
        key: "exposure-miss",
        scenario: "未观察到公网暴露",
        status: "not_affected",
        confidenceKey: "no_public_exposure",
        defaultConfidence: 0.8
      },
      {
        key: "exposure-hit",
        scenario: "存在匹配公网暴露",
        status: "affected",
        confidenceKey: "public_exposure",
        defaultConfidence: 0.76
      }
    ]
  }
];

const dataSources = [
  {
    title: "资产画像",
    code: "assets",
    icon: Database,
    items: ["platform / os_family / os_version", "kernel_version", "exposure_type / criticality"]
  },
  {
    title: "资产组件",
    code: "asset_components",
    icon: Boxes,
    items: ["component_name / component_type", "version / source_type", "install_path"]
  },
  {
    title: "资产暴露面",
    code: "asset_exposures",
    icon: Network,
    items: ["service_name / product / version", "protocol / port / address", "is_public"]
  },
  {
    title: "漏洞信息",
    code: "vulnerabilities",
    icon: ShieldAlert,
    items: ["product / affected_versions", "fixed_versions / notes", "CVSS / EPSS / KEV / PoC"]
  },
  {
    title: "漏洞条件",
    code: "notes JSON",
    icon: Puzzle,
    items: ["affected_os", "requires_module", "requires_feature_flag", "requires_public_access"]
  }
];

const matchingConfidenceRows: EditableNestedRow[] = matchingRules.flatMap((rule) =>
  rule.rows.map((row) => ({
    key: `${rule.ruleName}.${row.confidenceKey}`,
    group: rule.ruleName,
    field: row.confidenceKey,
    label: `${rule.name}：${row.scenario}`,
    codePath: rule.codePath
  }))
);

matchingConfidenceRows.push({
  key: "pipeline.no_conclusive_result",
  group: "pipeline",
  field: "no_conclusive_result",
  label: "Pipeline：没有有效结论",
  codePath: "backend/app/matching/pipeline.py"
});

const riskFactorValueRows: EditableNestedRow[] = [
  {
    key: "exploitability.kev",
    group: "exploitability",
    field: "kev",
    label: "可利用性：CISA KEV 命中",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "exploitability.poc",
    group: "exploitability",
    field: "poc",
    label: "可利用性：公开 PoC",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "exploitability.wild_exploitation",
    group: "exploitability",
    field: "wild_exploitation",
    label: "可利用性：野外利用",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "exploitability.epss_multiplier",
    group: "exploitability",
    field: "epss_multiplier",
    label: "可利用性：EPSS 乘数",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "exploitability.default",
    group: "exploitability",
    field: "default",
    label: "可利用性：默认值",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "exposure.public_exposure",
    group: "exposure",
    field: "public_exposure",
    label: "暴露面：观测到公网暴露",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "exposure.internet",
    group: "exposure",
    field: "internet",
    label: "暴露面：internet",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "exposure.public",
    group: "exposure",
    field: "public",
    label: "暴露面：public",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "exposure.external",
    group: "exposure",
    field: "external",
    label: "暴露面：external",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "exposure.dmz",
    group: "exposure",
    field: "dmz",
    label: "暴露面：dmz",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "exposure.default",
    group: "exposure",
    field: "default",
    label: "暴露面：默认值",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "business_criticality.low",
    group: "business_criticality",
    field: "low",
    label: "资产重要性：low",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "business_criticality.medium",
    group: "business_criticality",
    field: "medium",
    label: "资产重要性：medium",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "business_criticality.high",
    group: "business_criticality",
    field: "high",
    label: "资产重要性：high",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "business_criticality.critical",
    group: "business_criticality",
    field: "critical",
    label: "资产重要性：critical",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "business_criticality.default",
    group: "business_criticality",
    field: "default",
    label: "资产重要性：默认值",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "verification.verified",
    group: "verification",
    field: "verified",
    label: "验证状态：verified",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "verification.verification_pending",
    group: "verification",
    field: "verification_pending",
    label: "验证状态：pending",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "verification.verification_failed",
    group: "verification",
    field: "verification_failed",
    label: "验证状态：failed",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "verification.affected",
    group: "verification",
    field: "affected",
    label: "验证状态：affected 未验证",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "verification.needs_review",
    group: "verification",
    field: "needs_review",
    label: "验证状态：needs_review",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "verification.unverified",
    group: "verification",
    field: "unverified",
    label: "验证状态：unverified",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "verification.default",
    group: "verification",
    field: "default",
    label: "验证状态：默认值",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "asset_freshness.fresh",
    group: "asset_freshness",
    field: "fresh",
    label: "资产新鲜度：24 小时内",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "asset_freshness.stale",
    group: "asset_freshness",
    field: "stale",
    label: "资产新鲜度：7 天内",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "asset_freshness.critical",
    group: "asset_freshness",
    field: "critical",
    label: "资产新鲜度：超过 7 天",
    codePath: "backend/app/services/risk.py"
  },
  {
    key: "asset_freshness.unknown",
    group: "asset_freshness",
    field: "unknown",
    label: "资产新鲜度：无时间戳",
    codePath: "backend/app/services/risk.py"
  }
];

const riskWeightRows: EditableFlatRow[] = Object.keys(defaultRiskWeights).map((field) => ({
  key: field,
  field,
  label: field,
  codePath: "backend/app/services/risk.py"
}));

const priorityThresholdRows: EditableFlatRow[] = [
  { key: "low", field: "low", label: "low 起始阈值", codePath: "backend/app/services/risk.py" },
  { key: "medium", field: "medium", label: "medium 起始阈值", codePath: "backend/app/services/risk.py" },
  { key: "high", field: "high", label: "high 起始阈值", codePath: "backend/app/services/risk.py" },
  {
    key: "critical",
    field: "critical",
    label: "critical 起始阈值",
    codePath: "backend/app/services/risk.py"
  }
];

function nestedValue(
  source: NestedNumericMap | undefined,
  defaults: NestedNumericMap,
  group: string,
  field: string
) {
  return source?.[group]?.[field] ?? defaults[group]?.[field] ?? 0;
}

function flatValue(
  source: Record<string, number> | undefined,
  defaults: Record<string, number>,
  field: string
) {
  return source?.[field] ?? defaults[field] ?? 0;
}

function formatNumber(value: number, digits = 2) {
  return Number(value).toFixed(digits);
}

function buildRiskFactors(config: RuleNumericConfig | null): FactorRow[] {
  const values = config?.risk_factor_values ?? defaultRiskFactorValues;
  const weights = config?.risk_weights ?? defaultRiskWeights;
  return [
    {
      key: "severity",
      factor: "severity",
      source: "漏洞 CVSS",
      value: "直接使用 CVSS，缺失则为 0",
      weight: formatNumber(flatValue(weights, defaultRiskWeights, "severity"))
    },
    {
      key: "exploitability",
      factor: "exploitability",
      source: "KEV / PoC / 野外利用 / EPSS",
      value: `取最大信号：KEV=${nestedValue(values, defaultRiskFactorValues, "exploitability", "kev")}，PoC=${nestedValue(values, defaultRiskFactorValues, "exploitability", "poc")}，野外利用=${nestedValue(values, defaultRiskFactorValues, "exploitability", "wild_exploitation")}，EPSS=epss*${nestedValue(values, defaultRiskFactorValues, "exploitability", "epss_multiplier")}`,
      weight: formatNumber(flatValue(weights, defaultRiskWeights, "exploitability"))
    },
    {
      key: "exposure",
      factor: "exposure",
      source: "资产暴露面",
      value: `公网暴露=${nestedValue(values, defaultRiskFactorValues, "exposure", "public_exposure")}，internet/public/external=${nestedValue(values, defaultRiskFactorValues, "exposure", "internet")}，dmz=${nestedValue(values, defaultRiskFactorValues, "exposure", "dmz")}，其他=${nestedValue(values, defaultRiskFactorValues, "exposure", "default")}`,
      weight: formatNumber(flatValue(weights, defaultRiskWeights, "exposure"))
    },
    {
      key: "business_criticality",
      factor: "business_criticality",
      source: "资产重要性",
      value: `low=${nestedValue(values, defaultRiskFactorValues, "business_criticality", "low")}，medium=${nestedValue(values, defaultRiskFactorValues, "business_criticality", "medium")}，high=${nestedValue(values, defaultRiskFactorValues, "business_criticality", "high")}，critical=${nestedValue(values, defaultRiskFactorValues, "business_criticality", "critical")}`,
      weight: formatNumber(flatValue(weights, defaultRiskWeights, "business_criticality"))
    },
    {
      key: "confidence",
      factor: "confidence",
      source: "匹配置信度",
      value: "匹配置信度 * 10",
      weight: formatNumber(flatValue(weights, defaultRiskWeights, "confidence"))
    },
    {
      key: "verification",
      factor: "verification",
      source: "验证任务与证据",
      value: `verified=${nestedValue(values, defaultRiskFactorValues, "verification", "verified")}，pending=${nestedValue(values, defaultRiskFactorValues, "verification", "verification_pending")}，failed=${nestedValue(values, defaultRiskFactorValues, "verification", "verification_failed")}，affected=${nestedValue(values, defaultRiskFactorValues, "verification", "affected")}，needs_review=${nestedValue(values, defaultRiskFactorValues, "verification", "needs_review")}`,
      weight: formatNumber(flatValue(weights, defaultRiskWeights, "verification"))
    },
    {
      key: "asset_freshness",
      factor: "asset_freshness",
      source: "资产 last_seen_at",
      value: `24 小时内=${nestedValue(values, defaultRiskFactorValues, "asset_freshness", "fresh")}，7 天内=${nestedValue(values, defaultRiskFactorValues, "asset_freshness", "stale")}，超过 7 天=${nestedValue(values, defaultRiskFactorValues, "asset_freshness", "critical")}，无时间戳=${nestedValue(values, defaultRiskFactorValues, "asset_freshness", "unknown")}`,
      weight: formatNumber(flatValue(weights, defaultRiskWeights, "asset_freshness"))
    }
  ];
}

const ruleColumns: ColumnsType<RuleConfidenceRow> = [
  {
    title: "场景",
    dataIndex: "scenario"
  },
  {
    title: "状态",
    dataIndex: "status",
    width: 130,
    render: (value: string) => <Tag color={statusColorMap[value] ?? "blue"}>{value}</Tag>
  },
  {
    title: "置信度",
    dataIndex: "confidence",
    width: 100
  }
];

const factorColumns: ColumnsType<FactorRow> = [
  {
    title: "因子",
    dataIndex: "factor",
    width: 190,
    render: (value: string) => <Typography.Text code>{value}</Typography.Text>
  },
  {
    title: "来源",
    dataIndex: "source",
    width: 220
  },
  {
    title: "取值",
    dataIndex: "value"
  },
  {
    title: "权重",
    dataIndex: "weight",
    width: 90
  }
];

function StatusTagInline({ value }: { value: string }) {
  return <Tag color={statusColorMap[value] ?? "blue"}>{value}</Tag>;
}

function RuleCard({
  rule,
  config
}: {
  rule: MatchingRule;
  config: RuleNumericConfig | null;
}) {
  const RuleIcon = rule.icon;
  const rows = rule.rows.map((row) => ({
    ...row,
    confidence: formatNumber(
      nestedValue(
        config?.matching_confidences,
        defaultMatchingConfidences,
        rule.ruleName,
        row.confidenceKey
      )
    )
  }));
  return (
    <Card
      className="rule-card"
      title={
        <Space>
          <span className={`rule-card-icon rule-card-icon-${rule.color}`}>
            <RuleIcon size={20} />
          </span>
          <span>{rule.name}</span>
        </Space>
      }
    >
      <Typography.Text className="table-subtitle">
        {rule.codeName} · {rule.codePath}
      </Typography.Text>
      <Typography.Paragraph className="rule-summary">{rule.summary}</Typography.Paragraph>
      <Table<RuleConfidenceRow>
        rowKey="key"
        size="small"
        columns={ruleColumns}
        dataSource={rows}
        pagination={false}
      />
    </Card>
  );
}

export default function RuleExplainerPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [draft, setDraft] = useState<RuleNumericConfig | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  const configQuery = useQuery({
    queryKey: ["rule-config"],
    queryFn: getRuleNumericConfig
  });

  useEffect(() => {
    if (configQuery.data) {
      setDraft(configQuery.data);
    }
  }, [configQuery.data]);

  const activeConfig = draft ?? configQuery.data ?? null;
  const riskFactors = useMemo(() => buildRiskFactors(activeConfig), [activeConfig]);
  const activeWeightTotal = useMemo(
    () =>
      Object.values(activeConfig?.risk_weights ?? defaultRiskWeights).reduce(
        (sum, value) => sum + value,
        0
      ),
    [activeConfig]
  );
  const activeWarnings = useMemo(() => {
    const warnings = [...(activeConfig?.warnings ?? [])];
    if (Math.abs(activeWeightTotal - 1) > 0.001) {
      warnings.unshift(
        `当前草稿权重合计 ${activeWeightTotal.toFixed(4)}，建议保持 1.0000`
      );
    }
    return [...new Set(warnings)];
  }, [activeConfig, activeWeightTotal]);

  const saveMutation = useMutation({
    mutationFn: updateRuleNumericConfig,
    onSuccess: (data) => {
      setDraft(data);
      setIsEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["rule-config"] });
      void queryClient.invalidateQueries({ queryKey: ["match-results", "risk-config"] });
      messageApi.success("规则数值配置已保存");
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "规则数值配置保存失败");
    }
  });

  const resetMutation = useMutation({
    mutationFn: resetRuleNumericConfig,
    onSuccess: (data) => {
      setDraft(data);
      setIsEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["rule-config"] });
      void queryClient.invalidateQueries({ queryKey: ["match-results", "risk-config"] });
      messageApi.success("已恢复默认规则数值");
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : "恢复默认配置失败");
    }
  });

  function updateNestedDraft(
    section: "matching_confidences" | "risk_factor_values",
    group: string,
    field: string,
    value: number | null
  ) {
    setDraft((current) => {
      if (!current) {
        return current;
      }
      const nextSection = {
        ...current[section],
        [group]: {
          ...(current[section][group] ?? {}),
          [field]: Number(value ?? 0)
        }
      };
      return { ...current, [section]: nextSection };
    });
  }

  function updateFlatDraft(
    section: "risk_weights" | "risk_priority_thresholds",
    field: string,
    value: number | null
  ) {
    setDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [section]: {
          ...current[section],
          [field]: Number(value ?? 0)
        }
      };
    });
  }

  function saveDraft() {
    if (!draft) {
      return;
    }
    saveMutation.mutate({
      matching_confidences: draft.matching_confidences,
      risk_factor_values: draft.risk_factor_values,
      risk_weights: draft.risk_weights,
      risk_priority_thresholds: draft.risk_priority_thresholds
    });
  }

  function startEditing() {
    Modal.confirm({
      title: "确认编辑规则数值？",
      content:
        "这些数值会影响匹配置信度、风险因子分值、风险评分权重和风险优先级映射，可能改变整体风险分析结果。请确认已理解影响范围后再继续操作。",
      okText: "继续编辑",
      cancelText: "取消",
      onOk: () => setIsEditing(true)
    });
  }

  function cancelEditing() {
    setDraft(configQuery.data ?? null);
    setIsEditing(false);
  }

  const numberInput = (
    value: number,
    onChange: (nextValue: number | null) => void,
    max = 10
  ) => (
    <InputNumber
      min={0}
      max={max}
      step={0.01}
      precision={2}
      value={value}
      disabled={!isEditing}
      onChange={onChange}
    />
  );

  const nestedConfigColumns: ColumnsType<EditableNestedRow> = [
    {
      title: "项目",
      dataIndex: "label",
      width: 260
    },
    {
      title: "key",
      dataIndex: "field",
      width: 190,
      render: (value: string, row) => (
        <Typography.Text code>
          {row.group}.{value}
        </Typography.Text>
      )
    },
    {
      title: "代码文件",
      dataIndex: "codePath",
      width: 250,
      render: (value: string) => <Typography.Text code>{value}</Typography.Text>
    },
    {
      title: "数值",
      dataIndex: "field",
      width: 120,
      render: (_: string, row) =>
        numberInput(
          nestedValue(
            activeConfig?.matching_confidences,
            defaultMatchingConfidences,
            row.group,
            row.field
          ),
          (value) =>
            updateNestedDraft("matching_confidences", row.group, row.field, value),
          1
        )
    }
  ];

  const riskFactorValueColumns: ColumnsType<EditableNestedRow> = [
    {
      title: "项目",
      dataIndex: "label",
      width: 260
    },
    {
      title: "key",
      dataIndex: "field",
      width: 190,
      render: (value: string, row) => (
        <Typography.Text code>
          {row.group}.{value}
        </Typography.Text>
      )
    },
    {
      title: "代码文件",
      dataIndex: "codePath",
      width: 250,
      render: (value: string) => <Typography.Text code>{value}</Typography.Text>
    },
    {
      title: "分值",
      dataIndex: "field",
      width: 120,
      render: (_: string, row) =>
        numberInput(
          nestedValue(
            activeConfig?.risk_factor_values,
            defaultRiskFactorValues,
            row.group,
            row.field
          ),
          (value) =>
            updateNestedDraft("risk_factor_values", row.group, row.field, value)
        )
    }
  ];

  const flatConfigColumns: ColumnsType<EditableFlatRow> = [
    {
      title: "项目",
      dataIndex: "label",
      width: 220
    },
    {
      title: "key",
      dataIndex: "field",
      width: 170,
      render: (value: string) => <Typography.Text code>{value}</Typography.Text>
    },
    {
      title: "代码文件",
      dataIndex: "codePath",
      width: 250,
      render: (value: string) => <Typography.Text code>{value}</Typography.Text>
    },
    {
      title: "数值",
      dataIndex: "field",
      width: 120,
      render: (value: string) =>
        numberInput(
          flatValue(activeConfig?.risk_weights, defaultRiskWeights, value),
          (nextValue) => updateFlatDraft("risk_weights", value, nextValue),
          1
        )
    }
  ];

  const thresholdColumns: ColumnsType<EditableFlatRow> = [
    {
      title: "项目",
      dataIndex: "label",
      width: 220
    },
    {
      title: "key",
      dataIndex: "field",
      width: 170,
      render: (value: string) => <Typography.Text code>{value}</Typography.Text>
    },
    {
      title: "代码文件",
      dataIndex: "codePath",
      width: 250,
      render: (value: string) => <Typography.Text code>{value}</Typography.Text>
    },
    {
      title: "阈值",
      dataIndex: "field",
      width: 120,
      render: (value: string) =>
        numberInput(
          flatValue(
            activeConfig?.risk_priority_thresholds,
            defaultPriorityThresholds,
            value
          ),
          (nextValue) =>
            updateFlatDraft("risk_priority_thresholds", value, nextValue)
        )
    }
  ];

  useEffect(() => {
    if (!location.hash) {
      return;
    }
    window.requestAnimationFrame(() => {
      document
        .getElementById(location.hash.slice(1))
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [location.hash]);

  return (
    <Space className="page-stack rule-explainer-page" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title="规则匹配说明"
        extra={
          <Space wrap>
            <Button icon={<ExternalLink size={16} />} onClick={() => navigate("/matching")}>
              去漏洞比对
            </Button>
            <Button icon={<ShieldCheck size={16} />} onClick={() => navigate("/risk-queue")}>
              去风险队列
            </Button>
          </Space>
        }
      />

      <Alert
        type="info"
        showIcon
        message="一句话理解"
        description="先用规则链判断资产是否受漏洞影响并给出置信度，再结合漏洞严重度、可利用性、资产暴露、重要性、验证状态和资产新鲜度等 7 个因子，生成 0 到 10 的风险分和优先级。"
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card className="content-card explain-band" title="阶段一：匹配规则流水线">
            <div className="flow-strip">
              <div className="flow-node">
                <Database size={24} />
                <strong>数据输入</strong>
                <span>资产画像、组件、暴露面、漏洞条件</span>
              </div>
              <GitBranch className="flow-arrow" size={22} />
              <div className="flow-node">
                <Boxes size={24} />
                <strong>构建上下文</strong>
                <span>生成 MatchContext</span>
              </div>
              <GitBranch className="flow-arrow" size={22} />
              <div className="flow-node">
                <Filter size={24} />
                <strong>规则评估</strong>
                <span>5 条规则依次输出结论</span>
              </div>
              <GitBranch className="flow-arrow" size={22} />
              <div className="flow-node">
                <CheckCircle2 size={24} />
                <strong>结果聚合</strong>
                <span>状态、置信度、原因、证据</span>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card className="content-card explain-band" title="阶段二：风险模型 risk-v2.0">
            <div className="flow-strip">
              <div className="flow-node">
                <Sparkles size={24} />
                <strong>7 个因子</strong>
                <span>漏洞、资产、验证多维信号</span>
              </div>
              <GitBranch className="flow-arrow" size={22} />
              <div className="flow-node">
                <Calculator size={24} />
                <strong>加权计算</strong>
                <span>Σ 因子分 * 权重</span>
              </div>
              <GitBranch className="flow-arrow" size={22} />
              <div className="flow-node">
                <Flag size={24} />
                <strong>风险优先级</strong>
                <span>none / low / medium / high / critical</span>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <section id="rules" className="scroll-section">
        <Typography.Title level={2}>匹配规则流水线</Typography.Title>
        <Typography.Paragraph className="explanation-text">
          每条规则都会输出状态、置信度、原因和证据。状态不是简单投票，而是按阻断、复核、受影响的优先级合并。
        </Typography.Paragraph>
        <Row gutter={[16, 16]}>
          {matchingRules.map((rule) => (
            <Col key={rule.codeName} xs={24} lg={12} xxl={8}>
              <RuleCard rule={rule} config={activeConfig} />
            </Col>
          ))}
        </Row>
      </section>

      <section id="trace" className="scroll-section">
        <Card className="content-card" title="Pipeline 如何合并最终状态与置信度">
          <Timeline
            items={[
              {
                dot: <ShieldAlert size={18} />,
                color: "green",
                children: (
                  <Space direction="vertical" size={4}>
                    <Typography.Text strong>
                      存在阻断型 <StatusTagInline value="not_affected" />？
                    </Typography.Text>
                    <Typography.Text>
                      最终状态为 <StatusTagInline value="not_affected" />，置信度取阻断结果中的最大值。
                    </Typography.Text>
                  </Space>
                )
              },
              {
                dot: <HelpCircle size={18} />,
                color: "orange",
                children: (
                  <Space direction="vertical" size={4}>
                    <Typography.Text strong>
                      否则，存在 <StatusTagInline value="needs_review" />？
                    </Typography.Text>
                    <Typography.Text>
                      最终状态为 <StatusTagInline value="needs_review" />，置信度取 review 结果中的最小值。
                    </Typography.Text>
                  </Space>
                )
              },
              {
                dot: <CheckCircle2 size={18} />,
                color: "red",
                children: (
                  <Space direction="vertical" size={4}>
                    <Typography.Text strong>
                      否则，存在 <StatusTagInline value="affected" />？
                    </Typography.Text>
                    <Typography.Text>
                      最终状态为 <StatusTagInline value="affected" />，置信度取 affected 结果中的最小值。
                    </Typography.Text>
                  </Space>
                )
              },
              {
                dot: <RefreshCw size={18} />,
                color: "blue",
                children: (
                  <Space direction="vertical" size={4}>
                    <Typography.Text strong>没有有效结论</Typography.Text>
                    <Typography.Text>
                      默认进入 <StatusTagInline value="needs_review" />，置信度为 0.30。
                    </Typography.Text>
                  </Space>
                )
              }
            ]}
          />
        </Card>
      </section>

      <section id="risk-factors" className="scroll-section">
        <Card className="content-card" title="风险模型 risk-v2.0 与 7 个风险因子">
          <Space className="risk-formula" direction="vertical" size={10}>
            <Typography.Text strong>
              仅当匹配状态不是 <StatusTagInline value="not_affected" /> 时进入风险计算；否则风险分直接为 0。
            </Typography.Text>
            <pre className="json-block">
              risk_score = Σ(round(factor_value * factor_weight, 2)){"\n"}
              risk_score = min(risk_score, 10.0)
            </pre>
          </Space>
          <Table<FactorRow>
            rowKey="key"
            columns={factorColumns}
            dataSource={riskFactors}
            pagination={false}
            scroll={{ x: 980 }}
          />
        </Card>
      </section>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card className="content-card" title="风险优先级映射">
            <Descriptions
              bordered
              size="small"
              column={1}
              items={[
                { key: "none", label: "none", children: "score = 0" },
                {
                  key: "low",
                  label: "low",
                  children: `${formatNumber(flatValue(activeConfig?.risk_priority_thresholds, defaultPriorityThresholds, "low"))} <= score < ${formatNumber(flatValue(activeConfig?.risk_priority_thresholds, defaultPriorityThresholds, "medium"))}`
                },
                {
                  key: "medium",
                  label: "medium",
                  children: `${formatNumber(flatValue(activeConfig?.risk_priority_thresholds, defaultPriorityThresholds, "medium"))} <= score < ${formatNumber(flatValue(activeConfig?.risk_priority_thresholds, defaultPriorityThresholds, "high"))}`
                },
                {
                  key: "high",
                  label: "high",
                  children: `${formatNumber(flatValue(activeConfig?.risk_priority_thresholds, defaultPriorityThresholds, "high"))} <= score < ${formatNumber(flatValue(activeConfig?.risk_priority_thresholds, defaultPriorityThresholds, "critical"))}`
                },
                {
                  key: "critical",
                  label: "critical",
                  children: `score >= ${formatNumber(flatValue(activeConfig?.risk_priority_thresholds, defaultPriorityThresholds, "critical"))}`
                }
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="content-card" title="示例计算">
            <Descriptions
              bordered
              size="small"
              column={1}
              items={[
                {
                  key: "input",
                  label: "输入",
                  children: "affected、CVSS 6.0、KEV、公网暴露、high 资产、置信度 0.76、未验证、快照超过 7 天"
                },
                {
                  key: "score",
                  label: "风险分",
                  children: "6.95"
                },
                {
                  key: "priority",
                  label: "优先级",
                  children: <Tag color="orange">medium</Tag>
                },
                {
                  key: "fresh",
                  label: "快照新鲜时",
                  children: "asset_freshness 从 2 提升到 10，总分约 7.35，优先级变为 high"
                }
              ]}
            />
          </Card>
        </Col>
      </Row>

      <section id="data-sources" className="scroll-section">
        <Typography.Title level={2}>关键数据来源</Typography.Title>
        <Row gutter={[16, 16]}>
          {dataSources.map((source) => {
            const SourceIcon = source.icon;
            return (
              <Col key={source.code} xs={24} md={12} xl={8} xxl={4}>
                <div className="source-tile">
                  <Space>
                    <SourceIcon size={20} />
                    <Typography.Text strong>{source.title}</Typography.Text>
                  </Space>
                  <Typography.Text code>{source.code}</Typography.Text>
                  <ul>
                    {source.items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              </Col>
            );
          })}
        </Row>
      </section>

      <section id="config" className="scroll-section">
        <Card
          className="content-card"
          title="可配置数值"
          extra={
            <Space wrap>
              <Typography.Text type="secondary">
                权重合计 {formatNumber(activeWeightTotal, 4)}
              </Typography.Text>
              {!isEditing ? (
                <Button type="primary" onClick={startEditing} disabled={!activeConfig}>
                  编辑
                </Button>
              ) : (
                <>
                  <Button
                    type="primary"
                    onClick={saveDraft}
                    loading={saveMutation.isPending}
                    disabled={!activeConfig}
                  >
                    保存配置
                  </Button>
                  <Button onClick={cancelEditing}>取消编辑</Button>
                  <Popconfirm
                    title="恢复默认数值？"
                    okText="恢复"
                    cancelText="取消"
                    onConfirm={() => resetMutation.mutate()}
                  >
                    <Button loading={resetMutation.isPending} disabled={!activeConfig}>
                      恢复默认
                    </Button>
                  </Popconfirm>
                </>
              )}
            </Space>
          }
        >
          <Space direction="vertical" size={16} className="full-width">
            {activeWarnings.length ? (
              <Alert
                type="warning"
                showIcon
                message="配置提示"
                description={activeWarnings.join("；")}
              />
            ) : null}
            <Alert
              type={isEditing ? "warning" : "info"}
              showIcon
              message={
                isEditing
                  ? "当前处于编辑模式。数值调整可能影响整体风险分析，请谨慎保存。"
                  : "数值配置当前为只读状态。点击编辑并确认风险提示后，才能修改置信度赋值、风险因子分值、风险权重和优先级阈值。"
              }
              description="保存后对新评估和重评估生效，已存风险快照需要重评估刷新；规则判断逻辑仍由对应代码文件控制。"
            />
            <Typography.Title level={4}>流水线置信度赋值</Typography.Title>
            <Table<EditableNestedRow>
              rowKey="key"
              size="small"
              loading={configQuery.isLoading}
              columns={nestedConfigColumns}
              dataSource={matchingConfidenceRows}
              pagination={false}
              scroll={{ x: 900 }}
            />
            <Typography.Title level={4}>风险模型因子分值</Typography.Title>
            <Table<EditableNestedRow>
              rowKey="key"
              size="small"
              loading={configQuery.isLoading}
              columns={riskFactorValueColumns}
              dataSource={riskFactorValueRows}
              pagination={{ pageSize: 8, hideOnSinglePage: true }}
              scroll={{ x: 900 }}
            />
            <Typography.Title level={4}>风险评分权重</Typography.Title>
            <Table<EditableFlatRow>
              rowKey="key"
              size="small"
              loading={configQuery.isLoading}
              columns={flatConfigColumns}
              dataSource={riskWeightRows}
              pagination={false}
              scroll={{ x: 760 }}
            />
            <Typography.Title level={4}>风险优先级映射</Typography.Title>
            <Table<EditableFlatRow>
              rowKey="key"
              size="small"
              loading={configQuery.isLoading}
              columns={thresholdColumns}
              dataSource={priorityThresholdRows}
              pagination={false}
              scroll={{ x: 760 }}
            />
          </Space>
        </Card>
      </section>
    </Space>
  );
}

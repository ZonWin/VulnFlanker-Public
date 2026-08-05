import { t } from "@/app/i18n";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Switch,
  Tag,
  Tooltip,
  Typography,
  message
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Ban,
  CircleAlert,
  Download,
  KeyRound,
  Plus,
  RefreshCw,
  Search,
  ServerCog,
  ShieldOff,
  Trash2,
  Wifi
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import {
  createAgentEnrollmentToken,
  deleteAgent,
  disableAgent,
  getAgentEnrollmentTokens,
  getAgents,
  revokeAgentEnrollmentToken
} from "@/api/agents";
import {
  createBusinessSystem,
  createPerson,
  createResponsibilityTeam,
  getBusinessSystems,
  getPeople,
  getResponsibilityTeams,
  updateBusinessSystem,
  updatePerson
} from "@/api/ownership";
import type {
  AgentEnrollmentToken,
  AgentEnrollmentTokenCreateResponse,
  AgentEnrollmentTokenStatus,
  AgentSummary
} from "@/api/types";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import { AgentStatusTag } from "@/components/ValueTags";
import { formatDateTime } from "@/utils/format";
import { useAuth } from "@/app/auth";

interface AgentScriptFormValues {
  agentIngressUrl: string;
  enrollmentToken: string;
  binaryBaseUrl: string;
  sourceArchiveUrl: string;
  agentSourceDir: string;
  installDir: string;
  stateDir: string;
  logDir: string;
  serviceName: string;
  installService: boolean;
  environmentType: string;
  exposureType: string;
  criticality: string;
  businessSystem: string;
  ownerTeam: string;
  ownerPerson: string;
  allowAutoVerify: boolean;
  allowAutoRemediate: boolean;
  heartbeatSeconds: number;
  snapshotSeconds: number;
  taskPollSeconds: number;
  requestTimeoutSeconds: number;
}

interface EnrollmentTokenFormValues {
  name: string;
  expiresAt?: string;
  maxUses?: number | null;
}

interface OwnershipQuickCreateFormValues {
  createTeam: boolean;
  existingTeamId?: string;
  teamCode?: string;
  teamName?: string;
  createPerson: boolean;
  existingPersonId?: string;
  personName?: string;
  employeeNo?: string;
  personEmail?: string;
  createBusinessSystem: boolean;
  existingBusinessSystemId?: string;
  businessSystemCode?: string;
  businessSystemName?: string;
}

type OwnershipQuickCreateSource = "businessSystem" | "ownerTeam" | "ownerPerson";
type ScriptSelectOption = { label: string; value: string };

const DIRECT_CREATE_OPTION_VALUE = "__direct_create__";

const environmentOptions = [
  { label: "production", value: "production" },
  { label: "staging", value: "staging" },
  { label: "development", value: "development" },
  { label: "testing", value: "testing" }
];

const exposureOptions = [
  { label: "internal", value: "internal" },
  { label: "public", value: "public" },
  { label: "dmz", value: "dmz" },
  { label: "restricted", value: "restricted" }
];

const criticalityOptions = [
  { label: "critical", value: "critical" },
  { label: "high", value: "high" },
  { label: "medium", value: "medium" },
  { label: "low", value: "low" }
];

function defaultAgentIngressUrl() {
  const configuredUrl = (import.meta.env.VITE_AGENT_INGRESS_BASE_URL ?? "").replace(/\/$/, "");
  if (configuredUrl) {
    return configuredUrl;
  }
  const url = new URL(window.location.origin);
  if (url.port === "5173") {
    url.port = "8001";
  }
  return url.toString().replace(/\/$/, "");
}

function platformDownloadUrl(agentIngressUrl: string, path: string) {
  return `${agentIngressUrl.replace(/\/$/, "")}${path}`;
}

function defaultAgentScriptValues(): AgentScriptFormValues {
  const agentIngressUrl = defaultAgentIngressUrl();
  return {
    agentIngressUrl,
    enrollmentToken: "",
    binaryBaseUrl: platformDownloadUrl(
      agentIngressUrl,
      "/agent/v1/downloads/vulnflanker-agent-linux"
    ),
    sourceArchiveUrl: platformDownloadUrl(
      agentIngressUrl,
      "/agent/v1/downloads/source.tar.gz"
    ),
    agentSourceDir: "",
    installDir: "/opt/vulnflanker",
    stateDir: "/var/lib/vulnflanker",
    logDir: "/var/log/vulnflanker",
    serviceName: "vulnflanker-agent",
    installService: true,
    environmentType: "production",
    exposureType: "internal",
    criticality: "medium",
    businessSystem: "",
    ownerTeam: "",
    ownerPerson: "",
    allowAutoVerify: true,
    allowAutoRemediate: false,
    heartbeatSeconds: 60,
    snapshotSeconds: 3600,
    taskPollSeconds: 30,
    requestTimeoutSeconds: 10
  };
}

function shellQuote(value: string | number | boolean) {
  return `'${String(value).replace(/'/g, "'\\''")}'`;
}

function systemdEnvironmentLine(key: string, value: string | number | boolean) {
  const escaped = `${key}=${String(value)}`
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"');
  return `Environment="${escaped}"`;
}

function buildAgentScript(values: AgentScriptFormValues) {
  const envEntries: Array<[string, string | number | boolean]> = [
    ["VULNFLANKER_AGENT_INGRESS_URL", values.agentIngressUrl],
    ["VULNFLANKER_SERVER_URL", values.agentIngressUrl],
    ["VULNFLANKER_AGENT_ENROLLMENT_TOKEN", values.enrollmentToken],
    ["VULNFLANKER_AGENT_STATE_DIR", values.stateDir],
    ["VULNFLANKER_AGENT_LOG_DIR", values.logDir],
    ["VULNFLANKER_AGENT_ENVIRONMENT_TYPE", values.environmentType],
    ["VULNFLANKER_AGENT_EXPOSURE_TYPE", values.exposureType],
    ["VULNFLANKER_AGENT_CRITICALITY", values.criticality],
    ["VULNFLANKER_AGENT_BUSINESS_SYSTEM", values.businessSystem],
    ["VULNFLANKER_AGENT_OWNER_TEAM", values.ownerTeam],
    ["VULNFLANKER_AGENT_OWNER_PERSON", values.ownerPerson],
    ["VULNFLANKER_AGENT_ALLOW_AUTO_VERIFY", values.allowAutoVerify],
    ["VULNFLANKER_AGENT_ALLOW_AUTO_REMEDIATE", values.allowAutoRemediate],
    ["VULNFLANKER_AGENT_HEARTBEAT_SECONDS", values.heartbeatSeconds],
    ["VULNFLANKER_AGENT_SNAPSHOT_SECONDS", values.snapshotSeconds],
    ["VULNFLANKER_AGENT_TASK_POLL_SECONDS", values.taskPollSeconds],
    ["VULNFLANKER_AGENT_REQUEST_TIMEOUT_SECONDS", values.requestTimeoutSeconds]
  ];
  const envLines = envEntries
    .map(([key, value]) => `export ${key}=${shellQuote(value)}`)
    .join("\n");
  const systemdEnvLines = envEntries
    .map(([key, value]) => systemdEnvironmentLine(key, value))
    .join("\n");

  return `#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR=${shellQuote(values.installDir)}
SERVICE_NAME=${shellQuote(values.serviceName)}
INSTALL_SERVICE=${shellQuote(values.installService)}
AGENT_SOURCE_DIR=${shellQuote(values.agentSourceDir)}
BINARY_BASE_URL=${shellQuote(values.binaryBaseUrl)}
SOURCE_ARCHIVE_URL=${shellQuote(values.sourceArchiveUrl)}

${envLines}

UPGRADE=false

usage() {
  cat <<USAGE
Usage: $0 [--upgrade]

Options:
  --upgrade   Replace an existing Agent binary, restart systemd service, and roll back on startup failure.
  -h, --help  Show this help.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --upgrade)
      UPGRADE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

run_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "This script needs root permission for installation directories or systemd setup." >&2
    exit 1
  fi
}

download_source() {
  local target_dir="$1"
  local archive="$target_dir/vulnflanker.tar.gz"

  if [ -z "$SOURCE_ARCHIVE_URL" ]; then
    echo "AGENT_SOURCE_DIR is empty and SOURCE_ARCHIVE_URL is not configured." >&2
    exit 1
  fi

  if ! download_file "$SOURCE_ARCHIVE_URL" "$archive"; then
    echo "Failed to download agent source from $SOURCE_ARCHIVE_URL" >&2
    exit 1
  fi

  tar -xzf "$archive" -C "$target_dir"
  find "$target_dir" -maxdepth 3 -type d -path "*/agent" | head -n 1
}

download_file() {
  local url="$1"
  local output="$2"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$output" && return 0
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$url" -O "$output" && return 0
  fi

  rm -f "$output"
  return 1
}

detect_linux_arch() {
  case "$(uname -m)" in
    x86_64|amd64) echo "amd64" ;;
    aarch64|arm64) echo "arm64" ;;
    *) return 1 ;;
  esac
}

build_agent() {
  local build_dir="$1"
  local output="$2"

  if ! command -v go >/dev/null 2>&1; then
    echo "Go 1.22+ is required to build vulnflanker-agent." >&2
    exit 1
  fi

  (cd "$build_dir" && mkdir -p bin && go build -o "$output" ./cmd/vulnflanker-agent)
}

prepare_agent_binary() {
  local output="$1"
  local arch=""

  if [ -n "$BINARY_BASE_URL" ] && arch="$(detect_linux_arch)"; then
    local binary_url="$BINARY_BASE_URL-$arch"
    echo "Trying platform binary $binary_url"
    if download_file "$binary_url" "$output"; then
      chmod +x "$output"
      return 0
    fi
    echo "Platform binary is unavailable for linux-$arch, falling back to source build."
  fi

  if [ -n "$AGENT_SOURCE_DIR" ] && [ -d "$AGENT_SOURCE_DIR" ]; then
    build_agent "$AGENT_SOURCE_DIR" "$output"
  else
    local agent_source
    agent_source="$(download_source "$tmpdir")"
    build_agent "$agent_source" "$output"
  fi

  chmod +x "$output"
}

validate_agent_binary() {
  local binary="$1"

  if ! "$binary" -h 2>&1 | grep -q -- "-agent-ingress-url"; then
    echo "Agent binary at $binary does not support -agent-ingress-url." >&2
    echo "Rebuild platform Agent artifacts, then rerun this script with --upgrade." >&2
    exit 1
  fi
}

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

run_root install -d -m 0755 "$INSTALL_DIR"
run_root install -d -m 0755 "$VULNFLANKER_AGENT_STATE_DIR" "$VULNFLANKER_AGENT_LOG_DIR"

agent_binary="$INSTALL_DIR/vulnflanker-agent"
candidate_binary="$tmpdir/vulnflanker-agent"
backup_binary=""
backup_unit=""
upgraded_binary=false
changed_binary=false
reuse_existing=false
unit_file="/etc/systemd/system/\${SERVICE_NAME}.service"

if [ -x "$agent_binary" ] && [ "$UPGRADE" != "true" ]; then
  echo "Using existing $INSTALL_DIR/vulnflanker-agent"
  reuse_existing=true
else
  if [ -x "$agent_binary" ]; then
    backup_binary="$INSTALL_DIR/vulnflanker-agent.$(date +%Y%m%d%H%M%S).bak"
    echo "Upgrading existing Agent binary; backup will be written to $backup_binary"
  fi

  prepare_agent_binary "$candidate_binary"
  validate_agent_binary "$candidate_binary"
  if [ -n "$backup_binary" ]; then
    run_root cp -p "$agent_binary" "$backup_binary"
    if [ "$INSTALL_SERVICE" = "true" ] && command -v systemctl >/dev/null 2>&1; then
      if [ -f "$unit_file" ]; then
        backup_unit="$INSTALL_DIR/\${SERVICE_NAME}.service.$(date +%Y%m%d%H%M%S).bak"
        run_root cp -p "$unit_file" "$backup_unit"
      fi
    fi
    upgraded_binary=true
  fi
  run_root install -m 0755 "$candidate_binary" "$agent_binary"
  changed_binary=true
fi

echo "Agent binary is ready at $agent_binary"

if [ "$INSTALL_SERVICE" = "true" ] && command -v systemctl >/dev/null 2>&1; then
  if [ "$reuse_existing" = "true" ] && [ -f "$unit_file" ]; then
    echo "Keeping existing $unit_file. Use --upgrade to replace the Agent binary and rewrite the unit."
    if ! run_root systemctl enable --now "$SERVICE_NAME"; then
      run_root systemctl status "$SERVICE_NAME" -l --no-pager || true
      exit 1
    fi
  else
    if [ "$reuse_existing" = "true" ]; then
      validate_agent_binary "$agent_binary"
    fi
    run_root tee "$unit_file" >/dev/null <<UNIT
[Unit]
Description=VulnFlanker Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
${systemdEnvLines}
ExecStart=${values.installDir}/vulnflanker-agent -once=false -agent-ingress-url ${values.agentIngressUrl}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
    run_root systemctl daemon-reload
    run_root systemctl enable "$SERVICE_NAME"
    if [ "$changed_binary" = "true" ]; then
      if ! run_root systemctl restart "$SERVICE_NAME"; then
        if [ "$upgraded_binary" = "true" ] && [ -n "$backup_binary" ] && [ -f "$backup_binary" ]; then
          echo "Agent failed to start after upgrade; rolling back to $backup_binary" >&2
          run_root install -m 0755 "$backup_binary" "$agent_binary"
          if [ -n "$backup_unit" ] && [ -f "$backup_unit" ]; then
            run_root cp -p "$backup_unit" "$unit_file"
            run_root systemctl daemon-reload
            run_root systemctl restart "$SERVICE_NAME"
          else
            run_root rm -f "$unit_file"
            run_root systemctl daemon-reload
            run_root systemctl reset-failed "$SERVICE_NAME" || true
            echo "Rollback restored the previous Agent binary, but no previous systemd unit existed." >&2
            exit 1
          fi
        else
          run_root systemctl status "$SERVICE_NAME" -l --no-pager || true
          exit 1
        fi
      fi
    else
      if ! run_root systemctl enable --now "$SERVICE_NAME"; then
        run_root systemctl status "$SERVICE_NAME" -l --no-pager || true
        exit 1
      fi
    fi
  fi
  run_root systemctl status "$SERVICE_NAME" --no-pager
else
  "$INSTALL_DIR/vulnflanker-agent" -once=false -agent-ingress-url "$VULNFLANKER_AGENT_INGRESS_URL"
fi
`;
}

function tokenSuffix(token?: string | null) {
  const normalized = token?.trim();
  return normalized && normalized.length >= 4 ? normalized.slice(-4) : "";
}

function agentScriptFilename(token?: string | null) {
  const suffix = tokenSuffix(token);
  return suffix
    ? `install-vulnflanker-agent-${suffix}.sh`
    : "install-vulnflanker-agent.sh";
}

function downloadScript(content: string, token?: string | null) {
  const blob = new Blob([content], { type: "text/x-shellscript;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = agentScriptFilename(token);
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function displayValue(value?: string | number | null) {
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

const enrollmentTokenStatusMeta: Record<
  AgentEnrollmentTokenStatus,
  { color: string; label: string }
> = {
  active: { color: "green", label: t("有效") },
  expired: { color: "orange", label: t("已过期") },
  used_up: { color: "blue", label: t("已用完") },
  revoked: { color: "red", label: t("已吊销") }
};

function EnrollmentTokenStatusTag({ value }: { value: AgentEnrollmentTokenStatus }) {
  const meta = enrollmentTokenStatusMeta[value] ?? { color: "default", label: value };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

function tokenUsage(record: AgentEnrollmentToken) {
  if (record.max_uses === null) {
    return t("{{v0}} / 不限", { v0: record.used_count });
  }
  return `${record.used_count} / ${record.max_uses}`;
}

function taskSummary(record: AgentSummary) {
  const stats = record.task_stats;
  if (!stats.total) {
    return "-";
  }
  return t("{{v0}}/{{v1}} 完成", { v0: stats.completed, v1: stats.total });
}

function limitedScriptOptions(
  options: ScriptSelectOption[],
  searchText: string
): ScriptSelectOption[] {
  const normalizedSearch = searchText.trim().toLowerCase();
  const matchedOptions = normalizedSearch
    ? options.filter(
        (option) =>
          option.label.toLowerCase().includes(normalizedSearch) ||
          option.value.toLowerCase().includes(normalizedSearch)
      )
    : options;
  return [
    ...matchedOptions.slice(0, 5),
    { label: t("直接新增"), value: DIRECT_CREATE_OPTION_VALUE }
  ];
}

function matchesAgentSearch(agent: AgentSummary, keyword: string) {
  const terms = keyword
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);

  if (!terms.length) {
    return true;
  }

  const searchableText = [
    agent.agent_id,
    agent.hostname,
    agent.status,
    agent.asset_id,
    agent.asset_hostname,
    agent.asset_primary_ip,
    agent.platform,
    agent.version,
    agent.last_error
  ]
    .filter((value): value is string => Boolean(value))
    .join(" ")
    .toLowerCase();

  return terms.every((term) => searchableText.includes(term));
}

export default function AgentListPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_superuser);
  const [scriptForm] = Form.useForm<AgentScriptFormValues>();
  const [tokenForm] = Form.useForm<EnrollmentTokenFormValues>();
  const [ownershipQuickCreateForm] = Form.useForm<OwnershipQuickCreateFormValues>();
  const [messageApi, contextHolder] = message.useMessage();
  const queryClient = useQueryClient();
  const [scriptModalOpen, setScriptModalOpen] = useState(false);
  const [tokenModalOpen, setTokenModalOpen] = useState(false);
  const [ownershipQuickCreateOpen, setOwnershipQuickCreateOpen] = useState(false);
  const [businessSystemSearchText, setBusinessSystemSearchText] = useState("");
  const [responsibilityTeamSearchText, setResponsibilityTeamSearchText] = useState("");
  const [personSearchText, setPersonSearchText] = useState("");
  const [createdEnrollmentToken, setCreatedEnrollmentToken] =
    useState<AgentEnrollmentTokenCreateResponse | null>(null);
  const [latestEnrollmentToken, setLatestEnrollmentToken] = useState("");
  const [searchText, setSearchText] = useState("");
  const scriptDefaults = useMemo(() => defaultAgentScriptValues(), []);
  const watchedScriptValues = Form.useWatch([], scriptForm) ?? scriptDefaults;
  const scriptPreview = useMemo(
    () => buildAgentScript({ ...scriptDefaults, ...watchedScriptValues }),
    [scriptDefaults, watchedScriptValues]
  );
  const focusedAgentId = searchParams.get("agent_id")?.trim() ?? "";
  const agentsQuery = useQuery({
    queryKey: ["agents", "list"],
    queryFn: getAgents
  });
  const enrollmentTokensQuery = useQuery({
    queryKey: ["agents", "enrollment-tokens"],
    queryFn: getAgentEnrollmentTokens
  });
  const businessSystemsQuery = useQuery({
    queryKey: ["ownership", "systems", "agent-script-options"],
    queryFn: () =>
      getBusinessSystems({
        status: "active",
        page_size: 200,
        sort_by: "name",
        sort_order: "asc"
      })
  });
  const responsibilityTeamsQuery = useQuery({
    queryKey: ["ownership", "teams", "agent-script-options"],
    queryFn: () =>
      getResponsibilityTeams({
        status: "active",
        page_size: 200,
        sort_by: "name",
        sort_order: "asc"
      })
  });
  const peopleQuery = useQuery({
    queryKey: ["ownership", "people", "agent-script-options"],
    queryFn: () =>
      getPeople({
        status: "active",
        page_size: 200,
        sort_by: "name",
        sort_order: "asc"
      })
  });
  const createTokenMutation = useMutation({
    mutationFn: createAgentEnrollmentToken,
    onSuccess: (token) => {
      setCreatedEnrollmentToken(token);
      setLatestEnrollmentToken(token.enrollment_token);
      scriptForm.setFieldsValue({ enrollmentToken: token.enrollment_token });
      void queryClient.invalidateQueries({ queryKey: ["agents", "enrollment-tokens"] });
      messageApi.success(t("注册令牌已创建，请及时复制明文 token"));
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("创建注册令牌失败"));
    }
  });
  const revokeTokenMutation = useMutation({
    mutationFn: revokeAgentEnrollmentToken,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agents", "enrollment-tokens"] });
      messageApi.success(t("注册令牌已吊销"));
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("吊销注册令牌失败"));
    }
  });
  const disableAgentMutation = useMutation({
    mutationFn: disableAgent,
    onSuccess: () => {
      invalidateAgentLifecycleQueries();
      messageApi.success(t("Agent 已禁用，资产数据已保留"));
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("禁用 Agent 失败"));
    }
  });
  const deleteAgentMutation = useMutation({
    mutationFn: deleteAgent,
    onSuccess: () => {
      invalidateAgentLifecycleQueries();
      messageApi.success(t("Agent 和对应资产已删除"));
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("删除 Agent 失败"));
    }
  });
  const quickCreateOwnershipMutation = useMutation({
    mutationFn: async (values: OwnershipQuickCreateFormValues) => {
      const teams = responsibilityTeamsQuery.data?.items ?? [];
      const people = peopleQuery.data?.items ?? [];
      const systems = businessSystemsQuery.data?.items ?? [];

      let teamId = values.existingTeamId ?? "";
      let teamName = "";
      if (values.createTeam) {
        const team = await createResponsibilityTeam({
          code: values.teamCode?.trim() ?? "",
          name: values.teamName?.trim() ?? ""
        });
        teamId = team.id;
        teamName = team.name;
      } else {
        const team = teams.find((item) => item.id === teamId);
        if (!team) {
          throw new Error(t("请选择已有负责团队，或新增团队"));
        }
        teamName = team.name;
      }

      let personId = values.existingPersonId ?? "";
      let personName = "";
      if (values.createPerson) {
        const person = await createPerson({
          name: values.personName?.trim() ?? "",
          employee_no: values.employeeNo?.trim() || null,
          email: values.personEmail?.trim() || null,
          team_id: teamId,
          status: "active"
        });
        personId = person.id;
        personName = person.name;
      } else {
        const person = people.find((item) => item.id === personId);
        if (!person) {
          throw new Error(t("请选择已有负责人，或新增负责人"));
        }
        const updatedPerson =
          person.team.id === teamId
            ? person
            : await updatePerson(person.id, {
                expected_version: person.version,
                team_id: teamId
              });
        personId = updatedPerson.id;
        personName = updatedPerson.name;
      }

      let businessSystemName = "";
      if (values.createBusinessSystem) {
        const system = await createBusinessSystem({
          code: values.businessSystemCode?.trim() ?? "",
          name: values.businessSystemName?.trim() ?? "",
          responsible_person_id: personId,
          status: "active"
        });
        businessSystemName = system.name;
      } else {
        const system = systems.find((item) => item.id === values.existingBusinessSystemId);
        if (!system) {
          throw new Error(t("请选择已有业务系统，或新增业务系统"));
        }
        const updatedSystem =
          system.responsible_person?.id === personId
            ? system
            : await updateBusinessSystem(system.id, {
                expected_version: system.version,
                responsible_person_id: personId
              });
        businessSystemName = updatedSystem.name;
      }

      return {
        businessSystem: businessSystemName,
        ownerPerson: personName,
        ownerTeam: teamName
      };
    },
    onSuccess: (fieldUpdates) => {
      scriptForm.setFieldsValue(fieldUpdates);
      ownershipQuickCreateForm.resetFields();
      setOwnershipQuickCreateOpen(false);
      setBusinessSystemSearchText("");
      setResponsibilityTeamSearchText("");
      setPersonSearchText("");
      void queryClient.invalidateQueries({ queryKey: ["ownership"] });
      messageApi.success(t("归属数据已创建并填入脚本"));
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("归属数据创建失败"));
    }
  });

  const allAgents = agentsQuery.data ?? [];
  const agents = useMemo(
    () =>
      allAgents
        .filter((agent) => !focusedAgentId || agent.agent_id.includes(focusedAgentId))
        .filter((agent) => matchesAgentSearch(agent, searchText)),
    [allAgents, focusedAgentId, searchText]
  );
  const hasAgentFilter = Boolean(focusedAgentId || searchText.trim());
  const metrics = useMemo(
    () => ({
      total: agents.length,
      online: agents.filter((agent) => agent.status === "online").length,
      offline: agents.filter((agent) => agent.status === "offline").length,
      errors: agents.filter((agent) => Boolean(agent.last_error)).length
    }),
    [agents]
  );
  const businessSystemOptions = useMemo(
    () =>
      (businessSystemsQuery.data?.items ?? []).map((system) => ({
        label: `${system.name} (${system.code})`,
        value: system.name
      })),
    [businessSystemsQuery.data]
  );
  const responsibilityTeamOptions = useMemo(
    () =>
      (responsibilityTeamsQuery.data?.items ?? []).map((team) => ({
        label: `${team.name} (${team.code})`,
        value: team.name
      })),
    [responsibilityTeamsQuery.data]
  );
  const personOptions = useMemo(
    () =>
      (peopleQuery.data?.items ?? []).map((person) => ({
        label: [
          person.name,
          person.employee_no ? t("工号 {{v0}}", { v0: person.employee_no }) : null,
          person.team?.name ?? null
        ]
          .filter(Boolean)
          .join(" / "),
        value: person.name
      })),
    [peopleQuery.data]
  );
  const existingBusinessSystemOptions = useMemo(
    () =>
      (businessSystemsQuery.data?.items ?? []).map((system) => ({
        label: `${system.name} (${system.code})`,
        value: system.id
      })),
    [businessSystemsQuery.data]
  );
  const existingResponsibilityTeamOptions = useMemo(
    () =>
      (responsibilityTeamsQuery.data?.items ?? []).map((team) => ({
        label: `${team.name} (${team.code})`,
        value: team.id
      })),
    [responsibilityTeamsQuery.data]
  );
  const existingPersonOptions = useMemo(
    () =>
      (peopleQuery.data?.items ?? []).map((person) => ({
        label: [
          person.name,
          person.employee_no ? t("工号 {{v0}}", { v0: person.employee_no }) : null,
          person.team?.name ?? null
        ]
          .filter(Boolean)
          .join(" / "),
        value: person.id
      })),
    [peopleQuery.data]
  );
  const visibleBusinessSystemOptions = useMemo(
    () => limitedScriptOptions(businessSystemOptions, businessSystemSearchText),
    [businessSystemOptions, businessSystemSearchText]
  );
  const visibleResponsibilityTeamOptions = useMemo(
    () => limitedScriptOptions(responsibilityTeamOptions, responsibilityTeamSearchText),
    [responsibilityTeamOptions, responsibilityTeamSearchText]
  );
  const visiblePersonOptions = useMemo(
    () => limitedScriptOptions(personOptions, personSearchText),
    [personOptions, personSearchText]
  );

  function openOwnershipQuickCreate(source: OwnershipQuickCreateSource) {
    const values = scriptForm.getFieldsValue();
    const selectedTeam = (responsibilityTeamsQuery.data?.items ?? []).find(
      (team) => team.name === values.ownerTeam
    );
    const selectedPerson = (peopleQuery.data?.items ?? []).find(
      (person) => person.name === values.ownerPerson
    );
    const selectedSystem = (businessSystemsQuery.data?.items ?? []).find(
      (system) => system.name === values.businessSystem
    );
    const createTeam = source === "ownerTeam";
    const createPerson = source === "ownerPerson";
    ownershipQuickCreateForm.setFieldsValue({
      createTeam,
      existingTeamId: createTeam ? undefined : selectedTeam?.id,
      teamCode: "",
      teamName: source === "ownerTeam" ? responsibilityTeamSearchText.trim() : "",
      createPerson,
      existingPersonId: createPerson ? undefined : selectedPerson?.id,
      personName: source === "ownerPerson" ? personSearchText.trim() : "",
      employeeNo: "",
      personEmail: "",
      createBusinessSystem: source === "businessSystem",
      existingBusinessSystemId:
        source === "businessSystem" ? undefined : selectedSystem?.id,
      businessSystemCode: "",
      businessSystemName:
        source === "businessSystem" ? businessSystemSearchText.trim() : ""
    });
    setOwnershipQuickCreateOpen(true);
  }

  function handleScriptSelectChange(
    field: "businessSystem" | "ownerTeam" | "ownerPerson",
    source: OwnershipQuickCreateSource,
    value?: string
  ) {
    if (value !== DIRECT_CREATE_OPTION_VALUE) {
      return;
    }
    scriptForm.setFieldValue(field, undefined);
    openOwnershipQuickCreate(source);
  }

  function openScriptModal() {
    scriptForm.setFieldsValue({
      ...scriptDefaults,
      enrollmentToken: latestEnrollmentToken
    });
    setScriptModalOpen(true);
  }

  function openTokenModal() {
    tokenForm.setFieldsValue({
      name: "",
      expiresAt: "",
      maxUses: 1
    });
    setCreatedEnrollmentToken(null);
    setTokenModalOpen(true);
  }

  function invalidateAgentLifecycleQueries() {
    void queryClient.invalidateQueries({ queryKey: ["agents"] });
    void queryClient.invalidateQueries({ queryKey: ["assets"] });
    void queryClient.invalidateQueries({ queryKey: ["match-results"] });
    void queryClient.invalidateQueries({ queryKey: ["verification-tasks"] });
    void queryClient.invalidateQueries({ queryKey: ["task-center"] });
  }

  async function handleScriptDownload() {
    const values = await scriptForm.validateFields();
    downloadScript(
      buildAgentScript({ ...scriptDefaults, ...values }),
      values.enrollmentToken
    );
    messageApi.success(t("Agent 安装脚本已生成"));
    setScriptModalOpen(false);
  }

  async function handleCreateToken() {
    const values = await tokenForm.validateFields();
    createTokenMutation.mutate({
      name: values.name,
      expires_at: values.expiresAt?.trim() ? values.expiresAt : null,
      max_uses: values.maxUses ?? null
    });
  }

  function useCreatedTokenInScript() {
    if (!createdEnrollmentToken) {
      return;
    }
    setLatestEnrollmentToken(createdEnrollmentToken.enrollment_token);
    scriptForm.setFieldsValue({
      ...scriptDefaults,
      enrollmentToken: createdEnrollmentToken.enrollment_token
    });
    setTokenModalOpen(false);
    setScriptModalOpen(true);
  }

  const tokenColumns: ColumnsType<AgentEnrollmentToken> = [
    {
      title: t("名称"),
      dataIndex: "name",
      minWidth: 180,
      render: (value: string, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{value}</Typography.Text>
          <Typography.Text className="table-subtitle">
            ID：{record.id}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: (
        <Space className="table-column-title" size={4}>
          <span>{t("令牌预览")}</span>
          <Tooltip title={t("完整注册令牌仅在创建成功时展示一次；列表中只保留遮蔽预览，无法查看或复制完整令牌。")}>
            <CircleAlert size={14} />
          </Tooltip>
        </Space>
      ),
      dataIndex: "token_preview",
      width: 190,
      render: (value: string | null) => (
        <Typography.Text code>{value ?? t("历史令牌不可预览")}</Typography.Text>
      )
    },
    {
      title: t("状态"),
      dataIndex: "status",
      width: 110,
      render: (value: AgentEnrollmentTokenStatus) => <EnrollmentTokenStatusTag value={value} />
    },
    {
      title: t("使用次数"),
      key: "usage",
      width: 130,
      render: (_, record) => tokenUsage(record)
    },
    {
      title: t("过期时间"),
      dataIndex: "expires_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    {
      title: t("创建时间"),
      dataIndex: "created_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    {
      title: t("创建人"),
      dataIndex: "created_by_display",
      width: 160,
      render: (value: string | null, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{displayValue(value)}</Typography.Text>
          {record.created_by ? (
            <Typography.Text className="table-subtitle">ID：{record.created_by}</Typography.Text>
          ) : null}
        </Space>
      )
    },
    {
      title: t("操作"),
      key: "actions",
      width: 120,
      fixed: "right",
      render: (_, record) =>
        record.status === "active" ? (
          <Popconfirm
            title={t("吊销注册令牌")}
            description={t("吊销后该令牌不能再用于 Agent 注册。")}
            okText={t("吊销")}
            cancelText={t("取消")}
            onConfirm={() => revokeTokenMutation.mutate(record.id)}
          >
            <Button
              className="table-action-button"
              danger
              size="small"
              icon={<ShieldOff size={14} />}
              loading={revokeTokenMutation.isPending}
            >
              {t("吊销")}</Button>
          </Popconfirm>
        ) : (
          "-"
        )
    }
  ];

  const columns: ColumnsType<AgentSummary> = [
    {
      title: "Agent",
      dataIndex: "agent_id",
      minWidth: 240,
      render: (_: string, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text copyable>{record.agent_id}</Typography.Text>
          <Typography.Text className="table-subtitle" ellipsis>
            {displayValue(record.hostname)}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("状态"),
      dataIndex: "status",
      width: 110,
      render: (value: string) => <AgentStatusTag value={value} />
    },
    {
      title: "Agent IP",
      dataIndex: "asset_primary_ip",
      width: 150,
      render: (value: string | null) =>
        value ? <Typography.Text copyable>{value}</Typography.Text> : "-"
    },
    {
      title: t("资产"),
      key: "asset",
      minWidth: 180,
      render: (_, record) =>
        record.asset_id ? (
          <Typography.Link onClick={() => navigate(`/assets/${record.asset_id}`)}>
            {record.asset_hostname ?? record.asset_id}
          </Typography.Link>
        ) : (
          "-"
        )
    },
    {
      title: t("平台"),
      key: "platform",
      width: 180,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{displayValue(record.platform)}</Typography.Text>
          <Typography.Text className="table-subtitle">
            {displayValue(record.version)}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("最近心跳"),
      dataIndex: "last_heartbeat_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    {
      title: t("最近快照"),
      dataIndex: "last_snapshot_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    {
      title: t("最近取任务"),
      dataIndex: "last_task_poll_at",
      width: 190,
      render: (value: string | null) => formatDateTime(value)
    },
    {
      title: t("任务"),
      key: "tasks",
      width: 150,
      render: (_, record) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{taskSummary(record)}</Typography.Text>
          <Typography.Text className="table-subtitle">
            {record.task_stats.queued} {t("排队 /")}{record.task_stats.in_progress} {t("执行中")}</Typography.Text>
        </Space>
      )
    },
    {
      title: t("最近错误"),
      dataIndex: "last_error",
      minWidth: 220,
      render: (value: string | null) => (
        <Typography.Text className="table-subtitle" ellipsis>
          {displayValue(value)}
        </Typography.Text>
      )
    },
    {
      title: t("操作"),
      key: "actions",
      width: 170,
      fixed: "right",
      render: (_, record) => {
        const disableDisabled = !isAdmin || record.status === "disabled";
        return (
          <Space size={6}>
            <Tooltip
              title={
                !isAdmin
                  ? t("需要超级管理员权限")
                  : record.status === "disabled"
                    ? t("Agent 已禁用")
                    : t("保留资产数据，阻止该 Agent 继续上传新数据")
              }
            >
              <span>
                <Popconfirm
                  title={t("禁用 Agent")}
                  description={t("资产数据会保留，但该 Agent 的凭证会失效，无法再通过新 Agent 接口上传心跳、快照或任务结果。")}
                  okText={t("禁用")}
                  cancelText={t("取消")}
                  disabled={disableDisabled}
                  onConfirm={() => disableAgentMutation.mutate(record.agent_id)}
                >
                  <Button
                    className="table-action-button"
                    size="small"
                    icon={<Ban size={14} />}
                    disabled={disableDisabled}
                    loading={
                      disableAgentMutation.isPending &&
                      disableAgentMutation.variables === record.agent_id
                    }
                  >
                    {t("禁用")}</Button>
                </Popconfirm>
              </span>
            </Tooltip>
            <Tooltip title={!isAdmin ? t("需要超级管理员权限") : t("删除 Agent 及其资产数据")}>
              <span>
                <Popconfirm
                  title={t("删除 Agent")}
                  description={t("将删除该 Agent、对应资产，以及资产关联风险、验证任务和证据。此操作不可恢复。")}
                  okText={t("删除")}
                  cancelText={t("取消")}
                  okButtonProps={{ danger: true }}
                  disabled={!isAdmin}
                  onConfirm={() => deleteAgentMutation.mutate(record.agent_id)}
                >
                  <Button
                    className="table-action-button"
                    danger
                    size="small"
                    icon={<Trash2 size={14} />}
                    disabled={!isAdmin}
                    loading={
                      deleteAgentMutation.isPending &&
                      deleteAgentMutation.variables === record.agent_id
                    }
                  >
                    {t("删除")}</Button>
                </Popconfirm>
              </span>
            </Tooltip>
          </Space>
        );
      }
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title={t("Agent 管理")}
        extra={
          <Space wrap>
            <Button icon={<Download size={16} />} onClick={openScriptModal}>
              {t("下载脚本")}</Button>
            <Button
              icon={<RefreshCw size={16} />}
              onClick={() => agentsQuery.refetch()}
              loading={agentsQuery.isFetching}
            >
              {t("刷新")}</Button>
          </Space>
        }
      />

      {focusedAgentId ? (
        <Alert
          type="info"
          showIcon
          message={t("当前按 Agent {{v0}} 聚焦", { v0: focusedAgentId })}
          action={
            <Button size="small" onClick={() => navigate("/agents")}>
              {t("查看全部")}</Button>
          }
        />
      ) : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={6}>
          <Card className="metric-card">
            <Statistic title={t("Agent 总数")} value={metrics.total} prefix={<ServerCog size={24} />} />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-green">
            <Statistic title={t("在线")} value={metrics.online} prefix={<Wifi size={24} />} />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-red">
            <Statistic
              title={t("离线")}
              value={metrics.offline}
              prefix={<ShieldOff size={24} />}
            />
          </Card>
        </Col>
        <Col xs={24} lg={6}>
          <Card className="metric-card metric-card-red">
            <Statistic
              title={t("最近错误")}
              value={metrics.errors}
              prefix={<AlertCircle size={24} />}
            />
          </Card>
        </Col>
      </Row>

      <Card
        className="content-card"
        title={
          <Space>
            <KeyRound size={18} />
            <span>{t("注册令牌")}</span>
            <Tooltip title={t("吊销注册令牌后，该令牌不能再用于新的 Agent 注册；已经注册成功的 Agent 使用独立 agent_secret，仍可继续心跳、上传快照和提交任务结果。")}>
              <CircleAlert size={15} className="inline-help-icon" />
            </Tooltip>
          </Space>
        }
        extra={
          <Space wrap>
            <Button icon={<Plus size={16} />} type="primary" onClick={openTokenModal}>
              {t("创建令牌")}</Button>
            <Button
              icon={<RefreshCw size={16} />}
              onClick={() => enrollmentTokensQuery.refetch()}
              loading={enrollmentTokensQuery.isFetching}
            >
              {t("刷新")}</Button>
          </Space>
        }
      >
        {enrollmentTokensQuery.isError ? (
          <ErrorState error={enrollmentTokensQuery.error} />
        ) : null}
        <ResizableTable<AgentEnrollmentToken>
          storageKey="agent-enrollment-tokens"
          rowKey="id"
          columns={tokenColumns}
          dataSource={enrollmentTokensQuery.data ?? []}
          loading={enrollmentTokensQuery.isFetching}
          pagination={{
            pageSize: 5,
            showSizeChanger: true,
            showTotal: (total) => t("共 {{v0}} 条", { v0: total })
          }}
          locale={{
            emptyText: <EmptyState title={t("暂无注册令牌")} />
          }}
          scroll={{ x: 1180 }}
        />
      </Card>

      <Card className="content-card" title={t("Agent 列表")}>
        {agentsQuery.isError ? <ErrorState error={agentsQuery.error} /> : null}
        <div className="table-toolbar">
          <Input
            allowClear
            className="agent-search"
            prefix={<Search size={16} />}
            placeholder={t("搜索 Agent ID、主机名、IP、资产、平台、版本")}
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
          />
          <Typography.Text type="secondary">
            {hasAgentFilter
              ? t("匹配 {{v0}} / {{v1}} 条", { v0: agents.length, v1: allAgents.length })
              : t("共 {{v0}} 条", { v0: allAgents.length })}
          </Typography.Text>
        </div>
        <ResizableTable<AgentSummary>
          storageKey="agents"
          rowKey="agent_id"
          columns={columns}
          dataSource={agents}
          loading={agentsQuery.isFetching}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => t("共 {{v0}} 条", { v0: total })
          }}
          locale={{
            emptyText: (
              <EmptyState title={hasAgentFilter ? t("没有匹配的 Agent") : t("暂无 Agent")} />
            )
          }}
          scroll={{ x: 1690 }}
        />
      </Card>

      <Modal
        title={t("创建注册令牌")}
        open={tokenModalOpen}
        width={640}
        okText={t("创建令牌")}
        cancelText={t("关闭")}
        confirmLoading={createTokenMutation.isPending}
        onOk={() => void handleCreateToken()}
        onCancel={() => setTokenModalOpen(false)}
        destroyOnHidden
        footer={
          createdEnrollmentToken
            ? [
                <Button key="close" onClick={() => setTokenModalOpen(false)}>
                  {t("关闭")}</Button>,
                <Button key="script" type="primary" onClick={useCreatedTokenInScript}>
                  {t("填入安装脚本")}</Button>
              ]
            : undefined
        }
      >
        <Space className="page-stack" orientation="vertical" size={16}>
          {createdEnrollmentToken ? (
            <Alert
              type="success"
              showIcon
              message={t("注册令牌已创建")}
              description={
                <Space direction="vertical" size={8} style={{ width: "100%" }}>
                  <Typography.Text type="secondary">
                    {t("明文 token 只在本次创建后显示一次，关闭后无法再次查看。")}</Typography.Text>
                  <Input.TextArea
                    className="parameter-textarea"
                    value={createdEnrollmentToken.enrollment_token}
                    autoSize={{ minRows: 2, maxRows: 4 }}
                    readOnly
                  />
                  <Typography.Text copyable={{ text: createdEnrollmentToken.enrollment_token }}>
                    {t("复制注册令牌")}</Typography.Text>
                </Space>
              }
            />
          ) : null}
          <Form
            form={tokenForm}
            layout="vertical"
            initialValues={{ name: "", expiresAt: "", maxUses: 1 }}
            requiredMark={false}
            disabled={Boolean(createdEnrollmentToken)}
          >
            <Form.Item
              label={t("令牌名称")}
              name="name"
              rules={[{ required: true, message: t("请输入令牌名称") }]}
            >
              <Input placeholder="prod-linux-agents-2026-05" />
            </Form.Item>
            <Row gutter={16}>
              <Col xs={24} md={12}>
                <Form.Item label={t("过期时间")} name="expiresAt">
                  <Input type="datetime-local" />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item label={t("最大使用次数")} name="maxUses">
                  <InputNumber min={1} precision={0} style={{ width: "100%" }} />
                </Form.Item>
              </Col>
            </Row>
          </Form>
        </Space>
      </Modal>

      <Modal
        title={t("下载 Agent 脚本")}
        open={scriptModalOpen}
        width={920}
        okText={t("下载脚本")}
        cancelText={t("取消")}
        onOk={() => void handleScriptDownload()}
        onCancel={() => setScriptModalOpen(false)}
        destroyOnHidden
      >
        <Form
          form={scriptForm}
          layout="vertical"
          initialValues={scriptDefaults}
          onValuesChange={(changedValues: Partial<AgentScriptFormValues>) => {
            if (changedValues.agentIngressUrl) {
              scriptForm.setFieldsValue({
                binaryBaseUrl: platformDownloadUrl(
                  changedValues.agentIngressUrl,
                  "/agent/v1/downloads/vulnflanker-agent-linux"
                ),
                sourceArchiveUrl: platformDownloadUrl(
                  changedValues.agentIngressUrl,
                  "/agent/v1/downloads/source.tar.gz"
                )
              });
            }
          }}
          requiredMark={false}
        >
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item
                label={t("Agent 上报地址")}
                name="agentIngressUrl"
                rules={[{ required: true, message: t("请输入 Agent 上报地址") }]}
              >
                <Input placeholder="http://127.0.0.1:8001" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label={t("平台二进制地址前缀")} name="binaryBaseUrl">
                <Input placeholder="http://127.0.0.1:8001/agent/v1/downloads/vulnflanker-agent-linux" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label={t("注册令牌")}
                name="enrollmentToken"
                rules={[{ required: true, message: t("请输入 Agent 注册令牌") }]}
              >
                <Input.Password placeholder="vflet_xxx" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label={t("源码包地址")}
                name="sourceArchiveUrl"
                rules={[{ required: true, message: t("请输入源码包地址") }]}
              >
                <Input placeholder="http://127.0.0.1:8001/agent/v1/downloads/source.tar.gz" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label={t("本地源码目录")} name="agentSourceDir">
                <Input placeholder="/path/to/VulnFlanker/agent" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label={t("安装目录")}
                name="installDir"
                rules={[{ required: true, message: t("请输入安装目录") }]}
              >
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label={t("状态目录")}
                name="stateDir"
                rules={[{ required: true, message: t("请输入状态目录") }]}
              >
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label={t("日志目录")}
                name="logDir"
                rules={[{ required: true, message: t("请输入日志目录") }]}
              >
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label={t("服务名称")}
                name="serviceName"
                rules={[{ required: true, message: t("请输入服务名称") }]}
              >
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label={t("安装 systemd 服务")} name="installService" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={t("运行环境")} name="environmentType">
                <Select options={environmentOptions} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={t("暴露面")} name="exposureType">
                <Select options={exposureOptions} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={t("重要性")} name="criticality">
                <Select options={criticalityOptions} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={t("业务系统")} name="businessSystem">
                <Select
                  allowClear
                  showSearch
                  filterOption={false}
                  options={visibleBusinessSystemOptions}
                  loading={businessSystemsQuery.isLoading}
                  placeholder={t("选择业务系统")}
                  onSearch={setBusinessSystemSearchText}
                  onDropdownVisibleChange={(open) => {
                    if (!open) {
                      setBusinessSystemSearchText("");
                    }
                  }}
                  onChange={(value) =>
                    handleScriptSelectChange("businessSystem", "businessSystem", value)
                  }
                  notFoundContent={
                    businessSystemsQuery.isError ? t("业务系统加载失败") : undefined
                  }
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={t("负责团队")} name="ownerTeam">
                <Select
                  allowClear
                  showSearch
                  filterOption={false}
                  options={visibleResponsibilityTeamOptions}
                  loading={responsibilityTeamsQuery.isLoading}
                  placeholder={t("选择负责团队")}
                  onSearch={setResponsibilityTeamSearchText}
                  onDropdownVisibleChange={(open) => {
                    if (!open) {
                      setResponsibilityTeamSearchText("");
                    }
                  }}
                  onChange={(value) =>
                    handleScriptSelectChange("ownerTeam", "ownerTeam", value)
                  }
                  notFoundContent={
                    responsibilityTeamsQuery.isError ? t("负责团队加载失败") : undefined
                  }
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={t("负责人")} name="ownerPerson">
                <Select
                  allowClear
                  showSearch
                  filterOption={false}
                  options={visiblePersonOptions}
                  loading={peopleQuery.isLoading}
                  placeholder={t("选择负责人")}
                  onSearch={setPersonSearchText}
                  onDropdownVisibleChange={(open) => {
                    if (!open) {
                      setPersonSearchText("");
                    }
                  }}
                  onChange={(value) =>
                    handleScriptSelectChange("ownerPerson", "ownerPerson", value)
                  }
                  notFoundContent={peopleQuery.isError ? t("负责人加载失败") : undefined}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item label={t("自动验证")} name="allowAutoVerify" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item label={t("自动修复")} name="allowAutoRemediate" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col xs={24} md={4}>
              <Form.Item label={t("心跳秒")} name="heartbeatSeconds">
                <InputNumber min={5} precision={0} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={4}>
              <Form.Item label={t("快照秒")} name="snapshotSeconds">
                <InputNumber min={30} precision={0} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={4}>
              <Form.Item label={t("任务秒")} name="taskPollSeconds">
                <InputNumber min={5} precision={0} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={4}>
              <Form.Item label={t("超时秒")} name="requestTimeoutSeconds">
                <InputNumber min={1} precision={0} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label={t("脚本预览")}>
            <Input.TextArea
              className="parameter-textarea"
              value={scriptPreview}
              autoSize={{ minRows: 10, maxRows: 18 }}
              readOnly
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={t("直接新增归属数据")}
        open={ownershipQuickCreateOpen}
        width={720}
        okText={t("创建并填入")}
        cancelText={t("取消")}
        confirmLoading={quickCreateOwnershipMutation.isPending}
        onOk={() =>
          void ownershipQuickCreateForm
            .validateFields()
            .then((values) => quickCreateOwnershipMutation.mutate(values))
        }
        onCancel={() => {
          if (!quickCreateOwnershipMutation.isPending) {
            setOwnershipQuickCreateOpen(false);
          }
        }}
        destroyOnHidden
      >
        <Space className="page-stack" orientation="vertical" size={12}>
          <Alert
            type="info"
            showIcon
            message={t("在这里填完整归属关系")}
            description={t("业务系统、负责人、负责团队三项都需要在这里选择已有或直接新增；保存后会自动创建缺失数据并绑定关系。")}
          />
          <Form
            form={ownershipQuickCreateForm}
            layout="vertical"
            initialValues={{
              createTeam: false,
              createPerson: false,
              createBusinessSystem: false
            }}
            requiredMark={false}
          >
            <div className="ownership-quick-create-section">
              <div className="ownership-quick-create-heading">
                <Typography.Text strong>{t("业务系统")}</Typography.Text>
                <Form.Item name="createBusinessSystem" valuePropName="checked" noStyle>
                  <Switch checkedChildren={t("新增")} unCheckedChildren={t("选择已有")} />
                </Form.Item>
              </div>
              <Form.Item
                noStyle
                shouldUpdate={(prev, current) =>
                  prev.createBusinessSystem !== current.createBusinessSystem
                }
              >
                {({ getFieldValue }) =>
                  getFieldValue("createBusinessSystem") ? (
                    <Row gutter={16}>
                      <Col xs={24} md={12}>
                        <Form.Item
                          label={t("系统编码")}
                          name="businessSystemCode"
                          rules={[{ required: true, message: t("请输入系统编码") }]}
                        >
                          <Input placeholder="PAYMENT" />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={12}>
                        <Form.Item
                          label={t("系统名称")}
                          name="businessSystemName"
                          rules={[{ required: true, message: t("请输入系统名称") }]}
                        >
                          <Input placeholder={t("支付系统")} />
                        </Form.Item>
                      </Col>
                    </Row>
                  ) : (
                    <Form.Item
                      label={t("已有业务系统")}
                      name="existingBusinessSystemId"
                      rules={[{ required: true, message: t("请选择已有业务系统") }]}
                    >
                      <Select
                        showSearch
                        optionFilterProp="label"
                        options={existingBusinessSystemOptions}
                        loading={businessSystemsQuery.isLoading}
                        placeholder={t("选择已有业务系统")}
                      />
                    </Form.Item>
                  )
                }
              </Form.Item>
            </div>

            <div className="ownership-quick-create-section">
              <div className="ownership-quick-create-heading">
                <Typography.Text strong>{t("负责人")}</Typography.Text>
                <Form.Item name="createPerson" valuePropName="checked" noStyle>
                  <Switch checkedChildren={t("新增")} unCheckedChildren={t("选择已有")} />
                </Form.Item>
              </div>
              <Form.Item
                noStyle
                shouldUpdate={(prev, current) => prev.createPerson !== current.createPerson}
              >
                {({ getFieldValue }) =>
                  getFieldValue("createPerson") ? (
                    <Row gutter={16}>
                      <Col xs={24} md={12}>
                        <Form.Item
                          label={t("负责人姓名")}
                          name="personName"
                          rules={[{ required: true, message: t("请输入负责人姓名") }]}
                        >
                          <Input placeholder={t("张三")} />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={12}>
                        <Form.Item label={t("工号")} name="employeeNo">
                          <Input placeholder={t("可选")} />
                        </Form.Item>
                      </Col>
                      <Col xs={24}>
                        <Form.Item
                          label={t("邮箱")}
                          name="personEmail"
                          rules={[{ type: "email", message: t("请输入有效邮箱") }]}
                        >
                          <Input placeholder={t("可选")} />
                        </Form.Item>
                      </Col>
                    </Row>
                  ) : (
                    <Form.Item
                      label={t("已有负责人")}
                      name="existingPersonId"
                      rules={[{ required: true, message: t("请选择已有负责人") }]}
                    >
                      <Select
                        showSearch
                        optionFilterProp="label"
                        options={existingPersonOptions}
                        loading={peopleQuery.isLoading}
                        placeholder={t("选择已有负责人")}
                      />
                    </Form.Item>
                  )
                }
              </Form.Item>
            </div>

            <div className="ownership-quick-create-section">
              <div className="ownership-quick-create-heading">
                <Typography.Text strong>{t("负责团队")}</Typography.Text>
                <Form.Item name="createTeam" valuePropName="checked" noStyle>
                  <Switch checkedChildren={t("新增")} unCheckedChildren={t("选择已有")} />
                </Form.Item>
              </div>
              <Form.Item
                noStyle
                shouldUpdate={(prev, current) => prev.createTeam !== current.createTeam}
              >
                {({ getFieldValue }) =>
                  getFieldValue("createTeam") ? (
                    <Row gutter={16}>
                      <Col xs={24} md={12}>
                        <Form.Item
                          label={t("团队编码")}
                          name="teamCode"
                          rules={[{ required: true, message: t("请输入团队编码") }]}
                        >
                          <Input placeholder="TEAM-SRE" />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={12}>
                        <Form.Item
                          label={t("团队名称")}
                          name="teamName"
                          rules={[{ required: true, message: t("请输入团队名称") }]}
                        >
                          <Input placeholder={t("支付 SRE")} />
                        </Form.Item>
                      </Col>
                    </Row>
                  ) : (
                    <Form.Item
                      label={t("已有团队")}
                      name="existingTeamId"
                      rules={[{ required: true, message: t("请选择已有团队") }]}
                    >
                      <Select
                        showSearch
                        optionFilterProp="label"
                        options={existingResponsibilityTeamOptions}
                        loading={responsibilityTeamsQuery.isLoading}
                        placeholder={t("选择已有团队")}
                      />
                    </Form.Item>
                  )
                }
              </Form.Item>
            </div>
          </Form>
        </Space>
      </Modal>
    </Space>
  );
}

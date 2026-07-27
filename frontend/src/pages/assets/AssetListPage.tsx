import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  Modal,
  Pagination,
  Row,
  Select,
  Space,
  Statistic,
  Tag,
  Tooltip,
  Typography,
  message
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRightLeft,
  CircleHelp,
  Database,
  Eye,
  Globe2,
  RefreshCw,
  Search,
  ShieldAlert,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { bulkBindAssetBusinessSystems, getAssets } from "@/api/assets";
import {
  getBusinessSystems,
  getPeople,
  getResponsibilityTeams
} from "@/api/ownership";
import type { AssetOwnershipStatus, AssetSummary } from "@/api/types";
import { useAuth } from "@/app/auth";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import { CriticalityTag, ExposureTag } from "@/components/ValueTags";
import { formatDateTime } from "@/utils/format";

type AssetFilterKey =
  | "criticality"
  | "environment_type"
  | "exposure_type"
  | "platform"
  | "os_family";
type AssetFilters = Partial<Record<AssetFilterKey, string>>;
type OwnershipFilters = {
  businessSystemId?: string;
  personId?: string;
  teamId?: string;
  status?: AssetOwnershipStatus;
};

const assetFilterFields: Array<{ key: AssetFilterKey; placeholder: string }> = [
  { key: "criticality", placeholder: "关键性" },
  { key: "environment_type", placeholder: "环境" },
  { key: "exposure_type", placeholder: "暴露类型" },
  { key: "platform", placeholder: "平台" },
  { key: "os_family", placeholder: "系统族" }
];

const ownershipStatusOptions = [
  { label: "归属完整", value: "complete" },
  { label: "未分配", value: "unassigned" },
  { label: "链路不完整", value: "system_incomplete" }
];

const DEFAULT_PAGE_SIZE = 10;

function displayValue(value?: string | number | null) {
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

function normalized(value: unknown) {
  return String(value ?? "").trim().toLocaleLowerCase();
}

function matchesSearch(asset: AssetSummary, keyword: string) {
  const terms = normalized(keyword).split(/\s+/).filter(Boolean);
  if (!terms.length) return true;
  const ownership = asset.ownership;
  const text = [
    asset.id,
    asset.agent_id,
    asset.display_name,
    asset.hostname,
    asset.primary_ip,
    asset.platform,
    asset.os_family,
    asset.os_version,
    asset.architecture,
    ownership.business_system?.code,
    ownership.business_system?.name,
    ownership.responsible_person?.name,
    ownership.responsible_person?.email,
    ownership.responsibility_team?.code,
    ownership.responsibility_team?.name
  ]
    .map(normalized)
    .filter(Boolean)
    .join(" ");
  return terms.every((term) => text.includes(term));
}

function matchesFilters(
  asset: AssetSummary,
  filters: AssetFilters,
  ownershipFilters: OwnershipFilters
) {
  const baseMatch = assetFilterFields.every(({ key }) =>
    !filters[key] || asset[key] === filters[key]
  );
  const ownership = asset.ownership;
  return (
    baseMatch &&
    (!ownershipFilters.businessSystemId ||
      ownership.business_system?.id === ownershipFilters.businessSystemId) &&
    (!ownershipFilters.personId ||
      ownership.responsible_person?.id === ownershipFilters.personId) &&
    (!ownershipFilters.teamId ||
      ownership.responsibility_team?.id === ownershipFilters.teamId) &&
    (!ownershipFilters.status || ownership.status === ownershipFilters.status)
  );
}

function baseFilterOptions(assets: AssetSummary[], key: AssetFilterKey) {
  return Array.from(new Set(assets.map((asset) => asset[key]).filter(Boolean) as string[]))
    .sort((a, b) => a.localeCompare(b))
    .map((value) => ({ label: value, value }));
}

function relationshipOptions(
  assets: AssetSummary[],
  kind: "business_system" | "responsible_person" | "responsibility_team"
) {
  const items = new Map<string, string>();
  for (const asset of assets) {
    const relation = asset.ownership[kind];
    if (relation) {
      items.set(
        relation.id,
        "code" in relation ? `${relation.name} · ${relation.code}` : relation.name
      );
    }
  }
  return Array.from(items, ([value, label]) => ({ value, label })).sort((a, b) =>
    a.label.localeCompare(b.label)
  );
}

function OwnershipStatusTag({ status }: { status: AssetOwnershipStatus }) {
  if (status === "complete") return <Tag color="green">归属完整</Tag>;
  if (status === "system_incomplete") return <Tag color="gold">链路不完整</Tag>;
  return <Tag>未分配</Tag>;
}

export default function AssetListPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_superuser);
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [bindingForm] = Form.useForm<{ business_system_id: string }>();
  const bindingSystemId = Form.useWatch("business_system_id", bindingForm);
  const [searchText, setSearchText] = useState("");
  const [filters, setFilters] = useState<AssetFilters>({});
  const [ownershipFilters, setOwnershipFilters] = useState<OwnershipFilters>(() => ({
    businessSystemId: searchParams.get("business_system_id") ?? undefined,
    personId: searchParams.get("responsible_person_id") ?? undefined,
    teamId: searchParams.get("responsibility_team_id") ?? undefined,
    status:
      (searchParams.get("ownership_status") as AssetOwnershipStatus | null) ??
      undefined
  }));
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([]);
  const [bindingAssetIds, setBindingAssetIds] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const serverOwnershipFilters = {
    business_system_id: ownershipFilters.businessSystemId,
    responsible_person_id: ownershipFilters.personId,
    responsibility_team_id: ownershipFilters.teamId,
    ownership_status: ownershipFilters.status
  };
  const serverFilters = {
    ...serverOwnershipFilters,
    search: searchText.trim() || undefined,
    criticality: filters.criticality,
    environment_type: filters.environment_type,
    exposure_type: filters.exposure_type,
    platform: filters.platform,
    os_family: filters.os_family
  };

  const assetsQuery = useQuery({
    queryKey: ["assets", "list", serverFilters, currentPage, pageSize],
    queryFn: () =>
      getAssets({
        ...serverFilters,
        offset: (currentPage - 1) * pageSize,
        limit: pageSize
      })
  });
  const systemsQuery = useQuery({
    queryKey: ["ownership", "systems", "asset-binding-options"],
    queryFn: () => getBusinessSystems({ status: "active", page_size: 200, sort_by: "name", sort_order: "asc" }),
  });
  const peopleQuery = useQuery({
    queryKey: ["ownership", "people", "asset-filter-options"],
    queryFn: () => getPeople({ status: "active", page_size: 200, sort_by: "name", sort_order: "asc" })
  });
  const teamsQuery = useQuery({
    queryKey: ["ownership", "teams", "asset-filter-options"],
    queryFn: () =>
      getResponsibilityTeams({ status: "active", page_size: 200, sort_by: "name", sort_order: "asc" })
  });

  useEffect(() => {
    setCurrentPage(1);
  }, [filters, ownershipFilters, searchText]);

  const assetsPage = assetsQuery.data;
  const assets = assetsPage?.items ?? [];
  const selectedSystem = systemsQuery.data?.items.find(
    (system) => system.id === bindingSystemId
  );
  const filterOptions = useMemo(
    () =>
      Object.fromEntries(
        assetFilterFields.map(({ key }) => [key, baseFilterOptions(assets, key)])
      ) as Record<AssetFilterKey, Array<{ label: string; value: string }>>,
    [assets]
  );
  const ownershipOptions = useMemo(
    () => ({
      systems: (systemsQuery.data?.items ?? []).map((system) => ({
        value: system.id,
        label: `${system.name} · ${system.code}`
      })),
      people: (peopleQuery.data?.items ?? []).map((person) => ({
        value: person.id,
        label: `${person.name}${person.employee_no ? ` · ${person.employee_no}` : ""} · ${person.team.name}`
      })),
      teams: (teamsQuery.data?.items ?? []).map((team) => ({
        value: team.id,
        label: `${team.name} · ${team.code}`
      }))
    }),
    [peopleQuery.data?.items, systemsQuery.data?.items, teamsQuery.data?.items]
  );
  const hasActiveFilters =
    Boolean(searchText.trim()) ||
    Object.values(filters).some(Boolean) ||
    Object.values(ownershipFilters).some(Boolean);
  const metrics = useMemo(
    () => ({
      total: assetsPage?.total ?? assets.length,
      highCriticality:
        assetsPage?.high_criticality_count ??
        assets.filter((asset) => ["critical", "high"].includes(asset.criticality))
          .length,
      publicExposure:
        assetsPage?.public_exposure_count ??
        assets.filter((asset) =>
          ["internet", "public", "external", "dmz"].includes(asset.exposure_type)
        ).length,
      unassigned:
        assetsPage?.incomplete_ownership_count ??
        assets.filter((asset) => asset.ownership.status !== "complete").length
    }),
    [assets, assetsPage]
  );
  const total = assetsPage?.total ?? assets.length;

  const bindingMutation = useMutation({
    mutationFn: (value: string) =>
      bulkBindAssetBusinessSystems(
        bindingAssetIds,
        value === "__unassign__" ? null : value
      ),
    onSuccess: (result) => {
      messageApi.success(`已更新 ${result.updated_count} 个资产的运营归属`);
      setBindingAssetIds([]);
      setSelectedAssetIds([]);
      bindingForm.resetFields();
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      void queryClient.invalidateQueries({ queryKey: ["ownership"] });
    },
    onError: (error) => messageApi.error(error.message)
  });

  function openBinding(assetIds: string[]) {
    setBindingAssetIds(assetIds);
    bindingForm.resetFields();
  }

  function resetFilters() {
    setSearchText("");
    setFilters({});
    setOwnershipFilters({});
  }

  const columns: ColumnsType<AssetSummary> = [
    {
      title: "资产",
      key: "asset",
      minWidth: 250,
      render: (_, asset) => (
        <Space orientation="vertical" size={0}>
          <Typography.Link onClick={() => navigate(`/assets/${asset.id}`)}>
            {asset.display_name || asset.hostname}
          </Typography.Link>
          <Typography.Text className="table-subtitle">
            {asset.hostname}{asset.agent_id ? ` / ${asset.agent_id}` : ""}
          </Typography.Text>
        </Space>
      )
    },
    { title: "IP", dataIndex: "primary_ip", width: 145, render: displayValue },
    {
      title: "主机系统",
      key: "host_system",
      width: 190,
      render: (_, asset) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{displayValue(asset.platform)}</Typography.Text>
          <Typography.Text className="table-subtitle">
            {[asset.os_family, asset.os_version].filter(Boolean).join(" / ") || "-"}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: "业务系统",
      key: "business_system",
      width: 190,
      render: (_, asset) => asset.ownership.business_system ? (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{asset.ownership.business_system.name}</Typography.Text>
          <Typography.Text className="table-subtitle">{asset.ownership.business_system.code}</Typography.Text>
        </Space>
      ) : "-"
    },
    { title: "主责任人", key: "owner", width: 150, render: (_, asset) => asset.ownership.responsible_person?.name || "-" },
    { title: "责任团队", key: "team", width: 170, render: (_, asset) => asset.ownership.responsibility_team?.name || "-" },
    { title: "归属状态", key: "ownership_status", width: 115, render: (_, asset) => <OwnershipStatusTag status={asset.ownership.status} /> },
    { title: "关键性", dataIndex: "criticality", width: 105, render: (value: string) => <CriticalityTag value={value} /> },
    { title: "暴露类型", dataIndex: "exposure_type", width: 115, render: (value: string) => <ExposureTag value={value} /> },
    { title: "最近上报", dataIndex: "last_seen_at", width: 180, render: formatDateTime },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 165,
      render: (_, asset) => (
        <Space className="table-actions asset-row-actions" size={2}>
          <Button type="link" icon={<Eye size={15} />} onClick={() => navigate(`/assets/${asset.id}`)}>详情</Button>
          <Tooltip title={!isAdmin ? "需要超级管理员权限" : undefined}>
            <Button type="link" disabled={!isAdmin} icon={<ArrowRightLeft size={15} />} onClick={() => openBinding([asset.id])}>归属</Button>
          </Tooltip>
        </Space>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title="资产管理"
        subtitle="资产只绑定业务系统，专门责任人和责任团队由业务关系实时派生。"
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} loading={assetsQuery.isFetching} onClick={() => assetsQuery.refetch()}>刷新</Button>
            <Button
              type="primary"
              icon={<ArrowRightLeft size={16} />}
              disabled={!isAdmin || selectedAssetIds.length === 0}
              onClick={() => openBinding(selectedAssetIds)}
            >
              批量设置归属{selectedAssetIds.length ? `（${selectedAssetIds.length}）` : ""}
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={6}><Card className="metric-card"><Statistic title="资产总数" value={metrics.total} prefix={<Database size={24} />} /></Card></Col>
        <Col xs={24} lg={6}><Card className="metric-card metric-card-red"><Statistic title="高关键资产" value={metrics.highCriticality} prefix={<ShieldAlert size={24} />} /></Card></Col>
        <Col xs={24} lg={6}><Card className="metric-card metric-card-red"><Statistic title="公网暴露" value={metrics.publicExposure} prefix={<Globe2 size={24} />} /></Card></Col>
        <Col xs={24} lg={6}><Card className="metric-card"><Statistic title="待完善归属" value={metrics.unassigned} prefix={<CircleHelp size={24} />} /></Card></Col>
      </Row>

      <Card className="content-card asset-list-card" title="资产列表">
        {assetsQuery.isError ? <ErrorState error={assetsQuery.error} /> : null}
        <div className="table-toolbar asset-toolbar">
          <Input allowClear className="asset-search" prefix={<Search size={16} />} placeholder="搜索资产、业务系统、责任人或团队" value={searchText} onChange={(event) => setSearchText(event.target.value)} />
          <Space className="asset-filter-controls" size={[8, 8]} wrap>
            <Select allowClear showSearch className="asset-filter-select" optionFilterProp="label" options={ownershipOptions.systems} placeholder="业务系统" value={ownershipFilters.businessSystemId} onChange={(value) => setOwnershipFilters((current) => ({ ...current, businessSystemId: value }))} />
            <Select allowClear showSearch className="asset-filter-select" optionFilterProp="label" options={ownershipOptions.people} placeholder="责任人" value={ownershipFilters.personId} onChange={(value) => setOwnershipFilters((current) => ({ ...current, personId: value }))} />
            <Select allowClear showSearch className="asset-filter-select" optionFilterProp="label" options={ownershipOptions.teams} placeholder="责任团队" value={ownershipFilters.teamId} onChange={(value) => setOwnershipFilters((current) => ({ ...current, teamId: value }))} />
            <Select allowClear className="asset-filter-select" options={ownershipStatusOptions} placeholder="归属状态" value={ownershipFilters.status} onChange={(value) => setOwnershipFilters((current) => ({ ...current, status: value }))} />
            {assetFilterFields.map(({ key, placeholder }) => (
              <Select key={key} allowClear showSearch className="asset-filter-select" optionFilterProp="label" options={filterOptions[key]} placeholder={placeholder} value={filters[key]} onChange={(value) => setFilters((current) => ({ ...current, [key]: value }))} />
            ))}
            <Button icon={<X size={15} />} disabled={!hasActiveFilters} onClick={resetFilters}>重置</Button>
          </Space>
          <Typography.Text type="secondary">
            {hasActiveFilters ? `匹配 ${total} 条` : `共 ${total} 条`}
          </Typography.Text>
        </div>
        <ResizableTable<AssetSummary>
          className="asset-list-table"
          storageKey="assets-ownership"
          rowKey="id"
          rowSelection={isAdmin ? { selectedRowKeys: selectedAssetIds, onChange: (keys) => setSelectedAssetIds(keys.map(String)) } : undefined}
          columns={columns}
          dataSource={assets}
          loading={assetsQuery.isFetching}
          pagination={false}
          locale={{ emptyText: <EmptyState title={hasActiveFilters ? "没有匹配的资产" : "暂无资产"} /> }}
          scroll={{ x: 1780 }}
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
        title={`设置运营归属 · ${bindingAssetIds.length} 个资产`}
        open={bindingAssetIds.length > 0}
        okText="确认更新"
        confirmLoading={bindingMutation.isPending}
        onCancel={() => setBindingAssetIds([])}
        onOk={() => bindingForm.submit()}
      >
        <Alert showIcon type="info" message="只需选择业务系统" description="责任人和团队会从所选系统自动带出；选择解除归属后，资产将进入待分配状态。" />
        <Form form={bindingForm} layout="vertical" className="ownership-binding-form" onFinish={({ business_system_id }) => bindingMutation.mutate(business_system_id)}>
          <Form.Item label="业务系统" name="business_system_id" rules={[{ required: true, message: "请选择业务系统或解除归属" }]}>
            <Select
              showSearch
              optionFilterProp="label"
              loading={systemsQuery.isLoading}
              options={[
                { value: "__unassign__", label: "解除归属（进入待分配）" },
                ...(systemsQuery.data?.items ?? []).map((system) => ({ value: system.id, label: `${system.name} · ${system.code}` }))
              ]}
              placeholder="选择启用业务系统"
            />
          </Form.Item>
          {selectedSystem?.responsible_person ? (
            <Alert
              showIcon
              type="success"
              message={`${selectedSystem.responsible_person.name} · ${selectedSystem.responsible_person.team.name}`}
              description={selectedSystem.responsible_person.email || "责任人未设置邮箱"}
            />
          ) : bindingSystemId === "__unassign__" ? (
            <Alert showIcon type="warning" message="确认后将解除所选资产的结构化运营归属" />
          ) : null}
        </Form>
      </Modal>
    </Space>
  );
}

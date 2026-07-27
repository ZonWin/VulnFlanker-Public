import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Radio,
  Select,
  Space,
  Tooltip,
  Typography,
  message
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Power, RefreshCw, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { useAuth } from "@/app/auth";
import {
  activateBusinessSystem,
  createBusinessSystem,
  deactivateBusinessSystem,
  getBusinessSystems,
  getOwnershipSummary,
  getPeople,
  getResponsibilityTeams,
  updateBusinessSystem,
  type BusinessSystem,
  type BusinessSystemCreate,
  type BusinessSystemStatus,
  type BusinessSystemUpdate
} from "@/api/ownership";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import PageHeader from "@/components/PageHeader";
import ResizableTable from "@/components/ResizableTable";
import { formatDateTime } from "@/utils/format";
import {
  LifecycleTag,
  OwnershipMetrics,
  ReadOnlyNotice,
  cleanOptional
} from "@/pages/ownership/common";

interface SystemFormValues {
  code: string;
  name: string;
  description?: string;
  responsible_person_id?: string;
  status?: "draft" | "active";
}

interface DeactivateFormValues {
  asset_action?: "replace" | "unassign";
  replacement_system_id?: string;
}

const systemStatusOptions = [
  { label: "草稿", value: "draft" },
  { label: "启用", value: "active" },
  { label: "停用", value: "inactive" }
];

export default function BusinessSystemsPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_superuser);
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [systemForm] = Form.useForm<SystemFormValues>();
  const [deactivateForm] = Form.useForm<DeactivateFormValues>();
  const createStatus = Form.useWatch("status", systemForm);
  const assetAction = Form.useWatch("asset_action", deactivateForm);
  const [keyword, setKeyword] = useState(() => searchParams.get("keyword") ?? "");
  const [status, setStatus] = useState<BusinessSystemStatus | undefined>();
  const [teamId, setTeamId] = useState<string | undefined>();
  const [responsiblePersonId, setResponsiblePersonId] = useState<string | undefined>();
  const [hasAssets, setHasAssets] = useState<boolean | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [editingSystem, setEditingSystem] = useState<BusinessSystem | null>(null);
  const [isSystemModalOpen, setIsSystemModalOpen] = useState(false);
  const [deactivatingSystem, setDeactivatingSystem] = useState<BusinessSystem | null>(null);

  const systemsQuery = useQuery({
    queryKey: ["ownership", "systems", { keyword, status, teamId, responsiblePersonId, hasAssets, page, pageSize }],
    queryFn: () =>
      getBusinessSystems({ keyword, status, team_id: teamId, responsible_person_id: responsiblePersonId, has_assets: hasAssets, page, page_size: pageSize })
  });
  const summaryQuery = useQuery({ queryKey: ["ownership", "summary"], queryFn: getOwnershipSummary });
  const peopleQuery = useQuery({
    queryKey: ["ownership", "people", "system-form-options"],
    queryFn: () => getPeople({ page_size: 200, sort_by: "name", sort_order: "asc" })
  });
  const teamsQuery = useQuery({
    queryKey: ["ownership", "teams", "system-filter-options"],
    queryFn: () => getResponsibilityTeams({ page_size: 200, sort_by: "name", sort_order: "asc" })
  });
  const replacementSystemsQuery = useQuery({
    queryKey: ["ownership", "systems", "replacement-options"],
    queryFn: () => getBusinessSystems({ status: "active", page_size: 200, sort_by: "name", sort_order: "asc" }),
    enabled: Boolean(deactivatingSystem)
  });

  function refreshOwnership() {
    void queryClient.invalidateQueries({ queryKey: ["ownership"] });
  }

  const saveMutation = useMutation({
    mutationFn: async (values: SystemFormValues) => {
      if (editingSystem) {
        const payload: BusinessSystemUpdate = {
          expected_version: editingSystem.version,
          name: values.name.trim(),
          description: cleanOptional(values.description),
          responsible_person_id: values.responsible_person_id || null
        };
        return updateBusinessSystem(editingSystem.id, payload);
      }
      const payload: BusinessSystemCreate = {
        code: values.code.trim(),
        name: values.name.trim(),
        description: cleanOptional(values.description),
        responsible_person_id: values.responsible_person_id || null,
        status: values.status ?? "active"
      };
      return createBusinessSystem(payload);
    },
    onSuccess: () => {
      messageApi.success(editingSystem ? "业务系统已更新" : "业务系统已创建");
      setIsSystemModalOpen(false);
      setEditingSystem(null);
      systemForm.resetFields();
      refreshOwnership();
    },
    onError: (error) => messageApi.error(error.message)
  });

  const activateMutation = useMutation({
    mutationFn: (system: BusinessSystem) => activateBusinessSystem(system.id, system.version),
    onSuccess: () => {
      messageApi.success("业务系统已启用");
      refreshOwnership();
    },
    onError: (error) => messageApi.error(error.message)
  });

  const deactivateMutation = useMutation({
    mutationFn: (values: DeactivateFormValues) => {
      if (!deactivatingSystem) {
        throw new Error("未选择要停用的业务系统");
      }
      return deactivateBusinessSystem(deactivatingSystem.id, {
        expected_version: deactivatingSystem.version,
        replacement_system_id:
          values.asset_action === "replace" ? values.replacement_system_id : null,
        unassign_assets: values.asset_action === "unassign"
      });
    },
    onSuccess: () => {
      messageApi.success("业务系统已停用，关联资产已按选择处理");
      setDeactivatingSystem(null);
      deactivateForm.resetFields();
      refreshOwnership();
    },
    onError: (error) => messageApi.error(error.message)
  });

  function openCreate() {
    setEditingSystem(null);
    systemForm.resetFields();
    systemForm.setFieldsValue({ status: "active" });
    setIsSystemModalOpen(true);
  }

  function openEdit(system: BusinessSystem) {
    setEditingSystem(system);
    systemForm.setFieldsValue({
      code: system.code,
      name: system.name,
      description: system.description ?? undefined,
      responsible_person_id: system.responsible_person?.id,
      status: system.status === "draft" ? "draft" : "active"
    });
    setIsSystemModalOpen(true);
  }

  function confirmActivate(system: BusinessSystem) {
    Modal.confirm({
      title: "启用业务系统",
      content: system.responsible_person
        ? `将由 ${system.responsible_person.name}（${system.responsible_person.team.name}）负责该系统。`
        : "当前未设置责任人，请先编辑并选择启用人员。",
      okText: "确认启用",
      okButtonProps: { disabled: !system.responsible_person },
      onOk: () => activateMutation.mutateAsync(system)
    });
  }

  const columns: ColumnsType<BusinessSystem> = [
    {
      title: "业务系统",
      key: "system",
      minWidth: 250,
      render: (_, system) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text strong>{system.name}</Typography.Text>
          <Typography.Text className="table-subtitle">{system.code}</Typography.Text>
        </Space>
      )
    },
    {
      title: "专门责任人",
      key: "responsible_person",
      minWidth: 210,
      render: (_, system) =>
        system.responsible_person ? (
          <Space orientation="vertical" size={0}>
            <Typography.Text>{system.responsible_person.name}</Typography.Text>
            <Typography.Text className="table-subtitle">{system.responsible_person.email || "未设置邮箱"}</Typography.Text>
          </Space>
        ) : (
          <Typography.Text type="warning">待分配</Typography.Text>
        )
    },
    {
      title: "责任团队",
      key: "team",
      width: 190,
      render: (_, system) =>
        system.responsible_person ? (
          <Space orientation="vertical" size={0}>
            <Typography.Text>{system.responsible_person.team.name}</Typography.Text>
            <Typography.Text className="table-subtitle">{system.responsible_person.team.code}</Typography.Text>
          </Space>
        ) : "-"
    },
    { title: "状态", dataIndex: "status", width: 90, render: (value: BusinessSystemStatus) => <LifecycleTag status={value} /> },
    {
      title: "关联资产",
      dataIndex: "asset_count",
      width: 100,
      render: (count: number, system) => (
        <Typography.Link onClick={() => navigate(`/assets?business_system_id=${system.id}`)}>
          {count}
        </Typography.Link>
      )
    },
    { title: "更新时间", dataIndex: "updated_at", width: 185, render: formatDateTime },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 170,
      render: (_, system) => (
        <Space size={2}>
          <Tooltip title={!isAdmin ? "需要超级管理员权限" : undefined}>
            <Button type="link" disabled={!isAdmin} icon={<Pencil size={15} />} onClick={() => openEdit(system)}>编辑</Button>
          </Tooltip>
          {system.status === "active" ? (
            <Button
              type="link"
              danger
              disabled={!isAdmin}
              icon={<Power size={15} />}
              onClick={() => {
                setDeactivatingSystem(system);
                deactivateForm.resetFields();
                if (system.asset_count > 0) {
                  deactivateForm.setFieldsValue({ asset_action: "replace" });
                }
              }}
            >
              停用
            </Button>
          ) : (
            <Button type="link" disabled={!isAdmin} icon={<Power size={15} />} onClick={() => confirmActivate(system)}>启用</Button>
          )}
        </Space>
      )
    }
  ];

  const personOptions = (peopleQuery.data?.items ?? []).map((person) => ({
    label: `${person.name} · ${person.team.name}${person.status === "inactive" ? "（已停用）" : ""}`,
    value: person.id,
    disabled: person.status !== "active" || person.team.status !== "active"
  }));

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title="业务系统"
        subtitle="以业务系统作为资产运营归属入口，每个启用系统绑定一名专门责任人。"
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} loading={systemsQuery.isFetching} onClick={refreshOwnership}>刷新</Button>
            <Button type="primary" icon={<Plus size={16} />} disabled={!isAdmin} onClick={openCreate}>新建业务系统</Button>
          </Space>
        }
      />
      <ReadOnlyNotice isAdmin={isAdmin} />
      <OwnershipMetrics summary={summaryQuery.data} />
      <Card className="content-card" title="业务系统列表">
        <div className="table-toolbar ownership-toolbar">
          <Input
            allowClear
            prefix={<Search size={16} />}
            placeholder="搜索系统编码或名称"
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1);
            }}
          />
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="全部团队"
            loading={teamsQuery.isLoading}
            options={(teamsQuery.data?.items ?? []).map((team) => ({ label: team.name, value: team.id }))}
            value={teamId}
            onChange={(value) => {
              setTeamId(value);
              setPage(1);
            }}
          />
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="全部责任人"
            loading={peopleQuery.isLoading}
            options={(peopleQuery.data?.items ?? []).map((person) => ({ label: person.name, value: person.id }))}
            value={responsiblePersonId}
            onChange={(value) => {
              setResponsiblePersonId(value);
              setPage(1);
            }}
          />
          <Select
            allowClear
            placeholder="资产情况"
            options={[
              { label: "有关联资产", value: true },
              { label: "无关联资产", value: false }
            ]}
            value={hasAssets}
            onChange={(value) => {
              setHasAssets(value);
              setPage(1);
            }}
          />
          <Select
            allowClear
            placeholder="全部状态"
            options={systemStatusOptions}
            value={status}
            onChange={(value) => {
              setStatus(value);
              setPage(1);
            }}
          />
        </div>
        {systemsQuery.isError ? <ErrorState error={systemsQuery.error} /> : null}
        <ResizableTable
          rowKey="id"
          storageKey="ownership-business-systems"
          columns={columns}
          dataSource={systemsQuery.data?.items ?? []}
          loading={systemsQuery.isLoading}
          locale={{ emptyText: <EmptyState title="暂无业务系统，请先创建并分配责任人" /> }}
          pagination={{
            current: page,
            pageSize,
            total: systemsQuery.data?.total ?? 0,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个业务系统`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPageSize === pageSize ? nextPage : 1);
              setPageSize(nextPageSize);
            }
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      <Modal
        title={editingSystem ? "编辑业务系统" : "新建业务系统"}
        open={isSystemModalOpen}
        width={620}
        okText={editingSystem ? "保存" : "创建"}
        confirmLoading={saveMutation.isPending}
        onCancel={() => setIsSystemModalOpen(false)}
        onOk={() => systemForm.submit()}
      >
        <Form form={systemForm} layout="vertical" onFinish={(values) => saveMutation.mutate(values)}>
          <div className="ownership-form-grid">
            <Form.Item label="系统编码" name="code" rules={[{ required: true, message: "请输入系统编码" }]}>
              <Input disabled={Boolean(editingSystem)} maxLength={64} placeholder="例如 CRM" />
            </Form.Item>
            <Form.Item label="系统名称" name="name" rules={[{ required: true, message: "请输入系统名称" }]}>
              <Input maxLength={255} />
            </Form.Item>
            {!editingSystem ? (
              <Form.Item label="初始状态" name="status">
                <Select options={systemStatusOptions.filter((option) => option.value !== "inactive")} />
              </Form.Item>
            ) : null}
            <Form.Item
              label="专门责任人"
              name="responsible_person_id"
              rules={
                (!editingSystem && createStatus === "active") ||
                editingSystem?.status === "active"
                  ? [{ required: true, message: "启用系统必须选择责任人" }]
                  : []
              }
            >
              <Select allowClear showSearch optionFilterProp="label" loading={peopleQuery.isLoading} options={personOptions} placeholder="选择启用人员" />
            </Form.Item>
          </div>
          <Form.Item label="说明" name="description"><Input.TextArea maxLength={4000} rows={4} showCount /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`停用业务系统${deactivatingSystem ? ` · ${deactivatingSystem.name}` : ""}`}
        open={Boolean(deactivatingSystem)}
        okText="确认停用"
        okButtonProps={{ danger: true }}
        confirmLoading={deactivateMutation.isPending}
        onCancel={() => setDeactivatingSystem(null)}
        onOk={() => deactivateForm.submit()}
      >
        <Typography.Paragraph>
          当前关联 {deactivatingSystem?.asset_count ?? 0} 个资产。停用系统后，该系统不能继续作为新的资产归属。
        </Typography.Paragraph>
        <Form form={deactivateForm} layout="vertical" onFinish={(values) => deactivateMutation.mutate(values)}>
          {deactivatingSystem?.asset_count ? (
            <>
              <Form.Item label="关联资产处理" name="asset_action" rules={[{ required: true, message: "请选择资产处理方式" }]}>
                <Radio.Group>
                  <Radio value="replace">转移到其他业务系统</Radio>
                  <Radio value="unassign">解除归属，进入待分配</Radio>
                </Radio.Group>
              </Form.Item>
              {assetAction === "replace" ? (
                <Form.Item label="目标业务系统" name="replacement_system_id" rules={[{ required: true, message: "请选择目标业务系统" }]}>
                  <Select
                    showSearch
                    optionFilterProp="label"
                    loading={replacementSystemsQuery.isLoading}
                    options={(replacementSystemsQuery.data?.items ?? [])
                      .filter((system) => system.id !== deactivatingSystem?.id)
                      .map((system) => ({ value: system.id, label: `${system.name} · ${system.code}` }))}
                  />
                </Form.Item>
              ) : null}
            </>
          ) : (
            <Typography.Text type="secondary">该系统没有关联资产，可直接停用。</Typography.Text>
          )}
        </Form>
      </Modal>
    </Space>
  );
}

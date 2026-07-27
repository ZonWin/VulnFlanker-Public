import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Tooltip,
  Typography,
  message
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRightLeft, Pencil, Plus, Power, RefreshCw, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { useAuth } from "@/app/auth";
import {
  createResponsibilityTeam,
  getOwnershipSummary,
  getPeople,
  getResponsibilityTeams,
  setResponsibilityTeamStatus,
  transferTeamMembers,
  updateResponsibilityTeam,
  type ResponsibilityTeam,
  type TeamCreate,
  type TeamStatus,
  type TeamUpdate
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
  cleanOptional,
  lifecycleOptions
} from "@/pages/ownership/common";

interface TeamFormValues {
  code: string;
  name: string;
  description?: string;
}

interface TransferFormValues {
  person_ids: string[];
}

export default function ResponsibilityTeamPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_superuser);
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [teamForm] = Form.useForm<TeamFormValues>();
  const [transferForm] = Form.useForm<TransferFormValues>();
  const [keyword, setKeyword] = useState(() => searchParams.get("keyword") ?? "");
  const [status, setStatus] = useState<TeamStatus | undefined>();
  const [hasMembers, setHasMembers] = useState<boolean | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [editingTeam, setEditingTeam] = useState<ResponsibilityTeam | null>(null);
  const [isTeamModalOpen, setIsTeamModalOpen] = useState(false);
  const [transferTarget, setTransferTarget] = useState<ResponsibilityTeam | null>(null);

  const teamsQuery = useQuery({
    queryKey: ["ownership", "teams", { keyword, status, hasMembers, page, pageSize }],
    queryFn: () =>
      getResponsibilityTeams({ keyword, status, has_members: hasMembers, page, page_size: pageSize })
  });
  const summaryQuery = useQuery({
    queryKey: ["ownership", "summary"],
    queryFn: getOwnershipSummary
  });
  const transferPeopleQuery = useQuery({
    queryKey: ["ownership", "people", "transfer-options"],
    queryFn: () => getPeople({ page_size: 200, sort_by: "name", sort_order: "asc" }),
    enabled: Boolean(transferTarget)
  });

  function refreshOwnership() {
    void queryClient.invalidateQueries({ queryKey: ["ownership"] });
  }

  const saveMutation = useMutation({
    mutationFn: async (values: TeamFormValues) => {
      if (editingTeam) {
        const payload: TeamUpdate = {
          expected_version: editingTeam.version,
          name: values.name.trim(),
          description: cleanOptional(values.description)
        };
        return updateResponsibilityTeam(editingTeam.id, payload);
      }
      const payload: TeamCreate = {
        code: values.code.trim(),
        name: values.name.trim(),
        description: cleanOptional(values.description)
      };
      return createResponsibilityTeam(payload);
    },
    onSuccess: () => {
      messageApi.success(editingTeam ? "责任团队已更新" : "责任团队已创建");
      setIsTeamModalOpen(false);
      setEditingTeam(null);
      teamForm.resetFields();
      refreshOwnership();
    },
    onError: (error) => messageApi.error(error.message)
  });

  const statusMutation = useMutation({
    mutationFn: ({ team, action }: { team: ResponsibilityTeam; action: "activate" | "deactivate" }) =>
      setResponsibilityTeamStatus(team.id, action, team.version),
    onSuccess: (_, variables) => {
      messageApi.success(variables.action === "activate" ? "责任团队已启用" : "责任团队已停用");
      refreshOwnership();
    },
    onError: (error) => messageApi.error(error.message)
  });

  const transferMutation = useMutation({
    mutationFn: (values: TransferFormValues) => {
      if (!transferTarget) {
        throw new Error("未选择目标团队");
      }
      return transferTeamMembers(transferTarget.id, values.person_ids);
    },
    onSuccess: () => {
      messageApi.success("成员已转入目标团队，下游归属已同步更新");
      setTransferTarget(null);
      transferForm.resetFields();
      refreshOwnership();
    },
    onError: (error) => messageApi.error(error.message)
  });

  function openCreate() {
    setEditingTeam(null);
    teamForm.resetFields();
    setIsTeamModalOpen(true);
  }

  function openEdit(team: ResponsibilityTeam) {
    setEditingTeam(team);
    teamForm.setFieldsValue({
      code: team.code,
      name: team.name,
      description: team.description ?? undefined
    });
    setIsTeamModalOpen(true);
  }

  function confirmStatus(team: ResponsibilityTeam) {
    const action = team.status === "active" ? "deactivate" : "activate";
    Modal.confirm({
      title: action === "activate" ? "启用责任团队" : "停用责任团队",
      content:
        action === "deactivate"
          ? `团队当前关联 ${team.person_count} 名人员、${team.business_system_count} 个业务系统和 ${team.asset_count} 个资产；存在人员时需先完成成员转移。`
          : "启用后可继续作为人员归属团队使用。",
      okText: action === "activate" ? "确认启用" : "确认停用",
      okButtonProps: { danger: action === "deactivate" },
      onOk: () => statusMutation.mutateAsync({ team, action })
    });
  }

  const columns: ColumnsType<ResponsibilityTeam> = [
    {
      title: "团队",
      key: "team",
      minWidth: 250,
      render: (_, team) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text strong>{team.name}</Typography.Text>
          <Typography.Text className="table-subtitle">{team.code}</Typography.Text>
        </Space>
      )
    },
    {
      title: "说明",
      dataIndex: "description",
      minWidth: 240,
      ellipsis: true,
      render: (value: string | null) => value || "-"
    },
    { title: "状态", dataIndex: "status", width: 100, render: (value: TeamStatus) => <LifecycleTag status={value} /> },
    { title: "人员", dataIndex: "person_count", width: 90 },
    { title: "业务系统", dataIndex: "business_system_count", width: 100 },
    {
      title: "关联资产",
      dataIndex: "asset_count",
      width: 100,
      render: (count: number, team) => (
        <Typography.Link onClick={() => navigate(`/assets?responsibility_team_id=${team.id}`)}>
          {count}
        </Typography.Link>
      )
    },
    { title: "更新时间", dataIndex: "updated_at", width: 185, render: formatDateTime },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 250,
      render: (_, team) => (
        <Space size={2}>
          <Tooltip title={!isAdmin ? "需要超级管理员权限" : undefined}>
            <Button type="link" disabled={!isAdmin} icon={<Pencil size={15} />} onClick={() => openEdit(team)}>编辑</Button>
          </Tooltip>
          <Tooltip title={!isAdmin ? "需要超级管理员权限" : "将选中人员转入该团队"}>
            <Button
              type="link"
              disabled={!isAdmin || team.status !== "active"}
              icon={<ArrowRightLeft size={15} />}
              onClick={() => {
                setTransferTarget(team);
                transferForm.resetFields();
              }}
            >
              转入成员
            </Button>
          </Tooltip>
          <Button
            type="link"
            danger={team.status === "active"}
            disabled={!isAdmin}
            icon={<Power size={15} />}
            onClick={() => confirmStatus(team)}
          >
            {team.status === "active" ? "停用" : "启用"}
          </Button>
        </Space>
      )
    }
  ];

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title="责任团队"
        subtitle="维护人员的组织归属；团队调整会沿业务系统链路投影到资产。"
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} loading={teamsQuery.isFetching} onClick={() => refreshOwnership()}>刷新</Button>
            <Button type="primary" icon={<Plus size={16} />} disabled={!isAdmin} onClick={openCreate}>新建团队</Button>
          </Space>
        }
      />
      <ReadOnlyNotice isAdmin={isAdmin} />
      <OwnershipMetrics summary={summaryQuery.data} />
      <Card className="content-card" title="团队列表">
        <div className="table-toolbar ownership-toolbar">
          <Input
            allowClear
            prefix={<Search size={16} />}
            placeholder="搜索团队编码或名称"
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1);
            }}
          />
          <Select
            allowClear
            placeholder="全部状态"
            options={lifecycleOptions}
            value={status}
            onChange={(value) => {
              setStatus(value);
              setPage(1);
            }}
          />
          <Select
            allowClear
            placeholder="成员情况"
            options={[
              { label: "有成员", value: true },
              { label: "无成员", value: false }
            ]}
            value={hasMembers}
            onChange={(value) => {
              setHasMembers(value);
              setPage(1);
            }}
          />
        </div>
        {teamsQuery.isError ? <ErrorState error={teamsQuery.error} /> : null}
        <ResizableTable
          rowKey="id"
          storageKey="ownership-teams"
          columns={columns}
          dataSource={teamsQuery.data?.items ?? []}
          loading={teamsQuery.isLoading}
          locale={{ emptyText: <EmptyState title="暂无责任团队，请先新建团队" /> }}
          pagination={{
            current: page,
            pageSize,
            total: teamsQuery.data?.total ?? 0,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个团队`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPageSize === pageSize ? nextPage : 1);
              setPageSize(nextPageSize);
            }
          }}
          scroll={{ x: 1240 }}
        />
      </Card>

      <Modal
        title={editingTeam ? "编辑责任团队" : "新建责任团队"}
        open={isTeamModalOpen}
        okText={editingTeam ? "保存" : "创建"}
        confirmLoading={saveMutation.isPending}
        onCancel={() => setIsTeamModalOpen(false)}
        onOk={() => teamForm.submit()}
      >
        <Form form={teamForm} layout="vertical" onFinish={(values) => saveMutation.mutate(values)}>
          <Form.Item label="团队编码" name="code" rules={[{ required: true, message: "请输入团队编码" }]}>
            <Input disabled={Boolean(editingTeam)} maxLength={64} placeholder="例如 SEC-OPS" />
          </Form.Item>
          <Form.Item label="团队名称" name="name" rules={[{ required: true, message: "请输入团队名称" }]}>
            <Input maxLength={255} />
          </Form.Item>
          <Form.Item label="说明" name="description">
            <Input.TextArea maxLength={4000} rows={4} showCount />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`转入成员${transferTarget ? ` · ${transferTarget.name}` : ""}`}
        open={Boolean(transferTarget)}
        okText="确认转入"
        confirmLoading={transferMutation.isPending}
        onCancel={() => setTransferTarget(null)}
        onOk={() => transferForm.submit()}
      >
        <Typography.Paragraph type="secondary">
          人员所属团队改变后，其负责的业务系统及资产会自动显示新的责任团队。
        </Typography.Paragraph>
        <Form form={transferForm} layout="vertical" onFinish={(values) => transferMutation.mutate(values)}>
          <Form.Item label="选择人员" name="person_ids" rules={[{ required: true, message: "请选择至少一名人员" }]}>
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              loading={transferPeopleQuery.isLoading}
              options={(transferPeopleQuery.data?.items ?? [])
                .filter((person) => person.team.id !== transferTarget?.id)
                .map((person) => ({
                  value: person.id,
                  label: `${person.name} · ${person.team.name}${person.status === "inactive" ? "（已停用）" : ""}`
                }))}
              placeholder="搜索并选择要转入的人员"
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

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
import { Pencil, Plus, Power, RefreshCw, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { useAuth } from "@/app/auth";
import {
  activatePerson,
  createPerson,
  deactivatePerson,
  getOwnershipSummary,
  getPeople,
  getResponsibilityTeams,
  updatePerson,
  type Person,
  type PersonCreate,
  type PersonStatus,
  type PersonUpdate
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

interface PersonFormValues {
  employee_no?: string;
  name: string;
  email?: string;
  phone?: string;
  team_id: string;
  notes?: string;
  status?: PersonStatus;
}

interface DeactivateFormValues {
  replacement_person_id?: string;
}

export default function PeoplePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = Boolean(user?.is_superuser);
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [personForm] = Form.useForm<PersonFormValues>();
  const [deactivateForm] = Form.useForm<DeactivateFormValues>();
  const [keyword, setKeyword] = useState(() => searchParams.get("keyword") ?? "");
  const [status, setStatus] = useState<PersonStatus | undefined>();
  const [teamId, setTeamId] = useState<string | undefined>();
  const [hasEmail, setHasEmail] = useState<boolean | undefined>();
  const [hasSystems, setHasSystems] = useState<boolean | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [editingPerson, setEditingPerson] = useState<Person | null>(null);
  const [isPersonModalOpen, setIsPersonModalOpen] = useState(false);
  const [deactivatingPerson, setDeactivatingPerson] = useState<Person | null>(null);

  const peopleQuery = useQuery({
    queryKey: ["ownership", "people", { keyword, status, teamId, hasEmail, hasSystems, page, pageSize }],
    queryFn: () =>
      getPeople({ keyword, status, team_id: teamId, has_email: hasEmail, has_systems: hasSystems, page, page_size: pageSize })
  });
  const summaryQuery = useQuery({ queryKey: ["ownership", "summary"], queryFn: getOwnershipSummary });
  const teamsQuery = useQuery({
    queryKey: ["ownership", "teams", "form-options"],
    queryFn: () => getResponsibilityTeams({ page_size: 200, sort_by: "name", sort_order: "asc" })
  });
  const replacementPeopleQuery = useQuery({
    queryKey: ["ownership", "people", "replacement-options"],
    queryFn: () => getPeople({ status: "active", page_size: 200, sort_by: "name", sort_order: "asc" }),
    enabled: Boolean(deactivatingPerson)
  });

  function refreshOwnership() {
    void queryClient.invalidateQueries({ queryKey: ["ownership"] });
  }

  const saveMutation = useMutation({
    mutationFn: async (values: PersonFormValues) => {
      const fields = {
        employee_no: cleanOptional(values.employee_no),
        name: values.name.trim(),
        email: cleanOptional(values.email),
        phone: cleanOptional(values.phone),
        team_id: values.team_id,
        notes: cleanOptional(values.notes)
      };
      if (editingPerson) {
        const payload: PersonUpdate = {
          ...fields,
          expected_version: editingPerson.version
        };
        return updatePerson(editingPerson.id, payload);
      }
      const payload: PersonCreate = { ...fields, status: values.status ?? "active" };
      return createPerson(payload);
    },
    onSuccess: () => {
      messageApi.success(editingPerson ? "人员信息已更新" : "人员已创建");
      setIsPersonModalOpen(false);
      setEditingPerson(null);
      personForm.resetFields();
      refreshOwnership();
    },
    onError: (error) => messageApi.error(error.message)
  });

  const activateMutation = useMutation({
    mutationFn: (person: Person) => activatePerson(person.id, person.version),
    onSuccess: () => {
      messageApi.success("人员已启用");
      refreshOwnership();
    },
    onError: (error) => messageApi.error(error.message)
  });

  const deactivateMutation = useMutation({
    mutationFn: (values: DeactivateFormValues) => {
      if (!deactivatingPerson) {
        throw new Error("未选择要停用的人员");
      }
      return deactivatePerson(
        deactivatingPerson.id,
        deactivatingPerson.version,
        values.replacement_person_id
      );
    },
    onSuccess: () => {
      messageApi.success("人员已停用，负责的业务系统已按选择完成转移");
      setDeactivatingPerson(null);
      deactivateForm.resetFields();
      refreshOwnership();
    },
    onError: (error) => messageApi.error(error.message)
  });

  function openCreate() {
    setEditingPerson(null);
    personForm.resetFields();
    personForm.setFieldsValue({ status: "active" });
    setIsPersonModalOpen(true);
  }

  function openEdit(person: Person) {
    setEditingPerson(person);
    personForm.setFieldsValue({
      employee_no: person.employee_no ?? undefined,
      name: person.name,
      email: person.email ?? undefined,
      phone: person.phone ?? undefined,
      team_id: person.team.id,
      notes: person.notes ?? undefined,
      status: person.status
    });
    setIsPersonModalOpen(true);
  }

  const columns: ColumnsType<Person> = [
    {
      title: "人员",
      key: "person",
      minWidth: 220,
      render: (_, person) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text strong>{person.name}</Typography.Text>
          <Typography.Text className="table-subtitle">{person.employee_no || "未设置工号"}</Typography.Text>
        </Space>
      )
    },
    {
      title: "联系方式",
      key: "contact",
      minWidth: 230,
      render: (_, person) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{person.email || "-"}</Typography.Text>
          <Typography.Text className="table-subtitle">{person.phone || "-"}</Typography.Text>
        </Space>
      )
    },
    {
      title: "所属团队",
      key: "team",
      width: 190,
      render: (_, person) => (
        <Space orientation="vertical" size={0}>
          <Typography.Text>{person.team.name}</Typography.Text>
          <Typography.Text className="table-subtitle">{person.team.code}</Typography.Text>
        </Space>
      )
    },
    { title: "状态", dataIndex: "status", width: 90, render: (value: PersonStatus) => <LifecycleTag status={value} /> },
    { title: "负责系统", dataIndex: "business_system_count", width: 100 },
    {
      title: "下游资产",
      dataIndex: "asset_count",
      width: 100,
      render: (count: number, person) => (
        <Typography.Link onClick={() => navigate(`/assets?responsible_person_id=${person.id}`)}>
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
      render: (_, person) => (
        <Space size={2}>
          <Tooltip title={!isAdmin ? "需要超级管理员权限" : undefined}>
            <Button type="link" disabled={!isAdmin} icon={<Pencil size={15} />} onClick={() => openEdit(person)}>编辑</Button>
          </Tooltip>
          {person.status === "active" ? (
            <Button
              type="link"
              danger
              disabled={!isAdmin}
              icon={<Power size={15} />}
              onClick={() => {
                setDeactivatingPerson(person);
                deactivateForm.resetFields();
              }}
            >
              停用
            </Button>
          ) : (
            <Button
              type="link"
              disabled={!isAdmin}
              icon={<Power size={15} />}
              loading={activateMutation.isPending}
              onClick={() => activateMutation.mutate(person)}
            >
              启用
            </Button>
          )}
        </Space>
      )
    }
  ];

  const teamOptions = (teamsQuery.data?.items ?? []).map((team) => ({
    label: `${team.name} · ${team.code}${team.status === "inactive" ? "（已停用）" : ""}`,
    value: team.id,
    disabled: team.status !== "active"
  }));

  return (
    <Space className="page-stack" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader
        title="人员管理"
        subtitle="维护专门责任人及其团队；人员负责业务系统，资产归属沿该链路自动解析。"
        extra={
          <Space>
            <Button icon={<RefreshCw size={16} />} loading={peopleQuery.isFetching} onClick={refreshOwnership}>刷新</Button>
            <Button type="primary" icon={<Plus size={16} />} disabled={!isAdmin} onClick={openCreate}>新建人员</Button>
          </Space>
        }
      />
      <ReadOnlyNotice isAdmin={isAdmin} />
      <OwnershipMetrics summary={summaryQuery.data} />
      <Card className="content-card" title="人员列表">
        <div className="table-toolbar ownership-toolbar">
          <Input
            allowClear
            prefix={<Search size={16} />}
            placeholder="搜索姓名、工号、邮箱或电话"
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
            placeholder="邮箱情况"
            options={[
              { label: "有邮箱", value: true },
              { label: "无邮箱", value: false }
            ]}
            value={hasEmail}
            onChange={(value) => {
              setHasEmail(value);
              setPage(1);
            }}
          />
          <Select
            allowClear
            placeholder="负责系统"
            options={[
              { label: "负责系统", value: true },
              { label: "未负责系统", value: false }
            ]}
            value={hasSystems}
            onChange={(value) => {
              setHasSystems(value);
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
        </div>
        {peopleQuery.isError ? <ErrorState error={peopleQuery.error} /> : null}
        <ResizableTable
          rowKey="id"
          storageKey="ownership-people"
          columns={columns}
          dataSource={peopleQuery.data?.items ?? []}
          loading={peopleQuery.isLoading}
          locale={{ emptyText: <EmptyState title="暂无人员，请先创建并绑定团队" /> }}
          pagination={{
            current: page,
            pageSize,
            total: peopleQuery.data?.total ?? 0,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 名人员`,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPageSize === pageSize ? nextPage : 1);
              setPageSize(nextPageSize);
            }
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      <Modal
        title={editingPerson ? "编辑人员" : "新建人员"}
        open={isPersonModalOpen}
        width={620}
        okText={editingPerson ? "保存" : "创建"}
        confirmLoading={saveMutation.isPending}
        onCancel={() => setIsPersonModalOpen(false)}
        onOk={() => personForm.submit()}
      >
        <Form form={personForm} layout="vertical" onFinish={(values) => saveMutation.mutate(values)}>
          <div className="ownership-form-grid">
            <Form.Item label="姓名" name="name" rules={[{ required: true, message: "请输入姓名" }]}>
              <Input maxLength={255} />
            </Form.Item>
            <Form.Item label="工号" name="employee_no"><Input maxLength={64} /></Form.Item>
            <Form.Item label="所属团队" name="team_id" rules={[{ required: true, message: "请选择启用团队" }]}>
              <Select showSearch optionFilterProp="label" loading={teamsQuery.isLoading} options={teamOptions} />
            </Form.Item>
            {!editingPerson ? (
              <Form.Item label="初始状态" name="status"><Select options={lifecycleOptions} /></Form.Item>
            ) : null}
            <Form.Item label="邮箱" name="email" rules={[{ type: "email", message: "请输入有效邮箱" }]}>
              <Input maxLength={320} />
            </Form.Item>
            <Form.Item label="电话" name="phone"><Input maxLength={64} /></Form.Item>
          </div>
          <Form.Item label="备注" name="notes"><Input.TextArea maxLength={4000} rows={3} showCount /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`停用人员${deactivatingPerson ? ` · ${deactivatingPerson.name}` : ""}`}
        open={Boolean(deactivatingPerson)}
        okText="确认停用"
        okButtonProps={{ danger: true }}
        confirmLoading={deactivateMutation.isPending}
        onCancel={() => setDeactivatingPerson(null)}
        onOk={() => deactivateForm.submit()}
      >
        <Typography.Paragraph>
          该人员当前负责 {deactivatingPerson?.business_system_count ?? 0} 个业务系统，覆盖 {deactivatingPerson?.asset_count ?? 0} 个资产。
        </Typography.Paragraph>
        <Form form={deactivateForm} layout="vertical" onFinish={(values) => deactivateMutation.mutate(values)}>
          <Form.Item
            label="业务系统接替人"
            name="replacement_person_id"
            rules={deactivatingPerson?.business_system_count ? [{ required: true, message: "存在负责系统时必须选择接替人" }] : []}
            extra="转移与人员停用将在同一事务完成。"
          >
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              loading={replacementPeopleQuery.isLoading}
              options={(replacementPeopleQuery.data?.items ?? [])
                .filter((person) => person.id !== deactivatingPerson?.id)
                .map((person) => ({ value: person.id, label: `${person.name} · ${person.team.name}` }))}
              placeholder={deactivatingPerson?.business_system_count ? "请选择接替人" : "无负责系统，可不选择"}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

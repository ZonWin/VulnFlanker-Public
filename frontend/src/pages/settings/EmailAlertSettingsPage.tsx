import { t } from "@/app/i18n";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Form,
  Input,
  InputNumber,
  message,
  Row,
  Select,
  Space,
  Switch,
  Tag,
  Typography
} from "antd";
import { MailCheck, Save, Send } from "lucide-react";
import { useEffect, useState } from "react";

import {
  getEmailSettings,
  previewEmailTemplates,
  sendTestEmail,
  updateEmailSettings
} from "@/api/emailAlerts";
import type { EmailSettingsUpdate } from "@/api/types";
import ErrorState from "@/components/ErrorState";
import LoadingBlock from "@/components/LoadingBlock";
import PageHeader from "@/components/PageHeader";

type SettingsForm = EmailSettingsUpdate & { smtp_password?: string; clear_password?: boolean };
type TemplateDraft = {
  subject_template: string;
  text_body_template: string;
  html_body_template: string;
};

const defaultDraft: TemplateDraft = {
  subject_template: "",
  text_body_template: "",
  html_body_template: ""
};

export default function EmailAlertSettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<SettingsForm>();
  const [messageApi, contextHolder] = message.useMessage();
  const [testRecipient, setTestRecipient] = useState("");
  const [templateDraft, setTemplateDraft] = useState<TemplateDraft>(defaultDraft);
  const [debouncedDraft, setDebouncedDraft] = useState<TemplateDraft>(defaultDraft);

  const settingsQuery = useQuery({
    queryKey: ["email-settings"],
    queryFn: getEmailSettings
  });
  const settings = settingsQuery.data;
  const emailCapabilityEnabled = Form.useWatch("enabled", form);

  useEffect(() => {
    if (!settings) return;
    const values: SettingsForm = {
      enabled: settings.enabled,
      automatic_enabled: settings.automatic_enabled,
      risk_threshold: settings.risk_threshold,
      retry_enabled: settings.retry_enabled,
      smtp_host: settings.smtp_host,
      smtp_port: settings.smtp_port,
      smtp_security: settings.smtp_security,
      smtp_username: settings.smtp_username,
      smtp_password: "",
      clear_password: false,
      sender_name: settings.sender_name,
      sender_email: settings.sender_email,
      reply_to: settings.reply_to,
      timeout_seconds: settings.timeout_seconds,
      subject_template: settings.subject_template,
      text_body_template: settings.text_body_template,
      html_body_template: settings.html_body_template
    };
    form.setFieldsValue(values);
    const templates = {
      subject_template: settings.subject_template,
      text_body_template: settings.text_body_template,
      html_body_template: settings.html_body_template
    };
    setTemplateDraft(templates);
    setDebouncedDraft(templates);
  }, [form, settings]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedDraft(templateDraft), 250);
    return () => window.clearTimeout(timer);
  }, [templateDraft]);

  const previewQuery = useQuery({
    queryKey: ["email-settings", "preview", debouncedDraft],
    queryFn: () => previewEmailTemplates(debouncedDraft),
    enabled: Boolean(
      debouncedDraft.subject_template &&
      debouncedDraft.text_body_template &&
      debouncedDraft.html_body_template
    ),
    retry: false
  });

  const saveMutation = useMutation({
    mutationFn: (values: SettingsForm) => {
      const password = values.smtp_password?.trim();
      return updateEmailSettings({
        ...values,
        smtp_password: password || undefined,
        expected_version: settings?.version
      });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["email-settings"], data);
      form.setFieldValue("smtp_password", "");
      form.setFieldValue("clear_password", false);
      messageApi.success(t("邮件告警设置已保存"));
    },
    onError: (error) => messageApi.error(error instanceof Error ? error.message : t("保存邮件告警设置失败"))
  });

  const testMutation = useMutation({
    mutationFn: () => sendTestEmail(testRecipient.trim()),
    onSuccess: (result) => {
      messageApi.success(result.message);
      void queryClient.invalidateQueries({ queryKey: ["email-deliveries"] });
    },
    onError: (error) => messageApi.error(error instanceof Error ? error.message : t("测试邮件发送失败"))
  });

  if (settingsQuery.isLoading) return <LoadingBlock />;
  if (settingsQuery.isError) return <ErrorState error={settingsQuery.error} />;

  return (
    <Space className="page-stack email-settings-page" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader title={t("邮件告警设置")} />
      <Alert
        showIcon
        type="info"
        title={t("邮件发送与风险评估事务相互独立")}
        description={t("邮件失败不会回滚业务；缺少主责任人邮箱的告警会记录为已跳过。")}
      />
      <Form<SettingsForm>
        form={form}
        layout="vertical"
        requiredMark={false}
        onFinish={(values) => saveMutation.mutate(values)}
        onValuesChange={(_, values) => {
          setTemplateDraft({
            subject_template: values.subject_template ?? "",
            text_body_template: values.text_body_template ?? "",
            html_body_template: values.html_body_template ?? ""
          });
        }}
      >
        <Card className="content-card" title={t("告警策略")}>
          <Row gutter={[24, 8]}>
            <Col xs={24} md={8}>
              <Form.Item label={t("邮件能力总开关")} name="enabled" valuePropName="checked">
                <Switch checkedChildren={t("开启")} unCheckedChildren={t("关闭")} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={t("自动告警")} name="automatic_enabled" valuePropName="checked">
                <Switch checkedChildren={t("开启")} unCheckedChildren={t("关闭")} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={t("失败自动重试")} name="retry_enabled" valuePropName="checked">
                <Switch checkedChildren={t("开启")} unCheckedChildren={t("关闭")} />
              </Form.Item>
              <Typography.Text type="secondary">{t("默认在 1、5、30 分钟后重试")}</Typography.Text>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={t("风险阈值")} name="risk_threshold" rules={[{ required: true }]}>
                <Select options={[
                  { value: "low", label: t("低危及以上") },
                  { value: "medium", label: t("中危及以上") },
                  { value: "high", label: t("高危及以上") },
                  { value: "critical", label: t("严重风险") }
                ]} />
              </Form.Item>
            </Col>
          </Row>
        </Card>

        <Card className="content-card" title={t("邮件服务器")}>
          <Row gutter={[24, 0]}>
            <Col xs={24} md={16}><Form.Item label={t("SMTP 服务器")} name="smtp_host" rules={[{ required: true, message: t("请输入 SMTP 服务器") }]}><Input placeholder="smtp.example.com" autoComplete="off" /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item label={t("端口")} name="smtp_port" rules={[{ required: true }]}><InputNumber min={1} max={65535} style={{ width: "100%" }} /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item label={t("连接安全")} name="smtp_security" rules={[{ required: true }]}><Select options={[
              { value: "starttls", label: "STARTTLS" },
              { value: "ssl_tls", label: "SSL/TLS" },
              { value: "none", label: t("无加密（不推荐）") }
            ]} /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item label={t("超时（秒）")} name="timeout_seconds"><InputNumber min={5} max={60} style={{ width: "100%" }} /></Form.Item></Col>
            <Col xs={24} md={12}><Form.Item label={t("SMTP 用户名")} name="smtp_username"><Input autoComplete="username" /></Form.Item></Col>
            <Col xs={24} md={12}>
              <Form.Item label={t("SMTP 密码")} name="smtp_password" extra={settings?.has_password ? t("已安全保存；留空表示保持不变") : t("密码将加密保存且不会回显")}>
                <Input.Password autoComplete="new-password" placeholder={settings?.has_password ? t("保持现有密码") : t("输入 SMTP 密码")} />
              </Form.Item>
              {settings?.has_password ? <Form.Item name="clear_password" valuePropName="checked"><Checkbox>{t("清除已保存的 SMTP 密码")}</Checkbox></Form.Item> : null}
            </Col>
            <Col xs={24} md={8}><Form.Item label={t("发件人名称")} name="sender_name"><Input /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item label={t("发件邮箱")} name="sender_email" rules={[{ type: "email", message: t("请输入有效邮箱") }]}><Input /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item label="Reply-To" name="reply_to" rules={[{ type: "email", message: t("请输入有效邮箱") }]}><Input /></Form.Item></Col>
          </Row>
        </Card>

        <Card className="content-card" title={t("告警模板")}>
          <Space orientation="vertical" size={10} style={{ width: "100%" }}>
            <Typography.Text type="secondary">{t("仅支持以下受控占位符，不支持脚本或模板表达式。")}</Typography.Text>
            <Space wrap>{settings?.supported_template_variables.map((name) => <Tag key={name}>{`{{${name}}}`}</Tag>)}</Space>
          </Space>
          <Row gutter={[24, 16]} className="email-template-grid">
            <Col xs={24} xl={12}>
              <Form.Item label={t("邮件主题模板")} name="subject_template" rules={[{ required: true }]}><Input maxLength={500} /></Form.Item>
              <Form.Item label={t("纯文本正文模板")} name="text_body_template" rules={[{ required: true }]}><Input.TextArea rows={10} className="template-editor" /></Form.Item>
              <Form.Item label={t("HTML 正文模板")} name="html_body_template" rules={[{ required: true }]}><Input.TextArea rows={14} className="template-editor" /></Form.Item>
            </Col>
            <Col xs={24} xl={12}>
              <Typography.Title level={5}>{t("实时预览")}</Typography.Title>
              {previewQuery.isError ? <Alert type="error" showIcon title={t("模板校验失败")} description={previewQuery.error instanceof Error ? previewQuery.error.message : t("未知错误")} /> : null}
              <Card size="small" title={previewQuery.data?.subject || t("邮件主题预览")} loading={previewQuery.isFetching}>
                <Typography.Paragraph><pre className="email-text-preview">{previewQuery.data?.text_body || t("等待模板输入")}</pre></Typography.Paragraph>
                <iframe className="email-preview-frame" title={t("HTML 邮件预览")} sandbox="" srcDoc={previewQuery.data?.html_body || ""} />
              </Card>
            </Col>
          </Row>
        </Card>

        <Card className="content-card" title={t("测试发送")}>
          <Alert type="warning" showIcon title={t("请先保存设置，再发送测试邮件。总开关关闭时不可发送。")}/>
          <Space wrap className="email-test-row">
            <Input value={testRecipient} onChange={(event) => setTestRecipient(event.target.value)} placeholder={t("测试收件邮箱")} prefix={<MailCheck size={16} />} />
            <Button icon={<Send size={16} />} loading={testMutation.isPending} disabled={!emailCapabilityEnabled || !testRecipient.trim()} onClick={() => testMutation.mutate()}>{t("发送测试邮件")}</Button>
          </Space>
        </Card>

        <div className="platform-settings-actions">
          <Button type="primary" htmlType="submit" icon={<Save size={16} />} loading={saveMutation.isPending}>{t("保存设置")}</Button>
        </div>
      </Form>
    </Space>
  );
}

import { Alert, Button, Card, Form, Input, Typography } from "antd";
import {
  LockKeyhole,
  LogIn,
  ShieldCheck,
  UserPlus,
  UserRound
} from "lucide-react";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import type { LoginPayload, SetupAdminPayload } from "@/api/auth";
import { useAuth } from "@/app/auth";
import { platformLogoSrc, usePlatformSettings } from "@/app/platformSettings";

type LoginLocationState = {
  from?: {
    pathname?: string;
    search?: string;
  };
};

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, isLoading, loginAsync, needsSetup, setupAdminAsync } =
    useAuth();
  const { settings } = usePlatformSettings();
  const [form] = Form.useForm<LoginPayload>();
  const [setupForm] = Form.useForm<
    SetupAdminPayload & { confirmPassword: string }
  >();
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fromState = location.state as LoginLocationState | null;
  const targetPath =
    `${fromState?.from?.pathname ?? "/risk-queue"}${fromState?.from?.search ?? ""}`;

  if (!isLoading && isAuthenticated) {
    return <Navigate to={targetPath} replace />;
  }

  return (
    <main className="login-shell">
      <section className="login-panel" aria-label={`${settings.platform_name} 登录`}>
        <div className="login-brand">
          <span className="login-brand-mark">
            <img
              src={platformLogoSrc(settings)}
              alt={`${settings.platform_name} LOGO`}
              className="login-brand-logo"
            />
          </span>
          <div>
            <Typography.Title level={1}>{settings.platform_name}</Typography.Title>
            <Typography.Text>{settings.platform_subtitle}</Typography.Text>
          </div>
        </div>

        <Card className="login-card">
          {needsSetup ? (
            <>
              <Typography.Title level={2}>初始化管理员</Typography.Title>
              <Form
                form={setupForm}
                layout="vertical"
                requiredMark={false}
                onFinish={(values) => {
                  setSubmitting(true);
                  setErrorMessage(null);
                  void setupAdminAsync({
                    username: values.username,
                    password: values.password,
                    display_name: values.display_name || null
                  })
                    .then(() => {
                      navigate(targetPath, { replace: true });
                    })
                    .catch((error: unknown) => {
                      setErrorMessage(
                        error instanceof Error ? error.message : "初始化失败"
                      );
                    })
                    .finally(() => {
                      setSubmitting(false);
                    });
                }}
              >
                {errorMessage ? (
                  <Alert
                    className="login-error"
                    type="error"
                    showIcon
                    message={errorMessage}
                  />
                ) : null}

                <Form.Item
                  name="username"
                  label="用户名"
                  initialValue="admin"
                  rules={[
                    { required: true, message: "请输入用户名" },
                    { whitespace: true, message: "用户名不能只包含空格" }
                  ]}
                >
                  <Input
                    autoComplete="username"
                    prefix={<UserRound size={17} />}
                    placeholder="admin"
                  />
                </Form.Item>

                <Form.Item name="display_name" label="显示名称">
                  <Input
                    autoComplete="name"
                    prefix={<ShieldCheck size={17} />}
                    placeholder="系统管理员"
                  />
                </Form.Item>

                <Form.Item
                  name="password"
                  label="密码"
                  rules={[
                    { required: true, message: "请输入密码" },
                    { min: 8, message: "密码至少 8 位" }
                  ]}
                >
                  <Input.Password
                    autoComplete="new-password"
                    prefix={<LockKeyhole size={17} />}
                    placeholder="设置管理员密码"
                  />
                </Form.Item>

                <Form.Item
                  name="confirmPassword"
                  label="确认密码"
                  dependencies={["password"]}
                  rules={[
                    { required: true, message: "请再次输入密码" },
                    ({ getFieldValue }) => ({
                      validator(_, value) {
                        if (!value || getFieldValue("password") === value) {
                          return Promise.resolve();
                        }
                        return Promise.reject(new Error("两次输入的密码不一致"));
                      }
                    })
                  ]}
                >
                  <Input.Password
                    autoComplete="new-password"
                    prefix={<LockKeyhole size={17} />}
                    placeholder="再次输入管理员密码"
                  />
                </Form.Item>

                <Form.Item shouldUpdate>
                  {() => (
                    <Button
                      block
                      type="primary"
                      htmlType="submit"
                      icon={<UserPlus size={17} />}
                      loading={submitting}
                    >
                      创建管理员并进入系统
                    </Button>
                  )}
                </Form.Item>
              </Form>

              <Alert
                type="info"
                showIcon
                message="仅在系统不存在活跃超级管理员时开放初始化"
              />
            </>
          ) : (
            <>
              <Typography.Title level={2}>管理员登录</Typography.Title>
              <Form
                form={form}
                layout="vertical"
                requiredMark={false}
                onFinish={(values) => {
                  setSubmitting(true);
                  setErrorMessage(null);
                  void loginAsync(values)
                    .then(() => {
                      navigate(targetPath, { replace: true });
                    })
                    .catch((error: unknown) => {
                      setErrorMessage(
                        error instanceof Error ? error.message : "登录失败"
                      );
                    })
                    .finally(() => {
                      setSubmitting(false);
                    });
                }}
              >
                {errorMessage ? (
                  <Alert
                    className="login-error"
                    type="error"
                    showIcon
                    message={errorMessage}
                  />
                ) : null}

                <Form.Item
                  name="username"
                  label="用户名"
                  rules={[{ required: true, message: "请输入用户名" }]}
                >
                  <Input
                    autoComplete="username"
                    prefix={<UserRound size={17} />}
                    placeholder="admin"
                  />
                </Form.Item>

                <Form.Item
                  name="password"
                  label="密码"
                  rules={[{ required: true, message: "请输入密码" }]}
                >
                  <Input.Password
                    autoComplete="current-password"
                    prefix={<LockKeyhole size={17} />}
                    placeholder="输入管理员密码"
                  />
                </Form.Item>

                <Form.Item shouldUpdate>
                  {() => (
                    <Button
                      block
                      type="primary"
                      htmlType="submit"
                      icon={<LogIn size={17} />}
                      loading={submitting}
                    >
                      登录
                    </Button>
                  )}
                </Form.Item>
              </Form>
            </>
          )}
        </Card>
      </section>
    </main>
  );
}

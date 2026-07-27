import { Alert } from "antd";

interface ErrorStateProps {
  title?: string;
  error: unknown;
}

export default function ErrorState({ title = "请求失败", error }: ErrorStateProps) {
  const message = error instanceof Error ? error.message : "未知错误";

  return <Alert type="error" showIcon title={title} description={message} />;
}

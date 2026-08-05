import { t } from "@/app/i18n";
import { Alert } from "antd";

interface ErrorStateProps {
  title?: string;
  error: unknown;
}

export default function ErrorState({ title = t("请求失败"), error }: ErrorStateProps) {
  const message = error instanceof Error ? error.message : t("未知错误");

  return <Alert type="error" showIcon title={title} description={message} />;
}

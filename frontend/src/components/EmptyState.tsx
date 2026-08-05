import { t } from "@/app/i18n";
import { Empty } from "antd";
import type { ReactNode } from "react";

interface EmptyStateProps {
  title?: string;
  children?: ReactNode;
}

export default function EmptyState({ title = t("暂无数据"), children }: EmptyStateProps) {
  return (
    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={title}>
      {children}
    </Empty>
  );
}

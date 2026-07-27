import { Card, Space } from "antd";

import CopyrightInfoPanel from "@/components/CopyrightInfoPanel";
import PageHeader from "@/components/PageHeader";

export default function AboutInfoPage() {
  return (
    <Space className="page-stack about-info-page" orientation="vertical" size={16}>
      <PageHeader title="关于信息" />
      <Card className="content-card about-info-card">
        <CopyrightInfoPanel />
      </Card>
    </Space>
  );
}

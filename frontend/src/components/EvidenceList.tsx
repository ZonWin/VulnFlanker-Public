import { Empty, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { MatchEvidence, VerificationEvidence } from "@/api/types";
import ConfidenceBar from "@/components/ConfidenceBar";
import JsonDetails from "@/components/JsonDetails";
import { formatDateTime } from "@/utils/format";

type Evidence = MatchEvidence | VerificationEvidence;

interface EvidenceListProps {
  items: Evidence[];
  emptyText: string;
  mode?: "matching" | "verification";
}

function isVerificationEvidence(item: Evidence): item is VerificationEvidence {
  return "verification_task_id" in item;
}

function EvidenceExpandedDetail({ item }: { item: Evidence }) {
  return (
    <div className="evidence-expanded-detail">
      <div className="evidence-expanded-meta">
        {item.raw_ref ? (
          <Typography.Text type="secondary">原始来源：{item.raw_ref}</Typography.Text>
        ) : null}
        {isVerificationEvidence(item) ? (
          <Typography.Text type="secondary">
            验证时间：{formatDateTime(item.created_at)}
          </Typography.Text>
        ) : null}
      </div>
      <Typography.Text className="evidence-expanded-title">原始详情</Typography.Text>
      <JsonDetails value={item.details} />
    </div>
  );
}

export default function EvidenceList({
  items,
  emptyText,
  mode = "matching"
}: EvidenceListProps) {
  if (items.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />;
  }

  const columns: ColumnsType<Evidence> = [
    {
      title: "标题",
      dataIndex: "evidence_type",
      width: 220,
      render: (evidenceType: string) => (
        <Typography.Text strong>{evidenceType || "-"}</Typography.Text>
      )
    },
    {
      title: "标签",
      key: "labels",
      width: 170,
      render: (_: unknown, item) => (
        <Space size={4} wrap>
          {isVerificationEvidence(item) ? <Tag>只读验证</Tag> : <Tag>规则取证</Tag>}
          <Tag color={mode === "verification" ? "green" : "blue"}>
            {mode === "verification" ? "验证发现" : "事实依据"}
          </Tag>
        </Space>
      )
    },
    {
      title: "简述",
      dataIndex: "summary",
      render: (summary: string) => (
        <Typography.Text className="evidence-summary">{summary || "-"}</Typography.Text>
      )
    },
    {
      title: "置信度",
      dataIndex: "confidence",
      width: 130,
      render: (confidence: number) => <ConfidenceBar value={confidence} />
    }
  ];

  return (
    <Table<Evidence>
      className="evidence-table"
      rowKey="id"
      size="small"
      columns={columns}
      dataSource={items}
      pagination={{
        pageSize: 5,
        showSizeChanger: false,
        hideOnSinglePage: true,
        size: "small"
      }}
      expandable={{
        expandedRowRender: (item) => <EvidenceExpandedDetail item={item} />
      }}
    />
  );
}

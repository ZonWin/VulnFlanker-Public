import { Typography } from "antd";

import { formatJson } from "@/utils/format";

interface JsonDetailsProps {
  value: unknown;
}

export default function JsonDetails({ value }: JsonDetailsProps) {
  return (
    <Typography.Text>
      <pre className="json-block">{formatJson(value)}</pre>
    </Typography.Text>
  );
}

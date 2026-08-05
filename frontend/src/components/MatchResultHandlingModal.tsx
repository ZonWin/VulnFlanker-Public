import { t } from "@/app/i18n";
import { Button, Form, Input, Modal, Select, Space, Typography } from "antd";
import { RotateCcw, Save } from "lucide-react";
import { useEffect } from "react";

import type {
  MatchResultHandlingUpdate,
  MatchResultSummary
} from "@/api/types";
import HandlingStatusTag, {
  handlingStatusOptions,
  isClosedHandlingStatus
} from "@/components/HandlingStatusTag";
import StatusTag from "@/components/StatusTag";

interface MatchResultHandlingModalProps {
  open: boolean;
  result: MatchResultSummary | null;
  saving: boolean;
  reopening: boolean;
  onCancel: () => void;
  onSave: (values: MatchResultHandlingUpdate) => void;
  onReopen: (note?: string | null) => void;
}

interface HandlingFormValues extends MatchResultHandlingUpdate {}

export default function MatchResultHandlingModal({
  open,
  result,
  saving,
  reopening,
  onCancel,
  onSave,
  onReopen
}: MatchResultHandlingModalProps) {
  const [form] = Form.useForm<HandlingFormValues>();

  useEffect(() => {
    if (!open || !result) {
      return;
    }
    form.setFieldsValue({
      handling_status: result.handling_status,
      note: ""
    });
  }, [form, open, result]);

  return (
    <Modal
      open={open}
      title={t("人工处置")}
      onCancel={onCancel}
      destroyOnHidden
      footer={
        <Space>
          {isClosedHandlingStatus(result?.handling_status) ? (
            <Button
              icon={<RotateCcw size={15} />}
              loading={reopening}
              disabled={saving}
              onClick={() => onReopen(form.getFieldValue("note")?.trim() || null)}
            >
              {t("重新打开")}</Button>
          ) : null}
          <Button onClick={onCancel} disabled={saving || reopening}>
            {t("取消")}</Button>
          <Button
            type="primary"
            icon={<Save size={15} />}
            loading={saving}
            disabled={!result || reopening}
            onClick={() => form.submit()}
          >
            {t("保存处置")}</Button>
        </Space>
      }
    >
      {result ? (
        <Space className="handling-modal-context" orientation="vertical" size={10}>
          <Space orientation="vertical" size={0}>
            <Typography.Text strong>{result.vulnerability_canonical_id}</Typography.Text>
            <Typography.Text type="secondary">{result.asset_hostname}</Typography.Text>
          </Space>
          <Space wrap>
            <Typography.Text type="secondary">{t("匹配状态")}</Typography.Text>
            <StatusTag value={result.status} />
            <Typography.Text type="secondary">{t("当前处置")}</Typography.Text>
            <HandlingStatusTag value={result.handling_status} />
          </Space>
        </Space>
      ) : null}
      <Form
        form={form}
        layout="vertical"
        className="handling-form"
        onFinish={(values) =>
          onSave({
            handling_status: values.handling_status,
            note: values.note?.trim() || null
          })
        }
      >
        <Form.Item
          label={t("处置状态")}
          name="handling_status"
          rules={[{ required: true, message: t("请选择处置状态") }]}
        >
          <Select options={handlingStatusOptions} />
        </Form.Item>
        <Form.Item label={t("本次说明")} name="note">
          <Input.TextArea
            rows={4}
            maxLength={4000}
            showCount
            placeholder={t("记录通知、整改、复核或闭环依据")}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}

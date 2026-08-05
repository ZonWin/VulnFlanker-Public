import { t } from "@/app/i18n";
import { useEffect, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  Form,
  Image,
  Input,
  message,
  Popconfirm,
  Space,
  Typography,
  Upload
} from "antd";
import { ImageUp, RotateCcw, Save, Trash2 } from "lucide-react";

import {
  getPlatformSettings,
  resetPlatformSettings,
  updatePlatformSettings
} from "@/api/platformSettings";
import type { PlatformSettingsUpdate } from "@/api/types";
import {
  defaultLogoUrl,
  platformLogoSrc,
  platformSettingsQueryKey
} from "@/app/platformSettings";
import PageHeader from "@/components/PageHeader";

const maxLogoBytes = 300 * 1024;
const acceptedLogoTypes = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
  "image/svg+xml"
]);

function fileToDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
      } else {
        reject(new Error(t("读取图片失败")));
      }
    };
    reader.onerror = () => reject(new Error(t("读取图片失败")));
    reader.readAsDataURL(file);
  });
}

export default function PlatformSettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<PlatformSettingsUpdate>();
  const [messageApi, contextHolder] = message.useMessage();
  const settingsQuery = useQuery({
    queryKey: platformSettingsQueryKey,
    queryFn: getPlatformSettings
  });
  const settings = settingsQuery.data;
  const [logoPreview, setLogoPreview] = useState(defaultLogoUrl);
  const watchedPlatformName = Form.useWatch("platform_name", form);
  const watchedPlatformSubtitle = Form.useWatch("platform_subtitle", form);

  useEffect(() => {
    if (!settings) {
      return;
    }
    form.setFieldsValue({
      platform_name: settings.platform_name,
      platform_subtitle: settings.platform_subtitle,
      logo_data_url: settings.logo_data_url
    });
    setLogoPreview(platformLogoSrc(settings));
  }, [form, settings]);

  const saveMutation = useMutation({
    mutationFn: updatePlatformSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(platformSettingsQueryKey, data);
      messageApi.success(t("平台设置已保存"));
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("保存平台设置失败"));
    }
  });

  const resetMutation = useMutation({
    mutationFn: resetPlatformSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(platformSettingsQueryKey, data);
      form.setFieldsValue({
        platform_name: data.platform_name,
        platform_subtitle: data.platform_subtitle,
        logo_data_url: data.logo_data_url
      });
      setLogoPreview(platformLogoSrc(data));
      messageApi.success(t("平台设置已恢复默认"));
    },
    onError: (error) => {
      messageApi.error(error instanceof Error ? error.message : t("恢复默认失败"));
    }
  });

  async function selectLogo(file: File) {
    if (!acceptedLogoTypes.has(file.type)) {
      messageApi.error(t("请选择 PNG、JPG、WebP、GIF 或 SVG 图片"));
      return false;
    }
    if (file.size > maxLogoBytes) {
      messageApi.error(t("LOGO 图片不能超过 300 KB"));
      return false;
    }

    const dataUrl = await fileToDataUrl(file);
    form.setFieldValue("logo_data_url", dataUrl);
    setLogoPreview(dataUrl);
    return false;
  }

  function removeLogo() {
    form.setFieldValue("logo_data_url", null);
    setLogoPreview(defaultLogoUrl);
  }

  return (
    <Space className="page-stack platform-settings-page" orientation="vertical" size={16}>
      {contextHolder}
      <PageHeader title={t("平台设置")} />

      <Card className="content-card">
        <Form<PlatformSettingsUpdate>
          form={form}
          layout="vertical"
          requiredMark={false}
          onFinish={(values) => saveMutation.mutate(values)}
        >
          <div className="platform-settings-grid">
            <div className="logo-preview-panel">
              <div className="platform-logo-preview">
                <Image src={logoPreview} alt={t("平台 LOGO")} preview={false} />
              </div>
              <Space className="logo-upload-controls" wrap>
                <Upload
                  accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml"
                  beforeUpload={selectLogo}
                  showUploadList={false}
                >
                  <Button icon={<ImageUp size={16} />}>{t("上传图片")}</Button>
                </Upload>
                <Button icon={<Trash2 size={16} />} onClick={removeLogo}>
                  {t("移除图片")}</Button>
              </Space>
              <Typography.Text type="secondary">
                {t("PNG/JPG/WebP/GIF/SVG，最大 300 KB。")}</Typography.Text>
            </div>

            <div className="platform-settings-form">
              <Form.Item
                label={t("平台名称")}
                name="platform_name"
                rules={[
                  { required: true, message: t("请输入平台名称") },
                  { whitespace: true, message: t("平台名称不能只包含空格") }
                ]}
              >
                <Input maxLength={80} placeholder="VulnFlanker" />
              </Form.Item>

              <Form.Item
                label={t("平台副标题")}
                name="platform_subtitle"
                rules={[
                  { required: true, message: t("请输入平台副标题") },
                  { whitespace: true, message: t("平台副标题不能只包含空格") }
                ]}
              >
                <Input maxLength={120} placeholder={t("漏洞监测平台")} />
              </Form.Item>

              <Form.Item name="logo_data_url" hidden>
                <Input />
              </Form.Item>

              <div className="platform-brand-preview">
                <span className="brand-mark">
                  <img src={logoPreview} alt="" className="brand-logo" />
                </span>
                <div className="brand-copy">
                  <span>{watchedPlatformName || "VulnFlanker"}</span>
                  <strong>{watchedPlatformSubtitle || t("漏洞监测平台")}</strong>
                </div>
              </div>
            </div>
          </div>

          <div className="platform-settings-actions">
            <Space wrap>
              <Button
                type="primary"
                htmlType="submit"
                icon={<Save size={16} />}
                loading={saveMutation.isPending}
                disabled={settingsQuery.isLoading}
              >
                {t("保存设置")}</Button>
              <Popconfirm
                title={t("恢复默认平台设置？")}
                okText={t("恢复默认")}
                cancelText={t("取消")}
                onConfirm={() => resetMutation.mutate()}
              >
                <Button
                  icon={<RotateCcw size={16} />}
                  loading={resetMutation.isPending}
                  disabled={settingsQuery.isLoading}
                >
                  {t("恢复默认")}</Button>
              </Popconfirm>
            </Space>
          </div>
        </Form>
      </Card>
    </Space>
  );
}

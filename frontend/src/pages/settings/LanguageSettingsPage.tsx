import { useState } from "react";

import { Alert, Card, Radio, Space, Typography } from "antd";
import { Languages } from "lucide-react";

import { setLocale, supportedLocales, t, useI18n, type Locale } from "@/app/i18n";
import PageHeader from "@/components/PageHeader";

export default function LanguageSettingsPage() {
  const { locale } = useI18n();
  const [selectedLocale, setSelectedLocale] = useState<Locale>(locale);

  const handleChange = (nextLocale: Locale) => {
    if (nextLocale === locale) {
      return;
    }
    setSelectedLocale(nextLocale);
    setLocale(nextLocale);
    window.location.reload();
  };

  return (
    <div className="settings-page">
      <PageHeader
        title={t("语言设置")}
        subtitle={t("选择平台界面语言；设置会保存在当前浏览器中。")}
      />
      <Card className="content-card language-settings-card">
        <Space direction="vertical" size={20} className="language-settings-content">
          <div className="language-settings-intro">
            <span className="language-settings-icon" aria-hidden="true">
              <Languages size={22} />
            </span>
            <div>
              <Typography.Title level={4}>{t("界面语言")}</Typography.Title>
              <Typography.Paragraph type="secondary">
                {t("切换后，导航、按钮、表格和表单提示会使用所选语言。")}</Typography.Paragraph>
            </div>
          </div>
          <Radio.Group
            className="language-options"
            value={selectedLocale}
            onChange={(event) => handleChange(event.target.value as Locale)}
            optionType="button"
            buttonStyle="solid"
            options={supportedLocales.map((item) => ({
              value: item.value,
              label: item.value === "en-US" ? "English" : t("中文")
            }))}
          />
          <Alert
            showIcon
            type="info"
            message={t("语言设置")}
            description={t("语言切换会立即应用，并在下次打开平台时继续生效。")}
          />
        </Space>
      </Card>
    </div>
  );
}

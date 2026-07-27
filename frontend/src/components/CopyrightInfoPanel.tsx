import { Space, Typography } from "antd";
import { ExternalLink, QrCode, Scale } from "lucide-react";

import { platformLogoSrc, usePlatformSettings } from "@/app/platformSettings";

const projectRepositoryUrl = "https://github.com/ZonWin/VulnFlanker";

export default function CopyrightInfoPanel() {
  const { settings } = usePlatformSettings();
  const logoSrc = platformLogoSrc(settings);

  return (
    <div className="copyright-panel">
      <div className="copyright-summary">
        <div className="copyright-brand-mark">
          <img
            src={logoSrc}
            alt={`${settings.platform_name} LOGO`}
            className="copyright-brand-logo"
          />
        </div>
        <div>
          <Typography.Title level={4}>{settings.platform_name}</Typography.Title>
          <Typography.Text type="secondary">
            {settings.platform_subtitle}
          </Typography.Text>
        </div>
      </div>

      <div className="copyright-grid">
        <div className="copyright-info-block">
          <Space direction="vertical" size={12} className="full-width">
            <div className="copyright-meta-row">
              <span className="copyright-meta-icon">
                <Scale size={18} />
              </span>
              <div>
                <Typography.Text strong>开源许可</Typography.Text>
                <Typography.Text>Apache-2.0</Typography.Text>
              </div>
            </div>
            <div className="copyright-meta-row">
              <span className="copyright-meta-icon">
                <ExternalLink size={18} />
              </span>
              <div>
                <Typography.Text strong>项目链接</Typography.Text>
                <Typography.Link
                  href={projectRepositoryUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  {projectRepositoryUrl}
                </Typography.Link>
              </div>
            </div>
          </Space>
        </div>

        <div className="copyright-qr-placeholder" aria-label="二维码预留位">
          <QrCode size={42} />
          <Typography.Text strong>二维码预留位</Typography.Text>
        </div>
      </div>
    </div>
  );
}

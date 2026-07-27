import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  titleExtra?: ReactNode;
  subtitle?: ReactNode;
  extra?: ReactNode;
}

export default function PageHeader({ title, titleExtra, subtitle, extra }: PageHeaderProps) {
  return (
    <div className="page-header">
      <div className="page-header-main">
        <div className="page-header-title-row">
          <h1>{title}</h1>
          {titleExtra ? <div className="page-header-title-extra">{titleExtra}</div> : null}
        </div>
        {subtitle ? <div className="page-header-subtitle">{subtitle}</div> : null}
      </div>
      {extra ? <div className="page-header-extra">{extra}</div> : null}
    </div>
  );
}

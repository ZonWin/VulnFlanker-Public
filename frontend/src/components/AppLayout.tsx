import { t } from "@/app/i18n";
import { useEffect, useState } from "react";

import { Avatar, Button, Layout, Menu, Space, Tooltip } from "antd";
import type { MenuProps } from "antd";
import {
  Activity,
  BadgeInfo,
  Bot,
  Building2,
  ChevronsLeft,
  ChevronsRight,
  ClipboardCheck,
  ClipboardList,
  Database,
  FileClock,
  FileQuestion,
  ListChecks,
  LogOut,
  Mail,
  MessageSquareText,
  Radar,
  SearchCheck,
  ShieldAlert,
  ServerCog,
  Settings,
  ShieldCheck,
  UserRound,
  Users,
  Languages,
  LayoutDashboard
} from "lucide-react";
import { Outlet, useLocation, useNavigate } from "react-router";

import { useAuth } from "@/app/auth";
import { platformLogoSrc, usePlatformSettings } from "@/app/platformSettings";
import NotificationCenter from "@/components/NotificationCenter";

type NavItem = {
  key: string;
  label: string;
  icon: typeof Radar;
};

type NavGroup = {
  key: string;
  label: string;
  icon: typeof Radar;
  defaultKey: string;
  items: NavItem[];
};

const navGroups: NavGroup[] = [
  {
    key: "dashboard",
    label: t("总览"),
    icon: LayoutDashboard,
    defaultKey: "/dashboard",
    items: [{ key: "/dashboard", label: t("总览"), icon: LayoutDashboard }]
  },
  {
    key: "risk",
    label: t("风险管理"),
    icon: Radar,
    defaultKey: "/risk-queue",
    items: [
      { key: "/risk-queue", label: t("风险队列"), icon: Radar },
      { key: "/matching", label: t("漏洞比对"), icon: SearchCheck },
      { key: "/verification-tasks", label: t("验证中心"), icon: ListChecks },
      { key: "/rules", label: t("规则说明"), icon: FileQuestion }
    ]
  },
  {
    key: "assets",
    label: t("资产管理"),
    icon: Database,
    defaultKey: "/assets",
    items: [
      { key: "/assets", label: t("资产列表"), icon: Database },
      { key: "/business-systems", label: t("业务系统"), icon: Building2 },
      { key: "/people", label: t("人员管理"), icon: UserRound },
      { key: "/responsibility-teams", label: t("责任团队"), icon: Users },
      { key: "/agents", label: t("Agent 管理"), icon: ServerCog }
    ]
  },
  {
    key: "intel",
    label: t("漏洞情报"),
    icon: Activity,
    defaultKey: "/vulnerabilities",
    items: [
      { key: "/vulnerabilities", label: t("漏洞列表"), icon: Activity },
      { key: "/vulnerability-reviews", label: t("漏洞复核"), icon: ShieldAlert },
      { key: "/vulnerability-repository", label: t("漏洞仓库"), icon: Database },
      { key: "/intel", label: t("情报采集"), icon: ShieldCheck }
    ]
  },
  {
    key: "records",
    label: t("记录日志"),
    icon: ClipboardList,
    defaultKey: "/task-center",
    items: [
      { key: "/task-center", label: t("任务中心"), icon: ClipboardList },
      { key: "/audit/handling", label: t("处置记录"), icon: ClipboardCheck },
      { key: "/audit/notifications", label: t("历史消息"), icon: MessageSquareText },
      { key: "/audit/email-deliveries", label: t("邮件日志"), icon: Mail },
      { key: "/audit", label: t("审计日志"), icon: FileClock }
    ]
  },
  {
    key: "settings",
    label: t("系统设置"),
    icon: Settings,
    defaultKey: "/settings/platform",
    items: [
      { key: "/settings/platform", label: t("平台设置"), icon: Settings },
      { key: "/settings/email-alerts", label: t("邮件告警设置"), icon: Mail },
      { key: "/settings/ai", label: t("AI 补全设置"), icon: Bot },
      { key: "/settings/language", label: t("语言设置"), icon: Languages },
      { key: "/settings/about", label: t("关于信息"), icon: BadgeInfo }
    ]
  }
];

function pathMatches(pathname: string, key: string) {
  return pathname === key || pathname.startsWith(`${key}/`);
}

function findActiveNav(pathname: string) {
  for (const group of navGroups) {
    const item = group.items.find((navItem) => pathMatches(pathname, navItem.key));
    if (item) {
      return { group, item };
    }
  }

  return { group: navGroups[0], item: navGroups[0].items[0] };
}

function menuItems(items: NavItem[]): NonNullable<MenuProps["items"]> {
  return items.map((item) => {
    const Icon = item.icon;
    return {
      key: item.key,
      icon: <Icon size={17} />,
      label: item.label
    };
  });
}

const topNavItems: NonNullable<MenuProps["items"]> = navGroups.map((group) => {
  const Icon = group.icon;
  return {
    key: group.key,
    icon: <Icon size={17} />,
    label: group.label
  };
});

const SIDE_NAV_MIN_WIDTH = 220;
const SIDE_NAV_MAX_WIDTH = 360;
const SIDE_NAV_DEFAULT_WIDTH = 260;
const SIDE_NAV_WIDTH_STORAGE_KEY = "vulnflanker.side-nav-width";

function clampSideNavWidth(width: number) {
  return Math.min(SIDE_NAV_MAX_WIDTH, Math.max(SIDE_NAV_MIN_WIDTH, width));
}

export default function AppLayout() {
  const navigate = useNavigate();
  const { logoutAsync, user } = useAuth();
  const { settings } = usePlatformSettings();
  const { pathname } = useLocation();
  const { group: activeGroup, item: activeItem } = findActiveNav(pathname);
  const isDashboard = activeGroup.key === "dashboard";
  const [isSideCollapsed, setIsSideCollapsed] = useState(false);
  const [sideNavWidth, setSideNavWidth] = useState(() => {
    const storedWidth = Number(window.localStorage.getItem(SIDE_NAV_WIDTH_STORAGE_KEY));
    return Number.isFinite(storedWidth)
      ? clampSideNavWidth(storedWidth)
      : SIDE_NAV_DEFAULT_WIDTH;
  });
  const [isSideNavResizing, setIsSideNavResizing] = useState(false);
  const selectedKey = activeItem.key;
  const sideNavItems = menuItems(activeGroup.items);
  const CollapseIcon = isSideCollapsed ? ChevronsRight : ChevronsLeft;
  const logoSrc = platformLogoSrc(settings);

  useEffect(() => {
    window.localStorage.setItem(SIDE_NAV_WIDTH_STORAGE_KEY, String(sideNavWidth));
  }, [sideNavWidth]);

  useEffect(() => {
    if (!isSideNavResizing) {
      return undefined;
    }

    const handlePointerMove = (event: PointerEvent) => {
      setSideNavWidth(clampSideNavWidth(event.clientX));
    };
    const handlePointerUp = () => {
      setIsSideNavResizing(false);
    };

    document.body.classList.add("side-nav-resizing");
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);

    return () => {
      document.body.classList.remove("side-nav-resizing");
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [isSideNavResizing]);

  const updateSideNavWidth = (width: number) => {
    const nextWidth = clampSideNavWidth(width);
    setSideNavWidth(nextWidth);
    window.localStorage.setItem(SIDE_NAV_WIDTH_STORAGE_KEY, String(nextWidth));
  };

  const handleSideNavResizeKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
      return;
    }

    event.preventDefault();
    updateSideNavWidth(sideNavWidth + (event.key === "ArrowRight" ? 16 : -16));
  };

  return (
    <Layout className="app-shell">
      <Layout.Header className="topbar">
        <div className="brand" aria-label={settings.platform_name}>
          <div className="brand-mark">
            <img
              src={logoSrc}
              alt={`${settings.platform_name} LOGO`}
              className="brand-logo"
            />
          </div>
          <div className="brand-copy">
            <span>{settings.platform_name}</span>
            <strong>{settings.platform_subtitle}</strong>
          </div>
        </div>

        <Menu
          className="topnav"
          mode="horizontal"
          selectedKeys={[activeGroup.key]}
          items={topNavItems}
          onClick={({ key }) => {
            const nextGroup = navGroups.find((group) => group.key === key);
            if (nextGroup) {
              navigate(nextGroup.defaultKey);
            }
          }}
        />

        <Space className="operator" size={10}>
          <NotificationCenter />
          <Avatar className="operator-avatar" icon={<UserRound size={18} />} />
          <span className="operator-name">{user?.display_name || user?.username || t("管理员")}</span>
          <Tooltip title={t("退出登录")}>
            <Button
              className="view-button"
              icon={<LogOut size={17} />}
              onClick={() => {
                void logoutAsync().finally(() => navigate("/login", { replace: true }));
              }}
            />
          </Tooltip>
        </Space>
      </Layout.Header>

      <Layout className={`app-body${isDashboard ? " app-body-dashboard" : ""}`}>
        {!isDashboard ? (
          <Layout.Sider
            className={`side-nav${isSideCollapsed ? " side-nav-collapsed" : ""}`}
            width={sideNavWidth}
            collapsedWidth={80}
            collapsed={isSideCollapsed}
            theme="light"
            trigger={null}
        >
          <div className="side-nav-header">
            <div className="side-nav-title">{activeGroup.label}</div>
            <Tooltip title={isSideCollapsed ? t("展开侧栏") : t("收起侧栏")}>
              <Button
                className="side-nav-toggle"
                icon={<CollapseIcon size={17} />}
                onClick={() => setIsSideCollapsed((collapsed) => !collapsed)}
              />
            </Tooltip>
          </div>
          <Menu
            mode="inline"
            inlineCollapsed={isSideCollapsed}
            selectedKeys={[String(selectedKey)]}
            items={sideNavItems}
            onClick={({ key }) => navigate(key)}
          />
          {!isSideCollapsed ? (
            <div
              className="side-nav-resizer"
              role="separator"
              aria-orientation="vertical"
              aria-label={t("调整侧栏宽度")}
              tabIndex={0}
              onKeyDown={handleSideNavResizeKeyDown}
              onPointerDown={(event) => {
                event.preventDefault();
                setIsSideNavResizing(true);
              }}
            />
          ) : null}
          </Layout.Sider>
        ) : null}

        <Layout.Content
          className={`workspace${isDashboard ? " workspace-dashboard" : ""}`}
        >
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  );
}

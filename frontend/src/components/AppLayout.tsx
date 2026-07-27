import { useState } from "react";

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
  Radar,
  SearchCheck,
  ShieldAlert,
  ServerCog,
  Settings,
  ShieldCheck,
  UserRound,
  Users
} from "lucide-react";
import { Outlet, useLocation, useNavigate } from "react-router";

import { useAuth } from "@/app/auth";
import { platformLogoSrc, usePlatformSettings } from "@/app/platformSettings";

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
    key: "risk",
    label: "风险管理",
    icon: Radar,
    defaultKey: "/risk-queue",
    items: [
      { key: "/risk-queue", label: "风险队列", icon: Radar },
      { key: "/matching", label: "漏洞比对", icon: SearchCheck },
      { key: "/verification-tasks", label: "验证中心", icon: ListChecks },
      { key: "/rules", label: "规则说明", icon: FileQuestion }
    ]
  },
  {
    key: "assets",
    label: "资产管理",
    icon: Database,
    defaultKey: "/assets",
    items: [
      { key: "/assets", label: "资产列表", icon: Database },
      { key: "/business-systems", label: "业务系统", icon: Building2 },
      { key: "/people", label: "人员管理", icon: UserRound },
      { key: "/responsibility-teams", label: "责任团队", icon: Users },
      { key: "/agents", label: "Agent 管理", icon: ServerCog }
    ]
  },
  {
    key: "intel",
    label: "漏洞情报",
    icon: Activity,
    defaultKey: "/vulnerabilities",
    items: [
      { key: "/vulnerabilities", label: "漏洞列表", icon: Activity },
      { key: "/vulnerability-reviews", label: "漏洞复核", icon: ShieldAlert },
      { key: "/vulnerability-repository", label: "漏洞仓库", icon: Database },
      { key: "/intel", label: "情报采集", icon: ShieldCheck }
    ]
  },
  {
    key: "records",
    label: "记录日志",
    icon: ClipboardList,
    defaultKey: "/task-center",
    items: [
      { key: "/task-center", label: "任务中心", icon: ClipboardList },
      { key: "/audit/handling", label: "处置记录", icon: ClipboardCheck },
      { key: "/audit", label: "审计日志", icon: FileClock }
    ]
  },
  {
    key: "settings",
    label: "系统设置",
    icon: Settings,
    defaultKey: "/settings/platform",
    items: [
      { key: "/settings/platform", label: "平台设置", icon: Settings },
      { key: "/settings/ai", label: "AI 补全设置", icon: Bot },
      { key: "/settings/about", label: "关于信息", icon: BadgeInfo }
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

export default function AppLayout() {
  const navigate = useNavigate();
  const { logoutAsync, user } = useAuth();
  const { settings } = usePlatformSettings();
  const { pathname } = useLocation();
  const { group: activeGroup, item: activeItem } = findActiveNav(pathname);
  const [isSideCollapsed, setIsSideCollapsed] = useState(false);
  const selectedKey = activeItem.key;
  const sideNavItems = menuItems(activeGroup.items);
  const CollapseIcon = isSideCollapsed ? ChevronsRight : ChevronsLeft;
  const logoSrc = platformLogoSrc(settings);

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
          <Avatar className="operator-avatar" icon={<UserRound size={18} />} />
          <span>{user?.display_name || user?.username || "管理员"}</span>
          <Tooltip title="退出登录">
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

      <Layout className="app-body">
        <Layout.Sider
          className={`side-nav${isSideCollapsed ? " side-nav-collapsed" : ""}`}
          width={220}
          collapsedWidth={80}
          collapsed={isSideCollapsed}
          theme="light"
          trigger={null}
        >
          <div className="side-nav-header">
            <div className="side-nav-title">{activeGroup.label}</div>
            <Tooltip title={isSideCollapsed ? "展开侧栏" : "收起侧栏"}>
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
        </Layout.Sider>

        <Layout.Content className="workspace">
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  );
}

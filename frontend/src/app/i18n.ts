import { useSyncExternalStore } from "react";

import { englishTranslations } from "@/app/englishTranslations";

export const supportedLocales = [
  { value: "zh-CN", label: "中文", englishLabel: "Chinese" },
  { value: "en-US", label: "English", englishLabel: "English" }
] as const;

export type Locale = (typeof supportedLocales)[number]["value"];

export const localeStorageKey = "vulnflanker.locale";

let currentLocale: Locale = readStoredLocale();
const listeners = new Set<() => void>();

const manualTranslations: Record<string, string> = {
  "总览": "Dashboard",
  "风险概览": "Risk Overview",
  "资产概览": "Asset Overview",
  "漏洞概览": "Vulnerability Overview",
  "闭环概览": "Closure Overview",
  "风险趋势": "Risk Trend",
  "风险等级分布": "Risk Severity Distribution",
  "闭环性质分布": "Closure Type Distribution",
  "风险处置状态": "Risk Handling Status",
  "最高危的五条风险": "Top 5 Highest-Risk Items",
  "开放风险": "Open Risks",
  "新增风险": "New Risks",
  "闭环风险": "Closed Risks",
  "当前存量": "Current Total",
  "本周期新增": "New in Period",
  "近 {{v0}} 天新增": "New in Last {{v0}} Days",
  "较上周期": "vs. Previous Period",
  "上周期无新增": "No New Items in Previous Period",
  "闭环总数": "Total Closures",
  "本周期闭环总数": "Closures in This Period",
  "总数": "Total",
  "确认误报": "False Positive",
  "接受风险": "Risk Accepted",
  "已解决": "Resolved",
  "自定义": "Custom",
  "数据更新于 {{v0}}（{{v1}}）": "Updated {{v0}} ({{v1}})",
  "统计周期：{{v0}} 至 {{v1}}": "Period: {{v0}} to {{v1}}",
  "暂无风险趋势数据": "No Risk Trend Data",
  "暂无最高危风险": "No Open Risks",
  "风险分": "Risk Score",
  "风险编号": "Risk ID",
  "选择平台界面语言；设置会保存在当前浏览器中。":
    "Choose the platform interface language; the setting is saved in this browser.",
  "界面语言": "Interface language",
  "切换后，导航、按钮、表格和表单提示会使用所选语言。":
    "Navigation, buttons, tables, and form hints will use the selected language.",
  "语言切换会立即应用，并在下次打开平台时继续生效。":
    "The language is applied immediately and will remain active the next time you open the platform.",
  "选择平台界面语言": "Choose the platform interface language",
  "平台界面语言": "Platform interface language",
  "当前语言": "Current language",
  "语言设置": "Language Settings",
  "中文": "Chinese",
  "English": "English",
  "保存平台设置失败": "Failed to save platform settings",
  "平台设置已保存": "Platform settings saved",
  "保存平台设置": "Save platform settings",
  "平台设置已恢复默认": "Platform settings restored to defaults",
  "恢复默认平台设置？": "Restore default platform settings?",
  "确认更新": "Confirm update",
  "确认": "Confirm",
  "需要超级管理员权限": "Super administrator permission required",
  "请求失败": "Request failed",
  "未知错误": "Unknown error",
  "读取图片失败": "Failed to read image",
  "文件类型不支持": "File type is not supported",
  "漏洞监测平台": "Vulnerability Monitoring Platform",
  "没有有效结论": "No valid conclusion",
  "Pipeline 如何合并最终状态与置信度":
    "How Pipeline combines the final state and confidence",
  "Pipeline：没有有效结论": "Pipeline: No valid conclusion",
  "每条规则都会输出状态、置信度、原因和证据。状态不是简单投票，而是按阻断、复核、受影响的优先级合并。":
    "Each rule outputs a status, confidence, reason, and evidence. The final status is not decided by a simple vote; it is merged by the priority of blocking, review, and affected results.",
  "数值配置当前为只读状态。点击编辑并确认风险提示后，才能修改置信度赋值、风险因子分值、风险权重和优先级阈值。":
    "Numeric configuration is read-only. Click Edit and confirm the risk warning before changing confidence assignments, risk factor scores, risk weights, and priority thresholds.",
  "当前处置状态": "Current handling status",
  "任务中心": "Task Center",
  "风险待处理": "Risk items",
  "AI 漏洞补全": "AI enrichment",
  "条": "items",
  "请求失败，HTTP {{v0}}": "Request failed, HTTP {{v0}}",
  "共 {{v0}} 条": "{{v0}} items",
  "匹配 {{v0}} 条": "Matching {{v0}} items",
  "共 {{v0}} 个业务系统": "{{v0}} business systems",
  "共 {{v0}} 名人员": "{{v0}} people",
  "共 {{v0}} 个团队": "{{v0}} teams",
  "工号 {{v0}}": "Employee ID {{v0}}",
  "当前按 Agent {{v0}} 聚焦": "Focused on Agent {{v0}}",
  "评估状态：{{v0}}": "Evaluation status: {{v0}}",
  "复核状态：{{v0}}": "Review status: {{v0}}",
  "创建时间：{{v0}}": "Created at: {{v0}}",
  "风险模型 {{v0}}": "Risk model {{v0}}",
  "请输入{{v0}}": "Enter {{v0}}",
  "已更新 {{v0}} 个资产的运营归属": "Updated operational ownership for {{v0}} assets",
  "设置运营归属 · {{v0}} 个资产": "Set operational ownership · {{v0}} assets",
  "连接测试成功，模型 {{v0}}，耗时 {{v1}} ms":
    "Connection test succeeded: model {{v0}}, latency {{v1}} ms",
  "连接测试失败：{{v0}}": "Connection test failed: {{v0}}",
  "强制联网补全任务已创建，选中 {{v0}} 条":
    "Forced web enrichment task created for {{v0}} items",
  "归一化完成：{{v0}}": "Normalization completed: {{v0}}",
  "停用业务系统 · {{v0}}": "Disable business system · {{v0}}",
  "停用人员 · {{v0}}": "Disable person · {{v0}}",
  "处置历史：{{v0}}": "Handling history: {{v0}}",
  "任务 {{v0}} 已进入 {{v1}}": "Task {{v0}} entered {{v1}}",
  "匹配评估完成，生成 {{v0}} 条结果":
    "Matching evaluation completed, {{v0}} results generated",
  "已重评估 {{v0}}": "Re-evaluated {{v0}}",
  "确认清除“{{v0}}”采集的漏洞？":
    "Clear vulnerabilities collected by \"{{v0}}\"?",
  "登录": "Sign in",
  "站内消息": "Notifications",
  "站内消息，{{v0}} 条未读": "Notifications, {{v0}} unread",
  "未读消息列表": "Unread notifications",
  "暂无未读消息": "No unread notifications",
  "请选择一条消息查看详情": "Select a notification to view details",
  "全部已读": "Mark all as read",
  "标记已读失败": "Failed to mark as read",
  "全部已读失败": "Failed to mark all as read",
  "已将 {{v0}} 条消息标记为已读": "Marked {{v0}} notifications as read",
  "事件详情": "Event details",
  "事件类型": "Event type",
  "事件 ID": "Event ID",
  "发生时间": "Occurred at",
  "前往对应页面": "Go to related page",
  "历史消息": "Notification history",
  "历史消息详情": "Notification history details",
  "暂无历史消息": "No notification history",
  "全部类别": "All categories",
  "输入事件类型": "Enter event type",
  "邮件日志": "Email logs",
  "邮件投递详情": "Email delivery details",
  "暂无邮件日志": "No email logs",
  "邮件告警设置": "Email Alert Settings",
  "邮件能力总开关": "Email capability",
  "自动告警": "Automatic alerts",
  "手动告警": "Manual alert",
  "手动重发": "Manual resend",
  "失败自动重试": "Automatic failure retry",
  "默认在 1、5、30 分钟后重试": "Retries after 1, 5, and 30 minutes by default",
  "风险阈值": "Risk threshold",
  "低危及以上": "Low and above",
  "中危及以上": "Medium and above",
  "高危及以上": "High and above",
  "严重风险": "Critical only",
  "邮件服务器": "Mail server",
  "SMTP 服务器": "SMTP server",
  "请输入 SMTP 服务器": "Enter the SMTP server",
  "连接安全": "Connection security",
  "无加密（不推荐）": "No encryption (not recommended)",
  "超时（秒）": "Timeout (seconds)",
  "SMTP 用户名": "SMTP username",
  "SMTP 密码": "SMTP password",
  "输入 SMTP 密码": "Enter the SMTP password",
  "保持现有密码": "Keep existing password",
  "已安全保存；留空表示保持不变": "Stored securely; leave blank to keep it unchanged",
  "密码将加密保存且不会回显": "The password will be encrypted and will never be displayed",
  "清除已保存的 SMTP 密码": "Clear the stored SMTP password",
  "发件人名称": "Sender name",
  "发件邮箱": "Sender email",
  "请输入有效邮箱": "Enter a valid email address",
  "告警策略": "Alert policy",
  "告警模板": "Alert templates",
  "仅支持以下受控占位符，不支持脚本或模板表达式。":
    "Only the controlled placeholders below are supported; scripts and template expressions are not allowed.",
  "邮件主题模板": "Subject template",
  "纯文本正文模板": "Plain-text body template",
  "HTML 正文模板": "HTML body template",
  "实时预览": "Live preview",
  "邮件主题预览": "Email subject preview",
  "HTML 邮件预览": "HTML email preview",
  "模板校验失败": "Template validation failed",
  "等待模板输入": "Waiting for template input",
  "测试发送": "Test delivery",
  "测试收件邮箱": "Test recipient email",
  "发送测试邮件": "Send test email",
  "测试邮件": "Test email",
  "测试邮件发送失败": "Failed to send the test email",
  "请先保存设置，再发送测试邮件。总开关关闭时不可发送。":
    "Save the settings before sending a test email. Sending is unavailable while the main switch is off.",
  "邮件告警设置已保存": "Email alert settings saved",
  "保存邮件告警设置失败": "Failed to save email alert settings",
  "邮件发送与风险评估事务相互独立": "Email delivery is independent of risk evaluation transactions",
  "邮件失败不会回滚业务；缺少主责任人邮箱的告警会记录为已跳过。":
    "Email failures do not roll back business operations; alerts without a primary owner's email are logged as skipped.",
  "排队中": "Queued",
  "发送中": "Sending",
  "等待重试": "Retry scheduled",
  "已发送": "Sent",
  "发送失败": "Failed",
  "已跳过": "Skipped",
  "触发方式": "Trigger",
  "全部方式": "All triggers",
  "收件邮箱": "Recipient email",
  "风险数": "Risk count",
  "尝试": "Attempts",
  "跳过原因": "Skip reason",
  "最后错误": "Last error",
  "发送时间": "Sent at",
  "下次重试": "Next retry",
  "纯文本正文": "Plain-text body",
  "HTML 正文": "HTML body",
  "发送尝试": "Delivery attempts",
  "开始时间": "Started at",
  "上下文": "Context",
  "确认重新发送此邮件？": "Resend this email?",
  "将生成一条新的邮件投递记录。": "A new email delivery record will be created.",
  "重新发送失败": "Failed to resend email",
  "邮件告警": "Email alert",
  "邮件告警发起失败": "Failed to request the email alert",
  "开启": "On",
  "关闭": "Off",
  "端口": "Port",
  "确认发送风险邮件告警？": "Send a risk email alert?",
  "手动发送受风险阈值和邮件总开关限制，允许重复发送。":
    "Manual delivery is subject to the risk threshold and main email switch. Repeated delivery is allowed.",
  "确认发送": "Send",
  "风险详情": "Risk details",
  "类别": "Category",
  "标题": "Title",
  "摘要": "Summary",
  "收件人": "Recipient",
  "主题": "Subject",
  "状态": "Status",
  "创建时间": "Created at",
  "说明": "Description",
  "资产未绑定业务系统": "The asset is not assigned to a business system",
  "业务系统已停用": "The business system is inactive",
  "未设置主责任人": "No primary owner is assigned",
  "主责任人已停用": "The primary owner is inactive",
  "主责任人邮箱为空": "The primary owner's email is missing",
  "主责任人邮箱格式无效": "The primary owner's email address is invalid",
  "风险等级低于告警阈值": "The risk level is below the alert threshold",
  "邮件准备失败": "Email preparation failed"
};

const commonTermTranslations: Array<[string, string]> = [
  ["业务系统、负责人、负责团队", "business system, owner, and responsibility team"],
  ["责任人和团队", "owner and team"],
  ["责任人员", "responsible people"],
  ["责任团队", "responsibility team"],
  ["责任人", "owner"],
  ["负责人", "person in charge"],
  ["业务系统", "business system"],
  ["匹配结果", "matching results"],
  ["匹配状态", "matching status"],
  ["匹配", "Match"],
  ["风险队列", "Risk Queue"],
  ["风险管理", "Risk Management"],
  ["风险", "Risk"],
  ["漏洞比对", "Vulnerability Matching"],
  ["漏洞仓库", "Vulnerability Repository"],
  ["漏洞复核", "Vulnerability Review"],
  ["漏洞情报", "Vulnerability Intelligence"],
  ["漏洞", "Vulnerability"],
  ["资产管理", "Asset Management"],
  ["资产列表", "Asset List"],
  ["资产详情", "Asset Details"],
  ["资产", "Asset"],
  ["系统设置", "System Settings"],
  ["平台设置", "Platform Settings"],
  ["语言设置", "Language Settings"],
  ["关于信息", "About"],
  ["任务中心", "Task Center"],
  ["处置记录", "Handling Records"],
  ["审计日志", "Audit Logs"],
  ["记录日志", "Records & Logs"],
  ["情报采集", "Intelligence Collection"],
  ["验证中心", "Verification Center"],
  ["验证任务", "Verification Task"],
  ["验证", "Verify"],
  ["规则说明", "Rule Guide"],
  ["规则", "Rule"],
  ["Agent 管理", "Agent Management"],
  ["Agent", "Agent"],
  ["AI 补全", "AI Enrichment"],
  ["AI 设置", "AI Settings"],
  ["AI", "AI"],
  ["列表", "List"],
  ["详情", "Details"],
  ["设置", "Settings"],
  ["保存", "Save"],
  ["取消", "Cancel"],
  ["关闭", "Close"],
  ["刷新", "Refresh"],
  ["重置", "Reset"],
  ["查询", "Search"],
  ["筛选", "Filter"],
  ["查看", "View"],
  ["编辑", "Edit"],
  ["删除", "Delete"],
  ["创建", "Create"],
  ["新增", "Add"],
  ["操作", "Actions"],
  ["确认", "Confirm"],
  ["恢复", "Restore"],
  ["重试", "Retry"],
  ["执行", "Run"],
  ["开始", "Start"],
  ["停止", "Stop"],
  ["启用", "Enable"],
  ["禁用", "Disable"],
  ["启用中", "Enabled"],
  ["已启用", "Enabled"],
  ["已禁用", "Disabled"],
  ["成功", "Success"],
  ["失败", "Failed"],
  ["错误", "Error"],
  ["请求失败", "Request failed"],
  ["加载失败", "Failed to load"],
  ["加载", "Load"],
  ["保存失败", "Save failed"],
  ["更新失败", "Update failed"],
  ["创建失败", "Create failed"],
  ["暂无", "No "],
  ["没有", "No "],
  ["未设置", "Not set"],
  ["未配置", "Not configured"],
  ["未找到", "Not found"],
  ["无", "No "],
  ["请选择", "Select "],
  ["请选择", "Select "],
  ["请输入", "Enter "],
  ["选择", "Select"],
  ["当前", "Current"],
  ["默认", "Default"],
  ["状态", "Status"],
  ["原因", "Reason"],
  ["说明", "Description"],
  ["描述", "Description"],
  ["备注", "Notes"],
  ["标题", "Title"],
  ["名称", "Name"],
  ["姓名", "Name"],
  ["用户名", "Username"],
  ["密码", "Password"],
  ["邮箱", "Email"],
  ["地址", "Address"],
  ["版本", "Version"],
  ["平台", "Platform"],
  ["环境", "Environment"],
  ["关键性", "Criticality"],
  ["重要性", "Importance"],
  ["优先级", "Priority"],
  ["严重程度", "Severity"],
  ["严重度", "Severity"],
  ["暴露类型", "Exposure Type"],
  ["暴露面", "Exposure"],
  ["公网暴露", "Public Exposure"],
  ["组件", "Component"],
  ["证据", "Evidence"],
  ["来源", "Source"],
  ["时间", "Time"],
  ["创建时间", "Created At"],
  ["更新时间", "Updated At"],
  ["最近", "Latest"],
  ["全部", "All"],
  ["普通", "Normal"],
  ["高危", "High"],
  ["中危", "Medium"],
  ["低危", "Low"],
  ["严重", "Critical"],
  ["高", "High"],
  ["中", "Medium"],
  ["低", "Low"],
  ["待处理", "Pending"],
  ["处理中", "In progress"],
  ["已完成", "Completed"],
  ["已处理", "Handled"],
  ["待复核", "Needs review"],
  ["已验证", "Verified"],
  ["未验证", "Unverified"],
  ["已关闭", "Closed"],
  ["待分配", "Unassigned"],
  ["归属完整", "Ownership complete"],
  ["链路不完整", "Incomplete chain"],
  ["未分配", "Unassigned"],
  ["启用业务系统", "Enable business system"],
  ["责任团队", "Responsibility Team"],
  ["人员管理", "People"],
  ["责任团队管理", "Responsibility Teams"],
  ["系统管理员", "System Administrator"],
  ["管理员", "Administrator"],
  ["登录", "Sign in"],
  ["退出登录", "Sign out"],
  ["当前账号为只读权限", "This account has read-only access"],
  ["需要超级管理员权限", "Super administrator permission required"],
  ["共 ", "Total "],
  [" 条", " items"],
  [" 个资产", " assets"],
  [" 个业务系统", " business systems"],
  [" 名人员", " people"],
  ["已停用", "Disabled"]
];

function translateByCommonTerms(source: string) {
  return commonTermTranslations.reduce(
    (value, [from, to]) => value.replaceAll(from, to),
    source
  );
}

function isLocale(value: string | null): value is Locale {
  return value === "zh-CN" || value === "en-US";
}

function readStoredLocale() {
  if (typeof window === "undefined") {
    return "zh-CN" as const;
  }
  const stored = window.localStorage.getItem(localeStorageKey);
  return isLocale(stored) ? stored : ("zh-CN" as const);
}

function notifyLocaleChange() {
  listeners.forEach((listener) => listener());
}

export function getLocale(): Locale {
  return currentLocale;
}

export function setLocale(locale: Locale) {
  if (locale === currentLocale) {
    return;
  }
  currentLocale = locale;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(localeStorageKey, locale);
    document.documentElement.lang = locale;
  }
  notifyLocaleChange();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function interpolate(value: string, variables?: Record<string, string | number>) {
  if (!variables) {
    return value;
  }
  return value.replace(/\{\{?([\w.-]+)\}?\}/g, (match, key: string) =>
    key in variables ? String(variables[key]) : match
  );
}

export function translate(
  source: string,
  variables?: Record<string, string | number>
) {
  const translatedSource =
    currentLocale === "en-US"
      ? manualTranslations[source] ?? englishTranslations[source]
      : undefined;
  const value =
    currentLocale === "en-US"
      ? translatedSource && translatedSource !== source
        ? translatedSource
        : translateByCommonTerms(source)
      : source;
  return interpolate(value, variables);
}

export const t = translate;

export function useI18n() {
  const getServerLocale = () => "zh-CN" as Locale;
  const locale = useSyncExternalStore(subscribe, getLocale, getServerLocale);
  return {
    locale,
    locales: supportedLocales,
    t: translate,
    setLocale
  };
}

if (typeof document !== "undefined") {
  document.documentElement.lang = currentLocale;
}

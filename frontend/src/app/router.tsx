import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router";

import AppLayout from "@/components/AppLayout";
import LoadingBlock from "@/components/LoadingBlock";
import RequireAuth from "@/components/RequireAuth";

const LoginPage = lazy(() => import("@/pages/auth/LoginPage"));
const DashboardPage = lazy(() => import("@/pages/dashboard/DashboardPage"));
const RiskQueuePage = lazy(() => import("@/pages/risk-queue/RiskQueuePage"));
const TaskCenterPage = lazy(() => import("@/pages/task-center/TaskCenterPage"));
const AIEnrichmentBatchDetailPage = lazy(
  () => import("@/pages/task-center/AIEnrichmentBatchDetailPage")
);
const MatchResultsPage = lazy(() => import("@/pages/matching/MatchResultsPage"));
const RuleExplainerPage = lazy(() => import("@/pages/rules/RuleExplainerPage"));
const MatchResultDetailPage = lazy(
  () => import("@/pages/matching/MatchResultDetailPage")
);
const AssetListPage = lazy(() => import("@/pages/assets/AssetListPage"));
const AssetDetailPage = lazy(() => import("@/pages/assets/AssetDetailPage"));
const AgentListPage = lazy(() => import("@/pages/agents/AgentListPage"));
const BusinessSystemsPage = lazy(
  () => import("@/pages/ownership/BusinessSystemsPage")
);
const ResponsibilityTeamPage = lazy(
  () => import("@/pages/ownership/ResponsibilityTeamPage")
);
const PeoplePage = lazy(() => import("@/pages/ownership/PeoplePage"));
const VerificationTaskListPage = lazy(
  () => import("@/pages/verification/VerificationTaskListPage")
);
const VerificationTaskDetailPage = lazy(
  () => import("@/pages/verification/VerificationTaskDetailPage")
);
const VulnerabilityListPage = lazy(
  () => import("@/pages/vulnerabilities/VulnerabilityListPage")
);
const VulnerabilityRepositoryPage = lazy(
  () => import("@/pages/vulnerabilities/VulnerabilityRepositoryPage")
);
const VulnerabilityReviewPage = lazy(
  () => import("@/pages/vulnerabilities/VulnerabilityReviewPage")
);
const VulnerabilityDetailPage = lazy(
  () => import("@/pages/vulnerabilities/VulnerabilityDetailPage")
);
const AuditLogsPage = lazy(() => import("@/pages/audit/AuditLogsPage"));
const HandlingRecordsPage = lazy(
  () => import("@/pages/audit/HandlingRecordsPage")
);
const NotificationHistoryPage = lazy(
  () => import("@/pages/audit/NotificationHistoryPage")
);
const EmailDeliveryLogsPage = lazy(
  () => import("@/pages/audit/EmailDeliveryLogsPage")
);
const IntelCollectionPage = lazy(() => import("@/pages/intel/IntelCollectionPage"));
const PlatformSettingsPage = lazy(
  () => import("@/pages/settings/PlatformSettingsPage")
);
const AiSettingsPage = lazy(() => import("@/pages/settings/AiSettingsPage"));
const AboutInfoPage = lazy(() => import("@/pages/settings/AboutInfoPage"));
const LanguageSettingsPage = lazy(
  () => import("@/pages/settings/LanguageSettingsPage")
);
const EmailAlertSettingsPage = lazy(
  () => import("@/pages/settings/EmailAlertSettingsPage")
);

function page(element: ReactNode) {
  return <Suspense fallback={<LoadingBlock />}>{element}</Suspense>;
}

export const router = createBrowserRouter([
  { path: "/login", element: page(<LoginPage />) },
  {
    path: "/",
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: page(<DashboardPage />) },
      { path: "task-center", element: page(<TaskCenterPage />) },
      {
        path: "ai-enrichments/batches/:batchRunId",
        element: page(<AIEnrichmentBatchDetailPage />)
      },
      { path: "risk-queue", element: page(<RiskQueuePage />) },
      { path: "matching", element: page(<MatchResultsPage />) },
      { path: "rules", element: page(<RuleExplainerPage />) },
      { path: "matching/:matchResultId", element: page(<MatchResultDetailPage />) },
      { path: "assets", element: page(<AssetListPage />) },
      { path: "assets/:assetId", element: page(<AssetDetailPage />) },
      { path: "agents", element: page(<AgentListPage />) },
      { path: "business-systems", element: page(<BusinessSystemsPage />) },
      { path: "responsibility-teams", element: page(<ResponsibilityTeamPage />) },
      { path: "people", element: page(<PeoplePage />) },
      { path: "verification-tasks", element: page(<VerificationTaskListPage />) },
      {
        path: "verification-tasks/:taskId",
        element: page(<VerificationTaskDetailPage />)
      },
      { path: "vulnerabilities", element: page(<VulnerabilityListPage />) },
      { path: "vulnerability-reviews", element: page(<VulnerabilityReviewPage />) },
      {
        path: "vulnerability-repository",
        element: page(<VulnerabilityRepositoryPage />)
      },
      {
        path: "vulnerabilities/:vulnerabilityId",
        element: page(<VulnerabilityDetailPage />)
      },
      { path: "audit", element: page(<AuditLogsPage />) },
      { path: "audit/handling", element: page(<HandlingRecordsPage />) },
      { path: "audit/notifications", element: page(<NotificationHistoryPage />) },
      { path: "audit/email-deliveries", element: page(<EmailDeliveryLogsPage />) },
      { path: "intel", element: page(<IntelCollectionPage />) },
      { path: "settings/platform", element: page(<PlatformSettingsPage />) },
      { path: "settings/ai", element: page(<AiSettingsPage />) },
      { path: "settings/email-alerts", element: page(<EmailAlertSettingsPage />) },
      { path: "settings/language", element: page(<LanguageSettingsPage />) },
      { path: "settings/about", element: page(<AboutInfoPage />) }
    ]
  }
]);

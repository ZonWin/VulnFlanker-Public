import { request, type QueryParams } from "@/api/client";
import type { MatchHandlingStatus, RiskPriority } from "@/api/types";

export interface DashboardQuery extends QueryParams {
  days?: number;
  start_date?: string;
  end_date?: string;
}

export interface DashboardPeriod {
  timezone: string;
  start_date: string;
  end_date: string;
  previous_start_date: string;
  previous_end_date: string;
  generated_at: string;
}

export interface DashboardMetric {
  current_total: number;
  period_new: number;
  previous_new: number;
  change_percent: number | null;
}

export interface DashboardClosureSummary {
  total: number;
  resolved: number;
  false_positive: number;
  risk_accepted: number;
}

export interface DashboardDistributionItem {
  key: string;
  count: number;
}

export interface DashboardTrendPoint {
  date: string;
  open_count: number;
  new_count: number;
  closed_count: number;
}

export interface DashboardTopRisk {
  id: string;
  risk_code: string | null;
  risk_priority: RiskPriority;
  risk_score: number;
  vulnerability_id: string;
  vulnerability_canonical_id: string;
  vulnerability_title: string;
  asset_id: string;
  asset_name: string;
  handling_status: MatchHandlingStatus;
  risk_entered_at: string | null;
}

export interface DashboardOverview {
  period: DashboardPeriod;
  risk: DashboardMetric;
  asset: DashboardMetric;
  vulnerability: DashboardMetric;
  closure: DashboardClosureSummary;
  risk_priority_distribution: DashboardDistributionItem[];
  handling_status_distribution: DashboardDistributionItem[];
  trend: DashboardTrendPoint[];
  top_risks: DashboardTopRisk[];
}

export function getDashboard(query: DashboardQuery = {}) {
  return request<DashboardOverview>("/api/v1/dashboard", { query });
}

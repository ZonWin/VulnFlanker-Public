from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class DashboardPeriod(BaseModel):
    timezone: str
    start_date: date
    end_date: date
    previous_start_date: date
    previous_end_date: date
    generated_at: datetime


class DashboardMetric(BaseModel):
    current_total: int
    period_new: int
    previous_new: int
    change_percent: float | None = None


class DashboardClosureSummary(BaseModel):
    total: int
    resolved: int
    false_positive: int
    risk_accepted: int


class DashboardDistributionItem(BaseModel):
    key: str
    count: int


class DashboardTrendPoint(BaseModel):
    date: date
    open_count: int
    new_count: int
    closed_count: int


class DashboardTopRisk(BaseModel):
    id: str
    risk_code: str | None = None
    risk_priority: str
    risk_score: float
    vulnerability_id: str
    vulnerability_canonical_id: str
    vulnerability_title: str
    asset_id: str
    asset_name: str
    handling_status: str
    risk_entered_at: datetime | None = None


class DashboardOverview(BaseModel):
    period: DashboardPeriod
    risk: DashboardMetric
    asset: DashboardMetric
    vulnerability: DashboardMetric
    closure: DashboardClosureSummary
    risk_priority_distribution: list[DashboardDistributionItem] = Field(
        default_factory=list
    )
    handling_status_distribution: list[DashboardDistributionItem] = Field(
        default_factory=list
    )
    trend: list[DashboardTrendPoint] = Field(default_factory=list)
    top_risks: list[DashboardTopRisk] = Field(default_factory=list)

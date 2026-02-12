"""Pydantic models for ROI analytics and market research responses."""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class PurchaseBreakdown(BaseModel):
    listing_price: float
    estimated_closing_costs: float
    closing_cost_pct: float
    total_acquisition_cost: float
    down_payment_20pct: float
    loan_amount: float


class MortgageDetails(BaseModel):
    loan_amount: float
    interest_rate_pct: float
    term_years: int
    monthly_payment: float
    total_interest_paid: float


class MonthlyExpenses(BaseModel):
    mortgage: float
    property_tax: float
    insurance: float
    hoa: float
    maintenance_reserve: float
    vacancy_reserve: float
    total: float


class RentalProjection(BaseModel):
    estimated_monthly_rent: float
    gross_annual_income: float
    effective_gross_income: float  # after vacancy
    vacancy_rate_pct: float
    rent_to_price_ratio: float


class CashFlowAnalysis(BaseModel):
    monthly_income: float
    monthly_expenses: float
    monthly_cash_flow: float
    annual_cash_flow: float
    monthly_breakdown: MonthlyExpenses
    cumulative_cash_flow_by_year: List[Dict[str, Any]]  # [{year, cumulative, annual}]


class ROIMetrics(BaseModel):
    cap_rate_pct: float
    cash_on_cash_return_pct: float
    gross_rent_multiplier: float
    total_return_year_1_pct: float
    total_return_year_5_pct: float
    total_return_year_10_pct: float
    break_even_months: int
    investment_grade: str  # A, B, C, D, F


class AppreciationForecast(BaseModel):
    annual_rate_pct: float
    source: str
    projections: List[Dict[str, Any]]  # [{year, projected_value, equity, total_return_pct}]


class ROIAnalysis(BaseModel):
    purchase: PurchaseBreakdown
    mortgage: MortgageDetails
    rental: RentalProjection
    cash_flow: CashFlowAnalysis
    roi_metrics: ROIMetrics
    appreciation: AppreciationForecast


class DemographicData(BaseModel):
    population: Optional[int] = None
    median_household_income: Optional[float] = None
    homeownership_rate_pct: Optional[float] = None
    median_age: Optional[float] = None
    poverty_rate_pct: Optional[float] = None
    source: str = "estimated"


class EconomicIndicators(BaseModel):
    unemployment_rate_pct: Optional[float] = None
    job_growth_rate_pct: Optional[float] = None
    median_home_value: Optional[float] = None
    home_value_yoy_change_pct: Optional[float] = None
    rent_yoy_change_pct: Optional[float] = None
    source: str = "estimated"


class NeighborhoodScore(BaseModel):
    overall: float  # 0-100
    schools: float
    safety: float
    walkability: float
    economic_vitality: float


class ComparableMetrics(BaseModel):
    zip_median_price: float
    zip_median_price_per_sqft: float
    price_vs_median_pct: float  # positive = above median
    price_per_sqft_vs_median_pct: float
    zip_avg_days_on_market: int
    zip_active_listings: int


class MarketResearch(BaseModel):
    demographics: DemographicData
    economic: EconomicIndicators
    neighborhood_score: NeighborhoodScore
    comparables: ComparableMetrics
    zip_code: str
    city: str
    state: str


class InvestmentReport(BaseModel):
    property_id: str
    report_id: str
    roi_analysis: ROIAnalysis
    market_research: MarketResearch
    demand_simulation: Dict[str, Any]
    generated_at: str


class FullAnalysisRequest(BaseModel):
    property_id: str
    num_buyers: int = 1000
    num_simulations: int = 300

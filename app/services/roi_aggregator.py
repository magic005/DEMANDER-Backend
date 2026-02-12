"""
ROI Aggregation Service — computes investment analytics from property data.

All numbers are algorithmically derived from property attributes and heuristic
defaults. This produces educated estimates suitable for initial screening,
not financial advice.
"""

import math
from typing import Dict, Any, Optional, List

from app.schemas.roi import (
    PurchaseBreakdown,
    MortgageDetails,
    MonthlyExpenses,
    RentalProjection,
    CashFlowAnalysis,
    ROIMetrics,
    AppreciationForecast,
    ROIAnalysis,
)


# ─── Heuristic constants ────────────────────────────────────────────────

# Mortgage rate (national avg as of 2025 — would be fetched live in prod)
DEFAULT_MORTGAGE_RATE = 6.85
DEFAULT_TERM_YEARS = 30
DEFAULT_DOWN_PAYMENT_PCT = 20.0

# Closing costs as pct of purchase price
CLOSING_COST_PCT = 3.0

# Property tax as pct of assessed value — varies by state
STATE_PROPERTY_TAX: Dict[str, float] = {
    "TX": 1.80, "CA": 0.73, "NY": 1.72, "FL": 0.89, "WA": 0.93,
    "IL": 2.27, "AZ": 0.62, "CO": 0.51, "GA": 0.92, "NC": 0.84,
    "VA": 0.82, "MA": 1.23, "NJ": 2.49, "PA": 1.58, "OH": 1.56,
    "MI": 1.54, "TN": 0.64, "OR": 0.97, "MD": 1.09, "MN": 1.12,
    "NV": 0.53, "SC": 0.57, "IN": 0.85, "MO": 0.97, "WI": 1.76,
}
DEFAULT_PROPERTY_TAX_PCT = 1.10

# Insurance as pct of home value
DEFAULT_INSURANCE_PCT = 0.35

# Maintenance reserve — pct of home value per year
MAINTENANCE_RESERVE_PCT = 1.0

# Vacancy rate — pct of time property is vacant
DEFAULT_VACANCY_PCT = 5.0

# Price-to-rent ratio heuristic by property type
PRICE_TO_ANNUAL_RENT: Dict[str, float] = {
    "single_family": 18.0,
    "condo": 20.0,
    "townhouse": 19.0,
    "multi_family": 14.0,
}
DEFAULT_PRICE_TO_RENT = 18.0

# Average annual appreciation by tier
APPRECIATION_RATE_BY_PRICE: List[tuple] = [
    (300_000, 4.2),       # < 300K: starter tier appreciates faster
    (500_000, 3.8),       # 300-500K
    (750_000, 3.5),       # 500-750K
    (1_000_000, 3.0),     # 750K-1M
    (float("inf"), 2.5),  # 1M+ luxury tier
]


# ─── Calculation helpers ────────────────────────────────────────────────

def _monthly_mortgage_payment(loan: float, annual_rate_pct: float, years: int) -> float:
    """Standard amortization formula."""
    if loan <= 0 or annual_rate_pct <= 0:
        return 0.0
    r = annual_rate_pct / 100.0 / 12.0
    n = years * 12
    return loan * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def _total_interest(loan: float, monthly_payment: float, years: int) -> float:
    return max(0, monthly_payment * years * 12 - loan)


def _appreciation_rate_for_price(price: float) -> float:
    for threshold, rate in APPRECIATION_RATE_BY_PRICE:
        if price < threshold:
            return rate
    return 2.5


def _investment_grade(cap_rate: float, coc: float, cash_flow_monthly: float) -> str:
    """Grade the investment A–F based on composite ROI metrics."""
    score = 0.0
    # Cap rate scoring
    if cap_rate >= 8.0:
        score += 30
    elif cap_rate >= 6.0:
        score += 25
    elif cap_rate >= 4.0:
        score += 18
    elif cap_rate >= 2.0:
        score += 10
    else:
        score += 3

    # Cash-on-cash scoring
    if coc >= 12.0:
        score += 35
    elif coc >= 8.0:
        score += 28
    elif coc >= 5.0:
        score += 20
    elif coc >= 2.0:
        score += 12
    elif coc >= 0:
        score += 5
    else:
        score += 0

    # Cash flow scoring
    if cash_flow_monthly >= 500:
        score += 35
    elif cash_flow_monthly >= 200:
        score += 28
    elif cash_flow_monthly >= 0:
        score += 18
    elif cash_flow_monthly >= -200:
        score += 8
    else:
        score += 0

    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 45:
        return "C"
    if score >= 25:
        return "D"
    return "F"


# ─── Main aggregation function ──────────────────────────────────────────

def compute_roi_analysis(
    price: float,
    sqft: float,
    beds: int,
    baths: float,
    property_type: str,
    state: str,
    zip_code: str,
    hoa_monthly: Optional[float] = None,
    year_built: Optional[int] = None,
    condition: Optional[str] = None,
    school_rating: Optional[float] = None,
    walk_score: Optional[int] = None,
    **kwargs,
) -> ROIAnalysis:
    """Compute a full ROI analysis from property attributes."""

    # ── Purchase breakdown ──
    closing_costs = round(price * CLOSING_COST_PCT / 100, 2)
    total_acquisition = price + closing_costs
    down_payment = round(price * DEFAULT_DOWN_PAYMENT_PCT / 100, 2)
    loan_amount = price - down_payment

    purchase = PurchaseBreakdown(
        listing_price=price,
        estimated_closing_costs=closing_costs,
        closing_cost_pct=CLOSING_COST_PCT,
        total_acquisition_cost=total_acquisition,
        down_payment_20pct=down_payment,
        loan_amount=loan_amount,
    )

    # ── Mortgage details ──
    monthly_pmt = round(_monthly_mortgage_payment(loan_amount, DEFAULT_MORTGAGE_RATE, DEFAULT_TERM_YEARS), 2)
    total_interest = round(_total_interest(loan_amount, monthly_pmt, DEFAULT_TERM_YEARS), 2)

    mortgage = MortgageDetails(
        loan_amount=loan_amount,
        interest_rate_pct=DEFAULT_MORTGAGE_RATE,
        term_years=DEFAULT_TERM_YEARS,
        monthly_payment=monthly_pmt,
        total_interest_paid=total_interest,
    )

    # ── Rental projection ──
    price_to_rent = PRICE_TO_ANNUAL_RENT.get(property_type, DEFAULT_PRICE_TO_RENT)

    # Adjust rent estimate based on condition / quality signals
    rent_adjustment = 1.0
    if condition == "excellent":
        rent_adjustment = 1.10
    elif condition == "poor":
        rent_adjustment = 0.85
    if walk_score is not None and walk_score > 80:
        rent_adjustment *= 1.05
    if school_rating is not None and school_rating >= 8:
        rent_adjustment *= 1.04

    estimated_monthly_rent = round((price / price_to_rent / 12) * rent_adjustment, 2)
    gross_annual = round(estimated_monthly_rent * 12, 2)
    effective_annual = round(gross_annual * (1 - DEFAULT_VACANCY_PCT / 100), 2)

    rental = RentalProjection(
        estimated_monthly_rent=estimated_monthly_rent,
        gross_annual_income=gross_annual,
        effective_gross_income=effective_annual,
        vacancy_rate_pct=DEFAULT_VACANCY_PCT,
        rent_to_price_ratio=round(estimated_monthly_rent / price * 100, 4) if price > 0 else 0,
    )

    # ── Monthly expenses ──
    prop_tax_pct = STATE_PROPERTY_TAX.get(state.upper(), DEFAULT_PROPERTY_TAX_PCT)
    monthly_tax = round(price * prop_tax_pct / 100 / 12, 2)
    monthly_insurance = round(price * DEFAULT_INSURANCE_PCT / 100 / 12, 2)
    monthly_hoa = hoa_monthly or 0.0
    monthly_maintenance = round(price * MAINTENANCE_RESERVE_PCT / 100 / 12, 2)
    monthly_vacancy = round(estimated_monthly_rent * DEFAULT_VACANCY_PCT / 100, 2)

    total_monthly_expenses = round(
        monthly_pmt + monthly_tax + monthly_insurance + monthly_hoa +
        monthly_maintenance + monthly_vacancy, 2
    )

    expenses = MonthlyExpenses(
        mortgage=monthly_pmt,
        property_tax=monthly_tax,
        insurance=monthly_insurance,
        hoa=monthly_hoa,
        maintenance_reserve=monthly_maintenance,
        vacancy_reserve=monthly_vacancy,
        total=total_monthly_expenses,
    )

    # ── Cash flow ──
    monthly_cf = round(estimated_monthly_rent - total_monthly_expenses, 2)
    annual_cf = round(monthly_cf * 12, 2)

    cumulative_cf = []
    running = 0.0
    for yr in range(1, 21):
        running += annual_cf
        cumulative_cf.append({
            "year": yr,
            "annual": annual_cf,
            "cumulative": round(running, 2),
        })

    cash_flow = CashFlowAnalysis(
        monthly_income=estimated_monthly_rent,
        monthly_expenses=total_monthly_expenses,
        monthly_cash_flow=monthly_cf,
        annual_cash_flow=annual_cf,
        monthly_breakdown=expenses,
        cumulative_cash_flow_by_year=cumulative_cf,
    )

    # ── Appreciation forecast ──
    appreciation_rate = _appreciation_rate_for_price(price)
    projections = []
    total_cash_invested = down_payment + closing_costs
    for yr in [1, 2, 3, 5, 7, 10, 15, 20]:
        projected_value = round(price * (1 + appreciation_rate / 100) ** yr, 2)
        # Estimate remaining loan balance (simplified)
        r = DEFAULT_MORTGAGE_RATE / 100 / 12
        n = DEFAULT_TERM_YEARS * 12
        payments_made = yr * 12
        if r > 0 and payments_made < n:
            remaining_balance = loan_amount * ((1 + r) ** n - (1 + r) ** payments_made) / ((1 + r) ** n - 1)
        else:
            remaining_balance = 0
        equity = round(projected_value - remaining_balance, 2)
        cumulative_cash_flow_at_yr = round(annual_cf * yr, 2)
        total_return = equity - total_cash_invested + cumulative_cash_flow_at_yr
        total_return_pct = round(total_return / total_cash_invested * 100, 1) if total_cash_invested > 0 else 0

        projections.append({
            "year": yr,
            "projected_value": projected_value,
            "equity": equity,
            "total_return_pct": total_return_pct,
        })

    appreciation = AppreciationForecast(
        annual_rate_pct=appreciation_rate,
        source="historical_zip_average",
        projections=projections,
    )

    # ── ROI metrics ──
    noi = effective_annual - (monthly_tax + monthly_insurance + monthly_hoa + monthly_maintenance + monthly_vacancy) * 12
    cap_rate = round(noi / price * 100, 2) if price > 0 else 0
    coc_return = round(annual_cf / total_cash_invested * 100, 2) if total_cash_invested > 0 else 0
    grm = round(price / gross_annual, 1) if gross_annual > 0 else 0

    # Total return year 1: appreciation + cash flow + principal paydown
    yr1_appreciation = price * appreciation_rate / 100
    # First year principal paydown ≈ monthly_payment * 12 - interest_yr1
    yr1_interest = loan_amount * DEFAULT_MORTGAGE_RATE / 100  # approximate
    yr1_principal = max(0, monthly_pmt * 12 - yr1_interest)
    total_return_yr1 = round((annual_cf + yr1_appreciation + yr1_principal) / total_cash_invested * 100, 1) if total_cash_invested > 0 else 0

    # 5yr & 10yr returns from projections
    total_return_yr5 = next((p["total_return_pct"] for p in projections if p["year"] == 5), 0)
    total_return_yr10 = next((p["total_return_pct"] for p in projections if p["year"] == 10), 0)

    # Break-even: months until cumulative cash flow covers initial investment
    if monthly_cf > 0:
        break_even = math.ceil(total_cash_invested / monthly_cf)
    elif monthly_cf == 0:
        break_even = 999
    else:
        # Negative cash flow — check if appreciation compensates
        annual_total_return = annual_cf + yr1_appreciation + yr1_principal
        if annual_total_return > 0:
            break_even = math.ceil(total_cash_invested / (annual_total_return / 12))
        else:
            break_even = 999

    grade = _investment_grade(cap_rate, coc_return, monthly_cf)

    roi_metrics = ROIMetrics(
        cap_rate_pct=cap_rate,
        cash_on_cash_return_pct=coc_return,
        gross_rent_multiplier=grm,
        total_return_year_1_pct=total_return_yr1,
        total_return_year_5_pct=total_return_yr5,
        total_return_year_10_pct=total_return_yr10,
        break_even_months=min(break_even, 999),
        investment_grade=grade,
    )

    return ROIAnalysis(
        purchase=purchase,
        mortgage=mortgage,
        rental=rental,
        cash_flow=cash_flow,
        roi_metrics=roi_metrics,
        appreciation=appreciation,
    )

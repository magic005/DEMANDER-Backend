from pydantic import BaseModel
from typing import List, Optional


class FunnelStage(BaseModel):
    stage: str
    count: int
    rate: float


class ArchetypeBreakdown(BaseModel):
    name: str
    percentage: float
    engagement: str
    count: int


class DemandBlocker(BaseModel):
    factor: str
    impact: str
    affected_segments: List[str]
    description: str


class Recommendation(BaseModel):
    action: str
    impact: str
    estimated_lift: str
    description: str


class TimelinePoint(BaseModel):
    day: int
    cumulative: float
    daily: float


class PriceSensitivityPoint(BaseModel):
    price_point: float
    demand_change: float
    label: str


class CompetitiveContext(BaseModel):
    avg_days_on_market: int
    median_price: float
    active_listings: int
    avg_price_per_sqft: float
    this_property_price_per_sqft: float


class SaleProbability(BaseModel):
    day_30: float
    day_60: float
    day_90: float


class DemandReport(BaseModel):
    property_id: str
    demand_score: float
    sale_probability: SaleProbability
    time_to_first_offer: int
    buyer_pool_size: int
    funnel_data: List[FunnelStage]
    archetype_breakdown: List[ArchetypeBreakdown]
    demand_blockers: List[DemandBlocker]
    recommendations: List[Recommendation]
    timeline_data: List[TimelinePoint]
    price_sensitivity: List[PriceSensitivityPoint]
    competitive_context: CompetitiveContext
    simulation_runs: int
    generated_at: str


class SimulationRequest(BaseModel):
    property_id: str
    num_buyers: int = 1000
    num_simulations: int = 500

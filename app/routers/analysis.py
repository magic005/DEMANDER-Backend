"""Full analysis endpoint — orchestrates extraction, enrichment, ROI computation, and simulation."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.property import Property
from app.models.report import Report
from app.schemas.roi import FullAnalysisRequest, InvestmentReport
from app.services.roi_aggregator import compute_roi_analysis
from app.services.market_research import research_market
from app.simulation.engine import DemandSimulator, PropertyProfile

router = APIRouter()


def _build_profile(prop: Property) -> PropertyProfile:
    return PropertyProfile(
        price=prop.price,
        beds=prop.beds,
        baths=prop.baths,
        sqft=prop.sqft,
        lot_size_sqft=prop.lot_size_sqft,
        property_type=prop.property_type or "single_family",
        year_built=prop.year_built,
        condition=prop.condition,
        hoa_monthly=prop.hoa_monthly,
        school_rating=prop.school_rating,
        walk_score=prop.walk_score,
        fire_zone=prop.fire_zone or "none",
        flood_zone=prop.flood_zone or "none",
        parking=prop.parking,
    )


@router.post("/full")
async def run_full_analysis(request: FullAnalysisRequest, db: Session = Depends(get_db)):
    """Run complete investment analysis: ROI + market research + demand simulation."""

    prop = db.query(Property).filter(Property.id == request.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found. Create the property first.")

    # 1. ROI aggregation
    roi = compute_roi_analysis(
        price=prop.price,
        sqft=prop.sqft,
        beds=prop.beds,
        baths=prop.baths,
        property_type=prop.property_type or "single_family",
        state=prop.state,
        zip_code=prop.zip_code,
        hoa_monthly=prop.hoa_monthly,
        year_built=prop.year_built,
        condition=prop.condition,
        school_rating=prop.school_rating,
        walk_score=prop.walk_score,
    )

    # 2. Market research
    market = await research_market(
        price=prop.price,
        sqft=prop.sqft,
        zip_code=prop.zip_code,
        city=prop.city,
        state=prop.state,
        school_rating=prop.school_rating,
        walk_score=prop.walk_score,
    )

    # 3. Demand simulation
    profile = _build_profile(prop)
    simulator = DemandSimulator()
    sim_result = simulator.run(
        property_profile=profile,
        num_buyers=request.num_buyers,
        num_simulations=request.num_simulations,
    )

    # 4. Persist report with all data
    report = Report(
        property_id=request.property_id,
        demand_score=sim_result.demand_score,
        sale_probability_30=sim_result.sale_probability_30,
        sale_probability_60=sim_result.sale_probability_60,
        sale_probability_90=sim_result.sale_probability_90,
        time_to_first_offer=sim_result.time_to_first_offer,
        buyer_pool_size=sim_result.buyer_pool_size,
        simulation_runs=sim_result.simulation_runs,
        funnel_data=sim_result.funnel_data,
        archetype_breakdown=sim_result.archetype_breakdown,
        demand_blockers=sim_result.demand_blockers,
        recommendations=sim_result.recommendations,
        timeline_data=sim_result.timeline_data,
        price_sensitivity=sim_result.price_sensitivity,
        competitive_context=sim_result.competitive_context,
        roi_analysis=roi.model_dump(),
        market_research=market.model_dump(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Build simulation dict for response
    sim_dict = {
        "demand_score": sim_result.demand_score,
        "sale_probability": {
            "day_30": sim_result.sale_probability_30,
            "day_60": sim_result.sale_probability_60,
            "day_90": sim_result.sale_probability_90,
        },
        "time_to_first_offer": sim_result.time_to_first_offer,
        "buyer_pool_size": sim_result.buyer_pool_size,
        "funnel_data": sim_result.funnel_data,
        "archetype_breakdown": sim_result.archetype_breakdown,
        "demand_blockers": sim_result.demand_blockers,
        "recommendations": sim_result.recommendations,
        "timeline_data": sim_result.timeline_data,
        "price_sensitivity": sim_result.price_sensitivity,
        "competitive_context": sim_result.competitive_context,
        "simulation_runs": sim_result.simulation_runs,
    }

    return InvestmentReport(
        property_id=request.property_id,
        report_id=report.id,
        roi_analysis=roi,
        market_research=market,
        demand_simulation=sim_dict,
        generated_at=report.generated_at.isoformat(),
    )

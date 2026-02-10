"""Simulation trigger endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.property import Property
from app.models.report import Report
from app.schemas.report import SimulationRequest
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


@router.post("/run")
async def run_simulation(request: SimulationRequest, db: Session = Depends(get_db)):
    """Run a demand simulation for a given property and persist the report."""
    prop = db.query(Property).filter(Property.id == request.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found. Create the property first.")

    profile = _build_profile(prop)

    simulator = DemandSimulator()
    result = simulator.run(
        property_profile=profile,
        num_buyers=request.num_buyers,
        num_simulations=request.num_simulations,
    )

    # Persist the report
    report = Report(
        property_id=request.property_id,
        demand_score=result.demand_score,
        sale_probability_30=result.sale_probability_30,
        sale_probability_60=result.sale_probability_60,
        sale_probability_90=result.sale_probability_90,
        time_to_first_offer=result.time_to_first_offer,
        buyer_pool_size=result.buyer_pool_size,
        simulation_runs=result.simulation_runs,
        funnel_data=result.funnel_data,
        archetype_breakdown=result.archetype_breakdown,
        demand_blockers=result.demand_blockers,
        recommendations=result.recommendations,
        timeline_data=result.timeline_data,
        price_sensitivity=result.price_sensitivity,
        competitive_context=result.competitive_context,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "report_id": report.id,
        "property_id": request.property_id,
        "demand_score": result.demand_score,
        "sale_probability": {
            "day_30": result.sale_probability_30,
            "day_60": result.sale_probability_60,
            "day_90": result.sale_probability_90,
        },
        "time_to_first_offer": result.time_to_first_offer,
        "buyer_pool_size": result.buyer_pool_size,
        "funnel_data": result.funnel_data,
        "archetype_breakdown": result.archetype_breakdown,
        "demand_blockers": result.demand_blockers,
        "recommendations": result.recommendations,
        "timeline_data": result.timeline_data,
        "price_sensitivity": result.price_sensitivity,
        "competitive_context": result.competitive_context,
        "simulation_runs": result.simulation_runs,
        "generated_at": report.generated_at.isoformat(),
    }

"""Report management endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.report import Report
from app.models.property import Property

router = APIRouter()


def _report_to_response(report: Report, prop: Property = None) -> dict:
    resp = {
        "report_id": report.id,
        "property_id": report.property_id,
        "demand_score": report.demand_score,
        "sale_probability": {
            "day_30": report.sale_probability_30,
            "day_60": report.sale_probability_60,
            "day_90": report.sale_probability_90,
        },
        "time_to_first_offer": report.time_to_first_offer,
        "buyer_pool_size": report.buyer_pool_size,
        "simulation_runs": report.simulation_runs,
        "funnel_data": report.funnel_data,
        "archetype_breakdown": report.archetype_breakdown,
        "demand_blockers": report.demand_blockers,
        "recommendations": report.recommendations,
        "timeline_data": report.timeline_data,
        "price_sensitivity": report.price_sensitivity,
        "competitive_context": report.competitive_context,
        "roi_analysis": report.roi_analysis,
        "market_research": report.market_research,
        "generated_at": report.generated_at.isoformat() if report.generated_at else "",
    }
    if prop:
        resp["property"] = {
            "id": prop.id,
            "address": prop.full_address,
            "price": prop.price,
            "beds": prop.beds,
            "baths": prop.baths,
            "sqft": prop.sqft,
            "property_type": prop.property_type,
            "year_built": prop.year_built,
        }
    return resp


@router.get("/")
async def list_reports(db: Session = Depends(get_db)):
    """List all generated reports with their property summaries."""
    reports = db.query(Report).order_by(Report.generated_at.desc()).all()
    result = []
    for report in reports:
        prop = db.query(Property).filter(Property.id == report.property_id).first()
        result.append(_report_to_response(report, prop))
    return result


@router.get("/{report_id}")
async def get_report(report_id: str, db: Session = Depends(get_db)):
    """Get a specific report by ID."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    prop = db.query(Property).filter(Property.id == report.property_id).first()
    return _report_to_response(report, prop)


@router.get("/property/{property_id}")
async def get_reports_for_property(property_id: str, db: Session = Depends(get_db)):
    """Get all reports for a specific property."""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    reports = db.query(Report).filter(Report.property_id == property_id).order_by(Report.generated_at.desc()).all()
    return [_report_to_response(r, prop) for r in reports]


@router.delete("/{report_id}")
async def delete_report(report_id: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    db.delete(report)
    db.commit()
    return {"status": "deleted", "id": report_id}

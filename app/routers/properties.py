"""Property management endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.property import Property
from app.schemas.property import (
    PropertyCreate,
    PropertyResponse,
    PropertyUpdate,
    PropertyURLInput,
    PropertyExtractResponse,
    PropertyExtracted,
    PropertyType,
    RiskLevel,
    Condition,
    ParkingType,
)
from app.services.listing_extraction import extract_listing
from app.services.enrichment import enrich_property

router = APIRouter()


def _property_to_response(prop: Property) -> dict:
    return {
        "id": prop.id,
        "address": prop.address,
        "city": prop.city,
        "state": prop.state,
        "zip_code": prop.zip_code,
        "full_address": prop.full_address,
        "price": prop.price,
        "hoa_monthly": prop.hoa_monthly,
        "property_type": prop.property_type,
        "year_built": prop.year_built,
        "beds": prop.beds,
        "baths": prop.baths,
        "sqft": prop.sqft,
        "lot_size_sqft": prop.lot_size_sqft,
        "parking": prop.parking,
        "condition": prop.condition,
        "school_rating": prop.school_rating,
        "walk_score": prop.walk_score,
        "fire_zone": prop.fire_zone,
        "flood_zone": prop.flood_zone,
        "price_per_sqft": prop.price_per_sqft,
        "created_at": prop.created_at.isoformat() if prop.created_at else "",
    }


@router.post("/")
async def create_property(data: PropertyCreate, db: Session = Depends(get_db)):
    full_address = f"{data.address}, {data.city}, {data.state} {data.zip_code}"
    price_per_sqft = round(data.price / data.sqft, 2) if data.sqft > 0 else 0

    prop = Property(
        address=data.address,
        city=data.city,
        state=data.state,
        zip_code=data.zip_code,
        full_address=full_address,
        price=data.price,
        hoa_monthly=data.hoa_monthly,
        property_type=data.property_type.value if data.property_type else "single_family",
        year_built=data.year_built,
        beds=data.beds,
        baths=data.baths,
        sqft=data.sqft,
        lot_size_sqft=data.lot_size_sqft,
        parking=data.parking.value if data.parking else None,
        condition=data.condition.value if data.condition else None,
        school_rating=data.school_rating,
        walk_score=data.walk_score,
        fire_zone=data.fire_zone.value if data.fire_zone else "none",
        flood_zone=data.flood_zone.value if data.flood_zone else "none",
        price_per_sqft=price_per_sqft,
    )

    db.add(prop)
    db.commit()
    db.refresh(prop)
    return _property_to_response(prop)


@router.get("/")
async def list_properties(db: Session = Depends(get_db)):
    props = db.query(Property).order_by(Property.created_at.desc()).all()
    return [_property_to_response(p) for p in props]


@router.get("/{property_id}")
async def get_property(property_id: str, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return _property_to_response(prop)


@router.patch("/{property_id}")
async def update_property(property_id: str, data: PropertyUpdate, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(prop, field, value)

    # Recompute derived fields
    prop.full_address = f"{prop.address}, {prop.city}, {prop.state} {prop.zip_code}"
    prop.price_per_sqft = round(prop.price / prop.sqft, 2) if prop.sqft > 0 else 0
    prop.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(prop)
    return _property_to_response(prop)


@router.delete("/{property_id}")
async def delete_property(property_id: str, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    db.delete(prop)
    db.commit()
    return {"status": "deleted", "id": property_id}


@router.post("/extract")
async def extract_from_url(data: PropertyURLInput) -> PropertyExtractResponse:
    """Extract property details from a listing URL (API-first, scrape fallback) and enrich if possible."""

    result = await extract_listing(data.url)
    enriched = await enrich_property(result.data)

    merged = {**result.data, **enriched.data}
    confidence = {**result.confidence, **enriched.confidence}
    sources = {**result.sources, **enriched.sources}

    def _norm_state(s: str | None) -> str | None:
        if not s:
            return None
        s = s.strip()
        if len(s) == 2:
            return s.upper()
        # best-effort mapping for common full state names
        states = {
            "texas": "TX",
            "california": "CA",
            "new york": "NY",
            "florida": "FL",
            "washington": "WA",
            "illinois": "IL",
            "arizona": "AZ",
            "colorado": "CO",
            "georgia": "GA",
            "north carolina": "NC",
            "virginia": "VA",
            "massachusetts": "MA",
            "new jersey": "NJ",
            "pennsylvania": "PA",
            "ohio": "OH",
            "michigan": "MI",
        }
        return states.get(s.lower())

    extracted = PropertyExtracted(
        address=merged.get("address"),
        city=merged.get("city"),
        state=_norm_state(merged.get("state")),
        zip_code=merged.get("zip_code"),
        price=merged.get("price"),
        hoa_monthly=merged.get("hoa_monthly"),
        property_type=PropertyType(merged["property_type"]) if merged.get("property_type") in {e.value for e in PropertyType} else None,
        year_built=merged.get("year_built"),
        beds=merged.get("beds"),
        baths=merged.get("baths"),
        sqft=merged.get("sqft"),
        lot_size_sqft=merged.get("lot_size_sqft"),
        parking=ParkingType(merged["parking"]) if merged.get("parking") in {e.value for e in ParkingType} else None,
        condition=Condition(merged["condition"]) if merged.get("condition") in {e.value for e in Condition} else None,
        school_rating=merged.get("school_rating"),
        walk_score=merged.get("walk_score"),
        fire_zone=RiskLevel(merged["fire_zone"]) if merged.get("fire_zone") in {e.value for e in RiskLevel} else None,
        flood_zone=RiskLevel(merged["flood_zone"]) if merged.get("flood_zone") in {e.value for e in RiskLevel} else None,
    )

    return PropertyExtractResponse(
        status="extracted",
        url=data.url,
        message=result.message,
        extracted_data=extracted,
        confidence=confidence,
        sources=sources,
    )

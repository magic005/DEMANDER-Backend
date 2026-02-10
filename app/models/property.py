import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, Text
from app.db import Base


def generate_id():
    return f"prop-{uuid.uuid4().hex[:8]}"


class Property(Base):
    __tablename__ = "properties"

    id = Column(String, primary_key=True, default=generate_id)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String(2), nullable=False)
    zip_code = Column(String(10), nullable=False)
    full_address = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    hoa_monthly = Column(Float, nullable=True)
    property_type = Column(String, nullable=False, default="single_family")
    year_built = Column(Integer, nullable=True)
    beds = Column(Integer, nullable=False)
    baths = Column(Float, nullable=False)
    sqft = Column(Float, nullable=False)
    lot_size_sqft = Column(Float, nullable=True)
    parking = Column(String, nullable=True)
    condition = Column(String, nullable=True)
    school_rating = Column(Float, nullable=True)
    walk_score = Column(Integer, nullable=True)
    fire_zone = Column(String, nullable=False, default="none")
    flood_zone = Column(String, nullable=False, default="none")
    price_per_sqft = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, JSON
from app.db import Base


def generate_report_id():
    return f"rpt-{uuid.uuid4().hex[:8]}"


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=generate_report_id)
    property_id = Column(String, nullable=False, index=True)
    demand_score = Column(Float, nullable=False)
    sale_probability_30 = Column(Float, nullable=False)
    sale_probability_60 = Column(Float, nullable=False)
    sale_probability_90 = Column(Float, nullable=False)
    time_to_first_offer = Column(Integer, nullable=False)
    buyer_pool_size = Column(Integer, nullable=False)
    simulation_runs = Column(Integer, nullable=False)
    funnel_data = Column(JSON, nullable=False)
    archetype_breakdown = Column(JSON, nullable=False)
    demand_blockers = Column(JSON, nullable=False)
    recommendations = Column(JSON, nullable=False)
    timeline_data = Column(JSON, nullable=False)
    price_sensitivity = Column(JSON, nullable=False)
    competitive_context = Column(JSON, nullable=False)
    generated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

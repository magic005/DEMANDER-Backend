from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class PropertyType(str, Enum):
    SINGLE_FAMILY = "single_family"
    CONDO = "condo"
    TOWNHOUSE = "townhouse"
    MULTI_FAMILY = "multi_family"


class Condition(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ParkingType(str, Enum):
    GARAGE_1 = "garage_1"
    GARAGE_2 = "garage_2"
    GARAGE_3 = "garage_3"
    CARPORT = "carport"
    DRIVEWAY = "driveway"
    NONE = "none"


class PropertyCreate(BaseModel):
    address: str = Field(..., min_length=5)
    city: str
    state: str = Field(..., min_length=2, max_length=2)
    zip_code: str = Field(..., min_length=5, max_length=10)
    price: float = Field(..., gt=0)
    hoa_monthly: Optional[float] = Field(default=None, ge=0)
    property_type: PropertyType = PropertyType.SINGLE_FAMILY
    year_built: Optional[int] = Field(default=None, ge=1800, le=2030)
    beds: int = Field(..., ge=0, le=20)
    baths: float = Field(..., ge=0, le=20)
    sqft: float = Field(..., gt=0)
    lot_size_sqft: Optional[float] = Field(default=None, gt=0)
    parking: Optional[ParkingType] = None
    condition: Optional[Condition] = None
    school_rating: Optional[float] = Field(default=None, ge=1, le=10)
    walk_score: Optional[int] = Field(default=None, ge=0, le=100)
    fire_zone: Optional[RiskLevel] = RiskLevel.NONE
    flood_zone: Optional[RiskLevel] = RiskLevel.NONE


class PropertyResponse(PropertyCreate):
    id: str
    full_address: str
    price_per_sqft: float
    created_at: str

    class Config:
        from_attributes = True


class PropertyUpdate(BaseModel):
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    hoa_monthly: Optional[float] = Field(default=None, ge=0)
    property_type: Optional[PropertyType] = None
    year_built: Optional[int] = Field(default=None, ge=1800, le=2030)
    beds: Optional[int] = Field(default=None, ge=0, le=20)
    baths: Optional[float] = Field(default=None, ge=0, le=20)
    sqft: Optional[float] = Field(default=None, gt=0)
    lot_size_sqft: Optional[float] = Field(default=None, gt=0)
    parking: Optional[ParkingType] = None
    condition: Optional[Condition] = None
    school_rating: Optional[float] = Field(default=None, ge=1, le=10)
    walk_score: Optional[int] = Field(default=None, ge=0, le=100)
    fire_zone: Optional[RiskLevel] = None
    flood_zone: Optional[RiskLevel] = None


class PropertyURLInput(BaseModel):
    url: str = Field(..., min_length=10)

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


# ─── Meter ───────────────────────────────────────────────

class MeterCreate(BaseModel):
    property_id: int
    type: str = Field(..., pattern="^(cold_water|hot_water|electricity)$")
    name: str = Field(..., min_length=1, max_length=100)  # СУ1, СУ2, Основной...
    serial_number: Optional[str] = None
    tariff_type: str = Field(default="single", pattern="^(single|day_night)$")
    unit: Optional[str] = None  # auto-set by type if not provided


class MeterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    serial_number: Optional[str] = None
    tariff_type: Optional[str] = Field(None, pattern="^(single|day_night)$")
    is_active: Optional[bool] = None


class MeterOut(BaseModel):
    id: int
    property_id: int
    type: str
    name: str
    serial_number: Optional[str] = None
    tariff_type: str
    unit: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Meter Reading ───────────────────────────────────────

class MeterReadingCreate(BaseModel):
    meter_id: int
    reading_date: date
    value_t1: float = Field(..., ge=0)
    value_t2: Optional[float] = Field(None, ge=0)
    source: str = Field(default="manual", pattern="^(manual|photo|import)$")
    notes: Optional[str] = None


class MeterReadingUpdate(BaseModel):
    reading_date: Optional[date] = None
    value_t1: Optional[float] = Field(None, ge=0)
    value_t2: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None


class MeterReadingOut(BaseModel):
    id: int
    meter_id: int
    reading_date: date
    value_t1: float
    value_t2: Optional[float] = None
    consumption_t1: Optional[float] = None
    consumption_t2: Optional[float] = None
    source: str
    photo_path: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MeterWithLastReading(MeterOut):
    last_reading: Optional[MeterReadingOut] = None

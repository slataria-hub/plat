from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TariffCreate(BaseModel):
    property_id: int
    service_code: str = Field(..., min_length=1, max_length=50)
    start_date: date
    price_t1: float = Field(..., ge=0)
    price_t2: Optional[float] = Field(None, ge=0)
    unit: str = "rub"


class TariffUpdate(BaseModel):
    start_date: Optional[date] = None
    price_t1: Optional[float] = Field(None, ge=0)
    price_t2: Optional[float] = Field(None, ge=0)
    unit: Optional[str] = None


class TariffOut(BaseModel):
    id: int
    property_id: int
    service_code: str
    start_date: date
    price_t1: float
    price_t2: Optional[float] = None
    unit: str

    class Config:
        from_attributes = True


class TariffChange(BaseModel):
    service_code: str
    service_name: Optional[str] = None
    old_price_t1: Optional[float] = None
    new_price_t1: Optional[float] = None
    old_price_t2: Optional[float] = None
    new_price_t2: Optional[float] = None
    delta_t1: Optional[float] = None
    delta_pct_t1: Optional[float] = None
    change_date: Optional[date] = None


class TariffComparison(BaseModel):
    property_id: int
    from_date: date
    to_date: date
    changes: List[TariffChange]
    has_changes: bool


class PeriodAmountComparison(BaseModel):
    """Compare bill totals / items between two months"""
    service_code: Optional[str] = None
    service_name: Optional[str] = None
    amount_prev: float = 0
    amount_curr: float = 0
    delta: float = 0
    delta_pct: Optional[float] = None


class BillsPeriodComparison(BaseModel):
    property_id: int
    prev_year: int
    prev_month: int
    curr_year: int
    curr_month: int
    total_prev: float
    total_curr: float
    total_delta: float
    total_delta_pct: Optional[float] = None
    items: List[PeriodAmountComparison]

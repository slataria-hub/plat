from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


# ─── Service Type ────────────────────────────────────────

class ServiceTypeOut(BaseModel):
    id: int
    code: str
    name: str
    category: str

    class Config:
        from_attributes = True


# ─── Bill Item ───────────────────────────────────────────

class BillItemCreate(BaseModel):
    service_type_id: Optional[int] = None
    raw_name: Optional[str] = None
    volume: Optional[float] = None
    tariff: Optional[float] = None
    amount: float = Field(..., ge=0)


class BillItemOut(BaseModel):
    id: int
    bill_id: int
    service_type_id: Optional[int] = None
    raw_name: Optional[str] = None
    volume: Optional[float] = None
    tariff: Optional[float] = None
    amount: float
    service_type: Optional[ServiceTypeOut] = None

    class Config:
        from_attributes = True


# ─── Payment ─────────────────────────────────────────────

class PaymentCreate(BaseModel):
    amount: float = Field(..., ge=0)
    payment_date: date
    method: Optional[str] = None
    notes: Optional[str] = None


class PaymentOut(BaseModel):
    id: int
    bill_id: int
    amount: float
    payment_date: date
    method: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Bill ────────────────────────────────────────────────

class BillCreate(BaseModel):
    property_id: int
    provider: str = Field(..., min_length=1, max_length=150)
    period_year: int = Field(..., ge=2000, le=2100)
    period_month: int = Field(..., ge=1, le=12)
    total_accrued: float = Field(default=0.0, ge=0)
    total_paid: float = Field(default=0.0, ge=0)
    notes: Optional[str] = None
    items: Optional[List[BillItemCreate]] = None


class BillUpdate(BaseModel):
    provider: Optional[str] = Field(None, min_length=1, max_length=150)
    period_year: Optional[int] = Field(None, ge=2000, le=2100)
    period_month: Optional[int] = Field(None, ge=1, le=12)
    total_accrued: Optional[float] = Field(None, ge=0)
    total_paid: Optional[float] = Field(None, ge=0)
    status: Optional[str] = Field(None, pattern="^(draft|recognized|verified|paid)$")
    notes: Optional[str] = None


class BillOut(BaseModel):
    id: int
    property_id: int
    provider: str
    period_year: int
    period_month: int
    total_accrued: float
    total_paid: float
    status: str
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    recognized_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    items: List[BillItemOut] = []
    payments: List[PaymentOut] = []

    class Config:
        from_attributes = True


class BillListItem(BaseModel):
    """Compact version for registry"""
    id: int
    property_id: int
    provider: str
    period_year: int
    period_month: int
    total_accrued: float
    total_paid: float
    status: str
    file_type: Optional[str] = None
    created_at: datetime
    items_count: int = 0

    class Config:
        from_attributes = True

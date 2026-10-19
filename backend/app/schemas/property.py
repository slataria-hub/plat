from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PropertyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    address: Optional[str] = None
    account_number: Optional[str] = None


class PropertyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[str] = None
    account_number: Optional[str] = None
    is_active: Optional[bool] = None


class PropertyOut(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    account_number: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

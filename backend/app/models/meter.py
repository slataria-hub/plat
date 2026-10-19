from datetime import datetime, date
from sqlalchemy import String, Boolean, DateTime, Date, ForeignKey, Float, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class MeterType(str, enum.Enum):
    cold_water = "cold_water"
    hot_water = "hot_water"
    electricity = "electricity"


class TariffType(str, enum.Enum):
    single = "single"
    day_night = "day_night"


class Meter(Base):
    __tablename__ = "meters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # cold_water / hot_water / electricity
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # СУ1, СУ2, Основной...
    serial_number: Mapped[str] = mapped_column(String(100), nullable=True)
    tariff_type: Mapped[str] = mapped_column(String(20), default="single")  # single / day_night
    unit: Mapped[str] = mapped_column(String(10), default="m3")  # m3 / kwh
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    property = relationship("Property", back_populates="meters")
    readings = relationship("MeterReading", back_populates="meter", cascade="all, delete-orphan")


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"), nullable=False, index=True)
    reading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value_t1: Mapped[float] = mapped_column(Float, nullable=False)  # основной / день
    value_t2: Mapped[float] = mapped_column(Float, nullable=True)   # ночь
    consumption_t1: Mapped[float] = mapped_column(Float, nullable=True)
    consumption_t2: Mapped[float] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual / photo / import
    photo_path: Mapped[str] = mapped_column(String(500), nullable=True)
    notes: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    meter = relationship("Meter", back_populates="readings")

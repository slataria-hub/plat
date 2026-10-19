"""Extra models for features 1-12."""
from datetime import datetime, date
from sqlalchemy import String, Boolean, DateTime, Date, ForeignKey, Float, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class PropertySettings(Base):
    __tablename__ = "property_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), unique=True, nullable=False)
    reminder_day: Mapped[int] = mapped_column(Integer, default=15)  # day of month to remind
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reconcile_threshold: Mapped[float] = mapped_column(Float, default=0.5)  # m3 / kwh


class PeriodNote(Base):
    __tablename__ = "period_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    file_path: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UtilityAccount(Base):
    """Multiple лицевые счета / providers per property."""
    __tablename__ = "utility_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(150), nullable=False)
    account_number: Mapped[str] = mapped_column(String(100), nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="other")  # eirc / electricity / heat / water / other
    portal_url: Mapped[str] = mapped_column(String(500), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PropertyShare(Base):
    """Guest / family access: view-only by default."""
    __tablename__ = "property_shares"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    guest_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    guest_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="viewer")  # viewer only for now
    invite_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

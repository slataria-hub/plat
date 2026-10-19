"""Alerts: tariff changes, missing readings."""
from typing import Annotated, List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, func
from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.models.meter import Meter, MeterReading
from app.models.bill import Tariff, ServiceType
from app.api.deps import get_current_user
from app.services.seed import seed_service_types

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    property_id: Optional[int] = Query(None),
):
    """
    Soft notifications for the user:
    - recent tariff changes (last 90 days)
    - meters without readings this month
    """
    seed_service_types(db)
    props_q = select(Property).where(Property.user_id == current_user.id)
    if property_id:
        props_q = props_q.where(Property.id == property_id)
    properties = db.execute(props_q).scalars().all()

    service_names = {
        s.code: s.name for s in db.execute(select(ServiceType)).scalars().all()
    }

    alerts: list[dict] = []
    today = date.today()
    month_start = today.replace(day=1)
    cutoff = today - timedelta(days=400)

    for prop in properties:
        # Tariff changes
        tariffs = db.execute(
            select(Tariff)
            .where(Tariff.property_id == prop.id, Tariff.start_date >= cutoff)
            .order_by(desc(Tariff.start_date))
        ).scalars().all()

        for t in tariffs:
            # Find previous tariff for same service
            prev = db.execute(
                select(Tariff).where(
                    Tariff.property_id == prop.id,
                    Tariff.service_code == t.service_code,
                    Tariff.start_date < t.start_date,
                ).order_by(desc(Tariff.start_date)).limit(1)
            ).scalar_one_or_none()
            if prev and prev.price_t1 != t.price_t1:
                delta = round(t.price_t1 - prev.price_t1, 4)
                pct = round(delta / prev.price_t1 * 100, 1) if prev.price_t1 else None
                alerts.append({
                    "type": "tariff_change",
                    "severity": "warning" if delta > 0 else "info",
                    "property_id": prop.id,
                    "property_name": prop.name,
                    "title": f"Тариф изменён: {service_names.get(t.service_code, t.service_code)}",
                    "body": f"{prev.price_t1} → {t.price_t1}" + (f" ({pct:+.1f}%)" if pct is not None else ""),
                    "date": t.start_date.isoformat(),
                })

        # Missing readings this month
        meters = db.execute(
            select(Meter).where(Meter.property_id == prop.id, Meter.is_active == True)
        ).scalars().all()
        for meter in meters:
            last = db.execute(
                select(MeterReading)
                .where(MeterReading.meter_id == meter.id)
                .order_by(desc(MeterReading.reading_date))
                .limit(1)
            ).scalar_one_or_none()
            if not last or last.reading_date < month_start:
                type_labels = {
                    "cold_water": "Холодная вода",
                    "hot_water": "Горячая вода",
                    "electricity": "Электричество",
                }
                alerts.append({
                    "type": "missing_reading",
                    "severity": "info",
                    "property_id": prop.id,
                    "property_name": prop.name,
                    "title": f"Нет показаний: {type_labels.get(meter.type, meter.type)} · {meter.name}",
                    "body": f"Последние: {last.reading_date.isoformat() if last else 'никогда'}",
                    "date": today.isoformat(),
                    "meter_id": meter.id,
                })

    # Feature 1: calendar reading reminders
    from app.services.features import reading_reminders
    for prop in properties:
        alerts.extend(reading_reminders(db, prop.id))

    # sort: warnings first, then by date desc
    severity_order = {"warning": 0, "info": 1}
    alerts.sort(key=lambda a: (severity_order.get(a["severity"], 9), a.get("date", "")), reverse=False)
    alerts.sort(key=lambda a: a.get("date", ""), reverse=True)
    return {"count": len(alerts), "items": alerts}

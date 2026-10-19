"""Full backup: Excel + uploaded files → ZIP."""
import json
import zipfile
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.property import Property
from app.models.meter import Meter, MeterReading
from app.models.bill import Bill, BillItem, Payment, Tariff, ServiceType
from app.models.user import User
from app.services.export import export_property_to_excel
from app.services.files import get_absolute_path, ensure_upload_dir
from app.core.config import settings


def create_user_backup(db: Session, user_id: int) -> BytesIO:
    """
    Build a ZIP containing:
    - manifest.json (meta)
    - for each property: excel export + bill files
    - data.json (full structured dump)
    """
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise ValueError("Пользователь не найден")

    properties = db.execute(
        select(Property).where(Property.user_id == user_id)
    ).scalars().all()

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Manifest
        manifest = {
            "app": "MeterApp",
            "version": settings.VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "user_email": user.email,
            "user_name": user.name,
            "properties_count": len(properties),
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        # Full data dump
        dump = _build_data_dump(db, user_id, properties)
        zf.writestr("data.json", json.dumps(dump, ensure_ascii=False, indent=2, default=str))

        for prop in properties:
            safe_name = _safe(prop.name)
            # Excel per property
            try:
                xlsx = export_property_to_excel(db, prop.id, user_id)
                zf.writestr(f"properties/{safe_name}/data.xlsx", xlsx.read())
            except Exception:
                pass

            # Bill files
            bills = db.execute(
                select(Bill).where(Bill.property_id == prop.id)
            ).scalars().all()
            for bill in bills:
                if not bill.file_path:
                    continue
                abs_path = get_absolute_path(bill.file_path)
                if abs_path.exists():
                    period = f"{bill.period_year}-{bill.period_month:02d}"
                    ext = Path(bill.file_path).suffix
                    arcname = f"properties/{safe_name}/files/{period}_{bill.provider}{ext}"
                    zf.write(str(abs_path), arcname)

    buf.seek(0)
    return buf


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()[:50] or "property"


def _build_data_dump(db: Session, user_id: int, properties: list) -> dict:
    result = {"properties": []}
    service_names = {
        s.id: {"code": s.code, "name": s.name, "category": s.category}
        for s in db.execute(select(ServiceType)).scalars().all()
    }

    for prop in properties:
        p_data = {
            "id": prop.id,
            "name": prop.name,
            "address": prop.address,
            "account_number": prop.account_number,
            "meters": [],
            "bills": [],
            "tariffs": [],
        }

        meters = db.execute(
            select(Meter).where(Meter.property_id == prop.id)
        ).scalars().all()
        for m in meters:
            readings = db.execute(
                select(MeterReading).where(MeterReading.meter_id == m.id)
            ).scalars().all()
            p_data["meters"].append({
                "id": m.id,
                "type": m.type,
                "name": m.name,
                "serial_number": m.serial_number,
                "tariff_type": m.tariff_type,
                "unit": m.unit,
                "readings": [
                    {
                        "date": r.reading_date.isoformat() if r.reading_date else None,
                        "value_t1": r.value_t1,
                        "value_t2": r.value_t2,
                        "consumption_t1": r.consumption_t1,
                        "consumption_t2": r.consumption_t2,
                        "source": r.source,
                        "notes": r.notes,
                    }
                    for r in readings
                ],
            })

        bills = db.execute(
            select(Bill).where(Bill.property_id == prop.id)
        ).scalars().all()
        for b in bills:
            p_data["bills"].append({
                "provider": b.provider,
                "period_year": b.period_year,
                "period_month": b.period_month,
                "total_accrued": b.total_accrued,
                "total_paid": b.total_paid,
                "status": b.status,
                "file_path": b.file_path,
                "items": [
                    {
                        "raw_name": it.raw_name,
                        "service": service_names.get(it.service_type_id),
                        "volume": it.volume,
                        "tariff": it.tariff,
                        "amount": it.amount,
                    }
                    for it in b.items
                ],
                "payments": [
                    {
                        "amount": p.amount,
                        "date": p.payment_date.isoformat() if p.payment_date else None,
                        "method": p.method,
                        "notes": p.notes,
                    }
                    for p in b.payments
                ],
            })

        tariffs = db.execute(
            select(Tariff).where(Tariff.property_id == prop.id)
        ).scalars().all()
        for t in tariffs:
            p_data["tariffs"].append({
                "service_code": t.service_code,
                "start_date": t.start_date.isoformat() if t.start_date else None,
                "price_t1": t.price_t1,
                "price_t2": t.price_t2,
                "unit": t.unit,
            })

        result["properties"].append(p_data)

    return result

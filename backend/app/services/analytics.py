"""Aggregations for dashboards."""
from typing import Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.meter import Meter, MeterReading
from app.models.bill import Bill, BillItem, ServiceType

METER_LABELS = {
    "cold_water": "Холодная вода",
    "hot_water": "Горячая вода",
    "electricity": "Электричество",
}


def consumption_by_month(db: Session, property_id: int, year: Optional[int] = None) -> list[dict]:
    """
    Returns list of {year, month, type, consumption_t1, consumption_t2, unit}
    aggregated across meters of the same type.
    """
    meters = db.execute(
        select(Meter).where(Meter.property_id == property_id, Meter.is_active == True)
    ).scalars().all()

    # key: (year, month, type) -> sums
    agg: dict[tuple, dict] = defaultdict(lambda: {"t1": 0.0, "t2": 0.0, "unit": "m3", "count": 0})

    for meter in meters:
        q = select(MeterReading).where(MeterReading.meter_id == meter.id)
        if year:
            q = q.where(MeterReading.reading_date >= f"{year}-01-01",
                        MeterReading.reading_date <= f"{year}-12-31")
        readings = db.execute(q).scalars().all()
        for r in readings:
            if r.consumption_t1 is None and r.consumption_t2 is None:
                continue
            y, m = r.reading_date.year, r.reading_date.month
            key = (y, m, meter.type)
            if r.consumption_t1:
                agg[key]["t1"] += r.consumption_t1
            if r.consumption_t2:
                agg[key]["t2"] += r.consumption_t2
            agg[key]["unit"] = meter.unit
            agg[key]["count"] += 1

    result = []
    for (y, m, mtype), vals in sorted(agg.items()):
        result.append({
            "year": y,
            "month": m,
            "type": mtype,
            "type_label": METER_LABELS.get(mtype, mtype),
            "consumption_t1": round(vals["t1"], 3),
            "consumption_t2": round(vals["t2"], 3) if vals["t2"] else None,
            "unit": vals["unit"],
        })
    return result


def spending_by_month(db: Session, property_id: int, year: Optional[int] = None) -> list[dict]:
    """Monthly bill totals and by category."""
    q = select(Bill).where(Bill.property_id == property_id)
    if year:
        q = q.where(Bill.period_year == year)
    bills = db.execute(q.order_by(Bill.period_year, Bill.period_month)).scalars().all()

    service_cat = {
        s.id: s.category for s in db.execute(select(ServiceType)).scalars().all()
    }

    # key: (year, month) -> totals
    monthly: dict[tuple, dict] = defaultdict(lambda: {
        "total": 0.0, "water": 0.0, "heat": 0.0, "electricity": 0.0, "other": 0.0
    })

    for b in bills:
        key = (b.period_year, b.period_month)
        monthly[key]["total"] += b.total_accrued or 0
        for item in b.items:
            cat = service_cat.get(item.service_type_id, "other") if item.service_type_id else "other"
            if cat not in monthly[key]:
                cat = "other"
            monthly[key][cat] += item.amount or 0

    result = []
    for (y, m), vals in sorted(monthly.items()):
        result.append({
            "year": y,
            "month": m,
            "total": round(vals["total"], 2),
            "water": round(vals["water"], 2),
            "heat": round(vals["heat"], 2),
            "electricity": round(vals["electricity"], 2),
            "other": round(vals["other"], 2),
        })
    return result


def summary(db: Session, property_id: int, year: int) -> dict:
    """Year summary for dashboard cards."""
    cons = consumption_by_month(db, property_id, year)
    spend = spending_by_month(db, property_id, year)

    by_type: dict[str, float] = defaultdict(float)
    for c in cons:
        by_type[c["type"]] += c["consumption_t1"]
        if c["consumption_t2"]:
            by_type[c["type"]] += c["consumption_t2"]

    total_spent = sum(s["total"] for s in spend)

    return {
        "year": year,
        "total_spent": round(total_spent, 2),
        "months_with_bills": len(spend),
        "consumption": {
            t: round(v, 3) for t, v in by_type.items()
        },
        "avg_monthly_bill": round(total_spent / len(spend), 2) if spend else 0,
    }

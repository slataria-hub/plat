"""Business logic for features 1-8, 12 helpers."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any, Optional
from collections import defaultdict

from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from app.models.meter import Meter, MeterReading
from app.models.bill import Bill, BillItem, ServiceType, Tariff
from app.models.extra import PropertySettings


def get_or_create_settings(db: Session, property_id: int) -> PropertySettings:
    s = db.execute(
        select(PropertySettings).where(PropertySettings.property_id == property_id)
    ).scalar_one_or_none()
    if not s:
        s = PropertySettings(property_id=property_id)
        db.add(s)
        db.flush()
    return s


def reading_reminders(db: Session, property_id: int, today: Optional[date] = None) -> list[dict]:
    """Feature 1: calendar-based reminder to submit readings."""
    today = today or date.today()
    settings = get_or_create_settings(db, property_id)
    if not settings.reminder_enabled:
        return []

    reminder_day = max(1, min(28, settings.reminder_day or 15))
    # Window: from reminder_day until end of month (or first 5 days of next if late)
    in_window = today.day >= reminder_day
    # Also remind first 5 days of month if previous month still missing
    early_next = today.day <= 5

    alerts = []
    meters = db.execute(
        select(Meter).where(Meter.property_id == property_id, Meter.is_active == True)
    ).scalars().all()

    labels = {
        "cold_water": "Холодная вода",
        "hot_water": "Горячая вода",
        "electricity": "Электричество",
    }

    def month_has_reading(meter_id: int, y: int, m: int) -> bool:
        start = date(y, m, 1)
        end = date(y, m, monthrange(y, m)[1])
        row = db.execute(
            select(MeterReading).where(
                MeterReading.meter_id == meter_id,
                MeterReading.reading_date >= start,
                MeterReading.reading_date <= end,
            ).limit(1)
        ).scalar_one_or_none()
        return row is not None

    check_periods = []
    if in_window:
        check_periods.append((today.year, today.month, "current"))
    if early_next:
        prev = today.replace(day=1) - timedelta(days=1)
        check_periods.append((prev.year, prev.month, "previous"))

    seen = set()
    for y, m, kind in check_periods:
        for meter in meters:
            key = (meter.id, y, m)
            if key in seen:
                continue
            if month_has_reading(meter.id, y, m):
                continue
            seen.add(key)
            last = db.execute(
                select(MeterReading)
                .where(MeterReading.meter_id == meter.id)
                .order_by(desc(MeterReading.reading_date))
                .limit(1)
            ).scalar_one_or_none()
            alerts.append({
                "type": "reading_due",
                "severity": "warning" if kind == "current" and today.day >= reminder_day else "info",
                "property_id": property_id,
                "meter_id": meter.id,
                "title": f"Пора сдать показания: {labels.get(meter.type, meter.type)} · {meter.name}",
                "body": (
                    f"Нет показаний за {m:02d}.{y}. "
                    f"Напоминание с {reminder_day}-го числа. "
                    f"Последние: {last.reading_date.isoformat() if last else 'никогда'}"
                ),
                "date": today.isoformat(),
                "period_year": y,
                "period_month": m,
            })
    return alerts


def reconcile_period(
    db: Session,
    property_id: int,
    year: int,
    month: int,
    threshold: Optional[float] = None,
) -> dict:
    """Feature 2: compare bill volumes vs meter consumption."""
    settings = get_or_create_settings(db, property_id)
    thr = threshold if threshold is not None else (settings.reconcile_threshold or 0.5)

    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])

    # Consumption from readings in period
    meters = db.execute(
        select(Meter).where(Meter.property_id == property_id, Meter.is_active == True)
    ).scalars().all()

    consumption: dict[str, float] = defaultdict(float)
    for meter in meters:
        readings = db.execute(
            select(MeterReading).where(
                MeterReading.meter_id == meter.id,
                MeterReading.reading_date >= start,
                MeterReading.reading_date <= end,
            )
        ).scalars().all()
        for r in readings:
            c = (r.consumption_t1 or 0) + (r.consumption_t2 or 0)
            if meter.type == "cold_water":
                consumption["hvs"] += c
            elif meter.type == "hot_water":
                consumption["gvs"] += c
            elif meter.type == "electricity":
                consumption["electricity"] += c

    # Bill volumes
    bills = db.execute(
        select(Bill).where(
            Bill.property_id == property_id,
            Bill.period_year == year,
            Bill.period_month == month,
        )
    ).scalars().all()

    bill_vol: dict[str, float] = defaultdict(float)
    service_map = {
        "hvs": "hvs",
        "gvs_carrier": "gvs",
        "gvs_energy": "gvs",
        "gvs": "gvs",
        "electricity": "electricity",
        "electricity_day": "electricity",
        "electricity_night": "electricity",
    }
    for bill in bills:
        items = db.execute(select(BillItem).where(BillItem.bill_id == bill.id)).scalars().all()
        for it in items:
            code = None
            if it.service_type_id:
                st = db.get(ServiceType, it.service_type_id)
                if st:
                    code = st.code
            raw = (it.raw_name or "").lower().replace("ё", "е")
            if not code:
                if "одн" in raw.split() or raw.endswith("одн"):
                    continue
                if "горяч" in raw or "гвс" in raw:
                    code = "gvs"
                elif "холодн" in raw or "хвс" in raw or ("в/с" in raw and "горяч" not in raw):
                    code = "hvs"
                elif "электр" in raw or "квт" in raw:
                    code = "electricity"
            key = service_map.get(code or "", code)
            if key and it.volume is not None:
                if "одн" in raw:
                    continue
                bill_vol[key] += float(it.volume)

    labels = {"hvs": "Холодная вода", "gvs": "Горячая вода", "electricity": "Электричество"}
    units = {"hvs": "м³", "gvs": "м³", "electricity": "кВт·ч"}
    rows = []
    for key in ("hvs", "gvs", "electricity"):
        meter_c = round(consumption.get(key, 0), 3)
        bill_c = round(bill_vol.get(key, 0), 3)
        if meter_c == 0 and bill_c == 0:
            continue
        delta = round(bill_c - meter_c, 3)
        ok = abs(delta) <= thr
        rows.append({
            "resource": key,
            "label": labels[key],
            "unit": units[key],
            "meter_consumption": meter_c,
            "bill_volume": bill_c,
            "delta": delta,
            "threshold": thr,
            "ok": ok,
            "message": "OK" if ok else f"Расхождение {delta:+} {units[key]}",
        })

    return {
        "year": year,
        "month": month,
        "threshold": thr,
        "items": rows,
        "has_mismatch": any(not r["ok"] for r in rows),
    }


def expected_payment(db: Session, property_id: int, months: int = 6) -> dict:
    """Feature 3: typical month / expected payment from last N months."""
    bills = db.execute(
        select(Bill)
        .where(Bill.property_id == property_id)
        .order_by(desc(Bill.period_year), desc(Bill.period_month))
        .limit(months * 3)
    ).scalars().all()

    # group by period
    by_period: dict[tuple[int, int], float] = defaultdict(float)
    by_provider: dict[str, list[float]] = defaultdict(list)
    for b in bills:
        by_period[(b.period_year, b.period_month)] += float(b.total_accrued or 0)
        by_provider[b.provider].append(float(b.total_accrued or 0))

    periods = sorted(by_period.keys(), reverse=True)[:months]
    amounts = [by_period[p] for p in periods]
    avg = round(sum(amounts) / len(amounts), 2) if amounts else 0.0
    med = 0.0
    if amounts:
        s = sorted(amounts)
        med = s[len(s) // 2]

    provider_avg = {
        k: round(sum(v) / len(v), 2) for k, v in by_provider.items() if v
    }

    return {
        "months_used": len(periods),
        "periods": [{"year": y, "month": m, "total": by_period[(y, m)]} for y, m in periods],
        "average": avg,
        "median": med,
        "expected": avg,
        "by_provider_avg": provider_avg,
        "message": (
            f"Ожидаемый платёж ≈ {avg:,.2f} ₽ (среднее за {len(periods)} мес.)"
            if periods else "Недостаточно данных по квитанциям"
        ),
    }


def tariff_history(db: Session, property_id: int) -> list[dict]:
    """Feature 4: tariff change timeline."""
    tariffs = db.execute(
        select(Tariff)
        .where(Tariff.property_id == property_id)
        .order_by(Tariff.service_code, Tariff.start_date)
    ).scalars().all()

    names = {s.code: s.name for s in db.execute(select(ServiceType)).scalars().all()}
    by_code: dict[str, list] = defaultdict(list)
    for t in tariffs:
        by_code[t.service_code].append(t)

    timeline = []
    for code, items in by_code.items():
        prev = None
        for t in items:
            entry = {
                "service_code": code,
                "service_name": names.get(code, code),
                "start_date": t.start_date.isoformat(),
                "price_t1": t.price_t1,
                "price_t2": t.price_t2,
                "delta": None,
                "pct": None,
            }
            if prev and prev.price_t1:
                entry["delta"] = round(t.price_t1 - prev.price_t1, 4)
                entry["pct"] = round(entry["delta"] / prev.price_t1 * 100, 2)
            timeline.append(entry)
            prev = t

    timeline.sort(key=lambda x: x["start_date"], reverse=True)
    return timeline


def dual_tariff_compare(db: Session, property_id: int, year: int) -> dict:
    """Feature 8: compare day/night vs single tariff cost."""
    meters = db.execute(
        select(Meter).where(
            Meter.property_id == property_id,
            Meter.type == "electricity",
            Meter.is_active == True,
        )
    ).scalars().all()

    # get tariffs
    day_t = db.execute(
        select(Tariff)
        .where(Tariff.property_id == property_id, Tariff.service_code.in_(["electricity_day", "electricity"]))
        .order_by(desc(Tariff.start_date))
        .limit(1)
    ).scalar_one_or_none()
    night_t = db.execute(
        select(Tariff)
        .where(Tariff.property_id == property_id, Tariff.service_code == "electricity_night")
        .order_by(desc(Tariff.start_date))
        .limit(1)
    ).scalar_one_or_none()

    price_day = day_t.price_t1 if day_t else 8.11
    price_night = night_t.price_t1 if night_t else price_day * 0.6
    price_single = price_day  # approximate single = day rate

    start = date(year, 1, 1)
    end = date(year, 12, 31)
    total_day = total_night = 0.0
    months = []

    for m in range(1, 13):
        ms, me = date(year, m, 1), date(year, m, monthrange(year, m)[1])
        d = n = 0.0
        for meter in meters:
            readings = db.execute(
                select(MeterReading).where(
                    MeterReading.meter_id == meter.id,
                    MeterReading.reading_date >= ms,
                    MeterReading.reading_date <= me,
                )
            ).scalars().all()
            for r in readings:
                d += r.consumption_t1 or 0
                n += r.consumption_t2 or 0
        total_day += d
        total_night += n
        dual_cost = d * price_day + n * price_night
        single_cost = (d + n) * price_single
        if d + n > 0:
            months.append({
                "month": m,
                "day_kwh": round(d, 2),
                "night_kwh": round(n, 2),
                "dual_cost": round(dual_cost, 2),
                "single_cost": round(single_cost, 2),
                "savings": round(single_cost - dual_cost, 2),
            })

    dual_total = total_day * price_day + total_night * price_night
    single_total = (total_day + total_night) * price_single
    return {
        "year": year,
        "price_day": price_day,
        "price_night": price_night,
        "price_single": price_single,
        "total_day_kwh": round(total_day, 2),
        "total_night_kwh": round(total_night, 2),
        "dual_total": round(dual_total, 2),
        "single_total": round(single_total, 2),
        "savings": round(single_total - dual_total, 2),
        "months": months,
        "message": (
            f"За {year} двухтарифный выгоднее на {single_total - dual_total:,.0f} ₽"
            if single_total >= dual_total
            else f"За {year} однотарифный был бы дешевле на {dual_total - single_total:,.0f} ₽"
        ),
    }


def widget_summary(db: Session, user_id: int, property_id: Optional[int] = None) -> dict:
    """Feature 12: compact summary for widget / PWA."""
    from app.models.property import Property

    q = select(Property).where(Property.user_id == user_id)
    if property_id:
        q = q.where(Property.id == property_id)
    props = db.execute(q).scalars().all()
    if not props:
        return {"properties": [], "message": "Нет объектов"}

    out = []
    today = date.today()
    for prop in props:
        meters = db.execute(
            select(Meter).where(Meter.property_id == prop.id, Meter.is_active == True)
        ).scalars().all()
        meter_info = []
        for m in meters:
            last = db.execute(
                select(MeterReading)
                .where(MeterReading.meter_id == m.id)
                .order_by(desc(MeterReading.reading_date))
                .limit(1)
            ).scalar_one_or_none()
            meter_info.append({
                "id": m.id,
                "name": m.name,
                "type": m.type,
                "last_date": last.reading_date.isoformat() if last else None,
                "last_value_t1": last.value_t1 if last else None,
                "last_value_t2": last.value_t2 if last else None,
            })
        # last unpaid-ish bill total
        bill = db.execute(
            select(Bill)
            .where(Bill.property_id == prop.id)
            .order_by(desc(Bill.period_year), desc(Bill.period_month))
            .limit(1)
        ).scalar_one_or_none()
        due = 0.0
        if bill:
            due = max(0.0, float(bill.total_accrued or 0) - float(bill.total_paid or 0))
        exp = expected_payment(db, prop.id, months=3)
        out.append({
            "property_id": prop.id,
            "property_name": prop.name,
            "meters": meter_info,
            "last_bill_due": round(due, 2),
            "expected_payment": exp.get("expected", 0),
            "as_of": today.isoformat(),
        })
    return {"properties": out, "as_of": today.isoformat()}

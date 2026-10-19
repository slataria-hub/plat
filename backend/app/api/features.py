"""API for features 1-12."""
from __future__ import annotations

import secrets
from datetime import date
from typing import Annotated, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.models.extra import PropertySettings, PeriodNote, UtilityAccount, PropertyShare
from app.api.deps import get_current_user
from app.services.features import (
    get_or_create_settings,
    reading_reminders,
    reconcile_period,
    expected_payment,
    tariff_history,
    dual_tariff_compare,
    widget_summary,
)
from app.services.seed import seed_service_types

router = APIRouter(tags=["features"])


def _prop(db: Session, user_id: int, property_id: int) -> Property:
    p = db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user_id)
    ).scalar_one_or_none()
    if not p:
        # allow guest viewer?
        share = db.execute(
            select(PropertyShare).where(
                PropertyShare.property_id == property_id,
                PropertyShare.guest_user_id == user_id,
                PropertyShare.accepted == True,
            )
        ).scalar_one_or_none()
        if share:
            p = db.get(Property, property_id)
        if not p:
            raise HTTPException(404, "Объект не найден")
    return p


# ─── 1 Settings + enhanced notifications ─────────────────

class SettingsIn(BaseModel):
    reminder_day: Optional[int] = Field(None, ge=1, le=28)
    reminder_enabled: Optional[bool] = None
    reconcile_threshold: Optional[float] = Field(None, ge=0)


@router.get("/properties/{property_id}/settings")
def get_settings(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _prop(db, user.id, property_id)
    s = get_or_create_settings(db, property_id)
    return {
        "property_id": property_id,
        "reminder_day": s.reminder_day,
        "reminder_enabled": s.reminder_enabled,
        "reconcile_threshold": s.reconcile_threshold,
    }


@router.patch("/properties/{property_id}/settings")
def patch_settings(
    property_id: int,
    data: SettingsIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _prop(db, user.id, property_id)
    s = get_or_create_settings(db, property_id)
    if data.reminder_day is not None:
        s.reminder_day = data.reminder_day
    if data.reminder_enabled is not None:
        s.reminder_enabled = data.reminder_enabled
    if data.reconcile_threshold is not None:
        s.reconcile_threshold = data.reconcile_threshold
    db.flush()
    return {
        "property_id": property_id,
        "reminder_day": s.reminder_day,
        "reminder_enabled": s.reminder_enabled,
        "reconcile_threshold": s.reconcile_threshold,
    }


@router.get("/properties/{property_id}/reminders")
def get_reminders(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _prop(db, user.id, property_id)
    return {"items": reading_reminders(db, property_id)}


# ─── 2 Reconcile ─────────────────────────────────────────

@router.get("/properties/{property_id}/reconcile")
def reconcile(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    threshold: Optional[float] = Query(None),
):
    _prop(db, user.id, property_id)
    return reconcile_period(db, property_id, year, month, threshold)


# ─── 3 Expected payment ──────────────────────────────────

@router.get("/properties/{property_id}/expected-payment")
def expected(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    months: int = Query(6, ge=1, le=24),
):
    _prop(db, user.id, property_id)
    return expected_payment(db, property_id, months)


# ─── 4 Tariff history ────────────────────────────────────

@router.get("/properties/{property_id}/tariff-history")
def tariffs_hist(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    seed_service_types(db)
    _prop(db, user.id, property_id)
    return {"items": tariff_history(db, property_id)}


# ─── 6 Period notes ──────────────────────────────────────

class NoteIn(BaseModel):
    year: int
    month: int = Field(..., ge=1, le=12)
    text: str = ""


@router.get("/properties/{property_id}/notes")
def list_notes(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Optional[int] = None,
):
    _prop(db, user.id, property_id)
    q = select(PeriodNote).where(PeriodNote.property_id == property_id)
    if year:
        q = q.where(PeriodNote.year == year)
    rows = db.execute(q.order_by(PeriodNote.year.desc(), PeriodNote.month.desc())).scalars().all()
    return [
        {
            "id": n.id,
            "year": n.year,
            "month": n.month,
            "text": n.text,
            "file_path": n.file_path,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


@router.post("/properties/{property_id}/notes")
def create_note(
    property_id: int,
    data: NoteIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _prop(db, user.id, property_id)
    existing = db.execute(
        select(PeriodNote).where(
            PeriodNote.property_id == property_id,
            PeriodNote.year == data.year,
            PeriodNote.month == data.month,
        )
    ).scalar_one_or_none()
    if existing:
        existing.text = data.text
        db.flush()
        n = existing
    else:
        n = PeriodNote(property_id=property_id, year=data.year, month=data.month, text=data.text)
        db.add(n)
        db.flush()
    return {"id": n.id, "year": n.year, "month": n.month, "text": n.text}


@router.post("/properties/{property_id}/notes/{note_id}/file")
async def note_file(
    property_id: int,
    note_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    from app.services.files import save_upload
    _prop(db, user.id, property_id)
    n = db.execute(
        select(PeriodNote).where(PeriodNote.id == note_id, PeriodNote.property_id == property_id)
    ).scalar_one_or_none()
    if not n:
        raise HTTPException(404, "Заметка не найдена")
    rel, _ = await save_upload(file, subfolder=f"notes/{user.id}")
    n.file_path = rel
    db.flush()
    return {"id": n.id, "file_path": n.file_path}


# ─── 7 PDF export ────────────────────────────────────────

@router.get("/properties/{property_id}/export/pdf")
def export_pdf(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Optional[int] = None,
    month: Optional[int] = None,
):
    """Simple text-based PDF via reportlab if available, else plain text attachment."""
    from app.models.meter import Meter, MeterReading
    from sqlalchemy import desc

    prop = _prop(db, user.id, property_id)
    y = year or date.today().year
    lines = [f"MeterApp — отчёт по объекту «{prop.name}»", f"Год: {y}", ""]

    meters = db.execute(select(Meter).where(Meter.property_id == property_id)).scalars().all()
    for m in meters:
        lines.append(f"Счётчик: {m.name} ({m.type})")
        q = select(MeterReading).where(MeterReading.meter_id == m.id)
        if month:
            from calendar import monthrange
            start = date(y, month, 1)
            end = date(y, month, monthrange(y, month)[1])
            q = q.where(MeterReading.reading_date >= start, MeterReading.reading_date <= end)
        else:
            q = q.where(MeterReading.reading_date >= date(y, 1, 1), MeterReading.reading_date <= date(y, 12, 31))
        readings = db.execute(q.order_by(MeterReading.reading_date)).scalars().all()
        for r in readings:
            lines.append(
                f"  {r.reading_date}: {r.value_t1}"
                + (f" / {r.value_t2}" if r.value_t2 is not None else "")
                + (f"  расход {r.consumption_t1}" if r.consumption_t1 is not None else "")
            )
        lines.append("")

    from app.models.bill import Bill
    bq = select(Bill).where(Bill.property_id == property_id, Bill.period_year == y)
    if month:
        bq = bq.where(Bill.period_month == month)
    bills = db.execute(bq.order_by(Bill.period_month)).scalars().all()
    lines.append("Квитанции:")
    for b in bills:
        lines.append(f"  {b.period_month:02d}.{b.period_year} {b.provider}: {b.total_accrued} ₽ (оплачено {b.total_paid})")

    body = "\n".join(lines).encode("utf-8")

    # Try reportlab PDF
    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        y_pos = height - 40
        c.setFont("Helvetica", 10)
        for line in lines:
            # transliterate-ish: reportlab default font lacks cyrillic — write as UTF via simple escape
            safe = line.encode("latin-1", "replace").decode("latin-1")
            if y_pos < 40:
                c.showPage()
                c.setFont("Helvetica", 10)
                y_pos = height - 40
            c.drawString(40, y_pos, safe[:100])
            y_pos -= 14
        c.save()
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="meterapp_{property_id}_{y}.pdf"'},
        )
    except Exception:
        from io import BytesIO
        buf = BytesIO(body)
        return StreamingResponse(
            buf,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="meterapp_{property_id}_{y}.txt"'},
        )


# ─── 8 Dual tariff ───────────────────────────────────────

@router.get("/properties/{property_id}/dual-tariff-compare")
def dual_compare(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: int = Query(default_factory=lambda: date.today().year),
):
    _prop(db, user.id, property_id)
    return dual_tariff_compare(db, property_id, year)


# ─── 9 Utility accounts ──────────────────────────────────

class AccountIn(BaseModel):
    provider: str
    account_number: Optional[str] = None
    category: str = "other"
    portal_url: Optional[str] = None
    notes: Optional[str] = None


@router.get("/properties/{property_id}/accounts")
def list_accounts(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _prop(db, user.id, property_id)
    rows = db.execute(
        select(UtilityAccount).where(UtilityAccount.property_id == property_id, UtilityAccount.is_active == True)
    ).scalars().all()
    return [
        {
            "id": a.id,
            "provider": a.provider,
            "account_number": a.account_number,
            "category": a.category,
            "portal_url": a.portal_url,
            "notes": a.notes,
        }
        for a in rows
    ]


@router.post("/properties/{property_id}/accounts")
def create_account(
    property_id: int,
    data: AccountIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _prop(db, user.id, property_id)
    a = UtilityAccount(
        property_id=property_id,
        provider=data.provider,
        account_number=data.account_number,
        category=data.category,
        portal_url=data.portal_url,
        notes=data.notes,
    )
    db.add(a)
    db.flush()
    return {"id": a.id, "provider": a.provider, "account_number": a.account_number}


@router.delete("/properties/{property_id}/accounts/{account_id}")
def delete_account(
    property_id: int,
    account_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _prop(db, user.id, property_id)
    a = db.execute(
        select(UtilityAccount).where(UtilityAccount.id == account_id, UtilityAccount.property_id == property_id)
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Счёт не найден")
    a.is_active = False
    db.flush()
    return {"ok": True}


# ─── 10 Portal links (no free API — curated links) ───────

@router.get("/properties/{property_id}/portals")
def portals(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Feature 10: links to known LKs (no automated free API)."""
    _prop(db, user.id, property_id)
    accounts = db.execute(
        select(UtilityAccount).where(UtilityAccount.property_id == property_id, UtilityAccount.is_active == True)
    ).scalars().all()
    defaults = [
        {"name": "МосОблЕИРЦ", "url": "https://мособлеирц.рф/", "category": "eirc"},
        {"name": "Мосэнергосбыт", "url": "https://www.mosenergosbyt.ru/", "category": "electricity"},
        {"name": "ГИС ЖКХ", "url": "https://dom.gosuslugi.ru/", "category": "other"},
    ]
    custom = [
        {"name": a.provider, "url": a.portal_url, "category": a.category, "account_number": a.account_number}
        for a in accounts if a.portal_url
    ]
    return {
        "message": "Официального бесплатного API для автозагрузки квитанций нет. Откройте ЛК вручную или загрузите PDF в приложение.",
        "defaults": defaults,
        "accounts": custom,
    }


# ─── 11 Family / guest share ─────────────────────────────

class ShareIn(BaseModel):
    guest_email: EmailStr
    role: str = "viewer"


@router.get("/properties/{property_id}/shares")
def list_shares(
    property_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    prop = db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user.id)
    ).scalar_one_or_none()
    if not prop:
        raise HTTPException(404, "Объект не найден")
    rows = db.execute(
        select(PropertyShare).where(PropertyShare.property_id == property_id)
    ).scalars().all()
    return [
        {
            "id": s.id,
            "guest_email": s.guest_email,
            "role": s.role,
            "accepted": s.accepted,
            "invite_token": s.invite_token,
        }
        for s in rows
    ]


@router.post("/properties/{property_id}/shares")
def create_share(
    property_id: int,
    data: ShareIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    prop = db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user.id)
    ).scalar_one_or_none()
    if not prop:
        raise HTTPException(404, "Объект не найден")
    token = secrets.token_urlsafe(24)
    guest = db.execute(select(User).where(User.email == data.guest_email.lower())).scalar_one_or_none()
    s = PropertyShare(
        property_id=property_id,
        owner_user_id=user.id,
        guest_email=data.guest_email.lower(),
        guest_user_id=guest.id if guest else None,
        role="viewer",
        invite_token=token,
        accepted=False,
    )
    db.add(s)
    db.flush()
    return {
        "id": s.id,
        "guest_email": s.guest_email,
        "invite_token": token,
        "invite_path": f"/invite/{token}",
        "message": "Передайте ссылку с токеном гостю. После регистрации/входа с этим email доступ станет активным.",
    }


@router.post("/shares/accept/{token}")
def accept_share(
    token: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    s = db.execute(select(PropertyShare).where(PropertyShare.invite_token == token)).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Приглашение не найдено")
    if s.guest_email.lower() != user.email.lower():
        raise HTTPException(403, "Войдите под email, на который отправлено приглашение")
    s.guest_user_id = user.id
    s.accepted = True
    db.flush()
    return {"ok": True, "property_id": s.property_id}


@router.get("/shared-with-me")
def shared_with_me(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    rows = db.execute(
        select(PropertyShare).where(
            PropertyShare.guest_user_id == user.id,
            PropertyShare.accepted == True,
        )
    ).scalars().all()
    result = []
    for s in rows:
        p = db.get(Property, s.property_id)
        if p:
            result.append({"property_id": p.id, "property_name": p.name, "role": s.role})
    return result


# ─── 12 Widget ───────────────────────────────────────────

@router.get("/widget")
def widget(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    property_id: Optional[int] = None,
):
    return widget_summary(db, user.id, property_id)


# ─── 5 Quick readings batch ──────────────────────────────

class QuickReadingItem(BaseModel):
    meter_id: int
    value_t1: float
    value_t2: Optional[float] = None


class QuickReadingIn(BaseModel):
    reading_date: date
    items: List[QuickReadingItem]


@router.post("/properties/{property_id}/readings/quick")
def quick_readings(
    property_id: int,
    data: QuickReadingIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    from app.models.meter import Meter, MeterReading
    from app.api.meters import _calc_consumption

    _prop(db, user.id, property_id)
    created = []
    for item in data.items:
        meter = db.execute(
            select(Meter).where(Meter.id == item.meter_id, Meter.property_id == property_id)
        ).scalar_one_or_none()
        if not meter:
            continue
        cons_t1, cons_t2 = _calc_consumption(
            db, meter.id, data.reading_date, item.value_t1, item.value_t2
        )
        r = MeterReading(
            meter_id=meter.id,
            reading_date=data.reading_date,
            value_t1=item.value_t1,
            value_t2=item.value_t2,
            consumption_t1=cons_t1,
            consumption_t2=cons_t2,
            source="quick",
        )
        db.add(r)
        db.flush()
        created.append({"id": r.id, "meter_id": meter.id, "consumption_t1": cons_t1})
    return {"created": created, "count": len(created)}

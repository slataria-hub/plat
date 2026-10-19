from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.models.bill import Bill
from app.api.deps import get_current_user
from app.services.export import export_property_to_excel
from app.services.analytics import consumption_by_month, spending_by_month, summary
from app.services.ocr import recognize_bill_file
from app.services.files import get_absolute_path

router = APIRouter(tags=["export", "analytics", "ocr"])


def _get_user_property(db: Session, user_id: int, property_id: int) -> Property:
    prop = db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user_id)
    ).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Объект не найден")
    return prop


# ─── Excel export ────────────────────────────────────────

@router.get("/properties/{property_id}/export/excel")
def export_excel(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_user_property(db, current_user.id, property_id)
    try:
        buf = export_property_to_excel(db, property_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    filename = f"meterapp_property_{property_id}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Analytics ───────────────────────────────────────────

@router.get("/properties/{property_id}/analytics/consumption")
def get_consumption(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Optional[int] = Query(None),
):
    _get_user_property(db, current_user.id, property_id)
    return consumption_by_month(db, property_id, year)


@router.get("/properties/{property_id}/analytics/spending")
def get_spending(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Optional[int] = Query(None),
):
    _get_user_property(db, current_user.id, property_id)
    return spending_by_month(db, property_id, year)


@router.get("/properties/{property_id}/analytics/summary")
def get_summary(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: int = Query(...),
):
    _get_user_property(db, current_user.id, property_id)
    return summary(db, property_id, year)



# ─── OCR ─────────────────────────────────────────────────

@router.post("/bills/{bill_id}/recognize")
def recognize_bill(
    bill_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    apply: bool = Query(False, description="Применить результат к квитанции"),
):
    """
    OCR + разбор квитанции (Tesseract rus+eng + правила МосОблЕИРЦ).
    Если apply=true — обновляет поля квитанции и строки услуг.
    """
    from datetime import datetime, timezone
    from app.models.bill import BillItem, ServiceType
    from app.services.seed import seed_service_types

    bill = db.execute(
        select(Bill).join(Property).where(
            Bill.id == bill_id, Property.user_id == current_user.id
        )
    ).scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Квитанция не найдена")
    if not bill.file_path:
        raise HTTPException(status_code=400, detail="К квитанции не прикреплён файл")

    abs_path = get_absolute_path(bill.file_path)
    result = recognize_bill_file(abs_path)

    if apply and result.get("status") in ("done", "partial"):
        seed_service_types(db)
        code_to_id = {
            s.code: s.id
            for s in db.execute(select(ServiceType)).scalars().all()
        }
        if result.get("provider"):
            bill.provider = result["provider"]
        if result.get("period_year"):
            bill.period_year = result["period_year"]
        if result.get("period_month"):
            bill.period_month = result["period_month"]
        if result.get("total_accrued"):
            bill.total_accrued = result["total_accrued"]

        # Replace items if we got any
        items = result.get("items") or []
        if items:
            for old in list(bill.items):
                db.delete(old)
            db.flush()
            total = 0.0
            for it in items:
                amount = it.get("amount") or 0
                total += amount
                st_id = code_to_id.get(it.get("service_code")) if it.get("service_code") else None
                db.add(BillItem(
                    bill_id=bill.id,
                    service_type_id=st_id,
                    raw_name=it.get("raw_name"),
                    volume=it.get("volume"),
                    tariff=it.get("tariff"),
                    amount=amount,
                ))
            if not result.get("total_accrued") and total > 0:
                bill.total_accrued = round(total, 2)

        bill.status = "recognized"
        from datetime import datetime, timezone
        bill.recognized_at = datetime.now(timezone.utc)
        db.flush()
        result["applied"] = True
    else:
        result["applied"] = False

    return result


@router.post("/ocr/parse-text")
def parse_text_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    body: dict,
):
    """Parse raw text (pasted from PDF or manual) without a file."""
    from app.services.ocr import recognize_from_text
    text = body.get("text") or ""
    return recognize_from_text(text)


# ─── Full backup (ZIP) ───────────────────────────────────

@router.get("/backup/zip")
def download_backup(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Download full backup: data.json + Excel per property + uploaded bill files.
    """
    from app.services.backup import create_user_backup
    try:
        buf = create_user_backup(db, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    filename = f"meterapp_backup_{current_user.id}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Excel import ────────────────────────────────────────

@router.post("/properties/{property_id}/import/excel")
async def import_excel(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Import readings and payments from user's historical Excel workbook."""
    from app.services.import_excel import import_workbook

    _get_user_property(db, current_user.id, property_id)
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Нужен файл .xlsx")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 20 МБ)")
    try:
        report = import_workbook(db, property_id, data)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка импорта: {e}")
    return {"status": "ok", **report}

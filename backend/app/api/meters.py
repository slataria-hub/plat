from typing import Annotated, List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.models.meter import Meter, MeterReading
from app.schemas.meter import (
    MeterCreate, MeterUpdate, MeterOut,
    MeterReadingCreate, MeterReadingUpdate, MeterReadingOut,
    MeterWithLastReading,
)
from app.api.deps import get_current_user

router = APIRouter(tags=["meters"])


def _get_user_property(db: Session, user_id: int, property_id: int) -> Property:
    prop = db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user_id)
    ).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Объект не найден")
    return prop


def _get_user_meter(db: Session, user_id: int, meter_id: int) -> Meter:
    meter = db.execute(
        select(Meter)
        .join(Property)
        .where(Meter.id == meter_id, Property.user_id == user_id)
    ).scalar_one_or_none()
    if not meter:
        raise HTTPException(status_code=404, detail="Счётчик не найден")
    return meter


def _calc_consumption(db: Session, meter_id: int, reading_date: date, value_t1: float, value_t2: Optional[float]):
    """Calculate consumption as difference from previous reading."""
    prev = db.execute(
        select(MeterReading)
        .where(MeterReading.meter_id == meter_id, MeterReading.reading_date < reading_date)
        .order_by(desc(MeterReading.reading_date))
        .limit(1)
    ).scalar_one_or_none()

    cons_t1 = None
    cons_t2 = None
    if prev:
        cons_t1 = round(value_t1 - prev.value_t1, 3)
        if value_t2 is not None and prev.value_t2 is not None:
            cons_t2 = round(value_t2 - prev.value_t2, 3)
    return cons_t1, cons_t2


# ─── Meters CRUD ─────────────────────────────────────────

@router.get("/properties/{property_id}/meters", response_model=List[MeterWithLastReading])
def list_meters(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_user_property(db, current_user.id, property_id)
    meters = db.execute(
        select(Meter).where(Meter.property_id == property_id).order_by(Meter.type, Meter.name)
    ).scalars().all()

    result = []
    for m in meters:
        last = db.execute(
            select(MeterReading)
            .where(MeterReading.meter_id == m.id)
            .order_by(desc(MeterReading.reading_date))
            .limit(1)
        ).scalar_one_or_none()
        out = MeterWithLastReading.model_validate(m)
        if last:
            out.last_reading = MeterReadingOut.model_validate(last)
        result.append(out)
    return result


@router.post("/properties/{property_id}/meters", response_model=MeterOut, status_code=status.HTTP_201_CREATED)
def create_meter(
    property_id: int,
    data: MeterCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if data.property_id != property_id:
        raise HTTPException(status_code=400, detail="property_id в теле не совпадает с URL")

    _get_user_property(db, current_user.id, property_id)

    unit = data.unit
    if not unit:
        unit = "kwh" if data.type == "electricity" else "m3"

    meter = Meter(
        property_id=property_id,
        type=data.type,
        name=data.name,
        serial_number=data.serial_number,
        tariff_type=data.tariff_type,
        unit=unit,
    )
    db.add(meter)
    db.flush()
    db.refresh(meter)
    return meter


@router.get("/meters/{meter_id}", response_model=MeterOut)
def get_meter(
    meter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _get_user_meter(db, current_user.id, meter_id)


@router.patch("/meters/{meter_id}", response_model=MeterOut)
def update_meter(
    meter_id: int,
    data: MeterUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    meter = _get_user_meter(db, current_user.id, meter_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(meter, field, value)
    db.flush()
    db.refresh(meter)
    return meter


@router.delete("/meters/{meter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meter(
    meter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    meter = _get_user_meter(db, current_user.id, meter_id)
    db.delete(meter)


# ─── Readings CRUD ───────────────────────────────────────

@router.get("/meters/{meter_id}/readings", response_model=List[MeterReadingOut])
def list_readings(
    meter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    _get_user_meter(db, current_user.id, meter_id)
    q = select(MeterReading).where(MeterReading.meter_id == meter_id)
    if year:
        q = q.where(MeterReading.reading_date >= date(year, 1, 1),
                    MeterReading.reading_date <= date(year, 12, 31))
    q = q.order_by(desc(MeterReading.reading_date)).limit(limit)
    return db.execute(q).scalars().all()


@router.post("/meters/{meter_id}/readings", response_model=MeterReadingOut, status_code=status.HTTP_201_CREATED)
def create_reading(
    meter_id: int,
    data: MeterReadingCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if data.meter_id != meter_id:
        raise HTTPException(status_code=400, detail="meter_id в теле не совпадает с URL")

    meter = _get_user_meter(db, current_user.id, meter_id)

    # Validate day_night
    if meter.tariff_type == "day_night" and data.value_t2 is None:
        raise HTTPException(status_code=400, detail="Для двухтарифного счётчика нужно указать value_t2 (ночь)")

    cons_t1, cons_t2 = _calc_consumption(db, meter_id, data.reading_date, data.value_t1, data.value_t2)

    # Sanity check: consumption should not be negative (possible meter replacement)
    if cons_t1 is not None and cons_t1 < 0:
        # Allow but note it — user might have replaced the meter
        pass

    reading = MeterReading(
        meter_id=meter_id,
        reading_date=data.reading_date,
        value_t1=data.value_t1,
        value_t2=data.value_t2,
        consumption_t1=cons_t1,
        consumption_t2=cons_t2,
        source=data.source,
        notes=data.notes,
    )
    db.add(reading)
    db.flush()
    db.refresh(reading)
    return reading


@router.get("/readings/{reading_id}", response_model=MeterReadingOut)
def get_reading(
    reading_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    reading = db.execute(
        select(MeterReading)
        .join(Meter)
        .join(Property)
        .where(MeterReading.id == reading_id, Property.user_id == current_user.id)
    ).scalar_one_or_none()
    if not reading:
        raise HTTPException(status_code=404, detail="Показание не найдено")
    return reading


@router.patch("/readings/{reading_id}", response_model=MeterReadingOut)
def update_reading(
    reading_id: int,
    data: MeterReadingUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    reading = db.execute(
        select(MeterReading)
        .join(Meter)
        .join(Property)
        .where(MeterReading.id == reading_id, Property.user_id == current_user.id)
    ).scalar_one_or_none()
    if not reading:
        raise HTTPException(status_code=404, detail="Показание не найдено")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(reading, field, value)

    # Recalculate consumption if values or date changed
    if any(k in update_data for k in ("value_t1", "value_t2", "reading_date")):
        cons_t1, cons_t2 = _calc_consumption(
            db, reading.meter_id, reading.reading_date, reading.value_t1, reading.value_t2
        )
        reading.consumption_t1 = cons_t1
        reading.consumption_t2 = cons_t2

    db.flush()
    db.refresh(reading)
    return reading


@router.delete("/readings/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reading(
    reading_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    reading = db.execute(
        select(MeterReading)
        .join(Meter)
        .join(Property)
        .where(MeterReading.id == reading_id, Property.user_id == current_user.id)
    ).scalar_one_or_none()
    if not reading:
        raise HTTPException(status_code=404, detail="Показание не найдено")
    db.delete(reading)


# ─── Photo recognition for meter readings ────────────────

@router.post("/meters/{meter_id}/readings/from-photo")
async def reading_from_photo(
    meter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
    reading_date: Optional[str] = Form(None),
    apply: bool = Form(False),
):
    """
    Upload meter photo → OCR digits → optional create reading.
    Returns recognized values; if apply=true and date given, creates reading.
    """
    from datetime import date as date_cls
    from app.services.files import save_upload
    from app.services.meter_ocr import recognize_meter_photo
    from app.services.files import get_absolute_path

    meter = _get_user_meter(db, current_user.id, meter_id)
    relative, _ftype = await save_upload(file, subfolder=f"meters/{current_user.id}")
    abs_path = get_absolute_path(relative)

    ocr = recognize_meter_photo(abs_path, tariff_type=meter.tariff_type)
    ocr["photo_path"] = relative
    ocr["meter_id"] = meter_id

    if apply and ocr.get("status") == "done" and ocr.get("value_t1") is not None:
        if not reading_date:
            raise HTTPException(status_code=400, detail="Для сохранения нужна reading_date (YYYY-MM-DD)")
        try:
            rd = date_cls.fromisoformat(reading_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректная дата")

        if meter.tariff_type == "day_night" and ocr.get("value_t2") is None:
            raise HTTPException(status_code=400, detail="Для двухтарифного счётчика нужно value_t2 — проверьте фото или введите вручную")

        cons_t1, cons_t2 = _calc_consumption(
            db, meter_id, rd, float(ocr["value_t1"]),
            float(ocr["value_t2"]) if ocr.get("value_t2") is not None else None,
        )
        reading = MeterReading(
            meter_id=meter_id,
            reading_date=rd,
            value_t1=float(ocr["value_t1"]),
            value_t2=float(ocr["value_t2"]) if ocr.get("value_t2") is not None else None,
            consumption_t1=cons_t1,
            consumption_t2=cons_t2,
            source="photo",
            photo_path=relative,
        )
        db.add(reading)
        db.flush()
        db.refresh(reading)
        ocr["reading_id"] = reading.id
        ocr["consumption_t1"] = cons_t1
        ocr["consumption_t2"] = cons_t2
        ocr["applied"] = True
    else:
        ocr["applied"] = False

    return ocr

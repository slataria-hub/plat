from typing import Annotated, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, desc, func
from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.models.bill import Bill, BillItem, Payment, ServiceType
from app.schemas.bill import (
    BillCreate, BillUpdate, BillOut, BillListItem,
    BillItemCreate, BillItemOut,
    PaymentCreate, PaymentOut,
    ServiceTypeOut,
)
from app.api.deps import get_current_user
from app.services.files import save_upload
from app.services.seed import seed_service_types

router = APIRouter(tags=["bills"])


def _get_user_property(db: Session, user_id: int, property_id: int) -> Property:
    prop = db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user_id)
    ).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Объект не найден")
    return prop


def _get_user_bill(db: Session, user_id: int, bill_id: int) -> Bill:
    bill = db.execute(
        select(Bill)
        .join(Property)
        .where(Bill.id == bill_id, Property.user_id == user_id)
        .options(joinedload(Bill.items).joinedload(BillItem.service_type), joinedload(Bill.payments))
    ).unique().scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Квитанция не найдена")
    return bill


# ─── Service types ───────────────────────────────────────

@router.get("/service-types", response_model=List[ServiceTypeOut])
def list_service_types(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    seed_service_types(db)
    return db.execute(select(ServiceType).order_by(ServiceType.category, ServiceType.name)).scalars().all()


# ─── Bills registry ──────────────────────────────────────

@router.get("/properties/{property_id}/bills", response_model=List[BillListItem])
def list_bills(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    provider: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort: str = Query("period_desc", pattern="^(period_desc|period_asc|amount_desc|amount_asc)$"),
    limit: int = Query(50, ge=1, le=200),
):
    _get_user_property(db, current_user.id, property_id)

    q = (
        select(Bill, func.count(BillItem.id).label("items_count"))
        .outerjoin(BillItem)
        .where(Bill.property_id == property_id)
        .group_by(Bill.id)
    )
    if year:
        q = q.where(Bill.period_year == year)
    if month:
        q = q.where(Bill.period_month == month)
    if provider:
        q = q.where(Bill.provider.ilike(f"%{provider}%"))
    if status:
        q = q.where(Bill.status == status)

    if sort == "period_asc":
        q = q.order_by(Bill.period_year, Bill.period_month)
    elif sort == "amount_desc":
        q = q.order_by(desc(Bill.total_accrued))
    elif sort == "amount_asc":
        q = q.order_by(Bill.total_accrued)
    else:
        q = q.order_by(desc(Bill.period_year), desc(Bill.period_month))
    q = q.limit(limit)
    rows = db.execute(q).all()

    result = []
    for bill, items_count in rows:
        item = BillListItem.model_validate(bill)
        item.items_count = items_count or 0
        result.append(item)
    return result


@router.post("/properties/{property_id}/bills", response_model=BillOut, status_code=status.HTTP_201_CREATED)
def create_bill(
    property_id: int,
    data: BillCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if data.property_id != property_id:
        raise HTTPException(status_code=400, detail="property_id в теле не совпадает с URL")

    _get_user_property(db, current_user.id, property_id)
    seed_service_types(db)

    bill = Bill(
        property_id=property_id,
        provider=data.provider,
        period_year=data.period_year,
        period_month=data.period_month,
        total_accrued=data.total_accrued,
        total_paid=data.total_paid,
        notes=data.notes,
        status="draft",
    )
    db.add(bill)
    db.flush()

    if data.items:
        for it in data.items:
            db.add(BillItem(
                bill_id=bill.id,
                service_type_id=it.service_type_id,
                raw_name=it.raw_name,
                volume=it.volume,
                tariff=it.tariff,
                amount=it.amount,
            ))
        # Recalc total if items provided and total was 0
        if data.total_accrued == 0:
            bill.total_accrued = sum(it.amount for it in data.items)

    db.flush()
    return _get_user_bill(db, current_user.id, bill.id)


@router.get("/bills/{bill_id}", response_model=BillOut)
def get_bill(
    bill_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _get_user_bill(db, current_user.id, bill_id)


@router.patch("/bills/{bill_id}", response_model=BillOut)
def update_bill(
    bill_id: int,
    data: BillUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    bill = _get_user_bill(db, current_user.id, bill_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(bill, field, value)
    db.flush()
    return _get_user_bill(db, current_user.id, bill_id)


@router.delete("/bills/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(
    bill_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    bill = _get_user_bill(db, current_user.id, bill_id)
    db.delete(bill)


# ─── File upload ─────────────────────────────────────────

@router.post("/bills/{bill_id}/upload", response_model=BillOut)
async def upload_bill_file(
    bill_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    bill = _get_user_bill(db, current_user.id, bill_id)
    relative_path, file_type = await save_upload(file, subfolder=f"bills/{current_user.id}")
    bill.file_path = relative_path
    bill.file_type = file_type
    db.flush()
    return _get_user_bill(db, current_user.id, bill_id)


@router.post("/properties/{property_id}/bills/upload", response_model=BillOut, status_code=status.HTTP_201_CREATED)
async def create_bill_with_file(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
    provider: str = Form("МосОблЕИРЦ"),
    period_year: int = Form(...),
    period_month: int = Form(...),
    notes: Optional[str] = Form(None),
):
    """
    Create bill + upload file in one request.
    OCR/parsing will be added later — for now file is stored and bill is draft.
    """
    _get_user_property(db, current_user.id, property_id)
    seed_service_types(db)

    relative_path, file_type = await save_upload(file, subfolder=f"bills/{current_user.id}")

    bill = Bill(
        property_id=property_id,
        provider=provider,
        period_year=period_year,
        period_month=period_month,
        status="draft",
        file_path=relative_path,
        file_type=file_type,
        notes=notes,
    )
    db.add(bill)
    db.flush()
    return _get_user_bill(db, current_user.id, bill.id)


# ─── Bill items ──────────────────────────────────────────

@router.post("/bills/{bill_id}/items", response_model=BillItemOut, status_code=status.HTTP_201_CREATED)
def add_bill_item(
    bill_id: int,
    data: BillItemCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    bill = _get_user_bill(db, current_user.id, bill_id)
    item = BillItem(
        bill_id=bill.id,
        service_type_id=data.service_type_id,
        raw_name=data.raw_name,
        volume=data.volume,
        tariff=data.tariff,
        amount=data.amount,
    )
    db.add(item)
    # Update total
    bill.total_accrued = (bill.total_accrued or 0) + data.amount
    db.flush()
    db.refresh(item)
    return item


@router.delete("/bills/{bill_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill_item(
    bill_id: int,
    item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    bill = _get_user_bill(db, current_user.id, bill_id)
    item = next((i for i in bill.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Строка квитанции не найдена")
    bill.total_accrued = max(0, (bill.total_accrued or 0) - item.amount)
    db.delete(item)


# ─── Payments ────────────────────────────────────────────

@router.post("/bills/{bill_id}/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def add_payment(
    bill_id: int,
    data: PaymentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    bill = _get_user_bill(db, current_user.id, bill_id)
    payment = Payment(
        bill_id=bill.id,
        amount=data.amount,
        payment_date=data.payment_date,
        method=data.method,
        notes=data.notes,
    )
    db.add(payment)
    bill.total_paid = (bill.total_paid or 0) + data.amount
    if bill.total_paid >= bill.total_accrued and bill.total_accrued > 0:
        bill.status = "paid"
    db.flush()
    db.refresh(payment)
    return payment

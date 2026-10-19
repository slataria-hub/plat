from typing import Annotated, List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, and_
from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.models.bill import Tariff, Bill, BillItem, ServiceType
from app.schemas.tariff import (
    TariffCreate, TariffUpdate, TariffOut,
    TariffChange, TariffComparison,
    PeriodAmountComparison, BillsPeriodComparison,
)
from app.api.deps import get_current_user
from app.services.seed import seed_service_types

router = APIRouter(tags=["tariffs"])


def _get_user_property(db: Session, user_id: int, property_id: int) -> Property:
    prop = db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user_id)
    ).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Объект не найден")
    return prop


# ─── Tariffs CRUD ────────────────────────────────────────

@router.get("/properties/{property_id}/tariffs", response_model=List[TariffOut])
def list_tariffs(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service_code: Optional[str] = Query(None),
):
    _get_user_property(db, current_user.id, property_id)
    q = select(Tariff).where(Tariff.property_id == property_id)
    if service_code:
        q = q.where(Tariff.service_code == service_code)
    q = q.order_by(Tariff.service_code, desc(Tariff.start_date))
    return db.execute(q).scalars().all()


@router.post("/properties/{property_id}/tariffs", response_model=TariffOut, status_code=status.HTTP_201_CREATED)
def create_tariff(
    property_id: int,
    data: TariffCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if data.property_id != property_id:
        raise HTTPException(status_code=400, detail="property_id не совпадает")
    _get_user_property(db, current_user.id, property_id)

    t = Tariff(
        property_id=property_id,
        service_code=data.service_code,
        start_date=data.start_date,
        price_t1=data.price_t1,
        price_t2=data.price_t2,
        unit=data.unit,
    )
    db.add(t)
    db.flush()
    db.refresh(t)
    return t


@router.patch("/tariffs/{tariff_id}", response_model=TariffOut)
def update_tariff(
    tariff_id: int,
    data: TariffUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    t = db.execute(
        select(Tariff).join(Property).where(
            Tariff.id == tariff_id, Property.user_id == current_user.id
        )
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Тариф не найден")
    for f, v in data.model_dump(exclude_unset=True).items():
        setattr(t, f, v)
    db.flush()
    db.refresh(t)
    return t


@router.delete("/tariffs/{tariff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tariff(
    tariff_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    t = db.execute(
        select(Tariff).join(Property).where(
            Tariff.id == tariff_id, Property.user_id == current_user.id
        )
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Тариф не найден")
    db.delete(t)


# ─── Tariff changes detection ────────────────────────────

@router.get("/properties/{property_id}/tariffs/changes", response_model=TariffComparison)
def detect_tariff_changes(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    from_date: date = Query(...),
    to_date: date = Query(...),
):
    """
    Compare tariffs active at from_date vs to_date.
    Shows which services changed and by how much.
    """
    _get_user_property(db, current_user.id, property_id)
    seed_service_types(db)

    # Get all service codes for this property
    codes = db.execute(
        select(Tariff.service_code).where(Tariff.property_id == property_id).distinct()
    ).scalars().all()

    service_names = {
        s.code: s.name
        for s in db.execute(select(ServiceType)).scalars().all()
    }

    changes: List[TariffChange] = []

    for code in codes:
        # Tariff active at from_date (latest start_date <= from_date)
        old = db.execute(
            select(Tariff).where(
                Tariff.property_id == property_id,
                Tariff.service_code == code,
                Tariff.start_date <= from_date,
            ).order_by(desc(Tariff.start_date)).limit(1)
        ).scalar_one_or_none()

        new = db.execute(
            select(Tariff).where(
                Tariff.property_id == property_id,
                Tariff.service_code == code,
                Tariff.start_date <= to_date,
            ).order_by(desc(Tariff.start_date)).limit(1)
        ).scalar_one_or_none()

        if not old and not new:
            continue

        old_p1 = old.price_t1 if old else None
        new_p1 = new.price_t1 if new else None
        old_p2 = old.price_t2 if old else None
        new_p2 = new.price_t2 if new else None

        changed = (old_p1 != new_p1) or (old_p2 != new_p2)
        if not changed:
            continue

        delta = None
        delta_pct = None
        if old_p1 is not None and new_p1 is not None:
            delta = round(new_p1 - old_p1, 4)
            if old_p1 != 0:
                delta_pct = round((delta / old_p1) * 100, 2)

        changes.append(TariffChange(
            service_code=code,
            service_name=service_names.get(code),
            old_price_t1=old_p1,
            new_price_t1=new_p1,
            old_price_t2=old_p2,
            new_price_t2=new_p2,
            delta_t1=delta,
            delta_pct_t1=delta_pct,
            change_date=new.start_date if new else None,
        ))

    return TariffComparison(
        property_id=property_id,
        from_date=from_date,
        to_date=to_date,
        changes=changes,
        has_changes=len(changes) > 0,
    )


# ─── Bill amounts comparison between two periods ─────────

@router.get("/properties/{property_id}/bills/compare", response_model=BillsPeriodComparison)
def compare_bill_periods(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    prev_year: int = Query(...),
    prev_month: int = Query(..., ge=1, le=12),
    curr_year: int = Query(...),
    curr_month: int = Query(..., ge=1, le=12),
):
    """
    Compare accrued amounts by service between two months.
    Useful to see 'what changed and by how much' in the bill.
    """
    _get_user_property(db, current_user.id, property_id)
    seed_service_types(db)

    def _amounts(year: int, month: int) -> dict:
        bills = db.execute(
            select(Bill).where(
                Bill.property_id == property_id,
                Bill.period_year == year,
                Bill.period_month == month,
            )
        ).scalars().all()
        result = {}  # key: service_type_id or raw_name
        total = 0.0
        for b in bills:
            total += b.total_accrued or 0
            for item in b.items:
                key = item.service_type_id or item.raw_name or "other"
                result[key] = result.get(key, 0) + (item.amount or 0)
        return result, total

    prev_map, total_prev = _amounts(prev_year, prev_month)
    curr_map, total_curr = _amounts(curr_year, curr_month)

    service_names = {
        s.id: s.name for s in db.execute(select(ServiceType)).scalars().all()
    }
    service_codes = {
        s.id: s.code for s in db.execute(select(ServiceType)).scalars().all()
    }

    all_keys = set(prev_map.keys()) | set(curr_map.keys())
    items = []
    for key in sorted(all_keys, key=lambda k: str(k)):
        a_prev = prev_map.get(key, 0)
        a_curr = curr_map.get(key, 0)
        delta = round(a_curr - a_prev, 2)
        delta_pct = None
        if a_prev != 0:
            delta_pct = round((delta / a_prev) * 100, 2)

        name = None
        code = None
        if isinstance(key, int):
            name = service_names.get(key)
            code = service_codes.get(key)
        else:
            name = str(key)

        items.append(PeriodAmountComparison(
            service_code=code,
            service_name=name,
            amount_prev=round(a_prev, 2),
            amount_curr=round(a_curr, 2),
            delta=delta,
            delta_pct=delta_pct,
        ))

    total_delta = round(total_curr - total_prev, 2)
    total_delta_pct = None
    if total_prev != 0:
        total_delta_pct = round((total_delta / total_prev) * 100, 2)

    return BillsPeriodComparison(
        property_id=property_id,
        prev_year=prev_year,
        prev_month=prev_month,
        curr_year=curr_year,
        curr_month=curr_month,
        total_prev=round(total_prev, 2),
        total_curr=round(total_curr, 2),
        total_delta=total_delta,
        total_delta_pct=total_delta_pct,
        items=items,
    )

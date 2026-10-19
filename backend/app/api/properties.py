from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.models.user import User
from app.models.property import Property
from app.schemas.property import PropertyCreate, PropertyUpdate, PropertyOut
from app.api.deps import get_current_user

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=List[PropertyOut])
def list_properties(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    result = db.execute(
        select(Property).where(Property.user_id == current_user.id).order_by(Property.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=PropertyOut, status_code=status.HTTP_201_CREATED)
def create_property(
    data: PropertyCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    prop = Property(
        user_id=current_user.id,
        name=data.name,
        address=data.address,
        account_number=data.account_number,
    )
    db.add(prop)
    db.flush()
    db.refresh(prop)
    return prop


@router.get("/{property_id}", response_model=PropertyOut)
def get_property(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    prop = db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    ).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Объект не найден")
    return prop


@router.patch("/{property_id}", response_model=PropertyOut)
def update_property(
    property_id: int,
    data: PropertyUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    prop = db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    ).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Объект не найден")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prop, field, value)

    db.flush()
    db.refresh(prop)
    return prop


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    prop = db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    ).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Объект не найден")
    db.delete(prop)

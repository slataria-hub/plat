from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.bill import ServiceType

DEFAULT_SERVICES = [
    # Water
    {"code": "hvs", "name": "Холодная вода (ХВС)", "category": "water"},
    {"code": "gvs_carrier", "name": "ГВС — носитель", "category": "water"},
    {"code": "gvs_energy", "name": "ГВС — энергия", "category": "water"},
    {"code": "sewage", "name": "Стоки / водоотведение", "category": "water"},
    # Heat
    {"code": "heating", "name": "Отопление", "category": "heat"},
    # Electricity
    {"code": "electricity", "name": "Электроснабжение", "category": "electricity"},
    {"code": "electricity_day", "name": "Электроэнергия (день)", "category": "electricity"},
    {"code": "electricity_night", "name": "Электроэнергия (ночь)", "category": "electricity"},
    # Other
    {"code": "garbage", "name": "Обращение с ТКО (мусор)", "category": "other"},
    {"code": "capital_repair", "name": "Взнос на капитальный ремонт", "category": "other"},
    {"code": "maintenance", "name": "Содержание жилья / ЖКУ", "category": "other"},
    {"code": "other", "name": "Прочее", "category": "other"},
    {"code": "intercom", "name": "Запирающее устройство / домофон", "category": "other"},
    {"code": "security", "name": "Охрана", "category": "other"},
    {"code": "tv", "name": "Телевидение", "category": "other"},
    {"code": "insurance", "name": "Добровольное страхование", "category": "other"},
]


def seed_service_types(db: Session) -> int:
    """Insert default service types if table is empty. Returns count of inserted."""
    existing = db.execute(select(ServiceType).limit(1)).scalar_one_or_none()
    if existing:
        return 0

    for s in DEFAULT_SERVICES:
        db.add(ServiceType(**s))
    db.flush()
    return len(DEFAULT_SERVICES)

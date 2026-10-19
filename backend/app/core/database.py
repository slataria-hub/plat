from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from app.core.config import settings

# Backend root = folder that contains "app" package (…/meter-app/backend)
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT.mkdir(parents=True, exist_ok=True)

# Always use absolute path so SQLite works regardless of current working directory
_db_path = BACKEND_ROOT / "meterapp.db"
DATABASE_URL = f"sqlite:///{_db_path.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    # Import models so they register with metadata
    from app.models import (  # noqa: F401
        User, Property, Meter, MeterReading,
        ServiceType, Bill, BillItem, Payment, Tariff,
        PropertySettings, PeriodNote, UtilityAccount, PropertyShare,
    )
    Base.metadata.create_all(bind=engine)

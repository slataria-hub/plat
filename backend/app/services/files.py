import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.core.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
ALLOWED_CONTENT = {
    "image/jpeg", "image/png", "image/webp", "application/pdf"
}

# Absolute uploads dir next to backend root
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_ROOT = BACKEND_ROOT / "uploads"


def ensure_upload_dir() -> Path:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return UPLOAD_ROOT


async def save_upload(file: UploadFile, subfolder: str = "bills") -> tuple[str, str]:
    """
    Save uploaded file. Returns (relative_path, file_type).
    file_type is 'photo' or 'pdf'.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл без имени")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый формат. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. Максимум {settings.MAX_UPLOAD_SIZE_MB} МБ"
        )

    target_dir = ensure_upload_dir() / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}{ext}"
    full_path = target_dir / unique_name
    full_path.write_bytes(content)

    relative = f"{subfolder}/{unique_name}"
    file_type = "pdf" if ext == ".pdf" else "photo"
    return relative, file_type


def get_absolute_path(relative: str) -> Path:
    return UPLOAD_ROOT / relative

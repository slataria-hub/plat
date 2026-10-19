"""
OCR for meter displays (water / electricity).
Uses Tesseract with digits-focused config.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class MeterOcrResult:
    value_t1: Optional[float] = None
    value_t2: Optional[float] = None
    raw_text: str = ""
    candidates: list = None
    confidence: float = 0.0
    status: str = "pending"  # pending / done / failed
    message: str = ""

    def __post_init__(self):
        if self.candidates is None:
            self.candidates = []


def _ocr_digits(image_path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image, ImageOps, ImageFilter, ImageEnhance

        img = Image.open(image_path).convert("L")
        # enhance contrast for digit displays
        img = ImageOps.autocontrast(img)
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)

        # Try several configs
        texts = []
        for config in [
            "--psm 7 -c tessedit_char_whitelist=0123456789.,",
            "--psm 6 -c tessedit_char_whitelist=0123456789.,",
            "--psm 11",
            "--psm 6",
        ]:
            try:
                t = pytesseract.image_to_string(img, config=config)
                if t and t.strip():
                    texts.append(t)
            except Exception:
                pass
        return "\n".join(texts)
    except Exception as e:
        return ""


def _extract_numbers(text: str) -> list[float]:
    """Extract plausible meter readings from OCR text."""
    found = []
    # Common patterns: 1455, 1455.0, 01455, 9962.92
    for m in re.finditer(r"\d{3,7}(?:[.,]\d{1,3})?", text):
        s = m.group().replace(",", ".")
        try:
            v = float(s)
            # meter readings are typically 1..999999
            if 1 <= v <= 999999:
                found.append(v)
        except ValueError:
            pass
    # unique preserve order
    seen = set()
    out = []
    for v in found:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def recognize_meter_photo(file_path: str | Path, tariff_type: str = "single") -> dict:
    path = Path(file_path)
    result = MeterOcrResult()

    if not path.exists():
        result.status = "failed"
        result.message = "Файл не найден"
        return asdict(result)

    text = _ocr_digits(path)
    result.raw_text = text
    numbers = _extract_numbers(text)
    result.candidates = numbers

    if not numbers:
        result.status = "pending"
        result.message = "Цифры не распознаны — введите показания вручную"
        return asdict(result)

    if tariff_type == "day_night" and len(numbers) >= 2:
        # assume larger or first = day, second = night (heuristic)
        result.value_t1 = numbers[0]
        result.value_t2 = numbers[1]
        result.confidence = 0.6
        result.status = "done"
        result.message = f"Распознано: день {result.value_t1}, ночь {result.value_t2}"
    else:
        # pick the most likely reading: often the longest digit sequence
        best = max(numbers, key=lambda x: (len(str(int(x))), x))
        result.value_t1 = best
        result.confidence = 0.55 if len(numbers) == 1 else 0.4
        result.status = "done"
        result.message = f"Распознано: {best}" + (
            f" (варианты: {', '.join(str(n) for n in numbers[:5])})" if len(numbers) > 1 else ""
        )

    return asdict(result)

"""
OCR + parsing for utility bills (МосОблЕИРЦ and similar).

Pipeline:
1. PDF → images (pdf2image) or use image as-is
2. Tesseract OCR (rus+eng)
3. Rule-based extraction of period, totals, line items
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ─── Data structures ─────────────────────────────────────

@dataclass
class RecognizedItem:
    raw_name: str
    amount: Optional[float] = None
    volume: Optional[float] = None
    tariff: Optional[float] = None
    service_code: Optional[str] = None


@dataclass
class RecognizedBill:
    provider: Optional[str] = None
    period_year: Optional[int] = None
    period_month: Optional[int] = None
    total_accrued: Optional[float] = None
    items: list = field(default_factory=list)
    raw_text: Optional[str] = None
    confidence: float = 0.0
    status: str = "pending"  # pending / partial / done / failed
    message: str = ""


# ─── Service keyword map (МосОблЕИРЦ / ЕПД style) ────────

SERVICE_KEYWORDS = [
    # Order: more specific phrases first
    (["взнос на капитальн", "взнос на кр", "капремонт", "кап.ремонт", "капитальн"], "capital_repair"),
    (["обращение с тко", "тко", "мусор", "твёрдые коммунальн", "твердые коммунальн"], "garbage"),
    (["горячее в/с (энергия)", "горячее в/с энергия", "гвс - энергия", "гвс энергия", "гвс (энергия)"], "gvs_energy"),
    (["горячее в/с (носитель)", "горячее в/с носитель", "гвс - носитель", "гвс носитель", "гвс (носитель)", "теплоноситель"], "gvs_carrier"),
    (["холодное в/с", "холодная вода", "холодн. вода", "хол.вода", "хвс"], "hvs"),
    (["водоотведение", "сток", "стоки", "канализац"], "sewage"),
    (["отопление", "тепловая энергия", "теплоснабжение"], "heating"),
    (["электроснабжение", "электричество", "электроэнергия", "эл/снаб", "эл.энергия", "однотарифн"], "electricity"),
    (["содержание жилого", "содержание жилья", "содерж.жилья", "содержание"], "maintenance"),
    (["запирающ", "домофон"], "intercom"),
    (["охрана"], "security"),
    (["телевид", "антенн"], "tv"),
    (["добровольн", "страхован"], "insurance"),
    (["гвс", "горячее в/с", "горячая вода"], "gvs_energy"),  # fallback
]

MONTH_NAMES = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "мая": 5, "май": 5, "июн": 6,
    "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def match_service_code(raw_name: str) -> Optional[str]:
    name = (raw_name or "").lower().replace("ё", "е")
    for keywords, code in SERVICE_KEYWORDS:
        if any(k in name for k in keywords):
            return code
    return None


def _parse_amount(s: str) -> Optional[float]:
    """Parse Russian number formats: 1 234,56 / 1234.56 / 1234,56"""
    if not s:
        return None
    s = s.strip().replace("\xa0", " ").replace(" ", "").replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s in (".", "-"):
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


# ─── OCR engine ──────────────────────────────────────────

def _run_ocr_image(image_path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(image_path)
        # rus+eng for mixed bills
        text = pytesseract.image_to_string(img, lang="rus+eng")
        return text or ""
    except Exception as e:
        return f""


def _pdf_to_images(pdf_path: Path, out_dir: Path) -> list[Path]:
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), dpi=200, first_page=1, last_page=3)
        paths = []
        for i, img in enumerate(images):
            p = out_dir / f"page_{i}.png"
            img.save(str(p), "PNG")
            paths.append(p)
        return paths
    except Exception:
        return []


def extract_text(file_path: Path) -> str:
    """Extract text from image or PDF."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        tmp = file_path.parent / "_ocr_tmp"
        tmp.mkdir(exist_ok=True)
        pages = _pdf_to_images(file_path, tmp)
        texts = []
        for p in pages:
            texts.append(_run_ocr_image(p))
            try:
                p.unlink()
            except Exception:
                pass
        try:
            tmp.rmdir()
        except Exception:
            pass
        return "\n".join(texts)
    else:
        return _run_ocr_image(file_path)


# ─── Parsers ─────────────────────────────────────────────

def parse_period(text: str) -> tuple[Optional[int], Optional[int]]:
    """Extract year and month from bill text (ЕПД: ЗА август 2026 г.)."""
    year = None
    month = None
    lower = text.lower().replace("ё", "е")

    # "за август 2026" / "за август 2026 г" / "услуги за август 2026"
    m = re.search(
        r"(?:за|период)[:\s]+([а-яa-z]+)[ьи]?\s+(20[2-3]\d)",
        lower,
    )
    if not m:
        m = re.search(r"([а-яa-z]+)[ьи]?\s+(20[2-3]\d)\s*г", lower)
    if m:
        mon_str, y_str = m.group(1), m.group(2)
        year = int(y_str)
        for prefix, num in MONTH_NAMES.items():
            if mon_str.startswith(prefix) or prefix.startswith(mon_str[:3]):
                month = num
                break

    if not year:
        m = re.search(r"(20[2-3]\d)[-./](\d{1,2})", text)
        if m:
            year, month = int(m.group(1)), int(m.group(2))
        else:
            m = re.search(r"(\d{1,2})[-./](20[2-3]\d)", text)
            if m:
                month, year = int(m.group(1)), int(m.group(2))

    if not year:
        m = re.search(r"\b(20[2-3]\d)\b", text)
        if m:
            year = int(m.group(1))

    if month and not (1 <= month <= 12):
        month = None
    return year, month


def parse_provider(text: str) -> Optional[str]:
    lower = text.lower().replace("ё", "е")
    if "мособлеирц" in lower or "мособлеирп" in lower or "мос обл еир" in lower:
        return "МосОблЕИРЦ"
    if "техкомсервис" in lower:
        return "МосОблЕИРЦ"  # ЕПД идёт через ЕИРЦ, УК — Техкомсервис
    if "еирц" in lower or "еирп" in lower:
        return "МосОблЕИРЦ"
    if "теплосеть" in lower:
        return "Теплосеть"
    if "водоканал" in lower:
        return "Водоканал"
    if "единый платежный документ" in lower:
        return "МосОблЕИРЦ"
    m = re.search(r"(?:поставщик|получатель|ук)[:\s]+([А-Яа-яA-Za-z0-9\"«»\-\s]{3,40})", text, re.I)
    if m:
        return m.group(1).strip()[:80]
    return None


def parse_total(text: str) -> Optional[float]:
    """Prefer total WITHOUT voluntary insurance (основная сумма к оплате)."""
    patterns = [
        # "без учета добровольного страхования: 10 679,82"
        r"без\s+учета\s+добровольн[^\d]{0,40}?([0-9\s\xa0]+[.,]\d{2})",
        r"итого\s+к\s+оплате[^\d]{0,60}?без[^\d]{0,40}?([0-9\s\xa0]+[.,]\d{2})",
        # "10 679 руб. 82 коп"
        r"([0-9\s\xa0]+)\s*руб[.]?\s*(\d{1,2})\s*коп",
        # "Всего за август ... : 10 679,82"
        r"всего\s+за\s+[а-я]+\s+20\d\d[^\d]{0,80}?([0-9\s\xa0]+[.,]\d{2})",
        r"(?:итого\s*(?:к\s*оплате)?|всего\s*начислено|сумма\s*к\s*оплате)[:\s]*([0-9\s\xa0]+[.,]\d{2})",
        r"(?:итого|всего)[:\s]*([0-9\s\xa0]+[.,]\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I | re.DOTALL)
        if not m:
            continue
        if m.lastindex and m.lastindex >= 2:
            # руб + коп
            val = _parse_amount(f"{m.group(1)}.{m.group(2)}")
        else:
            val = _parse_amount(m.group(1))
        if val and val > 10:  # skip tiny false positives
            return val
    return None


def parse_line_items(text: str) -> list[RecognizedItem]:
    """
    Extract service lines from ЕПД table-like text.
    Prefers individual services over ОДН when both exist.
    """
    items: list[RecognizedItem] = []
    seen_codes: set[str] = set()
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) >= 4]

    def process_line(line_clean: str, want_odn: bool) -> Optional[RecognizedItem]:
        is_odn = bool(re.search(r"\bодн\b", line_clean.lower()))
        if want_odn != is_odn:
            return None

        lc = line_clean.replace("\xa0", " ").replace("\u202f", " ")
        # Exactly 2 decimal places — currency, not volumes like 11.581640
        money = re.findall(r"(\d{1,3}(?:[ ]\d{3})*[.,]\d{2})(?!\d)", lc)
        if not money:
            return None

        amount = None
        for m in reversed(money):
            val = _parse_amount(m)
            if val is not None and val >= 1:
                amount = val
                break
        if amount is None:
            return None

        name_part = re.split(r"\d", line_clean)[0].strip(" .-–—\t·•")
        if len(name_part) < 2:
            name_part = re.sub(r"[\d\s.,]+$", "", line_clean).strip(" .-–—")[:80]

        code = match_service_code(name_part or line_clean)
        if code and code in seen_codes and not is_odn:
            return None
        if code and not is_odn:
            seen_codes.add(code)

        volume = tariff = None
        # volume + unit + tariff + amount
        vol_m = re.search(
            r"(\d+[.,]\d+)\s*(?:куб|кв|кВт|квт|Гкал|гкал|абонент)?[^\d]{0,15}?"
            r"(\d+[.,]\d{2,4})\s+(\d{1,3}(?:[ ]\d{3})*[.,]\d{2})",
            lc,
            re.I,
        )
        if vol_m:
            volume = _parse_amount(vol_m.group(1))
            tariff = _parse_amount(vol_m.group(2))
        elif len(money) >= 2:
            tariff = _parse_amount(money[-2])

        display_name = name_part or line_clean[:60]
        if is_odn and "одн" not in display_name.lower():
            display_name = f"{display_name} ОДН"

        return RecognizedItem(
            raw_name=display_name,
            amount=amount,
            volume=volume,
            tariff=tariff,
            service_code=code,
        )

    for line in lines:
        it = process_line(line, want_odn=False)
        if it:
            items.append(it)
    for line in lines:
        it = process_line(line, want_odn=True)
        if it:
            items.append(it)

    matched = [i for i in items if i.service_code]
    return (matched if matched else items)[:20]


def parse_bill_text(text: str) -> RecognizedBill:
    result = RecognizedBill(raw_text=text)
    if not text or len(text.strip()) < 10:
        result.status = "failed"
        result.message = "Не удалось извлечь текст из файла"
        return result

    year, month = parse_period(text)
    result.period_year = year
    result.period_month = month
    result.provider = parse_provider(text) or "МосОблЕИРЦ"
    result.total_accrued = parse_total(text)
    result.items = [asdict(i) if not isinstance(i, dict) else i for i in parse_line_items(text)]
    # convert items properly
    parsed_items = parse_line_items(text)
    result.items = [
        {
            "raw_name": i.raw_name,
            "amount": i.amount,
            "volume": i.volume,
            "tariff": i.tariff,
            "service_code": i.service_code,
        }
        for i in parsed_items
    ]

    score = 0.0
    if result.provider:
        score += 0.2
    if result.period_year:
        score += 0.2
    if result.period_month:
        score += 0.15
    if result.total_accrued:
        score += 0.2
    if result.items:
        score += min(0.25, 0.05 * len(result.items))
    result.confidence = round(score, 2)

    if score >= 0.5:
        result.status = "done"
        result.message = f"Распознано: {len(result.items)} услуг, уверенность {int(score*100)}%"
    elif score >= 0.2:
        result.status = "partial"
        result.message = "Частично распознано — проверьте и дополните поля"
    else:
        result.status = "partial"
        result.message = "Текст извлечён, автоматический разбор слабый — заполните вручную"

    return result


def recognize_bill_file(file_path: str | Path) -> dict:
    path = Path(file_path)
    result = RecognizedBill()

    if not path.exists():
        result.status = "failed"
        result.message = "Файл не найден"
        return asdict(result)

    try:
        text = extract_text(path)
    except Exception as e:
        result.status = "failed"
        result.message = f"Ошибка OCR: {e}"
        return asdict(result)

    if not text.strip():
        result.status = "pending"
        result.message = (
            "Не удалось прочитать текст с файла. "
            "Проверьте качество фото или заполните поля вручную."
        )
        result.raw_text = ""
        return asdict(result)

    parsed = parse_bill_text(text)
    return asdict(parsed)


def recognize_from_text(text: str) -> dict:
    """Parse already known text (e.g. pasted by user)."""
    return asdict(parse_bill_text(text))

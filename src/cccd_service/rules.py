import re
import unicodedata
from datetime import date, datetime

from .ocr import OcrLine
from .schemas import ClaimedIdentity, DocumentSide, ExtractedIdentity

_DATE_PATTERN = re.compile(r"(?<!\d)([0-3]?\d)[/.-]([01]?\d)[/.-](\d{4})(?!\d)")
_ID_PATTERN = re.compile(r"(?<!\d)(?:\d[\s.]*){12}(?!\d)")

_FRONT_ANCHORS = (
    "CAN CUOC",
    "CONG HOA XA HOI CHU NGHIA VIET NAM",
    "HO VA TEN",
    "NGAY SINH",
    "QUOC TICH",
    "CO GIA TRI DEN",
)
_BACK_ANCHORS = (
    "DAC DIEM NHAN DANG",
    "NGAY THANG NAM CAP",
    "BO CONG AN",
    "VAN TAY",
    "NGON TRO",
    "IDENTIFICATION FEATURES",
)
_LABELS = (
    *_FRONT_ANCHORS,
    *_BACK_ANCHORS,
    "GIOI TINH",
    "QUE QUAN",
    "NOI THUONG TRU",
    "DATE OF BIRTH",
    "FULL NAME",
    "NATIONALITY",
    "PLACE OF ORIGIN",
    "PLACE OF RESIDENCE",
    "DATE OF EXPIRY",
)


def fold_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_marks.replace("Đ", "D").replace("đ", "d")).strip().upper()


def detect_side(lines: list[OcrLine], qr_value: str | None = None) -> DocumentSide:
    text = " ".join(fold_text(line.text) for line in lines)
    front_score = sum(anchor in text for anchor in _FRONT_ANCHORS) + (3 if qr_value else 0)
    back_score = sum(anchor in text for anchor in _BACK_ANCHORS)
    if front_score >= 2 and front_score > back_score:
        return DocumentSide.FRONT
    if back_score >= 2 and back_score > front_score:
        return DocumentSide.BACK
    return DocumentSide.UNKNOWN


def extract_ocr_identity(
    front_lines: list[OcrLine],
    back_lines: list[OcrLine],
) -> ExtractedIdentity:
    return ExtractedIdentity(
        id_number=_extract_id(front_lines),
        full_name=_extract_name(front_lines),
        date_of_birth=_date_near(front_lines, ("NGAY SINH", "DATE OF BIRTH")),
        gender=_extract_gender(front_lines),
        nationality=_extract_nationality(front_lines),
        place_of_origin=_text_near(front_lines, ("QUE QUAN", "PLACE OF ORIGIN")),
        place_of_residence=_text_near(front_lines, ("NOI THUONG TRU", "PLACE OF RESIDENCE"), 2),
        expiry_date=_date_near(front_lines, ("CO GIA TRI DEN", "DATE OF EXPIRY")),
        issue_date=_date_near(back_lines, ("NGAY THANG NAM CAP", "DATE OF ISSUE")),
    )


def parse_qr_identity(value: str | None) -> ExtractedIdentity | None:
    if not value:
        return None
    parts = [part.strip() for part in value.split("|")]
    if len(parts) < 6:
        return None

    id_number = re.sub(r"\D", "", parts[0])
    if len(id_number) != 12:
        return None
    return ExtractedIdentity(
        id_number=id_number,
        full_name=parts[2] or None,
        date_of_birth=_parse_date(parts[3]),
        gender=_normalize_gender(parts[4]),
        place_of_residence=parts[5] or None,
        issue_date=_parse_date(parts[6]) if len(parts) > 6 else None,
    )


def merge_identities(
    ocr_identity: ExtractedIdentity,
    qr_identity: ExtractedIdentity | None,
) -> ExtractedIdentity:
    if qr_identity is None:
        return ocr_identity
    values = ocr_identity.model_dump()
    for field, value in qr_identity.model_dump().items():
        if values.get(field) is None and value is not None:
            values[field] = value
    return ExtractedIdentity(**values)


def compare_qr_with_ocr(
    qr_identity: ExtractedIdentity | None,
    ocr_identity: ExtractedIdentity,
) -> bool | None:
    if qr_identity is None:
        return None
    comparisons: list[bool] = []
    if qr_identity.id_number and ocr_identity.id_number:
        comparisons.append(qr_identity.id_number == ocr_identity.id_number)
    if qr_identity.full_name and ocr_identity.full_name:
        comparisons.append(
            _normalize_name(qr_identity.full_name) == _normalize_name(ocr_identity.full_name)
        )
    if qr_identity.date_of_birth and ocr_identity.date_of_birth:
        comparisons.append(qr_identity.date_of_birth == ocr_identity.date_of_birth)
    if qr_identity.gender and ocr_identity.gender:
        comparisons.append(
            _normalize_gender(qr_identity.gender) == _normalize_gender(ocr_identity.gender)
        )
    return all(comparisons) if comparisons else None


def compare_with_claimed(
    extracted: ExtractedIdentity,
    claimed: ClaimedIdentity | None,
) -> bool | None:
    if claimed is None or not any((claimed.full_name, claimed.date_of_birth, claimed.gender)):
        return None

    comparisons: list[bool] = []
    if claimed.full_name:
        comparisons.append(
            bool(extracted.full_name)
            and _normalize_name(claimed.full_name) == _normalize_name(extracted.full_name)
        )
    if claimed.date_of_birth:
        comparisons.append(claimed.date_of_birth == extracted.date_of_birth)
    if claimed.gender:
        comparisons.append(
            bool(extracted.gender)
            and _normalize_gender(claimed.gender) == _normalize_gender(extracted.gender)
        )
    return all(comparisons)


def has_required_fields(identity: ExtractedIdentity) -> bool:
    return bool(identity.id_number and identity.full_name and identity.date_of_birth)


def validate_identity_rules(identity: ExtractedIdentity) -> list[str]:
    """Kiểm tra quy tắc cấu trúc CCCD, không thay thế xác thực với cơ quan phát hành."""
    id_number = identity.id_number or ""
    if not re.fullmatch(r"\d{12}", id_number):
        return ["ID_FORMAT_INVALID"]

    reasons: list[str] = []
    century_gender_code = int(id_number[3])
    if identity.date_of_birth:
        if identity.date_of_birth > date.today():
            reasons.append("DATE_OF_BIRTH_IN_FUTURE")
        if id_number[4:6] != f"{identity.date_of_birth.year % 100:02d}":
            reasons.append("ID_BIRTH_YEAR_MISMATCH")

        century_code = (identity.date_of_birth.year // 100 - 19) * 2
        if century_code not in range(0, 10) or century_gender_code not in {
            century_code,
            century_code + 1,
        }:
            reasons.append("ID_BIRTH_CENTURY_MISMATCH")

    normalized_gender = _normalize_gender(identity.gender)
    if normalized_gender in {"male", "female"}:
        expected_parity = 0 if normalized_gender == "male" else 1
        if century_gender_code % 2 != expected_parity:
            reasons.append("ID_GENDER_MISMATCH")

    if identity.issue_date and identity.issue_date > date.today():
        reasons.append("ISSUE_DATE_IN_FUTURE")
    if identity.issue_date and identity.expiry_date and identity.expiry_date < identity.issue_date:
        reasons.append("EXPIRY_BEFORE_ISSUE")
    return reasons


def _extract_id(lines: list[OcrLine]) -> str | None:
    for line in lines:
        for match in _ID_PATTERN.findall(line.text):
            value = re.sub(r"\D", "", match)
            if len(value) == 12:
                return value
    return None


def _extract_name(lines: list[OcrLine]) -> str | None:
    value = _text_near(lines, ("HO VA TEN", "FULL NAME"))
    if not value:
        return None
    value = re.sub(r"[^A-Za-zÀ-ỹĐđ\s'-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -'")
    return value or None


def _extract_gender(lines: list[OcrLine]) -> str | None:
    for index, line in enumerate(lines):
        folded = fold_text(line.text)
        if "GIOI TINH" not in folded and "SEX" not in folded:
            continue
        nearby = " ".join(fold_text(item.text) for item in lines[index : index + 2])
        match = re.search(r"(?:GIOI TINH|SEX).*?\b(NAM|NU|MALE|FEMALE)\b", nearby)
        if match:
            return _normalize_gender(match.group(1))
    return None


def _extract_nationality(lines: list[OcrLine]) -> str | None:
    for index, line in enumerate(lines):
        folded = fold_text(line.text)
        if "QUOC TICH" not in folded and "NATIONALITY" not in folded:
            continue
        nearby = " ".join(fold_text(item.text) for item in lines[index : index + 2])
        if "VIET NAM" in nearby:
            return "Việt Nam"
        return _inline_or_next(lines, index)
    return None


def _date_near(lines: list[OcrLine], labels: tuple[str, ...]) -> date | None:
    for index, line in enumerate(lines):
        if not any(label in fold_text(line.text) for label in labels):
            continue
        for candidate in lines[index : index + 3]:
            parsed = _parse_date(candidate.text)
            if parsed:
                return parsed
    return None


def _text_near(lines: list[OcrLine], labels: tuple[str, ...], next_lines: int = 1) -> str | None:
    for index, line in enumerate(lines):
        if not any(label in fold_text(line.text) for label in labels):
            continue
        inline = _inline_value(line.text)
        if inline:
            return inline
        values: list[str] = []
        for candidate in lines[index + 1 : index + 1 + next_lines]:
            if _is_label(candidate.text):
                break
            values.append(candidate.text.strip())
        value = " ".join(values).strip()
        if value:
            return value
    return None


def _inline_or_next(lines: list[OcrLine], index: int) -> str | None:
    inline = _inline_value(lines[index].text)
    if inline:
        return inline
    if index + 1 < len(lines) and not _is_label(lines[index + 1].text):
        return lines[index + 1].text.strip() or None
    return None


def _inline_value(value: str) -> str | None:
    if ":" not in value:
        return None
    tail = value.rsplit(":", 1)[1].strip()
    return tail or None


def _is_label(value: str) -> bool:
    folded = fold_text(value)
    return any(label in folded for label in _LABELS)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    match = _DATE_PATTERN.search(value)
    if match:
        parts = match.groups()
    else:
        digits = re.sub(r"\D", "", value)
        if len(digits) != 8:
            return None
        parts = (digits[:2], digits[2:4], digits[4:])
    try:
        return datetime(int(parts[2]), int(parts[1]), int(parts[0])).date()
    except ValueError:
        return None


def _normalize_name(value: str) -> str:
    return re.sub(r"[^A-Z ]", "", fold_text(value))


def _normalize_gender(value: str | None) -> str | None:
    folded = fold_text(value)
    if folded in {"NAM", "MALE", "M"}:
        return "male"
    if folded in {"NU", "FEMALE", "F"}:
        return "female"
    return folded.lower() or None

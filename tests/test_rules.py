from datetime import date

from cccd_service.ocr import OcrLine
from cccd_service.rules import (
    compare_qr_with_ocr,
    compare_with_claimed,
    detect_side,
    extract_ocr_identity,
    parse_qr_identity,
    validate_identity_rules,
)
from cccd_service.schemas import ClaimedIdentity, DocumentSide


def line(text: str, y: int) -> OcrLine:
    return OcrLine(text=text, confidence=0.95, box=(10, y, 500, y + 20))


def test_extract_and_cross_check_cccd_fields():
    front = [
        line("CĂN CƯỚC CÔNG DÂN", 10),
        line("Số / No: 079204001234", 30),
        line("Họ và tên / Full name:", 50),
        line("NGUYỄN VĂN AN", 70),
        line("Ngày sinh / Date of birth: 01/02/2004", 90),
        line("Giới tính / Sex: Nam", 110),
        line("Quốc tịch / Nationality: Việt Nam", 130),
        line("Nơi thường trú / Place of residence:", 150),
        line("Quận 1, Thành phố Hồ Chí Minh", 170),
    ]
    back = [
        line("ĐẶC ĐIỂM NHẬN DẠNG", 10),
        line("Ngày, tháng, năm cấp / Date of issue: 10/08/2021", 30),
        line("BỘ CÔNG AN", 50),
    ]
    qr = "079204001234|123456789|NGUYEN VAN AN|01022004|Nam|Quan 1, TP HCM|10082021"

    assert detect_side(front, qr) is DocumentSide.FRONT
    assert detect_side(back) is DocumentSide.BACK

    ocr_identity = extract_ocr_identity(front, back)
    qr_identity = parse_qr_identity(qr)
    assert ocr_identity.id_number == "079204001234"
    assert ocr_identity.full_name == "NGUYỄN VĂN AN"
    assert ocr_identity.date_of_birth == date(2004, 2, 1)
    assert ocr_identity.gender == "male"
    assert ocr_identity.issue_date == date(2021, 8, 10)
    assert compare_qr_with_ocr(qr_identity, ocr_identity) is True
    assert validate_identity_rules(ocr_identity) == []
    assert (
        compare_with_claimed(
            ocr_identity,
            ClaimedIdentity(
                full_name="Nguyễn Văn An",
                date_of_birth=date(2004, 2, 1),
                gender="male",
            ),
        )
        is True
    )


def test_rejects_invalid_qr_format():
    assert parse_qr_identity("not-an-id|missing-fields") is None


def test_detects_id_birth_year_mismatch():
    identity = parse_qr_identity(
        "079299001234|123456789|NGUYEN VAN AN|01022004|Nam|Quan 1|10082021"
    )

    assert identity is not None
    assert "ID_BIRTH_YEAR_MISMATCH" in validate_identity_rules(identity)

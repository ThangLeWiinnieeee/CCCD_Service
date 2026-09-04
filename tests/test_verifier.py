from datetime import date

import numpy as np

import cccd_service.verifier as verifier
from cccd_service.ocr import OcrLine
from cccd_service.schemas import ClaimedIdentity, Decision, ImageQuality
from cccd_service.vision import AnalyzedImage


def _line(text: str, y: int) -> OcrLine:
    return OcrLine(text=text, confidence=0.95, box=(10, y, 500, y + 20))


def test_verifier_returns_pass_for_consistent_document(monkeypatch):
    front_image = np.ones((638, 1010, 3), dtype=np.uint8)
    back_image = np.full((638, 1010, 3), 2, dtype=np.uint8)
    quality = ImageQuality(
        width=1010,
        height=638,
        blur_score=120,
        brightness=120,
        glare_ratio=0.01,
        document_detected=True,
        acceptable=True,
    )

    analyses = iter(
        [
            AnalyzedImage(front_image, front_image, quality),
            AnalyzedImage(back_image, back_image, quality),
        ]
    )
    front_lines = [
        _line("CĂN CƯỚC CÔNG DÂN", 10),
        _line("Số / No: 079204001234", 30),
        _line("Họ và tên / Full name:", 50),
        _line("NGUYỄN VĂN AN", 70),
        _line("Ngày sinh / Date of birth: 01/02/2004", 90),
        _line("Giới tính / Sex: Nam", 110),
    ]
    back_lines = [
        _line("ĐẶC ĐIỂM NHẬN DẠNG", 10),
        _line("Ngày, tháng, năm cấp: 10/08/2021", 30),
        _line("BỘ CÔNG AN", 50),
    ]
    ocr_results = iter([front_lines, back_lines])

    monkeypatch.setattr(verifier, "analyze_image", lambda *_: next(analyses))
    monkeypatch.setattr(verifier, "recognize_text", lambda *_: next(ocr_results))
    monkeypatch.setattr(
        verifier,
        "decode_qr",
        lambda *_: "079204001234|123456789|NGUYEN VAN AN|01022004|Nam|Quan 1|10082021",
    )

    result = verifier.verify_cccd(
        b"front",
        b"back",
        ClaimedIdentity(
            full_name="Nguyễn Văn An",
            date_of_birth=date(2004, 2, 1),
            gender="male",
        ),
    )

    assert result.decision is Decision.PASS
    assert result.extracted.id_number == "079204001234"
    assert result.checks.qr_ocr_match is True
    assert result.checks.profile_match is True

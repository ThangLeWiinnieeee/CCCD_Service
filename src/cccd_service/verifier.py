from .config import get_settings
from .ocr import mean_confidence, recognize_text
from .rules import (
    compare_qr_with_ocr,
    compare_with_claimed,
    detect_side,
    extract_ocr_identity,
    has_required_fields,
    merge_identities,
    parse_qr_identity,
    validate_identity_rules,
)
from .schemas import (
    ClaimedIdentity,
    Decision,
    DocumentSide,
    ExtractedIdentity,
    VerificationChecks,
    VerificationResult,
)
from .vision import analyze_image, decode_qr


def verify_cccd(
    front: bytes,
    back: bytes,
    claimed: ClaimedIdentity | None = None,
) -> VerificationResult:
    settings = get_settings()
    front_image = analyze_image(front, settings)
    back_image = analyze_image(back, settings)

    quality_reasons = [
        *(f"FRONT_{reason}" for reason in front_image.quality.reasons),
        *(f"BACK_{reason}" for reason in back_image.quality.reasons),
    ]
    if quality_reasons:
        return _result(
            decision=Decision.RETAKE,
            extracted=ExtractedIdentity(),
            front_quality=front_image.quality,
            back_quality=back_image.quality,
            reasons=quality_reasons,
        )

    front_lines = recognize_text(front_image.document)
    back_lines = recognize_text(back_image.document)
    qr_value = decode_qr(front_image.document, front_image.original)
    front_side = detect_side(front_lines, qr_value)
    back_side = detect_side(back_lines)

    ocr_identity = extract_ocr_identity(front_lines, back_lines)
    qr_identity = parse_qr_identity(qr_value)
    extracted = merge_identities(ocr_identity, qr_identity)
    front_confidence = mean_confidence(front_lines)
    back_confidence = mean_confidence(back_lines)
    qr_ocr_match = compare_qr_with_ocr(qr_identity, ocr_identity)
    profile_match = compare_with_claimed(extracted, claimed)
    required_fields_present = has_required_fields(extracted)
    identity_rule_reasons = validate_identity_rules(extracted)

    reasons: list[str] = []
    if front_side is not DocumentSide.FRONT:
        reasons.append("FRONT_SIDE_NOT_DETECTED")
    if back_side is not DocumentSide.BACK:
        reasons.append("BACK_SIDE_NOT_DETECTED")
    if not required_fields_present:
        reasons.append("REQUIRED_FIELDS_MISSING")
    if not front_lines or not back_lines:
        reasons.append("OCR_TEXT_NOT_FOUND")
    if not qr_value:
        reasons.append("QR_NOT_DECODED")
    elif qr_identity is None:
        reasons.append("QR_FORMAT_UNSUPPORTED")
    if qr_ocr_match is False:
        reasons.append("QR_OCR_MISMATCH")
    if profile_match is False:
        reasons.append("PROFILE_MISMATCH")
    reasons.extend(identity_rule_reasons)

    retake_reasons = {
        "FRONT_SIDE_NOT_DETECTED",
        "BACK_SIDE_NOT_DETECTED",
        "REQUIRED_FIELDS_MISSING",
        "OCR_TEXT_NOT_FOUND",
    }
    if any(reason in retake_reasons for reason in reasons):
        decision = Decision.RETAKE
    elif qr_ocr_match is False or identity_rule_reasons:
        decision = Decision.SUSPICIOUS
    elif profile_match is False or qr_identity is None:
        decision = Decision.REVIEW
    else:
        decision = Decision.PASS

    checks = VerificationChecks(
        front_quality=front_image.quality,
        back_quality=back_image.quality,
        front_detected=front_side is DocumentSide.FRONT,
        back_detected=back_side is DocumentSide.BACK,
        front_ocr_confidence=front_confidence,
        back_ocr_confidence=back_confidence,
        qr_decoded=bool(qr_value),
        qr_ocr_match=qr_ocr_match,
        profile_match=profile_match,
        required_fields_present=required_fields_present,
        identity_rules_valid=not identity_rule_reasons,
    )
    return VerificationResult(
        decision=decision,
        document_type="vn_cccd" if checks.front_detected and checks.back_detected else None,
        extracted=extracted,
        checks=checks,
        reasons=reasons,
        model_version=settings.model_version,
    )


def _result(
    *,
    decision: Decision,
    extracted: ExtractedIdentity,
    front_quality,
    back_quality,
    reasons: list[str],
) -> VerificationResult:
    return VerificationResult(
        decision=decision,
        extracted=extracted,
        checks=VerificationChecks(
            front_quality=front_quality,
            back_quality=back_quality,
            front_detected=False,
            back_detected=False,
            front_ocr_confidence=0.0,
            back_ocr_confidence=0.0,
            qr_decoded=False,
            required_fields_present=False,
            identity_rules_valid=False,
        ),
        reasons=reasons,
        model_version=get_settings().model_version,
    )

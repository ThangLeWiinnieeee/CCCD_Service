from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Decision(StrEnum):
    PASS = "pass"
    RETAKE = "retake"
    REVIEW = "review"
    SUSPICIOUS = "suspicious"


class DocumentSide(StrEnum):
    FRONT = "front"
    BACK = "back"
    UNKNOWN = "unknown"


class ClaimedIdentity(ApiModel):
    full_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=20)


class ExtractedIdentity(ApiModel):
    id_number: str | None = None
    full_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    nationality: str | None = None
    place_of_origin: str | None = None
    place_of_residence: str | None = None
    expiry_date: date | None = None
    issue_date: date | None = None


class ImageQuality(ApiModel):
    width: int
    height: int
    blur_score: float
    brightness: float
    glare_ratio: float
    document_detected: bool
    acceptable: bool
    reasons: list[str] = Field(default_factory=list)


class VerificationChecks(ApiModel):
    front_quality: ImageQuality
    back_quality: ImageQuality
    front_detected: bool
    back_detected: bool
    front_ocr_confidence: float
    back_ocr_confidence: float
    qr_decoded: bool
    qr_ocr_match: bool | None = None
    profile_match: bool | None = None
    required_fields_present: bool
    identity_rules_valid: bool


class VerificationResult(ApiModel):
    decision: Decision
    document_type: str | None = None
    extracted: ExtractedIdentity
    checks: VerificationChecks
    reasons: list[str] = Field(default_factory=list)
    model_version: str

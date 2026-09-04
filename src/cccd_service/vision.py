from dataclasses import dataclass

import cv2
import numpy as np

from .config import Settings, get_settings
from .schemas import ImageQuality


@dataclass(frozen=True)
class AnalyzedImage:
    original: np.ndarray
    document: np.ndarray
    quality: ImageQuality


def decode_image(data: bytes, settings: Settings | None = None) -> np.ndarray:
    settings = settings or get_settings()
    if not data or len(data) > settings.max_image_bytes:
        raise ValueError("Ảnh trống hoặc vượt quá dung lượng cho phép")

    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Không đọc được định dạng ảnh")

    height, width = image.shape[:2]
    if width * height > settings.max_image_pixels:
        raise ValueError("Độ phân giải ảnh vượt quá giới hạn cho phép")
    return image


def analyze_image(data: bytes, settings: Settings | None = None) -> AnalyzedImage:
    settings = settings or get_settings()
    image = decode_image(data, settings)
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    glare_ratio = float(np.count_nonzero(gray >= 245) / gray.size)

    document = _find_and_warp_document(image)
    document_detected = document is not None
    if document is None and _looks_like_cropped_card(width, height):
        document = _normalize_landscape(image)
        document_detected = True
    elif document is None:
        document = _normalize_landscape(image)

    reasons: list[str] = []
    if width < settings.min_image_width or height < settings.min_image_height:
        reasons.append("TOO_SMALL")
    if blur_score < settings.min_blur_score:
        reasons.append("BLURRY")
    if brightness < settings.min_brightness:
        reasons.append("TOO_DARK")
    elif brightness > settings.max_brightness:
        reasons.append("TOO_BRIGHT")
    if glare_ratio > settings.max_glare_ratio:
        reasons.append("TOO_MUCH_GLARE")
    if not document_detected:
        reasons.append("DOCUMENT_NOT_FOUND")

    quality = ImageQuality(
        width=width,
        height=height,
        blur_score=round(blur_score, 2),
        brightness=round(brightness, 2),
        glare_ratio=round(glare_ratio, 4),
        document_detected=document_detected,
        acceptable=not reasons,
        reasons=reasons,
    )
    return AnalyzedImage(original=image, document=document, quality=quality)


def decode_qr(*images: np.ndarray) -> str | None:
    detector = cv2.QRCodeDetector()
    for image in images:
        for candidate in (image, cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)):
            value, _, _ = detector.detectAndDecode(candidate)
            value = value.strip().replace("\x00", "")
            if value:
                return value[:4096]
    return None


def _find_and_warp_document(image: np.ndarray) -> np.ndarray | None:
    height, width = image.shape[:2]
    scale = min(1.0, 1600 / max(height, width))
    working = cv2.resize(image, None, fx=scale, fy=scale) if scale < 1 else image.copy()
    gray = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 60, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    min_area = working.shape[0] * working.shape[1] * 0.20
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:12]:
        if cv2.contourArea(contour) < min_area:
            break
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        points = polygon.reshape(4, 2).astype(np.float32) / scale
        warped = _warp(image, points)
        warped_height, warped_width = warped.shape[:2]
        ratio = max(warped_width, warped_height) / max(1, min(warped_width, warped_height))
        if 1.35 <= ratio <= 1.85:
            return _normalize_landscape(warped)
    return None


def _warp(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    ordered = _order_points(points)
    top_left, top_right, bottom_right, bottom_left = ordered
    width = int(
        max(np.linalg.norm(bottom_right - bottom_left), np.linalg.norm(top_right - top_left))
    )
    height = int(
        max(np.linalg.norm(top_right - bottom_right), np.linalg.norm(top_left - bottom_left))
    )
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(ordered, destination)
    return cv2.warpPerspective(image, matrix, (max(width, 1), max(height, 1)))


def _order_points(points: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype=np.float32)
    coordinate_sum = points.sum(axis=1)
    coordinate_diff = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(coordinate_sum)]
    ordered[2] = points[np.argmax(coordinate_sum)]
    ordered[1] = points[np.argmin(coordinate_diff)]
    ordered[3] = points[np.argmax(coordinate_diff)]
    return ordered


def _looks_like_cropped_card(width: int, height: int) -> bool:
    ratio = max(width, height) / max(1, min(width, height))
    return 1.35 <= ratio <= 1.85


def _normalize_landscape(image: np.ndarray) -> np.ndarray:
    if image.shape[0] > image.shape[1]:
        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    width = 1280
    height = max(1, round(image.shape[0] * width / image.shape[1]))
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)

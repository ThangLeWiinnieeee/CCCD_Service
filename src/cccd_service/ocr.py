from dataclasses import dataclass
from functools import lru_cache
from threading import Lock

import numpy as np

from .config import get_settings


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    box: tuple[int, int, int, int]


_OCR_LOCK = Lock()


@lru_cache(maxsize=1)
def get_ocr_engine():
    from paddleocr import PaddleOCR

    settings = get_settings()
    return PaddleOCR(
        lang=settings.ocr_language,
        ocr_version=settings.ocr_version,
        device=settings.ocr_device,
        cpu_threads=settings.ocr_cpu_threads,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def recognize_text(image: np.ndarray) -> list[OcrLine]:
    settings = get_settings()
    with _OCR_LOCK:
        results = get_ocr_engine().predict(
            input=image,
            text_rec_score_thresh=settings.min_ocr_confidence,
        )

    lines: list[OcrLine] = []
    for result in results:
        payload = result.json
        if callable(payload):
            payload = payload()
        data = payload.get("res", payload)
        texts = data.get("rec_texts", [])
        scores = data.get("rec_scores", [])
        boxes = data.get("rec_boxes", [])
        for index, text in enumerate(texts):
            clean_text = str(text).strip()
            if not clean_text:
                continue
            score = float(scores[index]) if index < len(scores) else 0.0
            box = _box_tuple(boxes[index]) if index < len(boxes) else (0, index, 0, index)
            lines.append(OcrLine(clean_text, score, box))
    return sorted(lines, key=lambda line: (line.box[1], line.box[0]))


def mean_confidence(lines: list[OcrLine]) -> float:
    if not lines:
        return 0.0
    return round(sum(line.confidence for line in lines) / len(lines), 4)


def _box_tuple(box) -> tuple[int, int, int, int]:
    values = box.tolist() if hasattr(box, "tolist") else list(box)
    if len(values) == 4 and not isinstance(values[0], list):
        return tuple(int(value) for value in values)
    array = np.asarray(values).reshape(-1, 2)
    return (
        int(array[:, 0].min()),
        int(array[:, 1].min()),
        int(array[:, 0].max()),
        int(array[:, 1].max()),
    )

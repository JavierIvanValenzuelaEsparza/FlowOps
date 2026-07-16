import logging
from typing import Any

import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_bytes, pdfinfo_from_bytes

from src.core.config import settings

logger = logging.getLogger("ocr.engine")


class OCREngine:
    def __init__(self, language: str | None = None) -> None:
        self.language = language or settings.OCR_LANGUAGE

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        denoised = cv2.medianBlur(gray, 3)
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def _extract(self, image: np.ndarray) -> tuple[str, float]:
        data = pytesseract.image_to_data(
            image, lang=self.language, output_type=pytesseract.Output.DICT
        )

        lines: dict[tuple[int, int, int], list[str]] = {}
        confidences: list[float] = []
        for i, raw_word in enumerate(data["text"]):
            word = raw_word.strip()
            if not word:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(word)
            confidence = float(data["conf"][i])
            if confidence >= 0:
                confidences.append(confidence)

        text = "\n".join(" ".join(words) for _, words in sorted(lines.items()))
        avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        return text, avg_confidence

    def process_image(self, image_bytes: bytes) -> dict[str, Any]:
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode the provided bytes as an image")

        logger.info("Processing image %dx%d", image.shape[1], image.shape[0])
        prepared = self._preprocess(image)
        text, confidence = self._extract(prepared)
        logger.info("Image OCR done: %d chars, confidence=%.1f", len(text), confidence)
        return {"text": text, "confidence": confidence, "pages": 1}

    def process_pdf(self, pdf_bytes: bytes) -> dict[str, Any]:
        info = pdfinfo_from_bytes(pdf_bytes)
        page_count = int(info["Pages"])
        logger.info("Processing PDF with %d page(s)", page_count)

        page_texts: list[str] = []
        page_confidences: list[float] = []
        for page_number in range(1, page_count + 1):
            pages = convert_from_bytes(
                pdf_bytes,
                dpi=settings.OCR_DPI,
                first_page=page_number,
                last_page=page_number,
                grayscale=True,
            )
            page_array = np.asarray(pages[0])
            prepared = self._preprocess(page_array)
            text, confidence = self._extract(prepared)
            page_texts.append(text)
            page_confidences.append(confidence)
            logger.info(
                "PDF page %d/%d done: %d chars, confidence=%.1f",
                page_number, page_count, len(text), confidence,
            )

        avg_confidence = (
            round(sum(page_confidences) / len(page_confidences), 2) if page_confidences else 0.0
        )
        return {"text": "\n\n".join(page_texts), "confidence": avg_confidence, "pages": page_count}

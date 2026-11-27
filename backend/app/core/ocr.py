import io
import re
from math import isfinite
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytesseract
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError


def _run_tesseract(image: Image.Image) -> str:
    """Normalizes image orientation/contrast and extracts numeric text via Tesseract."""
    normalized = ImageOps.exif_transpose(image)
    grayscale = ImageOps.grayscale(normalized)
    enhanced = ImageEnhance.Contrast(grayscale).enhance(2)

    text = pytesseract.image_to_string(
        enhanced,
        config=(
            "--psm 6 "
            "-c tessedit_char_whitelist=0123456789.,"
        ),
        timeout=10,
    )
    return text.strip()


def extract_text(image_path: str) -> str:
    """
    Extract text from an odometer or fuel pump photo.

    Use only with a trusted server-side image path.
    """
    path = Path(image_path)

    if not path.is_file():
        raise ValueError("Image file not found")

    try:
        with Image.open(path) as image:
            return _run_tesseract(image)
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        pytesseract.TesseractError,
        pytesseract.TesseractNotFoundError,
        RuntimeError,
    ) as exc:
        raise ValueError("Invalid, unreadable, or OCR-failed image") from exc


def extract_text_from_bytes(image_bytes: bytes) -> str:
    """Extract numeric text from in-memory image bytes using local Tesseract OCR."""
    if not image_bytes:
        raise ValueError("Empty image bytes")

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            return _run_tesseract(image)
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        pytesseract.TesseractError,
        pytesseract.TesseractNotFoundError,
        RuntimeError,
    ) as exc:
        raise ValueError("Invalid, unreadable, or OCR-failed image") from exc


def extract_numeric_candidates(text: str) -> List[float]:
    """
    Find numeric readings in OCR text.

    Example:
        '45600' -> [45600.0]
        '25.50' -> [25.5]
        '45,600' -> [45600.0]
    """
    numbers = re.findall(
        r"(?<!\d)\d+(?:[.,]\d+)*(?!\d)",
        text,
    )

    results = []

    for number in numbers:
        if "," in number and "." in number:
            # Example: 1,234.50
            normalized = number.replace(",", "")
        elif "," in number:
            parts = number.split(",")

            if len(parts) == 2 and len(parts[1]) == 3:
                # Example: 45,600
                normalized = number.replace(",", "")
            else:
                # Example: 25,50
                normalized = number.replace(",", ".")
        else:
            normalized = number

        try:
            results.append(float(normalized))
        except ValueError:
            continue

    return results


def verify_reading(
    ocr_text: str,
    manual_value: float,
    tolerance: float = 0.01,
) -> bool:
    if not isfinite(manual_value) or manual_value <= 0:
        return False

    if not isfinite(tolerance) or tolerance < 0:
        return False

    candidates = extract_numeric_candidates(ocr_text)

    # Reject missing or ambiguous readings.
    if len(candidates) != 1:
        return False

    return abs(candidates[0] - manual_value) <= tolerance


def verify_image_reading(
    image_bytes: bytes,
    manual_value: float,
    tolerance: float = 0.01,
    field_label: str = "Reading",
) -> Dict[str, Any]:
    """
    Runs Tesseract OCR on image bytes and compares the extracted reading against
    the operator's manual input. Never raises for unreadable/mismatched photos;
    instead returns structured status ('MATCH', 'MISMATCH', 'UNREADABLE') so
    entries can be flagged for owner review.
    """
    if not isfinite(manual_value) or manual_value <= 0:
        return {
            "status": "UNREADABLE",
            "matched": False,
            "extracted_text": None,
            "extracted_value": None,
            "candidates": [],
            "reason": f"Invalid manual {field_label.lower()} value",
        }

    try:
        ocr_text = extract_text_from_bytes(image_bytes)
    except ValueError:
        return {
            "status": "UNREADABLE",
            "matched": False,
            "extracted_text": None,
            "extracted_value": None,
            "candidates": [],
            "reason": f"{field_label} image could not be read by OCR",
        }

    candidates = extract_numeric_candidates(ocr_text)

    if len(candidates) == 0:
        return {
            "status": "UNREADABLE",
            "matched": False,
            "extracted_text": ocr_text,
            "extracted_value": None,
            "candidates": [],
            "reason": f"No numeric {field_label.lower()} detected in image",
        }

    if len(candidates) > 1:
        return {
            "status": "UNREADABLE",
            "matched": False,
            "extracted_text": ocr_text,
            "extracted_value": None,
            "candidates": candidates,
            "reason": f"Ambiguous {field_label.lower()} readings detected in image ({candidates})",
        }

    detected_value = candidates[0]
    if abs(detected_value - manual_value) <= tolerance:
        return {
            "status": "MATCH",
            "matched": True,
            "extracted_text": ocr_text,
            "extracted_value": detected_value,
            "candidates": candidates,
            "reason": None,
        }

    return {
        "status": "MISMATCH",
        "matched": False,
        "extracted_text": ocr_text,
        "extracted_value": detected_value,
        "candidates": candidates,
        "reason": f"{field_label} mismatch: OCR detected {detected_value}, entered {manual_value}",
    }

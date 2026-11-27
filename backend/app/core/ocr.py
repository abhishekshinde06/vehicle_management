
import re
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps, ImageEnhance, UnidentifiedImageError
from math import isfinite


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
            # Convert image to grayscale.
            image = ImageOps.grayscale(image)

            # Improve contrast for easier OCR.
            image = ImageEnhance.Contrast(image).enhance(2)

            # Read digits and decimal separators.
            text = pytesseract.image_to_string(
                image,
                config=(
                    "--psm 6 "
                    "-c tessedit_char_whitelist=0123456789.,"
                ),
                timeout=10,
            )

        return text.strip()

    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid or unreadable image") from exc
    except RuntimeError as exc:
        raise ValueError("OCR processing failed") from exc


def extract_numeric_candidates(text: str) -> list[float]:
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

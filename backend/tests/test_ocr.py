
from app.core.ocr import (
    extract_numeric_candidates,
    verify_reading,
)


def test_odometer_match():
    assert verify_reading("45600", 45600) is True


def test_odometer_mismatch():
    assert verify_reading("45600", 45700) is False


def test_fuel_litres_match():
    assert verify_reading("25.50", 25.50) is True


def test_fuel_litres_mismatch():
    assert verify_reading("25.50", 30.00) is False


def test_unreadable_text():
    assert verify_reading("unreadable", 25.50) is False


def test_thousand_separator():
    assert extract_numeric_candidates("45,600") == [45600.0]


def test_decimal_comma():
    assert extract_numeric_candidates("25,50") == [25.5]

def test_actual_image_ocr(tmp_path):
    from PIL import Image, ImageDraw, ImageFont
    from app.core.ocr import extract_text

    image = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype("Arial.ttf", 80)

    draw.text(
        (50, 50),
        "45600",
        fill="black",
        font=font,
    )

    image_path = tmp_path / "odometer.png"
    image.save(image_path)

    extracted_text = extract_text(str(image_path))

    assert verify_reading(extracted_text, 45600) is True
    assert verify_reading(extracted_text, 45700) is False

def test_ambiguous_reading():
    assert verify_reading(
        "2500 25.50 98.04", 25.50
    ) is False


def test_invalid_manual_reading():
    assert verify_reading("0", 0) is False


def test_non_finite_reading():
    assert verify_reading("25.50", float("inf")) is False


def test_invalid_tolerance():
    assert verify_reading("25.50", 25.50, -1) is False    
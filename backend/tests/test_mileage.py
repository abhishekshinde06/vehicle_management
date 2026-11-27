import pytest

from app.core.mileage import calculate_mileage


def test_full_tank_mileage():
    assert calculate_mileage(45000, 45600, 100) == 6.0


def test_mileage_with_partial_refills():
    assert calculate_mileage(45000, 45600, 80, 20) == 6.0


def test_partial_tank():
    assert calculate_mileage(
        45000, 45200, 20, is_full_tank=False
    ) is None


def test_decreasing_odometer():
    with pytest.raises(ValueError):
        calculate_mileage(45000, 44000, 100)


def test_zero_fuel():
    with pytest.raises(ValueError):
        calculate_mileage(45000, 45600, 0)


def test_negative_fuel():
    with pytest.raises(ValueError):
        calculate_mileage(45000, 45600, -10)


def test_negative_partial_fuel():
    with pytest.raises(ValueError):
        calculate_mileage(45000, 45600, 80, -20)


def test_invalid_numeric_value():
    with pytest.raises(ValueError):
        calculate_mileage(45000, float("inf"), 100)
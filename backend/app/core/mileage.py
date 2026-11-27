from math import isfinite


def calculate_mileage(
    previous_full_odometer: float,
    current_odometer: float,
    current_fuel_litres: float,
    partial_fuel_litres: float = 0.0,
    is_full_tank: bool = True,
) -> float | None:

    values = [
        previous_full_odometer,
        current_odometer,
        current_fuel_litres,
        partial_fuel_litres,
    ]

    if not all(isfinite(value) for value in values):
        raise ValueError("Invalid numeric values")

    if previous_full_odometer < 0:
        raise ValueError("Invalid previous odometer")

    if current_odometer <= previous_full_odometer:
        raise ValueError("Invalid current odometer")

    if current_fuel_litres <= 0:
        raise ValueError("Fuel quantity must be positive")

    if partial_fuel_litres < 0:
        raise ValueError("Invalid partial fuel quantity")

    if not is_full_tank:
        return None

    distance = current_odometer - previous_full_odometer

    total_fuel = current_fuel_litres + partial_fuel_litres

    return round(distance / total_fuel, 2)
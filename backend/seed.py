"""
Database Seeding Script
-----------------------
Pre-populates the database with the initial owner account, fleet vehicles,
and authorized petrol pumps.

IMPORTANT — Single-Transporter MVP Rules:
  - Public owner self-registration is DISABLED in the API.
  - The fleet owner account MUST be created through this script (or manually).
  - After running this script, the owner can log in and create operator accounts
    via POST /api/auth/create-operator.

Usage:
    cd backend
    alembic upgrade head        # ensure tables exist first
    python seed.py

Re-run safety:
    Safe to re-run at any time — existing records are skipped, never duplicated.
"""

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import User, Vehicle, PetrolPump


def seed_database():
    """
    Populates the database with starter records.

    Steps:
        1. Owner account     — logs in via mobile app to approve/reject entries
        2. Operator account  — logs in via tablet to submit fuel entries
        3. Fleet vehicles    — 3 trucks with initial odometer readings
        4. Petrol pumps      — 2 GPS-registered authorized refueling stops
    """
    print("=" * 60)
    print("  Vehicle Management — Database Seed")
    print("=" * 60)

    db = SessionLocal()
    try:
        # ------------------------------------------------------------------
        # 1. Owner account  (created here — public signup is disabled)
        # ------------------------------------------------------------------
        print("\n[1/4] Seeding Owner account...")
        owner = db.query(User).filter(User.username == "owner").first()
        if not owner:
            owner = User(
                username="owner",
                password_hash=get_password_hash("owner123"),
                role="owner",
                full_name="Fleet Owner (Vikram)",
                is_active=True,
            )
            db.add(owner)
            print("  + Created owner  — username: 'owner'    password: 'owner123'")
        else:
            print("  ~ owner already exists, skipped.")

        # ------------------------------------------------------------------
        # 2. Default operator account
        # ------------------------------------------------------------------
        print("\n[2/4] Seeding default Operator account...")
        operator = db.query(User).filter(User.username == "operator").first()
        if not operator:
            operator = User(
                username="operator",
                password_hash=get_password_hash("operator123"),
                role="operator",
                full_name="Tablet Operator (Ramesh)",
                is_active=True,
            )
            db.add(operator)
            print("  + Created operator — username: 'operator' password: 'operator123'")
        else:
            print("  ~ operator already exists, skipped.")

        # ------------------------------------------------------------------
        # 3. Fleet vehicles
        # ------------------------------------------------------------------
        print("\n[3/4] Seeding Fleet Vehicles...")
        vehicles_data = [
            {"vehicle_number": "MH-12-AB-1001", "model": "Tata Prima 4028.S",   "initial_odometer": 45000.0},
            {"vehicle_number": "MH-14-XY-2002", "model": "Ashok Leyland 3118",  "initial_odometer": 72500.0},
            {"vehicle_number": "MH-46-TR-3003", "model": "BharatBenz 2823R",    "initial_odometer": 28900.0},
        ]
        for v in vehicles_data:
            if not db.query(Vehicle).filter(Vehicle.vehicle_number == v["vehicle_number"]).first():
                db.add(Vehicle(**v))
                print(f"  + {v['vehicle_number']}  ({v['model']}, odometer: {v['initial_odometer']} km)")
            else:
                print(f"  ~ {v['vehicle_number']} already exists, skipped.")

        # ------------------------------------------------------------------
        # 4. Authorized petrol pumps
        # ------------------------------------------------------------------
        print("\n[4/4] Seeding Authorized Petrol Pumps...")
        pumps_data = [
            {
                "name": "Bharat Petroleum - Highway Hub",
                "address": "NH-48, Near Expressway Toll, Pune",
                "latitude": 18.5204,
                "longitude": 73.8567,
                "radius_meters": 150.0,
            },
            {
                "name": "Indian Oil - Transporter Hub",
                "address": "Transport Nagar, Nigdi, Pune",
                "latitude": 18.6510,
                "longitude": 73.7820,
                "radius_meters": 100.0,
            },
        ]
        for p in pumps_data:
            if not db.query(PetrolPump).filter(PetrolPump.name == p["name"]).first():
                db.add(PetrolPump(**p))
                print(f"  + '{p['name']}' (radius: {p['radius_meters']} m)")
            else:
                print(f"  ~ '{p['name']}' already exists, skipped.")

        db.commit()
        print("\n" + "=" * 60)
        print("  Seeding completed successfully!")
        print("  Login credentials:")
        print("    Owner    — username: owner    | password: owner123")
        print("    Operator — username: operator | password: operator123")
        print("=" * 60)

    except Exception as exc:
        db.rollback()
        print(f"\n!! Seeding failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

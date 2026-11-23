"""
Database Seeding Script
-----------------------
Pre-populates the database with initial master data:
1. Operator user ('operator' / 'operator123') for tablet login.
2. Owner user ('owner' / 'owner123') for mobile login.
3. Transporter fleet vehicles with initial odometer values.
4. Authorized petrol pumps with registered GPS coordinates and radius.
"""

from app.core.database import engine, Base, SessionLocal
from app.core.security import get_password_hash
from app.models import User, Vehicle, PetrolPump, FuelEntry, AuditLog


def seed_database():
    """
    Creates database tables if they do not exist and populates starter records.
    Safe to re-run; will not create duplicate entries.
    """
    print("[1/4] Ensuring database tables are created...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("[2/4] Seeding default User accounts...")
        # 1. Operator Account (for Tablet)
        operator_user = db.query(User).filter(User.username == "operator").first()
        if not operator_user:
            operator_user = User(
                username="operator",
                password_hash=get_password_hash("operator123"),
                role="operator",
                full_name="Tablet Operator (Ramesh)",
                is_active=True
            )
            db.add(operator_user)
            print("  + Added Operator: 'operator' (Password: 'operator123')")

        # 2. Owner Account (for Mobile)
        owner_user = db.query(User).filter(User.username == "owner").first()
        if not owner_user:
            owner_user = User(
                username="owner",
                password_hash=get_password_hash("owner123"),
                role="owner",
                full_name="Fleet Owner (Vikram)",
                is_active=True
            )
            db.add(owner_user)
            print("  + Added Owner: 'owner' (Password: 'owner123')")

        print("[3/4] Seeding Fleet Vehicles...")
        # 3. Sample Fleet Vehicles
        vehicles_data = [
            {"vehicle_number": "MH-12-AB-1001", "model": "Tata Prima 4028.S", "initial_odometer": 45000.0},
            {"vehicle_number": "MH-14-XY-2002", "model": "Ashok Leyland 3118", "initial_odometer": 72500.0},
            {"vehicle_number": "MH-46-TR-3003", "model": "BharatBenz 2823R", "initial_odometer": 28900.0},
        ]
        for v in vehicles_data:
            existing = db.query(Vehicle).filter(Vehicle.vehicle_number == v["vehicle_number"]).first()
            if not existing:
                vehicle = Vehicle(**v)
                db.add(vehicle)
                print(f"  + Added Vehicle: {v['vehicle_number']} (Initial Odometer: {v['initial_odometer']} km)")

        print("[4/4] Seeding Authorized Petrol Pumps...")
        # 4. Authorized Petrol Pumps
        pumps_data = [
            {
                "name": "Bharat Petroleum - Highway Hub",
                "address": "NH-48, Near Expressway Toll, Pune",
                "latitude": 18.5204,
                "longitude": 73.8567,
                "radius_meters": 150.0
            },
            {
                "name": "Indian Oil - Transporter Hub",
                "address": "Transport Nagar, Nigdi, Pune",
                "latitude": 18.6510,
                "longitude": 73.7820,
                "radius_meters": 100.0
            }
        ]
        for p in pumps_data:
            existing = db.query(PetrolPump).filter(PetrolPump.name == p["name"]).first()
            if not existing:
                pump = PetrolPump(**p)
                db.add(pump)
                print(f"  + Added Authorized Pump: '{p['name']}' (Radius: {p['radius_meters']}m)")

        db.commit()
        print(">> Database seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"!! Error seeding database: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

"""
Routes Package
--------------
Exposes all application route modules:
- auth
- vehicles
- petrol_pumps
- fuel_entries
"""

from app.routes import auth, vehicles, petrol_pumps, fuel_entries

__all__ = ["auth", "vehicles", "petrol_pumps", "fuel_entries"]

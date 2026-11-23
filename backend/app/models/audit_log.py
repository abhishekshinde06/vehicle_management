import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    fuel_entry_id = Column(String, ForeignKey("fuel_entries.id"), nullable=False, index=True)
    action = Column(String, nullable=False)  # "CREATED", "APPROVED", "REJECTED", "UPDATED"
    performed_by = Column(String, ForeignKey("users.id"), nullable=False)
    remarks = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

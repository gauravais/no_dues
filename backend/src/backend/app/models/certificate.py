"""Certificate model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True)
    request_id = Column(
        Integer, ForeignKey("clearance_requests.id"), nullable=False, unique=True
    )
    certificate_code = Column(
        String(36), nullable=False, unique=True,
        default=lambda: str(uuid.uuid4())
    )
    issued_at = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    hod_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    request = relationship("ClearanceRequest", back_populates="certificate")
    hod_user = relationship(
        "User", back_populates="issued_certificates",
        foreign_keys=[hod_user_id]
    )

"""BankDetail model and account-number masking helper."""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


def mask_account_number(account_number: str) -> str:
    """Return the account number with all but the last 4 digits masked.

    Example: '123456781234' -> '********1234'
    Raises ValueError if the account number has fewer than 4 characters.
    """
    if len(account_number) < 4:
        raise ValueError("Account number must have at least 4 characters.")
    return "*" * (len(account_number) - 4) + account_number[-4:]


class BankDetail(Base):
    __tablename__ = "bank_details"

    id = Column(Integer, primary_key=True)
    roster_id = Column(
        Integer, ForeignKey("student_roster.id"), nullable=False, unique=True
    )
    account_holder_name = Column(String(255), nullable=False)
    account_number = Column(String(30), nullable=False)
    ifsc_code = Column(String(11), nullable=False)
    bank_address = Column(String(500), nullable=False)

    roster_entry = relationship("StudentRoster", back_populates="bank_detail")

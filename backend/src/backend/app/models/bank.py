"""BankDetail model and account-number masking helper."""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.core.crypto import encrypt_bank_account, decrypt_bank_account


def mask_account_number(account_number: str) -> str:
    """Return the account number with all but the last 4 digits masked.

    Decrypted transparently if encrypted.
    Example: '123456781234' -> '********1234'
    Raises ValueError if the account number has fewer than 4 characters.
    """
    plain = decrypt_bank_account(account_number)
    if len(plain) < 4:
        raise ValueError("Account number must have at least 4 characters.")
    return "*" * (len(plain) - 4) + plain[-4:]


class BankDetail(Base):
    __tablename__ = "bank_details"

    id = Column(Integer, primary_key=True)
    roster_id = Column(
        Integer, ForeignKey("student_roster.id"), nullable=False, unique=True
    )
    account_holder_name = Column(String(255), nullable=False)
    _account_number = Column("account_number", String(255), nullable=False)
    ifsc_code = Column(String(11), nullable=False)
    bank_address = Column(String(500), nullable=False)

    roster_entry = relationship("StudentRoster", back_populates="bank_detail")

    @property
    def account_number(self) -> str:
        return decrypt_bank_account(self._account_number)

    @account_number.setter
    def account_number(self, value: str) -> None:
        self._account_number = encrypt_bank_account(value)

    @property
    def masked_account_number(self) -> str:
        return mask_account_number(self._account_number)

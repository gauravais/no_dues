"""Pydantic schemas for student bank details."""
from pydantic import BaseModel, Field


class BankDetailRead(BaseModel):
    """Masked bank details view for a student."""
    account_number_masked: str = Field(
        ...,
        description="Securely masked bank account number (all but last 4 digits hidden)",
        examples=["********1234"],
    )
    ifsc_code: str = Field(
        ...,
        description="11-character Indian Financial System Code",
        examples=["SBIN0001234"],
    )
    account_holder_name: str = Field(
        ...,
        description="Official account holder name as recorded in the bank",
        examples=["Arjun Mehta"],
    )
    bank_address: str = Field(
        ...,
        description="Bank branch name and location",
        examples=["State Bank of India, Main Campus Branch, Palwal"],
    )


class BankDetailUpdate(BaseModel):
    """Payload to update student bank details."""
    account_number: str = Field(
        ...,
        pattern=r"^\d{9,18}$",
        description="Full bank account number (digits only, 9 to 18 digits)",
        examples=["123456789012"],
    )
    ifsc_code: str = Field(
        ...,
        pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$",
        description="Standard 11-character IFSC code matching ^[A-Z]{4}0[A-Z0-9]{6}$",
        examples=["SBIN0001234"],
    )
    account_holder_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of account holder",
        examples=["Arjun Mehta"],
    )
    bank_address: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Bank branch and address",
        examples=["State Bank of India, Main Campus Branch, Palwal"],
    )

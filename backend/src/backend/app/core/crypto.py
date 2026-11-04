"""Encryption utilities for sensitive data at rest using Fernet."""
from cryptography.fernet import Fernet, InvalidToken
from backend.app.core.config import settings


def get_fernet() -> Fernet:
    """Returns a Fernet cipher instance initialized with the application's BANK_DATA_KEY."""
    key = settings.get_bank_data_key()
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encrypt_bank_account(plain_account: str) -> str:
    """
    Encrypts a plain bank account number into a Fernet ciphertext token.
    If the input is already a Fernet token (starts with 'gAAAAA'), returns it unchanged.
    """
    if not plain_account:
        return plain_account
    cleaned = plain_account.strip()
    if cleaned.startswith("gAAAAA") and len(cleaned) > 50:
        return cleaned
    cipher = get_fernet()
    return cipher.encrypt(cleaned.encode("utf-8")).decode("utf-8")


def decrypt_bank_account(cipher_text: str) -> str:
    """
    Decrypts a Fernet ciphertext token back into the plain bank account number.
    If the value is not a Fernet token (or decryption fails), returns the original value.
    """
    if not cipher_text:
        return cipher_text
    cleaned = cipher_text.strip()
    if not cleaned.startswith("gAAAAA"):
        return cleaned
    try:
        cipher = get_fernet()
        return cipher.decrypt(cleaned.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return cleaned

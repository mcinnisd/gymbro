# app/utils/encryption.py

from cryptography.fernet import Fernet
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def get_cipher(key=None):
    """
    Retrieves the Fernet cipher using the ENCRYPTION_KEY.
    If key is provided, uses it. Otherwise, fetches from app configuration.
    """
    if not key:
        key = current_app.config.get("ENCRYPTION_KEY")
        
    if not key:
        logger.error("ENCRYPTION_KEY not set in configuration.")
        raise ValueError("ENCRYPTION_KEY not set in configuration.")
    try:
        return Fernet(key.encode())
    except Exception as e:
        logger.error(f"Invalid ENCRYPTION_KEY: {e}")
        raise

def encrypt_data(plain_text: str, key: str = None) -> str:
    """
    Encrypts plain text using Fernet symmetric encryption.
    """
    try:
        cipher = get_cipher(key)
        encrypted = cipher.encrypt(plain_text.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise

def decrypt_data(encrypted_text: str, key: str = None) -> str:
    """
    Decrypts encrypted text using Fernet symmetric encryption.
    """
    try:
        cipher = get_cipher(key)
        decrypted = cipher.decrypt(encrypted_text.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise

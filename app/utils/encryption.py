# app/utils/encryption.py

from cryptography.fernet import Fernet
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def get_cipher():
    """
    Retrieves the Fernet cipher using the ENCRYPTION_KEY from the app's configuration.
    """
    key = current_app.config.get("ENCRYPTION_KEY")
    if not key:
        logger.error("ENCRYPTION_KEY not set in configuration.")
        raise ValueError("ENCRYPTION_KEY not set in configuration.")
    try:
        return Fernet(key.encode())
    except Exception as e:
        logger.error(f"Invalid ENCRYPTION_KEY: {e}")
        raise

def encrypt_data(plain_text: str) -> str:
    """
    Encrypts plain text using Fernet symmetric encryption.
    
    Args:
        plain_text (str): The data to encrypt.
    
    Returns:
        str: The encrypted data as a string.
    """
    try:
        cipher = get_cipher()
        encrypted = cipher.encrypt(plain_text.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise

def decrypt_data(encrypted_text: str) -> str:
    """
    Decrypts encrypted text using Fernet symmetric encryption.
    
    Args:
        encrypted_text (str): The encrypted data to decrypt.
    
    Returns:
        str: The decrypted plain text.
    """
    try:
        cipher = get_cipher()
        decrypted = cipher.decrypt(encrypted_text.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise

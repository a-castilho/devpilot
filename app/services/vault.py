import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class Vault:
    def __init__(self) -> None:
        configured = get_settings().encryption_key.encode()
        if configured:
            key = configured
        elif get_settings().env == "development":
            digest = hashlib.sha256(get_settings().bootstrap_token.encode()).digest()
            key = base64.urlsafe_b64encode(digest)
        else:
            raise RuntimeError("DEVPILOT_ENCRYPTION_KEY is required outside development")

        self.fernet = Fernet(key)
        next_key = os.getenv("DEVPILOT_ENCRYPTION_KEY_NEXT", "").strip().encode()
        self.next_fernet = Fernet(next_key) if next_key and next_key != key else None

    def encrypt(self, secret: str) -> str:
        fernet = self.next_fernet or self.fernet
        return fernet.encrypt(secret.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        encoded = encrypted.encode()
        if self.next_fernet is not None:
            try:
                return self.next_fernet.decrypt(encoded).decode()
            except InvalidToken:
                pass
        try:
            return self.fernet.decrypt(encoded).decode()
        except InvalidToken as error:
            raise ValueError("Credential cannot be decrypted with the configured key ring") from error

    def rotate(self, encrypted: str) -> str:
        """Re-encrypt legacy ciphertext with the shared next key when configured."""
        if self.next_fernet is None:
            return encrypted

        encoded = encrypted.encode()
        try:
            self.next_fernet.decrypt(encoded)
            return encrypted
        except InvalidToken:
            pass

        try:
            plaintext = self.fernet.decrypt(encoded)
        except InvalidToken as error:
            raise ValueError("Credential cannot be decrypted with the configured key ring") from error
        return self.next_fernet.encrypt(plaintext).decode()

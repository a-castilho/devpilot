import base64
import hashlib

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

    def encrypt(self, secret: str) -> str:
        return self.fernet.encrypt(secret.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        try:
            return self.fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken as error:
            raise ValueError("Credential cannot be decrypted with the current key") from error

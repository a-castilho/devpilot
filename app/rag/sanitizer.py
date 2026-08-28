from __future__ import annotations

import re


class RagSanitizer:
    """Best-effort secret scrubber before RAG persistence.

    This is intentionally conservative. Source adapters should also exclude known
    secret files such as .env and private keys before content reaches this layer.
    """

    _SECRET_ASSIGNMENT = re.compile(
        r"(?i)([\"']?(?:api[_-]?key|token|password|secret)[\"']?\s*[:=]\s*)"
        r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,}\]]+)"
    )
    _PRIVATE_KEY = re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
    )

    def sanitize(self, content: str) -> str:
        sanitized = self._PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", content)
        return self._SECRET_ASSIGNMENT.sub(r"\1[REDACTED]", sanitized)

    @staticmethod
    def should_exclude_path(path: str) -> bool:
        normalized = path.replace("\\", "/").lower()
        excluded_parts = (
            "/.git/",
            "/node_modules/",
            "/vendor/",
            "/dist/",
            "/build/",
            "/coverage/",
        )
        if any(part in f"/{normalized.strip('/')}/" for part in excluded_parts):
            return True
        basename = normalized.rsplit("/", 1)[-1]
        if basename in {".env", ".env.local", ".env.production", ".env.development"}:
            return True
        return basename.endswith((".pem", ".key", ".p12", ".pfx"))

from __future__ import annotations

import re


class RagSanitizer:
    """Best-effort secret scrubber before RAG persistence.

    This is intentionally conservative. Source adapters should also exclude known
    secret files such as .env and private keys before content reaches this layer.
    """

    _PATTERNS = (
        re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s\"']+"),
        re.compile(r"(?i)(token\s*[:=]\s*)[^\s\"']+"),
        re.compile(r"(?i)(password\s*[:=]\s*)[^\s\"']+"),
        re.compile(r"(?i)(secret\s*[:=]\s*)[^\s\"']+"),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    )

    def sanitize(self, content: str) -> str:
        sanitized = content
        for pattern in self._PATTERNS:
            if "PRIVATE KEY" in pattern.pattern:
                sanitized = pattern.sub("[REDACTED PRIVATE KEY]", sanitized)
            else:
                sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
        return sanitized

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

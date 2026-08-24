from __future__ import annotations

import base64
import hashlib
import json
import os
import pwd
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption


AUDIT_SCHEMA_VERSION = 2


class LinuxAuditError(RuntimeError):
    """Raised when the Linux audit identity cannot sign or verify an event."""


def _identity_dir() -> Path:
    raw = os.environ.get("DEVPILOT_LINUX_AUDIT_IDENTITY_DIR", "").strip()
    target = Path(raw).expanduser() if raw else Path.home() / ".devpilot" / "identity"
    target.mkdir(parents=True, exist_ok=True)
    try:
        target.chmod(0o700)
    except OSError:
        pass
    return target


def linux_identity() -> dict[str, Any]:
    euid = os.geteuid()
    try:
        account = pwd.getpwuid(euid)
        username = account.pw_name
    except KeyError:
        username = str(euid)
    return {
        "username": username,
        "uid": os.getuid(),
        "euid": euid,
        "gid": os.getgid(),
        "egid": os.getegid(),
        "hostname": socket.gethostname(),
    }


def _load_or_create_private_key() -> Ed25519PrivateKey:
    root = _identity_dir()
    private_path = root / "audit-private.key"
    public_path = root / "audit-public.key"

    if private_path.exists():
        try:
            raw = base64.b64decode(private_path.read_text(encoding="ascii").strip(), validate=True)
            key = Ed25519PrivateKey.from_private_bytes(raw)
        except (OSError, ValueError) as error:
            raise LinuxAuditError("Chave privada de auditoria Linux inválida") from error
    else:
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        try:
            private_path.write_text(base64.b64encode(raw).decode("ascii") + "\n", encoding="ascii")
            private_path.chmod(0o600)
        except OSError as error:
            raise LinuxAuditError("Não foi possível criar a identidade de auditoria Linux") from error

    public_raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public_text = base64.b64encode(public_raw).decode("ascii")
    try:
        if not public_path.exists() or public_path.read_text(encoding="ascii").strip() != public_text:
            public_path.write_text(public_text + "\n", encoding="ascii")
            public_path.chmod(0o644)
    except OSError as error:
        raise LinuxAuditError("Não foi possível publicar a chave de auditoria Linux") from error
    return key


def _normalize_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "username": str(identity.get("username") or ""),
        "uid": int(identity.get("uid", -1)),
        "euid": int(identity.get("euid", -1)),
        "gid": int(identity.get("gid", -1)),
        "egid": int(identity.get("egid", -1)),
        "hostname": str(identity.get("hostname") or ""),
    }


def canonical_document(
    event: dict[str, Any],
    *,
    identity: dict[str, Any],
    signed_at: str,
) -> dict[str, Any]:
    details = event.get("details")
    if not isinstance(details, dict):
        raise LinuxAuditError("Detalhes do evento de auditoria devem ser um objeto")
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "previous_hash": str(event.get("previous_hash") or ""),
        "workspace_id": str(event.get("workspace_id") or ""),
        "project_id": str(event.get("project_id") or ""),
        "task_id": str(event.get("task_id") or ""),
        "run_id": str(event.get("run_id") or ""),
        "actor": str(event.get("actor") or ""),
        "action": str(event.get("action") or ""),
        "outcome": str(event.get("outcome") or "success"),
        "details": details,
        "linux_identity": _normalize_identity(identity),
        "signed_at": str(signed_at),
    }


def canonical_bytes(document: dict[str, Any]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def identity_status() -> dict[str, Any]:
    private_key = _load_or_create_private_key()
    public_raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {
        "linux_identity": linux_identity(),
        "signature_algorithm": "ed25519",
        "signing_public_key": base64.b64encode(public_raw).decode("ascii"),
        "signing_key_id": hashlib.sha256(public_raw).hexdigest(),
    }


def attest_event(event: dict[str, Any]) -> dict[str, Any]:
    private_key = _load_or_create_private_key()
    identity = linux_identity()
    signed_at = datetime.now(timezone.utc).isoformat()
    document = canonical_document(event, identity=identity, signed_at=signed_at)
    payload = canonical_bytes(document)
    public_raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    signature = private_key.sign(payload)
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "event_hash": hashlib.sha256(payload).hexdigest(),
        "signed_at": signed_at,
        "linux_identity": identity,
        "signature_algorithm": "ed25519",
        "signing_public_key": base64.b64encode(public_raw).decode("ascii"),
        "signing_key_id": hashlib.sha256(public_raw).hexdigest(),
        "signature": base64.b64encode(signature).decode("ascii"),
    }


def verify_attestation(event: dict[str, Any], attestation: dict[str, Any]) -> tuple[bool, str]:
    if int(attestation.get("schema_version") or 0) != AUDIT_SCHEMA_VERSION:
        return False, "schema_version"
    if attestation.get("signature_algorithm") != "ed25519":
        return False, "signature_algorithm"
    try:
        public_raw = base64.b64decode(str(attestation["signing_public_key"]), validate=True)
        signature = base64.b64decode(str(attestation["signature"]), validate=True)
        public_key = Ed25519PublicKey.from_public_bytes(public_raw)
        document = canonical_document(
            event,
            identity=dict(attestation["linux_identity"]),
            signed_at=str(attestation["signed_at"]),
        )
        payload = canonical_bytes(document)
    except (KeyError, TypeError, ValueError, LinuxAuditError) as error:
        return False, f"invalid_payload:{error}"

    event_hash = hashlib.sha256(payload).hexdigest()
    if event_hash != str(attestation.get("event_hash") or ""):
        return False, "event_hash"
    if hashlib.sha256(public_raw).hexdigest() != str(attestation.get("signing_key_id") or ""):
        return False, "signing_key_id"
    try:
        public_key.verify(signature, payload)
    except InvalidSignature:
        return False, "signature"
    return True, "ok"

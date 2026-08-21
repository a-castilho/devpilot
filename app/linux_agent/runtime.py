from __future__ import annotations

import json
import os
import pty
import select
import shutil
import signal
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TerminalSession:
    id: str
    actor: str
    cwd: str
    created_at: str
    process: subprocess.Popen[bytes]
    master_fd: int
    log_path: Path
    metadata_path: Path
    state: str = "running"
    exit_code: int | None = None
    closed_at: str | None = None
    last_activity_at: str = field(default_factory=utc_now)
    sequence: int = 0
    chunks: deque[tuple[int, str]] = field(default_factory=lambda: deque(maxlen=4096))
    lock: threading.RLock = field(default_factory=threading.RLock)
    reader: threading.Thread | None = None

    def public(self) -> dict[str, Any]:
        with self.lock:
            return {
                "id": self.id,
                "actor": self.actor,
                "cwd": self.cwd,
                "created_at": self.created_at,
                "last_activity_at": self.last_activity_at,
                "state": self.state,
                "exit_code": self.exit_code,
                "closed_at": self.closed_at,
                "pid": self.process.pid,
            }


class SessionNotFound(KeyError):
    pass


class SessionManager:
    def __init__(self, data_dir: Path, *, shell: str | None = None) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.sessions_dir = self.data_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.sessions_dir.chmod(0o700)
        except OSError:
            pass
        preferred = shell or os.environ.get("SHELL") or "/bin/bash"
        self.shell = preferred if Path(preferred).exists() else "/bin/sh"
        self._sessions: dict[str, TerminalSession] = {}
        self._lock = threading.RLock()

    def create(
        self,
        *,
        actor: str,
        cwd: str | None = None,
        columns: int = 120,
        rows: int = 34,
    ) -> dict[str, Any]:
        target_cwd = Path(cwd or Path.home()).expanduser().resolve()
        if not target_cwd.is_dir():
            raise ValueError("Diretório inicial não existe")

        session_id = uuid4().hex
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(mode=0o700)
        log_path = session_dir / "terminal.log"
        metadata_path = session_dir / "session.json"
        log_path.touch(mode=0o600)

        master_fd, slave_fd = pty.openpty()
        try:
            self._resize_pty(master_fd, columns=columns, rows=rows)
            env = os.environ.copy()
            env.setdefault("TERM", "xterm-256color")
            env["DEVPILOT_TERMINAL_SESSION_ID"] = session_id
            process = subprocess.Popen(
                [self.shell, "-i"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=str(target_cwd),
                env=env,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            os.close(slave_fd)

        session = TerminalSession(
            id=session_id,
            actor=actor,
            cwd=str(target_cwd),
            created_at=utc_now(),
            process=process,
            master_fd=master_fd,
            log_path=log_path,
            metadata_path=metadata_path,
        )
        self._persist(session)

        reader = threading.Thread(
            target=self._reader_loop,
            args=(session,),
            name=f"devpilot-terminal-{session_id[:8]}",
            daemon=True,
        )
        session.reader = reader
        with self._lock:
            self._sessions[session_id] = session
        reader.start()
        return session.public()

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            sessions = list(self._sessions.values())
        return [session.public() for session in sorted(sessions, key=lambda item: item.created_at, reverse=True)]

    def get(self, session_id: str) -> TerminalSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFound(session_id)
        self._refresh_state(session)
        return session

    def send_input(self, session_id: str, data: str) -> dict[str, Any]:
        session = self.get(session_id)
        if session.state != "running":
            raise RuntimeError("Sessão de terminal não está ativa")
        payload = data.encode("utf-8", errors="replace")
        if not payload:
            return session.public()
        try:
            os.write(session.master_fd, payload)
        except OSError as error:
            self._refresh_state(session)
            raise RuntimeError("Não foi possível enviar dados ao terminal") from error
        with session.lock:
            session.last_activity_at = utc_now()
        self._persist(session)
        return session.public()

    def output(self, session_id: str, *, after: int = 0) -> dict[str, Any]:
        session = self.get(session_id)
        with session.lock:
            chunks = list(session.chunks)
            earliest = chunks[0][0] if chunks else session.sequence + 1
            selected = [{"sequence": seq, "text": text} for seq, text in chunks if seq > after]
            return {
                "session": session.public(),
                "chunks": selected,
                "last_sequence": session.sequence,
                "truncated": bool(chunks and after and after < earliest - 1),
            }

    def resize(self, session_id: str, *, columns: int, rows: int) -> dict[str, Any]:
        session = self.get(session_id)
        self._resize_pty(session.master_fd, columns=columns, rows=rows)
        return session.public()

    def close(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        if session.state == "running":
            self._terminate_process(session)
        self._refresh_state(session)
        return session.public()

    def close_all(self) -> None:
        with self._lock:
            ids = list(self._sessions)
        for session_id in ids:
            try:
                self.close(session_id)
            except Exception:
                continue

    def system_snapshot(self) -> dict[str, Any]:
        memory = self._memory_snapshot()
        disk = shutil.disk_usage("/")
        try:
            load_1, load_5, load_15 = os.getloadavg()
        except OSError:
            load_1 = load_5 = load_15 = 0.0
        uptime_seconds = None
        try:
            uptime_seconds = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
        except (OSError, ValueError, IndexError):
            pass
        with self._lock:
            active = sum(1 for session in self._sessions.values() if session.state == "running")
        return {
            "hostname": os.uname().nodename,
            "kernel": os.uname().release,
            "machine": os.uname().machine,
            "pid": os.getpid(),
            "uptime_seconds": uptime_seconds,
            "load": {"1m": load_1, "5m": load_5, "15m": load_15},
            "memory": memory,
            "disk_root": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
            },
            "active_terminal_sessions": active,
        }

    def _reader_loop(self, session: TerminalSession) -> None:
        try:
            with session.log_path.open("ab", buffering=0) as log_file:
                while True:
                    self._refresh_state(session)
                    readable, _, _ = select.select([session.master_fd], [], [], 0.15)
                    if readable:
                        try:
                            chunk = os.read(session.master_fd, 65536)
                        except OSError:
                            chunk = b""
                        if chunk:
                            log_file.write(chunk)
                            text = chunk.decode("utf-8", errors="replace")
                            with session.lock:
                                session.sequence += 1
                                session.chunks.append((session.sequence, text))
                                session.last_activity_at = utc_now()
                            self._persist(session)
                            continue
                    if session.process.poll() is not None:
                        break
        finally:
            if session.process.poll() is None:
                self._terminate_process(session)
            self._refresh_state(session, force_closed=True)
            try:
                os.close(session.master_fd)
            except OSError:
                pass

    def _refresh_state(self, session: TerminalSession, *, force_closed: bool = False) -> None:
        exit_code = session.process.poll()
        if exit_code is None and not force_closed:
            return
        with session.lock:
            if session.state == "closed":
                return
            session.state = "closed"
            session.exit_code = exit_code
            session.closed_at = session.closed_at or utc_now()
            session.last_activity_at = session.closed_at
        self._persist(session)

    def _terminate_process(self, session: TerminalSession) -> None:
        try:
            os.killpg(session.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            session.process.wait(timeout=2.0)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(session.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        try:
            session.process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass

    def _persist(self, session: TerminalSession) -> None:
        with session.lock:
            metadata = session.public()
            temporary = session.metadata_path.with_name(
                f".{session.metadata_path.name}.{threading.get_ident()}.tmp"
            )
            temporary.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            os.replace(temporary, session.metadata_path)

    @staticmethod
    def _resize_pty(fd: int, *, columns: int, rows: int) -> None:
        import fcntl
        import struct
        import termios

        columns = max(20, min(int(columns), 400))
        rows = max(5, min(int(rows), 200))
        size = struct.pack("HHHH", rows, columns, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)

    @staticmethod
    def _memory_snapshot() -> dict[str, int | None]:
        values: dict[str, int] = {}
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, raw = line.split(":", 1)
                amount = int(raw.strip().split()[0]) * 1024
                values[key] = amount
        except (OSError, ValueError, IndexError):
            return {"total": None, "available": None, "used": None}
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        used = total - available if total is not None and available is not None else None
        return {"total": total, "available": available, "used": used}

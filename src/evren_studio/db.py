"""SQLite yerel veritabanÄ±.

Tablolar:
- chats / messages : sohbet geÃ§miÅŸi
- error_records    : kalÄ±cÄ± hata kayÄ±tlarÄ± (hata kataloÄŸunun veri boyutu)
- monitor_sessions / monitor_checks : izleme ajanÄ± olaylarÄ±
- model_health     : model baÅŸÄ±na son test ve saÄŸlÄ±k durumu
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'Yeni sohbet',
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    reasoning TEXT,
    model TEXT,
    request_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS error_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    app_version TEXT,
    operation TEXT NOT NULL,
    model TEXT,
    api_path TEXT,
    http_status INTEGER,
    error_code TEXT,
    message TEXT NOT NULL,
    request_id TEXT,
    retry_after TEXT,
    monitor_state TEXT,
    context TEXT,
    attempted_fix TEXT,
    fix_result TEXT,
    next_steps TEXT,
    signature TEXT
);
CREATE TABLE IF NOT EXISTS monitor_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    target_url TEXT NOT NULL,
    interval_minutes INTEGER NOT NULL,
    duration_minutes INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    last_check_at TEXT,
    remaining_minutes INTEGER
);
CREATE TABLE IF NOT EXISTS monitor_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES monitor_sessions(id) ON DELETE CASCADE,
    checked_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    ok INTEGER NOT NULL,
    detail TEXT,
    content_hash TEXT,
    change_detected INTEGER NOT NULL DEFAULT 0,
    change_summary TEXT
);
CREATE TABLE IF NOT EXISTS model_health (
    model TEXT PRIMARY KEY,
    last_test_at TEXT,
    healthy INTEGER,
    last_http_status INTEGER,
    last_error TEXT,
    latency_ms INTEGER
);
"""


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ErrorRecord:
    operation: str
    message: str
    created_at: str = ""
    app_version: str = ""
    model: str | None = None
    api_path: str | None = None
    http_status: int | None = None
    error_code: str | None = None
    request_id: str | None = None
    retry_after: str | None = None
    monitor_state: str | None = None
    context: str | None = None
    attempted_fix: str | None = None
    fix_result: str | None = None
    next_steps: str | None = None
    signature: str | None = None


class Database:
    """TÃ¼m yerel veri eriÅŸimi bu sÄ±nÄ±ftan geÃ§er."""

    def __init__(self, db_path: Path):
        self.path = db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.RLock()
        self.conn.row_factory = sqlite3.Row
        self._exec("PRAGMA foreign_keys = ON")
        self._script(SCHEMA)
        self._exec(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self._commit()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self.conn.execute(sql, params)

    def _commit(self) -> None:
        with self._lock:
            self.conn.commit()

    def _script(self, sql: str) -> None:
        with self._lock:
            self.conn.executescript(sql)

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    # ---- Sohbetler -------------------------------------------------

    def create_chat(self, model: str, title: str = "Yeni sohbet") -> int:
        now = utcnow_iso()
        cur = self._exec(
            "INSERT INTO chats(title, model, created_at, updated_at) VALUES(?,?,?,?)",
            (title, model, now, now),
        )
        self._commit()
        return int(cur.lastrowid)

    def rename_chat(self, chat_id: int, title: str) -> None:
        self._exec(
            "UPDATE chats SET title=?, updated_at=? WHERE id=?",
            (title, utcnow_iso(), chat_id),
        )
        self._commit()

    def delete_chat(self, chat_id: int) -> None:
        self._exec("DELETE FROM chats WHERE id=?", (chat_id,))
        self._commit()

    def list_chats(self, search: str = "") -> list[sqlite3.Row]:
        if search:
            like = f"%{search}%"
            return self._exec(
                "SELECT * FROM chats WHERE title LIKE ? ORDER BY updated_at DESC",
                (like,),
            ).fetchall()
        return self._exec(
            "SELECT * FROM chats ORDER BY updated_at DESC"
        ).fetchall()

    def add_message(
        self,
        chat_id: int,
        role: str,
        content: str,
        model: str | None = None,
        reasoning: str | None = None,
        request_id: str | None = None,
    ) -> int:
        self._exec(
            "INSERT INTO messages(chat_id, role, content, reasoning, model, request_id, created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (chat_id, role, content, reasoning, model, request_id, utcnow_iso()),
        )
        self._exec(
            "UPDATE chats SET updated_at=? WHERE id=?", (utcnow_iso(), chat_id)
        )
        self._commit()
        cur = self._exec("SELECT last_insert_rowid()")
        return int(cur.fetchone()[0])

    def get_messages(self, chat_id: int) -> list[sqlite3.Row]:
        return self._exec(
            "SELECT * FROM messages WHERE chat_id=? ORDER BY id", (chat_id,)
        ).fetchall()

    # ---- Hata kayÄ±tlarÄ± ----------------------------------------------

    def add_error(self, rec: ErrorRecord) -> int:
        if not rec.created_at:
            rec.created_at = utcnow_iso()
        cur = self._exec(
            "INSERT INTO error_records(created_at, app_version, operation, model, api_path,"
            " http_status, error_code, message, request_id, retry_after, monitor_state,"
            " context, attempted_fix, fix_result, next_steps, signature)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec.created_at, rec.app_version, rec.operation, rec.model, rec.api_path,
                rec.http_status, rec.error_code, rec.message, rec.request_id,
                rec.retry_after, rec.monitor_state, rec.context, rec.attempted_fix,
                rec.fix_result, rec.next_steps, rec.signature,
            ),
        )
        self._commit()
        return int(cur.lastrowid)

    def update_error_fix(self, error_id: int, attempted_fix: str, fix_result: str,
                         next_steps: str) -> None:
        self._exec(
            "UPDATE error_records SET attempted_fix=?, fix_result=?, next_steps=? WHERE id=?",
            (attempted_fix, fix_result, next_steps, error_id),
        )
        self._commit()

    def list_errors(self, limit: int = 200) -> list[sqlite3.Row]:
        return self._exec(
            "SELECT * FROM error_records ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def find_similar_errors(self, signature: str, limit: int = 5) -> list[sqlite3.Row]:
        """AynÄ± imzalÄ± geÃ§miÅŸ hatalarÄ± bulur (kurtarma rehberi aramasÄ±)."""
        return self._exec(
            "SELECT * FROM error_records WHERE signature=? ORDER BY id DESC LIMIT ?",
            (signature, limit),
        ).fetchall()

    def purge_old_errors(self, retention_days: int) -> int:
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat(
            timespec="seconds"
        )
        cur = self._exec("DELETE FROM error_records WHERE created_at < ?", (cutoff,))
        self._commit()
        return cur.rowcount

    # ---- Ä°zleme ajanÄ± -------------------------------------------------

    def start_monitor_session(self, target_url: str, interval_minutes: int,
                              duration_minutes: int) -> int:
        cur = self._exec(
            "INSERT INTO monitor_sessions(started_at, target_url, interval_minutes,"
            " duration_minutes, status) VALUES(?,?,?,?, 'running')",
            (utcnow_iso(), target_url, interval_minutes, duration_minutes),
        )
        self._commit()
        return int(cur.lastrowid)

    def finish_monitor_session(self, session_id: int, status: str) -> None:
        self._exec(
            "UPDATE monitor_sessions SET ended_at=?, status=? WHERE id=?",
            (utcnow_iso(), status, session_id),
        )
        self._commit()

    def get_open_monitor_session(self) -> sqlite3.Row | None:
        """Uygulama kapandÄ±ysa kaldÄ±ÄŸÄ± izlemeyi bulur (devam seÃ§eneÄŸi iÃ§in)."""
        return self._exec(
            "SELECT * FROM monitor_sessions WHERE status='running' ORDER BY id DESC LIMIT 1"
        ).fetchone()

    def add_monitor_check(self, session_id: int, kind: str, ok: bool, detail: str,
                          content_hash: str | None = None,
                          change_detected: bool = False,
                          change_summary: str | None = None,
                          checked_at: str = "") -> int:
        self._exec(
            "INSERT INTO monitor_checks(session_id, checked_at, kind, ok, detail,"
            " content_hash, change_detected, change_summary) VALUES(?,?,?,?,?,?,?,?)",
            (
                session_id, checked_at or utcnow_iso(), kind, int(ok), detail,
                content_hash, int(change_detected), change_summary,
            ),
        )
        self._exec(
            "UPDATE monitor_sessions SET last_check_at=? WHERE id=?",
            (utcnow_iso(), session_id),
        )
        self._commit()
        cur = self._exec("SELECT last_insert_rowid()")
        return int(cur.fetchone()[0])

    def last_monitor_hash(self, session_id: int) -> str | None:
        row = self._exec(
            "SELECT content_hash FROM monitor_checks WHERE session_id=? AND kind='announcement'"
            " AND content_hash IS NOT NULL ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return row["content_hash"] if row else None

    def list_monitor_checks(self, session_id: int) -> list[sqlite3.Row]:
        return self._exec(
            "SELECT * FROM monitor_checks WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()

    # ---- Model saÄŸlÄ±ÄŸÄ± --------------------------------------------------

    def upsert_model_health(self, model: str, healthy: bool,
                            http_status: int | None = None, error: str | None = None,
                            latency_ms: int | None = None) -> None:
        self._exec(
            "INSERT INTO model_health(model, last_test_at, healthy, last_http_status,"
            " last_error, latency_ms) VALUES(?,?,?,?,?,?)"
            " ON CONFLICT(model) DO UPDATE SET last_test_at=excluded.last_test_at,"
            " healthy=excluded.healthy, last_http_status=excluded.last_http_status,"
            " last_error=excluded.last_error, latency_ms=excluded.latency_ms",
            (model, utcnow_iso(), int(healthy), http_status, error, latency_ms),
        )
        self._commit()

    def get_model_health(self, model: str) -> sqlite3.Row | None:
        return self._exec(
            "SELECT * FROM model_health WHERE model=?", (model,)
        ).fetchone()

    def all_model_health(self) -> list[sqlite3.Row]:
        return self._exec("SELECT * FROM model_health ORDER BY model").fetchall()

    # ---- DÄ±ÅŸa aktarma -----------------------------------------------------

    def export_chat_markdown(self, chat_id: int) -> str:
        chat = self._exec("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
        if not chat:
            return ""
        lines = [
            f"# {chat['title']}",
            "",
            f"- Model: {chat['model']}",
            f"- OluÅŸturulma: {chat['created_at']}",
            "",
        ]
        role_labels = {"user": "KullanÄ±cÄ±", "assistant": "Asistan", "system": "Sistem"}
        for msg in self.get_messages(chat_id):
            lines.append(f"## {role_labels.get(msg['role'], msg['role'])}")
            lines.append("")
            lines.append(msg["content"] or "")
            lines.append("")
        return "\n".join(lines)

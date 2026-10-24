"""SQLite yerel veritabanı.

Tablolar:
- chats / messages : sohbet geçmişi
- error_records    : kalıcı hata kayıtları (hata kataloğunun veri boyutu)
- monitor_sessions / monitor_checks : izleme ajanı olayları
- model_health     : model başına son test ve sağlık durumu
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 3

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
CREATE TABLE IF NOT EXISTS model_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    model TEXT NOT NULL,
    role TEXT,
    ok INTEGER NOT NULL DEFAULT 1,
    error_kind TEXT,
    duration_s REAL,
    first_chunk_s REAL,
    out_tokens INTEGER,
    empty INTEGER NOT NULL DEFAULT 0,
    event TEXT,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_model_calls_at ON model_calls(at);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'Yeni oturum',
    workspace TEXT,
    model TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'onayli',
    protocol TEXT,
    todos TEXT,
    pinned INTEGER NOT NULL DEFAULT 0,
    legacy_chat_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    reasoning TEXT,
    tool_calls TEXT,
    tool_call_id TEXT,
    name TEXT,
    meta TEXT,
    model TEXT,
    request_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_session_messages ON session_messages(session_id, id);
CREATE TABLE IF NOT EXISTS project_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    workspace TEXT,
    status TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    session_id INTEGER,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_usage_costs_time ON usage_costs(created_at);
CREATE TABLE IF NOT EXISTS file_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    turn_id INTEGER,
    path TEXT NOT NULL,
    before_text TEXT,
    after_text TEXT,
    reverted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _Result:
    """Kilit altında okunmuş sorgu sonucu (sqlite3.Cursor'un kullanılan kısmı)."""

    def __init__(self, lastrowid: int | None, rowcount: int, rows: list):
        self.lastrowid = lastrowid
        self.rowcount = rowcount
        self._rows = rows

    def fetchall(self) -> list:
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


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
    """Tüm yerel veri erişimi bu sınıftan geçer."""

    def __init__(self, db_path: Path):
        self.path = db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.RLock()
        self.conn.row_factory = sqlite3.Row
        self._exec("PRAGMA foreign_keys = ON")
        self._script(SCHEMA)
        row = self._exec("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        version = int(row["value"]) if row else None
        if version is not None and version < 2:
            self._migrate_chats_to_sessions()
        # v3: oturum başına sağlayıcı (eski oturumlar EVREN)
        cols = {r["name"] for r in self._exec("PRAGMA table_info(sessions)").fetchall()}
        if "provider" not in cols:
            self._exec("ALTER TABLE sessions ADD COLUMN provider TEXT NOT NULL DEFAULT 'evren'")
        self._exec(
            "INSERT INTO meta(key, value) VALUES('schema_version', ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
        self._commit()

    def _migrate_chats_to_sessions(self) -> None:
        """v1 → v2: eski sohbetleri klasörsüz oturum olarak kopyalar (eskiler silinmez)."""
        for chat in self._exec("SELECT * FROM chats ORDER BY id").fetchall():
            exists = self._exec(
                "SELECT 1 FROM sessions WHERE legacy_chat_id=?", (chat["id"],)
            ).fetchone()
            if exists:
                continue
            cur = self._exec(
                "INSERT INTO sessions(title, workspace, model, mode, legacy_chat_id,"
                " created_at, updated_at) VALUES(?, NULL, ?, 'onayli', ?, ?, ?)",
                (chat["title"], chat["model"], chat["id"], chat["created_at"],
                 chat["updated_at"]),
            )
            sid = cur.lastrowid
            self._exec(
                "INSERT INTO session_messages(session_id, role, content, reasoning,"
                " model, request_id, created_at)"
                " SELECT ?, role, content, reasoning, model, request_id, created_at"
                " FROM messages WHERE chat_id=? ORDER BY id",
                (sid, chat["id"]),
            )

    def _exec(self, sql: str, params: tuple = ()) -> "_Result":
        # Satırlar kilit altında okunur: ajan iş parçacığı yazarken arayüz
        # iş parçacığı güvenle okuyabilir.
        with self._lock:
            cur = self.conn.execute(sql, params)
            rows = cur.fetchall() if cur.description else []
            return _Result(cur.lastrowid, cur.rowcount, rows)

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

    # ---- Hata kayıtları ----------------------------------------------

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
        """Aynı imzalı geçmiş hataları bulur (kurtarma rehberi araması)."""
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

    # ---- İzleme ajanı -------------------------------------------------

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
        """Uygulama kapandıysa kaldığı izlemeyi bulur (devam seçeneği için)."""
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

    # ---- Model sağlığı --------------------------------------------------

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

    # ---- Auto Pro gerçek kullanım kaydı (A1, agent/modelstats.py) ----------

    MODEL_CALLS_KEEP_DAYS = 7

    def add_model_call(self, model: str, *, role: str | None = None, ok: bool = True,
                       error_kind: str | None = None, duration_s: float | None = None,
                       first_chunk_s: float | None = None, out_tokens: int | None = None,
                       empty: bool = False, event: str | None = None, detail: str | None = None) -> None:
        """Bir model çağrısı (veya `event="switch"` yedeğe geçiş) kaydı. Eski kayıtlar budanır."""
        self._exec(
            "INSERT INTO model_calls(at, model, role, ok, error_kind, duration_s, first_chunk_s, out_tokens,"
            " empty, event, detail) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (utcnow_iso(), model, role, int(ok), error_kind, duration_s, first_chunk_s, out_tokens,
             int(empty), event, (detail or "")[:300] or None),
        )
        self._exec("DELETE FROM model_calls WHERE at < strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)",
                   (f"-{self.MODEL_CALLS_KEEP_DAYS} days",))
        self._commit()

    def recent_model_calls(self, hours: float = 6.0, model: str | None = None) -> list[dict]:
        # `at` ISO biçiminde (T ayraçlı): SQLite datetime() boşluklu döndürür, metin karşılaştırması
        # aynı günün tüm kayıtlarını "yeni" sayardı → aynı biçimle karşılaştır.
        sql = "SELECT * FROM model_calls WHERE at >= strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)"
        params: tuple = (f"-{float(hours)} hours",)
        if model:
            sql += " AND model=?"
            params += (model,)
        return [dict(r) for r in self._exec(sql + " ORDER BY id", params).fetchall()]

    def marked_bad_messages(self) -> set[int]:
        """A5: 👎 ile işaretlenmiş yanıtların mesaj kimlikleri (detail = "mesaj:<id>")."""
        rows = self._exec("SELECT detail FROM model_calls WHERE event='feedback_bad' AND detail LIKE 'mesaj:%'")
        out = set()
        for r in rows.fetchall():
            try:
                out.add(int(str(r["detail"]).split(":", 1)[1]))
            except (ValueError, IndexError):
                pass
        return out

    def get_model_health(self, model: str) -> sqlite3.Row | None:
        return self._exec(
            "SELECT * FROM model_health WHERE model=?", (model,)
        ).fetchone()

    def all_model_health(self) -> list[sqlite3.Row]:
        return self._exec("SELECT * FROM model_health ORDER BY model").fetchall()

    # ---- Dışa aktarma -----------------------------------------------------

    def export_chat_markdown(self, chat_id: int) -> str:
        chat = self._exec("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
        if not chat:
            return ""
        lines = [
            f"# {chat['title']}",
            "",
            f"- Model: {chat['model']}",
            f"- Oluşturulma: {chat['created_at']}",
            "",
        ]
        role_labels = {"user": "Kullanıcı", "assistant": "Asistan", "system": "Sistem"}
        for msg in self.get_messages(chat_id):
            lines.append(f"## {role_labels.get(msg['role'], msg['role'])}")
            lines.append("")
            lines.append(msg["content"] or "")
            lines.append("")
        return "\n".join(lines)

    # ---- Oturumlar (sohbet + kod ajanı) -------------------------------------

    def create_session(self, model: str, workspace: str | None = None,
                       mode: str = "manuel", title: str = "Yeni oturum",
                       provider: str = "evren") -> int:
        now = utcnow_iso()
        cur = self._exec(
            "INSERT INTO sessions(title, workspace, model, mode, provider, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (title, workspace, model, mode, provider, now, now),
        )
        self._commit()
        return int(cur.lastrowid)

    def get_session(self, session_id: int) -> sqlite3.Row | None:
        return self._exec("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()

    def list_sessions(self, search: str = "", limit: int = 500) -> list[sqlite3.Row]:
        if search:
            like = f"%{search}%"
            return self._exec(
                "SELECT * FROM sessions WHERE title LIKE ? OR workspace LIKE ?"
                " OR id IN (SELECT session_id FROM session_messages WHERE content LIKE ?)"
                " ORDER BY pinned DESC, updated_at DESC LIMIT ?",
                (like, like, like, limit),
            ).fetchall()
        return self._exec(
            "SELECT * FROM sessions ORDER BY pinned DESC, updated_at DESC LIMIT ?", (limit,)
        ).fetchall()

    def update_session(self, session_id: int, **fields: Any) -> None:
        allowed = {"title", "workspace", "model", "mode", "protocol", "pinned", "provider"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        cols = ", ".join(f"{k}=?" for k in sets)
        self._exec(
            f"UPDATE sessions SET {cols}, updated_at=? WHERE id=?",
            (*sets.values(), utcnow_iso(), session_id),
        )
        self._commit()

    def delete_session(self, session_id: int) -> None:
        self._exec("DELETE FROM sessions WHERE id=?", (session_id,))
        self._commit()

    def set_session_todos(self, session_id: int, todos: list[dict]) -> None:
        self._exec(
            "UPDATE sessions SET todos=?, updated_at=? WHERE id=?",
            (json.dumps(todos, ensure_ascii=False), utcnow_iso(), session_id),
        )
        self._commit()

    def get_session_todos(self, session_id: int) -> list[dict]:
        row = self.get_session(session_id)
        if not row or not row["todos"]:
            return []
        try:
            return json.loads(row["todos"])
        except json.JSONDecodeError:
            return []

    def add_session_message(self, session_id: int, role: str, content: str, *,
                            reasoning: str | None = None,
                            tool_calls: list[dict] | None = None,
                            tool_call_id: str | None = None,
                            name: str | None = None,
                            meta: dict | None = None,
                            model: str | None = None,
                            request_id: str | None = None) -> int:
        now = utcnow_iso()
        cur = self._exec(
            "INSERT INTO session_messages(session_id, role, content, reasoning, tool_calls,"
            " tool_call_id, name, meta, model, request_id, created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                session_id, role, content or "", reasoning,
                json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                tool_call_id, name,
                json.dumps(meta, ensure_ascii=False) if meta else None,
                model, request_id, now,
            ),
        )
        self._exec("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        self._commit()
        return int(cur.lastrowid)

    def get_session_messages(self, session_id: int) -> list[dict[str, Any]]:
        rows = self._exec(
            "SELECT * FROM session_messages WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for key in ("tool_calls", "meta"):
                if d.get(key):
                    try:
                        d[key] = json.loads(d[key])
                    except json.JSONDecodeError:
                        d[key] = None
            out.append(d)
        return out

    def delete_session_messages_from(self, session_id: int, message_id: int) -> None:
        """Bir mesajdan itibaren sonrasını siler (mesajı düzenleyip yeniden gönderme)."""
        self._exec(
            "DELETE FROM session_messages WHERE session_id=? AND id>=?",
            (session_id, message_id),
        )
        self._commit()

    def add_file_change(self, session_id: int, turn_id: int | None, rel_path: str,
                        before: str | None, after: str | None) -> int:
        cur = self._exec(
            "INSERT INTO file_changes(session_id, turn_id, path, before_text, after_text,"
            " created_at) VALUES(?,?,?,?,?,?)",
            (session_id, turn_id, rel_path, before, after, utcnow_iso()),
        )
        self._commit()
        return int(cur.lastrowid)

    def list_file_changes(self, session_id: int) -> list[sqlite3.Row]:
        return self._exec(
            "SELECT * FROM file_changes WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()

    def get_file_change(self, change_id: int) -> sqlite3.Row | None:
        return self._exec("SELECT * FROM file_changes WHERE id=?", (change_id,)).fetchone()

    def mark_change_reverted(self, change_id: int) -> None:
        self._exec("UPDATE file_changes SET reverted=1 WHERE id=?", (change_id,))
        self._commit()

    def export_session_markdown(self, session_id: int) -> str:
        s = self.get_session(session_id)
        if not s:
            return ""
        lines = [f"# {s['title']}", "", f"- Model: {s['model']}"]
        if s["workspace"]:
            lines.append(f"- Proje: `{s['workspace']}`")
        lines += [f"- Oluşturulma: {s['created_at']}", ""]
        labels = {"user": "Kullanıcı", "assistant": "Asistan", "summary": "Özet"}
        for m in self.get_session_messages(session_id):
            if m["role"] == "tool":
                summary = (m.get("meta") or {}).get("summary") or m.get("name")
                lines += [f"> Araç: {summary}", ""]
                continue
            lines += [f"## {labels.get(m['role'], m['role'])}", "", m["content"] or ""]
            for c in m.get("tool_calls") or []:
                lines.append(f"- araç çağrısı: `{c.get('name')}` {c.get('arguments', '')[:200]}")
            lines.append("")
        return "\n".join(lines)

    # ---- Tahmini maliyet (ücretli sağlayıcılar) -----------------------------

    def add_usage_cost(self, provider: str, model: str, usage: dict[str, int], cost_usd: float,
                       session_id: int | None = None) -> int:
        cur = self._exec(
            "INSERT INTO usage_costs(created_at, session_id, provider, model, input_tokens,"
            " output_tokens, cached_tokens, cost_usd) VALUES(?,?,?,?,?,?,?,?)",
            (utcnow_iso(), session_id, provider, model, int(usage.get("input_tokens") or 0),
             int(usage.get("output_tokens") or 0), int(usage.get("cached_tokens") or 0), float(cost_usd)),
        )
        self._commit()
        return int(cur.lastrowid)

    # ---- proje ajanı (agent/project.py, ui/project_ui.py) ----

    def add_project_run(self, session_id: int | None, workspace: str | None, status: str,
                        state_json: str) -> int:
        now = utcnow_iso()
        cur = self._exec(
            "INSERT INTO project_runs(session_id, workspace, status, state_json, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?)", (session_id, workspace, status, state_json, now, now))
        self._commit()
        return int(cur.lastrowid)

    def update_project_run(self, run_id: int, status: str, state_json: str) -> None:
        self._exec("UPDATE project_runs SET status=?, state_json=?, updated_at=? WHERE id=?",
                   (status, state_json, utcnow_iso(), run_id))
        self._commit()

    def latest_project_run(self, session_id: int) -> sqlite3.Row | None:
        return self._exec("SELECT * FROM project_runs WHERE session_id=? ORDER BY id DESC LIMIT 1",
                          (session_id,)).fetchone()

    def month_spend(self, month_prefix: str | None = None) -> dict[str, float]:
        """{sağlayıcı: USD} — month_prefix 'YYYY-MM' (UTC); varsayılan bu ay."""
        prefix = month_prefix or utcnow_iso()[:7]
        rows = self._exec(
            "SELECT provider, SUM(cost_usd) AS total FROM usage_costs WHERE created_at LIKE ?"
            " GROUP BY provider", (prefix + "%",),
        ).fetchall()
        return {r["provider"]: float(r["total"] or 0) for r in rows}

    def wipe_user_data(self) -> None:
        self._script(
            "DELETE FROM session_messages; DELETE FROM file_changes; DELETE FROM sessions;"
            " DELETE FROM usage_costs; DELETE FROM project_runs;"
            " DELETE FROM messages; DELETE FROM chats;"
            " DELETE FROM error_records; DELETE FROM monitor_checks;"
            " DELETE FROM monitor_sessions; DELETE FROM model_health;"
        )
        self._commit()

"""SQLite yerel veritabanı.

Tablolar:
- chats / messages : sohbet geçmişi
- error_records    : kalıcı hata kayıtları (hata kataloğunun veri boyutu)
- monitor_sessions / monitor_checks : izleme ajanı olayları
- model_health     : model başına son test ve sağlık durumu
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 3

# ---- dosya geçmişi sıkıştırma (2026-11-12, kullanıcı onayı) -------------------------------------------------------
# Ajanın her dosya değişikliği dosyanın TAM önceki/sonraki hâlini saklar; gerçek veritabanında bu metin 12,7 MB'ın
# 8,4 MB'ıydı. Yeni kayıtlar zlib ile sıkıştırılmış BLOB olarak yazılır (gerçek veride 3,3 kat küçük). Okurken açılır:
# çağıranlar aynı `before_text` / `after_text` METNİNİ görür. Eski (TEXT) kayıtlar okunmaya devam eder
# ve açılıştan sonra arka planda dönüştürülür (`pack_file_changes`). NULL = dosya yoktu / silindi; NULL olarak kalır.
# Açma Python'da yapılır (SQL işlevi DEĞİL): tek başına vekil karakter içeren metni SQLite metin olarak döndüremez;
# böylece her metin birebir korunur. list_file_changes / get_file_change sözlük döndürür (aynı anahtarlar).
# Bilinen kısıt: 0.5.0'a geri dönülürse eski sürüm sıkıştırılmış kayıtları açamaz (hata verir; dosyaya içerik yazmaz).
PACK_MAGIC = b"EZ1"
PACK_DONE_KEY = "dosya_gecmisi_sikistirma"


def pack_text(text: str | None) -> bytes | None:
    if text is None:
        return None
    return PACK_MAGIC + zlib.compress(text.encode("utf-8", "surrogatepass"), 6)


def unpack_text(value: Any) -> str | None:
    """BLOB (sıkıştırılmış) → metin; eski TEXT ve NULL aynen."""
    if value is None or isinstance(value, str):
        return value
    data = bytes(value)
    if data.startswith(PACK_MAGIC):
        return zlib.decompress(data[len(PACK_MAGIC):]).decode("utf-8", "surrogatepass")
    return data.decode("utf-8", "surrogatepass")


def _pack_verified(text: str) -> bytes | None:
    """Sıkıştırır ve hemen geri açıp karşılaştırır; tutmazsa None (satıra dokunulmaz — veri kaybı olmaz)."""
    packed = pack_text(text)
    try:
        return packed if unpack_text(packed) == text else None
    except (zlib.error, UnicodeDecodeError):
        return None


def _change_row(row: sqlite3.Row) -> dict[str, Any]:
    """Dosya değişikliği satırı, içerikler açılmış (anahtarlar eski `SELECT *` ile aynı)."""
    d = dict(row)
    d["before_text"] = unpack_text(d.get("before_text"))
    d["after_text"] = unpack_text(d.get("after_text"))
    return d

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
-- Madde 14 motor karnesi (2026-11-06): belirlenmiş ölçüm günlerinde gerçek görev paketiyle ölçülen puan.
-- good_day = ölçüm anında hafif yoklama motoru "iyi" buldu mu (yalnız iyi gün ölçümleri gerçek puan sayılır).
CREATE TABLE IF NOT EXISTS model_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    model TEXT NOT NULL,
    suite TEXT NOT NULL,
    score REAL NOT NULL,
    good_day INTEGER NOT NULL DEFAULT 1,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_model_scores_model ON model_scores(model);
CREATE TABLE IF NOT EXISTS skills (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    folder TEXT NOT NULL,
    source TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    scope TEXT NOT NULL DEFAULT 'tum',
    projects TEXT,
    checker TEXT,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    model TEXT,
    mode TEXT,
    skills TEXT,
    instructions TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    profile TEXT,
    created_at TEXT NOT NULL
);
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
-- Zamanlanmış görevler (Madde 12c, 2026-11-05; Claude Code masaüstü "Scheduled tasks" örnek alındı)
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL,
    workspace TEXT,
    model TEXT NOT NULL DEFAULT 'auto-pro',
    mode TEXT NOT NULL DEFAULT 'auto',
    kind TEXT NOT NULL DEFAULT 'daily',
    time_hm TEXT NOT NULL DEFAULT '09:00',
    weekday INTEGER NOT NULL DEFAULT 0,
    cron TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    last_handled_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scheduled_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES scheduled_tasks(id) ON DELETE CASCADE,
    scheduled_for TEXT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    session_id INTEGER,
    catch_up INTEGER NOT NULL DEFAULT 0,
    manual INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_scheduled_runs ON scheduled_runs(task_id, id);
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


def _is_network_path(path: Path) -> bool:
    """UNC yolu (\\\\sunucu\\paylasim) ya da eşlenmiş ağ sürücüsü (Z:) mi? SQLite'ın WAL kipi ağ dosya sisteminde güvenli
    çalışmaz (Ayarlar'da veri klasörü başka yere taşınabilir)."""
    p = str(path)
    if p.startswith(("\\\\", "//")):
        return True
    drive = Path(p).drive
    if os.name != "nt" or not drive.endswith(":"):
        return False
    try:
        import ctypes
        return ctypes.windll.kernel32.GetDriveTypeW(drive + "\\") == 4      # DRIVE_REMOTE
    except (AttributeError, OSError):
        return False


class Database:
    """Tüm yerel veri erişimi bu sınıftan geçer."""

    def __init__(self, db_path: Path):
        self.path = db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.RLock()
        self.conn.row_factory = sqlite3.Row
        self._exec("PRAGMA foreign_keys = ON")
        self.journal_mode = self._set_journal_mode()
        self._script(SCHEMA)
        row = self._exec("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        version = int(row["value"]) if row else None
        if version is not None and version < 2:
            self._migrate_chats_to_sessions()
        # v3: oturum başına sağlayıcı (eski oturumlar EVREN)
        cols = {r["name"] for r in self._exec("PRAGMA table_info(sessions)").fetchall()}
        if "provider" not in cols:
            self._exec("ALTER TABLE sessions ADD COLUMN provider TEXT NOT NULL DEFAULT 'evren'")
        # F4 (2026-10-24): oturuma bağlı ajan profili (E5); eski oturumlar profilsiz
        if "profile" not in cols:
            self._exec("ALTER TABLE sessions ADD COLUMN profile TEXT")
        # Madde 12c (2026-11-05): zamanlanmış görevin başlattığı oturum (görev silinince oturum KALIR)
        if "scheduled_task_id" not in cols:
            self._exec("ALTER TABLE sessions ADD COLUMN scheduled_task_id INTEGER")
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

    # ---- küçük anahtar/değer kayıtları (meta tablosu; ör. kota sonrası otomatik devam planı) ----

    def get_meta(self, key: str) -> str | None:
        row = self._exec("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._exec("INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (key, value))
        self._commit()          # uygulama kapanıp açılınca da okunmalı (R-03)

    def delete_meta(self, key: str) -> None:
        self._exec("DELETE FROM meta WHERE key=?", (key,))
        self._commit()

    def _set_journal_mode(self) -> str:
        """WAL kipi (2026-11-13 ölçümü, 200 mesaj yazmanın ortancası: mesaj başına 3,42 → 0,96 ms). Eski kipte her işlem
        yanında bir -journal dosyası açıp silerdi (Windows'ta virüs tarayıcısı her yeni dosyayı yoklar); WAL'da okuma
        yazmayı beklemez. synchronous FULL kalır: elektrik kesintisinde de son mesaj kaybolmaz (NORMAL 0,06 ms ölçüldü
        ama işletim sistemi çökerse son işlemler geri alınabilir). Ağ sürücüsünde WAL güvenli değildir (paylaşılan
        bellek dosyası) → orada eski kipe (DELETE) döner. Dönüş: etkin kip."""
        want = "DELETE" if _is_network_path(self.path) else "WAL"
        try:
            return str(self._exec(f"PRAGMA journal_mode={want}").fetchone()[0]).lower()
        except sqlite3.DatabaseError:                  # kip değiştirilemedi (salt okunur ortam vb.) → olduğu gibi
            return str(self._exec("PRAGMA journal_mode").fetchone()[0]).lower()

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

    # ---- Madde 14: motor karnesi ------------------------------------------------------------

    def add_model_score(self, model: str, suite: str, score: float, *, good_day: bool = True,
                        details: str | None = None) -> None:
        self._exec("INSERT INTO model_scores(at, model, suite, score, good_day, details) VALUES(?,?,?,?,?,?)",
                   (utcnow_iso(), model, suite, float(score), int(good_day), details))
        self._commit()

    def model_scores(self, days: float = 60.0) -> list[dict]:
        sql = ("SELECT * FROM model_scores WHERE at >= strftime('%Y-%m-%dT%H:%M:%S', 'now', ?) ORDER BY id")
        return [dict(r) for r in self._exec(sql, (f"-{float(days)} days",)).fetchall()]

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

    # ---- F4: skill'ler, profiller, şablonlar ----------------------------------------------

    def list_skills(self) -> list[dict]:
        return [dict(r) for r in self._exec("SELECT * FROM skills ORDER BY name COLLATE NOCASE").fetchall()]

    def upsert_skill(self, row: dict) -> None:
        cols = ["slug", "name", "description", "folder", "source", "enabled", "scope", "projects", "checker"]
        vals = [row.get(c) for c in cols]
        self._exec(
            f"INSERT INTO skills({', '.join(cols)}, added_at) VALUES({', '.join('?' * len(cols))}, ?)"
            " ON CONFLICT(slug) DO UPDATE SET " + ", ".join(f"{c}=excluded.{c}" for c in cols[1:]),
            (*vals, utcnow_iso()))
        self._commit()

    def delete_skill(self, slug: str) -> None:
        self._exec("DELETE FROM skills WHERE slug=?", (slug,))
        self._commit()

    def list_profiles(self) -> list[dict]:
        return [dict(r) for r in self._exec("SELECT * FROM profiles ORDER BY name COLLATE NOCASE").fetchall()]

    def get_profile(self, name: str) -> dict | None:
        r = self._exec("SELECT * FROM profiles WHERE name=?", (name,)).fetchone()
        return dict(r) if r else None

    def save_profile(self, name: str, model: str | None, mode: str | None, skills: str | None,
                     instructions: str | None) -> None:
        self._exec(
            "INSERT INTO profiles(name, model, mode, skills, instructions, created_at) VALUES(?,?,?,?,?,?)"
            " ON CONFLICT(name) DO UPDATE SET model=excluded.model, mode=excluded.mode, skills=excluded.skills,"
            " instructions=excluded.instructions",
            (name, model, mode, skills, instructions, utcnow_iso()))
        self._commit()

    def delete_profile(self, name: str) -> None:
        self._exec("DELETE FROM profiles WHERE name=?", (name,))
        self._exec("UPDATE sessions SET profile=NULL WHERE profile=?", (name,))
        self._commit()

    def list_templates(self) -> list[dict]:
        return [dict(r) for r in self._exec("SELECT * FROM templates ORDER BY id").fetchall()]

    def add_template(self, name: str, prompt: str, profile: str | None = None) -> int:
        cur = self._exec("INSERT INTO templates(name, prompt, profile, created_at) VALUES(?,?,?,?)",
                         (name, prompt, profile, utcnow_iso()))
        self._commit()
        return int(cur.lastrowid)

    def delete_template(self, template_id: int) -> None:
        self._exec("DELETE FROM templates WHERE id=?", (template_id,))
        self._commit()

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
        allowed = {"title", "workspace", "model", "mode", "protocol", "pinned", "provider", "profile",
                   "scheduled_task_id"}
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

    # ---- zamanlanmış görevler (Madde 12c) ----

    TASK_FIELDS = ("name", "description", "prompt", "workspace", "model", "mode", "kind", "time_hm", "weekday",
                   "cron", "enabled", "last_handled_at")

    def create_scheduled_task(self, **fields: Any) -> int:
        now = utcnow_iso()
        data = {k: v for k, v in fields.items() if k in self.TASK_FIELDS}
        cols = ", ".join(list(data) + ["created_at", "updated_at"])
        marks = ", ".join("?" for _ in range(len(data) + 2))
        cur = self._exec(f"INSERT INTO scheduled_tasks({cols}) VALUES({marks})", (*data.values(), now, now))
        self._commit()
        return int(cur.lastrowid)

    def update_scheduled_task(self, task_id: int, **fields: Any) -> None:
        data = {k: v for k, v in fields.items() if k in self.TASK_FIELDS}
        if not data:
            return
        sets = ", ".join(f"{k}=?" for k in data)
        self._exec(f"UPDATE scheduled_tasks SET {sets}, updated_at=? WHERE id=?",
                   (*data.values(), utcnow_iso(), task_id))
        self._commit()

    def delete_scheduled_task(self, task_id: int) -> None:
        """Görev ve geçmişi silinir; başlattığı oturumlar SİLİNMEZ (Claude Code'da da arşivde kalır)."""
        self._exec("UPDATE sessions SET scheduled_task_id=NULL WHERE scheduled_task_id=?", (task_id,))
        self._exec("DELETE FROM scheduled_runs WHERE task_id=?", (task_id,))
        self._exec("DELETE FROM scheduled_tasks WHERE id=?", (task_id,))
        self._commit()

    def get_scheduled_task(self, task_id: int) -> sqlite3.Row | None:
        return self._exec("SELECT * FROM scheduled_tasks WHERE id=?", (task_id,)).fetchone()

    def list_scheduled_tasks(self) -> list[sqlite3.Row]:
        return self._exec("SELECT * FROM scheduled_tasks ORDER BY name COLLATE NOCASE").fetchall()

    def add_scheduled_run(self, task_id: int, status: str, *, scheduled_for: str | None = None,
                          reason: str = "", catch_up: bool = False, manual: bool = False) -> int:
        cur = self._exec(
            "INSERT INTO scheduled_runs(task_id, scheduled_for, status, reason, catch_up, manual, created_at)"
            " VALUES(?, ?, ?, ?, ?, ?, ?)",
            (task_id, scheduled_for, status, reason, int(catch_up), int(manual), utcnow_iso()))
        self._commit()
        return int(cur.lastrowid)

    def update_scheduled_run(self, run_id: int, **fields: Any) -> None:
        allowed = {"status", "reason", "session_id", "started_at", "finished_at"}
        data = {k: v for k, v in fields.items() if k in allowed}
        if not data:
            return
        sets = ", ".join(f"{k}=?" for k in data)
        self._exec(f"UPDATE scheduled_runs SET {sets} WHERE id=?", (*data.values(), run_id))
        self._commit()

    def list_scheduled_runs(self, task_id: int, limit: int = 20, offset: int = 0) -> list[sqlite3.Row]:
        return self._exec("SELECT * FROM scheduled_runs WHERE task_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                          (task_id, limit, offset)).fetchall()

    def count_scheduled_runs(self, task_id: int) -> int:
        return int(self._exec("SELECT COUNT(*) AS n FROM scheduled_runs WHERE task_id=?",
                              (task_id,)).fetchone()["n"])

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
            (session_id, turn_id, rel_path, pack_text(before), pack_text(after), utcnow_iso()),
        )
        self._commit()
        return int(cur.lastrowid)

    def list_file_changes(self, session_id: int) -> list[dict[str, Any]]:
        return [_change_row(r) for r in self._exec(
            "SELECT * FROM file_changes WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()]

    def list_file_change_meta(self, session_id: int) -> list[sqlite3.Row]:
        """Dosya içerikleri OLMADAN değişiklik listesi (sağ panel; 2026-11-12: gerçek oturumda 145 değişiklik = 8,3 MB
        metin her açılışta belleğe alınıyordu). İçerik gerektiğinde `get_file_change` ile tek tek okunur."""
        return self._exec(
            "SELECT id, session_id, turn_id, path, reverted, created_at, before_text IS NULL AS is_new,"
            " after_text IS NULL AS is_deleted FROM file_changes WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()

    def get_file_change(self, change_id: int) -> dict[str, Any] | None:
        row = self._exec("SELECT * FROM file_changes WHERE id=?", (change_id,)).fetchone()
        return _change_row(row) if row is not None else None

    def mark_change_reverted(self, change_id: int) -> None:
        self._exec("UPDATE file_changes SET reverted=1 WHERE id=?", (change_id,))
        self._commit()

    # ---- dosya geçmişi bakımı (sıkıştırma + küçültme) ----

    def pack_file_changes(self, batch: int = 40) -> int:
        """Eski (sıkıştırılmamış) dosya geçmişi kayıtlarını sıkıştırır; dönüştürülen satır sayısı. Kimlik sırasıyla bir
        kez taranır; her parti kısa bir işlemdir (sıkıştırma kilit DIŞINDA yapılır, arayüz beklemez). Her değer yazılmadan
        önce açılıp aslıyla karşılaştırılır; tutmazsa o satıra dokunulmaz. Metinler yazıldıktan sonra değişmez; parti
        arasında silinen satırda UPDATE etkisiz kalır."""
        last, done = 0, 0
        while True:
            rows = self._exec(
                "SELECT id, before_text, after_text FROM file_changes WHERE id > ? AND"
                " (typeof(before_text) = 'text' OR typeof(after_text) = 'text') ORDER BY id LIMIT ?", (last, batch),
            ).fetchall()
            if not rows:
                return done
            last = rows[-1]["id"]
            updates = []
            for r in rows:
                vals = []
                for v in (r["before_text"], r["after_text"]):
                    vals.append(_pack_verified(v) if isinstance(v, str) else v)
                if all(not isinstance(old, str) or new is not None
                       for old, new in zip((r["before_text"], r["after_text"]), vals)):
                    updates.append((vals[0], vals[1], r["id"]))
            with self._lock:
                self.conn.executemany("UPDATE file_changes SET before_text=?, after_text=? WHERE id=?", updates)
                self.conn.commit()
            done += len(updates)

    def compact_if_worthwhile(self, min_free_ratio: float = 0.25, max_mb: float = 200.0) -> bool:
        """Boş sayfalar dosyanın ≥ %25'iyse VACUUM ile dosyayı küçültür. Büyük veritabanında (> 200 MB) yapılmaz:
        VACUUM süresince bağlantı kilitli kalır; boş sayfalar zaten yeni verilere yeniden kullanılır."""
        pages = int(self._exec("PRAGMA page_count").fetchone()[0])
        free = int(self._exec("PRAGMA freelist_count").fetchone()[0])
        size_mb = pages * int(self._exec("PRAGMA page_size").fetchone()[0]) / 1e6
        if pages == 0 or free / pages < min_free_ratio or size_mb > max_mb:
            return False
        with self._lock:
            self.conn.commit()
            self.conn.execute("VACUUM")
            if self.journal_mode == "wal":
                # WAL'da VACUUM yeni içeriği -wal dosyasına yazar; ana dosya ancak checkpoint'te küçülür ve -wal
                # veritabanı boyunda kalırdı → hemen aktar ve -wal'ı sıfırla
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return True

    def maintain_file_history(self) -> dict:
        """Açılıştan sonra arka planda bir kez: eski kayıtları sıkıştır, gerekiyorsa küçült, bitti işaretini yaz."""
        if self.get_meta(PACK_DONE_KEY) == "1":
            return {"sikistirilan": 0, "kuculdu": False, "zaten": True}
        before = self.path.stat().st_size if self.path.is_file() else 0
        n = self.pack_file_changes()
        shrunk = self.compact_if_worthwhile() if n else False
        self.set_meta(PACK_DONE_KEY, "1")
        after = self.path.stat().st_size if self.path.is_file() else 0
        return {"sikistirilan": n, "kuculdu": shrunk, "once_bayt": before, "sonra_bayt": after, "zaten": False}

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

    def project_run_states(self, limit: int = 30) -> list[str]:
        """F5 #5 tahmin: son proje çalışmalarının durum JSON'ları."""
        return [r["state_json"] for r in self._exec(
            "SELECT state_json FROM project_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def recent_assistant_metas(self, limit: int = 300) -> list[str]:
        """F5 #5 tahmin: son asistan mesajlarının meta JSON'u (usage)."""
        return [r["meta"] for r in self._exec(
            "SELECT meta FROM session_messages WHERE role='assistant' AND meta IS NOT NULL ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()]

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

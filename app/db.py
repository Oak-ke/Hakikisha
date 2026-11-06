"""SQLite store for reported/confirmed scam indicators and a log of checks."""
import datetime as dt
import json
import sqlite3
import threading

from .config import settings
from .models import CheckResult, Signal

SCHEMA = """
CREATE TABLE IF NOT EXISTS indicators (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- domain | phone | till | url
    value TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'reported',  -- reported | confirmed | cleared
    reports INTEGER NOT NULL DEFAULT 1,
    note TEXT,
    first_seen TEXT,
    last_seen TEXT,
    UNIQUE(kind, value)
);
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY,
    input TEXT, final_url TEXT, level TEXT, score INTEGER, signals TEXT, created_at TEXT
);
"""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def report(self, kind: str, value: str, note: str = "") -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """INSERT INTO indicators(kind, value, note, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(kind, value) DO UPDATE SET
                     reports = reports + 1, last_seen = excluded.last_seen""",
                (kind, value.lower(), note, _now(), _now()),
            )

    def set_status(self, kind: str, value: str, status: str, note: str = "") -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """INSERT INTO indicators(kind, value, status, reports, note, first_seen, last_seen)
                   VALUES (?, ?, ?, 0, ?, ?, ?)
                   ON CONFLICT(kind, value) DO UPDATE SET
                     status = excluded.status, note = excluded.note, last_seen = excluded.last_seen""",
                (kind, value.lower(), status, note, _now(), _now()),
            )

    def lookup(self, pairs: list[tuple[str, str]]) -> list[sqlite3.Row]:
        rows = []
        with self.lock:
            for kind, value in dict.fromkeys(pairs):
                row = self.conn.execute(
                    "SELECT * FROM indicators WHERE kind = ? AND value = ?", (kind, value.lower())
                ).fetchone()
                if row:
                    rows.append(row)
        return rows

    def log_check(self, r: CheckResult) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO checks(input, final_url, level, score, signals, created_at) VALUES (?,?,?,?,?,?)",
                (r.input[:500], r.final_url, r.level.value, r.score,
                 json.dumps([s.code for s in r.signals]), _now()),
            )


def signals_from_rows(rows) -> list[Signal]:
    out = []
    for row in rows:
        label = {"domain": "website", "url": "link", "phone": "phone number", "till": "till number"}[row["kind"]]
        label_sw = {"domain": "tovuti", "url": "kiungo", "phone": "namba ya simu", "till": "namba ya till"}[row["kind"]]
        if row["status"] == "confirmed":
            out.append(Signal(f"known_scam_{row['kind']}", 100,
                              f"This {label} is a confirmed scam",
                              f"Hii {label_sw} imethibitishwa kuwa ya utapeli", strong=True))
        elif row["status"] == "reported":
            n = row["reports"]
            w = 30 if n >= 3 else 10
            out.append(Signal(f"reported_{row['kind']}", w,
                              f"This {label} has been reported by {n} user(s)",
                              f"Hii {label_sw} imeripotiwa na watumiaji {n}"))
    return out


_db: DB | None = None


def get_db() -> DB:
    global _db
    if _db is None:
        _db = DB(settings.DB_PATH)
    return _db


def set_db(db: DB) -> None:
    """Swap the database (used by tests)."""
    global _db
    _db = db

"""SQLite helpers: connection, schema and sample data for the simulated fleet."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "endpoint_risk.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    owner TEXT NOT NULL,
    os TEXT NOT NULL,
    patch_level INTEGER NOT NULL,
    encryption_enabled INTEGER NOT NULL,
    failed_logins INTEGER NOT NULL,
    last_seen TEXT NOT NULL,
    risk_score INTEGER NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'Low',
    status TEXT NOT NULL DEFAULT 'Secure'
);
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    issue_type TEXT NOT NULL,
    detail TEXT NOT NULL,
    points INTEGER NOT NULL,
    recommended_fix TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    detected_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event TEXT NOT NULL,
    message TEXT NOT NULL
);
"""

# name, owner, os, patch_level, encryption_enabled, failed_logins, hours_since_last_seen
SAMPLE_DEVICES = [
    ("LAPTOP-HR-01",     "Asha Menon",    "Windows 11",     10, 1, 0, 2),
    ("LAPTOP-FIN-02",    "Rohan Desai",   "Windows 10",      7, 1, 1, 26),
    ("DESKTOP-DEV-03",   "Priya Nair",    "Ubuntu 22.04",   10, 0, 0, 1),
    ("LAPTOP-SALES-04",  "Karan Mehta",   "macOS 14",        8, 0, 6, 5),
    ("SERVER-DB-05",     "IT Operations", "Ubuntu Server",   6, 1, 12, 1),
    ("DESKTOP-OPS-06",   "Neha Kulkarni", "Windows 10",     10, 1, 0, 12 * 24),
    ("LAPTOP-EXEC-07",   "Vikram Joshi",  "macOS 14",       10, 0, 8, 3),
    ("TABLET-FIELD-08",  "Sana Sheikh",   "Android 14",      5, 1, 0, 15 * 24),
    ("LAPTOP-SUP-09",    "Dev Patil",     "Windows 11",      9, 0, 5, 9 * 24),
    ("WORKSTATION-10",   "Meera Iyer",    "Windows 11",     10, 1, 2, 1),
]


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.replace(microsecond=0).isoformat()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db():
    """Open a connection, commit on success, always close."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_event(conn, event, message):
    conn.execute(
        "INSERT INTO activity_log (timestamp, event, message) VALUES (?, ?, ?)",
        (iso(now_utc()), event, message),
    )


def init_db(reset=False):
    """Create tables and load the 10 sample devices if the database is empty."""
    import risk_engine  # imported here to avoid a circular import

    with db() as conn:
        if reset:
            conn.executescript(
                "DROP TABLE IF EXISTS issues; DROP TABLE IF EXISTS devices; "
                "DROP TABLE IF EXISTS activity_log;"
            )
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        if count == 0:
            now = now_utc()
            for name, owner, os_name, patch, enc, fails, hours in SAMPLE_DEVICES:
                conn.execute(
                    "INSERT INTO devices (name, owner, os, patch_level, encryption_enabled, "
                    "failed_logins, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name, owner, os_name, patch, enc, fails, iso(now - timedelta(hours=hours))),
                )
            for row in conn.execute("SELECT id FROM devices").fetchall():
                risk_engine.evaluate_device(conn, row["id"])
            log_event(conn, "SYSTEM",
                      "Demo data loaded: 10 simulated devices registered and scanned.")

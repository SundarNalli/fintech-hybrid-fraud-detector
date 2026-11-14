"""SQLite plumbing: open the database, create tables, load the synthetic world.

Times are stored as epoch seconds (REAL) so comparisons are plain numbers, not
string ordering. The service uses one read-write connection. Agent tools get a
separate connection opened with `mode=ro`, so a write fails at the database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hybrid_fraud.sim.models import Dataset

DDL = """
CREATE TABLE IF NOT EXISTS merchants (
    merchant_id TEXT PRIMARY KEY, created_at REAL NOT NULL, legal_name TEXT, sector TEXT, mcc_code TEXT,
    avg_daily_volume_30d REAL NOT NULL, chargeback_rate_90d REAL NOT NULL, is_top_200 INTEGER NOT NULL, kyb_text TEXT);
CREATE TABLE IF NOT EXISTS beneficiaries (
    beneficiary_id TEXT PRIMARY KEY, name TEXT, first_seen_at REAL NOT NULL, on_mule_list INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS beneficiary_links (
    merchant_id TEXT NOT NULL, beneficiary_id TEXT NOT NULL, added_at REAL NOT NULL,
    PRIMARY KEY (merchant_id, beneficiary_id));
CREATE INDEX IF NOT EXISTS idx_links_bene ON beneficiary_links(beneficiary_id);
CREATE TABLE IF NOT EXISTS device_links (merchant_id TEXT NOT NULL, device_id TEXT NOT NULL, first_seen_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_devices ON device_links(device_id);
CREATE INDEX IF NOT EXISTS idx_devices_m ON device_links(merchant_id);
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, created_at REAL NOT NULL, category TEXT, text TEXT);
CREATE INDEX IF NOT EXISTS idx_tickets ON tickets(merchant_id, created_at);

CREATE TABLE IF NOT EXISTS payouts (
    payout_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    body_hash TEXT NOT NULL,
    merchant_id TEXT NOT NULL, beneficiary_id TEXT NOT NULL, amount_usd REAL NOT NULL, created_at REAL NOT NULL,
    payload TEXT NOT NULL,
    state TEXT NOT NULL,
    response TEXT NOT NULL,
    hold_deadline REAL);
CREATE INDEX IF NOT EXISTS idx_payouts_bene ON payouts(beneficiary_id, created_at);
CREATE INDEX IF NOT EXISTS idx_payouts_hold ON payouts(state, hold_deadline);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    """Read-write connection. Autocommit mode: the service opens its own transactions."""
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(DDL)
    return conn


def connect_readonly(path: str | Path) -> sqlite3.Connection:
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


def load_world(conn: sqlite3.Connection, ds: Dataset) -> None:
    """Load merchants, payees, devices and tickets. Never the labels."""
    ts = lambda d: d.timestamp()
    conn.execute("BEGIN")
    conn.executemany("INSERT OR IGNORE INTO merchants VALUES (?,?,?,?,?,?,?,?,?)", [
        (m.merchant_id, ts(m.created_at), m.legal_name, m.sector, m.mcc_code, m.avg_daily_volume_30d,
         m.chargeback_rate_90d, int(m.is_top_200), m.kyb_text) for m in ds.merchants])
    conn.executemany("INSERT OR IGNORE INTO beneficiaries VALUES (?,?,?,?)", [
        (b.beneficiary_id, b.name, ts(b.first_seen_at), int(b.on_mule_list)) for b in ds.beneficiaries])
    conn.executemany("INSERT OR IGNORE INTO beneficiary_links VALUES (?,?,?)", [
        (l.merchant_id, l.beneficiary_id, ts(l.added_at)) for l in ds.beneficiary_links])
    conn.executemany("INSERT INTO device_links VALUES (?,?,?)", [
        (l.merchant_id, l.device_id, ts(l.first_seen_at)) for l in ds.device_links])
    conn.executemany("INSERT OR IGNORE INTO tickets VALUES (?,?,?,?,?)", [
        (t.ticket_id, t.merchant_id, ts(t.created_at), t.category, t.text) for t in ds.tickets])
    conn.execute("COMMIT")

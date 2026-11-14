"""Run the service locally.

    python -m hybrid_fraud.service.main            # http://127.0.0.1:8000/docs

The database path comes from FRAUD_DB_PATH (default data/local/fraud.db, which is
git-ignored). An empty database is filled from the committed synthetic snapshot.
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from hybrid_fraud.core.config import load_thresholds
from hybrid_fraud.service.api import create_app
from hybrid_fraud.service.payout_service import PayoutService
from hybrid_fraud.sim.dataset_io import read_dataset
from hybrid_fraud.store.db import connect, load_world

DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "local" / "fraud.db"


def build_service(db_path: Path) -> PayoutService:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    if conn.execute("SELECT COUNT(*) FROM merchants").fetchone()[0] == 0:
        load_world(conn, read_dataset())
    return PayoutService(conn, load_thresholds())


if __name__ == "__main__":
    service = build_service(Path(os.environ.get("FRAUD_DB_PATH", DEFAULT_DB)))
    uvicorn.run(create_app(service), host="127.0.0.1", port=8000)

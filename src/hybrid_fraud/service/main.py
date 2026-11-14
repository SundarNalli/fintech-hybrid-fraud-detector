"""Run the service locally.

    python -m hybrid_fraud.service.main            # http://127.0.0.1:8000/docs

Settings come from the environment (see .env.example):
  FRAUD_DB_PATH                  database file (default data/local/fraud.db, git-ignored)
  OPENROUTER_API_KEY             set it to use a live model; unset means replay mode
  FRAUD_REPLAY_DIR               recorded responses for replay mode (default data/replay)
  LLM_INPUT_USD_PER_MTOK / LLM_OUTPUT_USD_PER_MTOK   prices, so cost per case can be metered

An empty database is filled from the committed synthetic snapshot. With no key and no
recordings, a held payout simply escalates to the human queue: failing safe.
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from hybrid_fraud.agent.budget import Prices
from hybrid_fraud.agent.providers import make_provider
from hybrid_fraud.core.config import load_thresholds
from hybrid_fraud.service.api import create_app
from hybrid_fraud.service.gray_zone import GrayZoneProcessor
from hybrid_fraud.service.payout_service import PayoutService
from hybrid_fraud.sim.dataset_io import read_dataset
from hybrid_fraud.store.db import connect, load_world

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "data" / "local" / "fraud.db"
DEFAULT_REPLAY = ROOT / "data" / "replay"


def build_service(db_path: Path) -> PayoutService:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    if conn.execute("SELECT COUNT(*) FROM merchants").fetchone()[0] == 0:
        load_world(conn, read_dataset())
    return PayoutService(conn, load_thresholds())


def prices_from_env(env=os.environ) -> Prices:
    per_token = lambda name: float(env.get(name) or 0) / 1_000_000
    return Prices(per_token("LLM_INPUT_USD_PER_MTOK"), per_token("LLM_OUTPUT_USD_PER_MTOK"))


if __name__ == "__main__":
    db_path = Path(os.environ.get("FRAUD_DB_PATH", DEFAULT_DB))
    service = build_service(db_path)
    provider = make_provider(Path(os.environ.get("FRAUD_REPLAY_DIR", DEFAULT_REPLAY)))
    gray = GrayZoneProcessor(service, db_path, provider, load_thresholds(), prices_from_env())
    uvicorn.run(create_app(service, gray_zone=gray), host="127.0.0.1", port=8000)

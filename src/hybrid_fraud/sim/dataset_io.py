"""Write the dataset as gzipped JSON lines plus a manifest, and read it back.

The committed snapshot lives in data/synthetic/. The manifest records the seed,
the generator version and a hash of every table (of the uncompressed text), so
anyone can check that a regenerated dataset is identical. Gzip headers carry no
timestamp, so the compressed files are reproducible too.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from hybrid_fraud.sim.models import Dataset

GENERATOR_VERSION = "1"
TABLES = ["merchants", "beneficiaries", "beneficiary_links", "device_links", "tickets", "payouts", "labels"]
DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic"


def write_dataset(ds: Dataset, directory: Path = DEFAULT_DIR) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for table in TABLES:
        raw = "".join(row.model_dump_json() + "\n" for row in getattr(ds, table)).encode("utf-8")
        with open(directory / f"{table}.jsonl.gz", "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as gz:
            gz.write(raw)
        hashes[table] = hashlib.sha256(raw).hexdigest()
    fraud = [l for l in ds.labels if l.is_fraud]
    amounts = {p.payout_id: p.amount_usd for p in ds.payouts}
    manifest = {
        "synthetic": True,
        "seed": ds.seed,
        "noise": ds.noise,
        "generator_version": GENERATOR_VERSION,
        "payouts": len(ds.payouts),
        "fraud_payouts": len(fraud),
        "fraud_bps_by_count": round(len(fraud) / len(ds.payouts) * 10000, 2),
        "fraud_bps_by_dollars": round(
            sum(amounts[l.payout_id] for l in fraud) / sum(amounts.values()) * 10000, 2),
        "sha256_uncompressed": hashes,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def read_dataset(directory: Path = DEFAULT_DIR) -> Dataset:
    meta = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    tables = {}
    for table in TABLES:
        with gzip.open(directory / f"{table}.jsonl.gz", "rt", encoding="utf-8") as f:
            tables[table] = [json.loads(line) for line in f]
    return Dataset.model_validate({"seed": meta["seed"], "noise": meta["noise"], **tables})

"""Regenerate the committed snapshot in data/synthetic/.

Run:  python -m hybrid_fraud.sim.make_snapshot
"""

from hybrid_fraud.sim.dataset_io import write_dataset
from hybrid_fraud.sim.generate_data import generate

if __name__ == "__main__":
    manifest = write_dataset(generate())
    print({k: v for k, v in manifest.items() if k != "sha256_uncompressed"})

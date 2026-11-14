import hashlib
import json
from datetime import timedelta
from pathlib import Path

from hybrid_fraud.core.schemas import Payout
from hybrid_fraud.hot_path.features import PayoutFeatures
from hybrid_fraud.sim.generate_data import generate
from hybrid_fraud.sim.lookup import DatasetLookup

MANIFEST = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "manifest.json"


def digest(ds) -> str:
    return hashlib.sha256("".join(p.model_dump_json() for p in ds.payouts).encode()).hexdigest()


def test_the_dataset_has_20000_payouts_and_48_bps_of_fraud_by_count(dataset):
    fraud = [l for l in dataset.labels if l.is_fraud]
    assert len(dataset.payouts) == 20000 and len(fraud) == 96


def test_the_same_seed_gives_identical_data_and_a_different_seed_does_not(dataset):
    assert digest(generate()) == digest(dataset)
    assert digest(generate(seed=1)) != digest(dataset)


def test_the_committed_snapshot_matches_what_the_generator_produces(dataset):
    manifest = json.loads(MANIFEST.read_text())
    raw = "".join(p.model_dump_json() + "\n" for p in dataset.payouts).encode()
    assert manifest["sha256_uncompressed"]["payouts"] == hashlib.sha256(raw).hexdigest()


def test_every_record_is_labelled_synthetic(dataset):
    assert all(p.synthetic is True for p in dataset.payouts)


def test_fraud_labels_never_appear_in_what_the_service_can_see():
    for model in (Payout, PayoutFeatures):
        assert not [f for f in model.model_fields if "fraud" in f or "label" in f]


def test_fraud_is_not_only_young_merchants(replayed):
    old = [r for r in replayed if r.is_fraud and r.features.account_age_days >= 90]
    assert len(old) / 96 >= 0.3


def test_all_four_fraud_shapes_are_present(dataset):
    assert {l.fraud_type for l in dataset.labels if l.is_fraud} == {"bustout", "takeover", "mule", "structuring"}


def test_a_payee_is_never_older_than_the_account_that_added_it(replayed):
    assert all(r.features.beneficiary_age_hrs <= r.features.account_age_days * 24 + 1e-6 for r in replayed)


def test_a_device_login_that_has_not_happened_yet_is_not_counted(dataset):
    lookup = DatasetLookup(dataset)
    link = next(l for l in dataset.device_links if l.device_id.startswith("dev_atk"))
    before = lookup.shared_device_merchants(link.device_id, link.first_seen_at - timedelta(seconds=1))
    after = lookup.shared_device_merchants(link.device_id, link.first_seen_at)
    assert after == before + 1


def test_payouts_are_in_time_order(dataset):
    times = [p.created_at for p in dataset.payouts]
    assert times == sorted(times)

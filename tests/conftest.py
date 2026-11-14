import shutil
import time

import pytest

from hybrid_fraud.core.config import load_thresholds
from hybrid_fraud.service.payout_service import PayoutService
from hybrid_fraud.sim.generate_data import generate
from hybrid_fraud.sim.replay import replay
from hybrid_fraud.store.db import connect, load_world


@pytest.fixture(scope="session")
def thresholds():
    return load_thresholds()


@pytest.fixture(scope="session")
def dataset():
    return generate()


@pytest.fixture(scope="session")
def replayed(dataset, thresholds):
    return replay(dataset, thresholds)


@pytest.fixture(scope="session")
def world_db_path(dataset, tmp_path_factory):
    """A database holding the synthetic world and no payouts. Tests copy it."""
    path = tmp_path_factory.mktemp("world") / "world.db"
    conn = connect(path)
    load_world(conn, dataset)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return path


@pytest.fixture
def make_service(world_db_path, thresholds, tmp_path):
    """Build a service on its own copy of the world. Passing the same `db` again is a restart."""
    opened = []

    def _make(clock=time.time, db=None):
        path = db or tmp_path / "svc.db"
        if not path.exists():
            shutil.copy(world_db_path, path)
        conn = connect(path)
        opened.append(conn)
        return PayoutService(conn, thresholds, clock), path

    yield _make
    for c in opened:
        c.close()


@pytest.fixture(scope="session")
def full_run(dataset, world_db_path, thresholds, tmp_path_factory):
    """All 20,000 payouts submitted in order. Returns (db path, responses)."""
    path = tmp_path_factory.mktemp("full") / "full.db"
    shutil.copy(world_db_path, path)
    conn = connect(path)
    service = PayoutService(conn, thresholds)
    responses = [service.submit(p, f"key_{p.payout_id}") for p in dataset.payouts]
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return path, responses

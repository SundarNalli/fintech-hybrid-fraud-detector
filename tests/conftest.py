import pytest

from hybrid_fraud.core.config import load_thresholds
from hybrid_fraud.sim.generate_data import generate
from hybrid_fraud.sim.replay import replay


@pytest.fixture(scope="session")
def thresholds():
    return load_thresholds()


@pytest.fixture(scope="session")
def dataset():
    return generate()


@pytest.fixture(scope="session")
def replayed(dataset, thresholds):
    return replay(dataset, thresholds)

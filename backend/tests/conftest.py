import pytest

from tripopt.graph import TemporalGraph
from tripopt.synthetic import SyntheticConfig, generate


@pytest.fixture(scope="session")
def small():
    ds = generate(SyntheticConfig(n_airports=12, n_hubs=2, days=4, seed=3))
    return ds, TemporalGraph(ds.flights)

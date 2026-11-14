import pytest

from hybrid_fraud.hot_path.router import route
from hybrid_fraud.sim.scenarios import scenarios

ALL = scenarios()


@pytest.mark.parametrize("sc", ALL, ids=[s.name for s in ALL])
def test_each_scenario_routes_as_expected(sc, thresholds):
    assert route(sc.features, thresholds).route == sc.expected_route


def test_the_two_gray_scenarios_are_the_ones_the_agent_sees():
    assert [s.expected_agent_action is not None for s in ALL] == [False, False, True, True]


@pytest.mark.parametrize("sc", ALL, ids=[s.name for s in ALL])
def test_scenario_evidence_ids_are_stable_and_unique(sc):
    ids = [e.evidence_id for e in sc.evidence]
    assert len(ids) == len(set(ids)) == 4
    assert all(i.split(":")[0] in {"merchant_profile", "entity_graph", "support_tickets", "beneficiary_history"}
               for i in ids)


def test_scenario_text_that_a_merchant_can_write_is_marked_as_merchant_authored():
    for sc in ALL:
        by_source = {e.source: e for e in sc.evidence}
        assert "kyb_text" in by_source["merchant_profile"].merchant_authored
        assert "ticket_text" in by_source["support_tickets"].merchant_authored
        assert "beneficiary_name" in by_source["beneficiary_history"].merchant_authored

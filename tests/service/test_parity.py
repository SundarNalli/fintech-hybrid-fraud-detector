def test_the_service_makes_the_same_decision_as_the_in_memory_replay_for_every_payout(full_run, replayed):
    """Two independent implementations of the same lookups (dict vs SQLite) must agree."""
    _, responses = full_run
    assert len(responses) == len(replayed) == 20000
    mismatches = [
        (r.payout_id, r.route.value, row.result.route.value)
        for r, row in zip(responses, replayed)
        if r.route != row.result.route or r.reason_codes != [c.value for c in row.result.reason_codes]
    ]
    assert mismatches == []


def test_every_decision_has_a_deterministic_reason(full_run):
    _, responses = full_run
    assert all(r.reason_codes and r.evidence_trace for r in responses)

from datetime import datetime, timedelta, timezone

from hybrid_fraud.core.schemas import Payout
from hybrid_fraud.hot_path.gate0_rules import gate0_hits
from hybrid_fraud.hot_path.velocity import VelocityCounters

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def payout(minutes: float, amount: float = 100.0, merchant="m1", bene="b1") -> Payout:
    return Payout(payout_id=f"p{minutes}", merchant_id=merchant, beneficiary_id=bene, amount_usd=amount,
                  rail="RTP", beneficiary_name="x", payout_memo="x", device_id="d",
                  created_at=T0 + timedelta(minutes=minutes))


def test_the_payout_being_scored_counts_in_its_own_totals():
    snap = VelocityCounters().snapshot(payout(0, 250.0))
    assert snap.count_1h == 1 and snap.usd_1h == 250.0


def test_an_event_exactly_one_hour_old_is_outside_the_window():
    c = VelocityCounters()
    c.record(payout(0))
    assert c.snapshot(payout(60)).count_1h == 1  # lower edge is exclusive


def test_an_event_59_minutes_old_is_inside_the_window():
    c = VelocityCounters()
    c.record(payout(0))
    assert c.snapshot(payout(59)).count_1h == 2


def test_dollars_are_counted_per_beneficiary_across_merchants():
    c = VelocityCounters()
    for i in range(3):
        c.record(payout(i, 2000.0, merchant=f"m{i}", bene="mule"))
    snap = c.snapshot(payout(5, 2000.0, merchant="m9", bene="mule"))
    assert snap.beneficiary_distinct_merchants_24h == 4
    assert snap.beneficiary_usd_24h == 8000.0


def test_first_time_payee_is_true_only_for_a_new_merchant_payee_pair():
    c = VelocityCounters()
    assert c.snapshot(payout(0)).first_time_payee
    c.record(payout(0))
    assert not c.snapshot(payout(5)).first_time_payee
    assert c.snapshot(payout(5, merchant="m2")).first_time_payee


def test_ten_payouts_of_2400_dollars_are_stopped_by_the_third(thresholds):
    """The $2,500 loophole: no single payout is large, but the hour adds up."""
    from conftest import make_features

    c = VelocityCounters()
    stopped_at = None
    for i in range(10):
        p = payout(i * 5, 2400.0)
        snap = c.snapshot(p)
        f = make_features(amount_usd=2400.0, account_age_days=40, avg_daily_volume_30d=1500,
                          velocity_count_1h=snap.count_1h, velocity_usd_1h=snap.usd_1h)
        if gate0_hits(f, thresholds.gate0) and stopped_at is None:
            stopped_at = i + 1
        c.record(p)
    assert stopped_at == 3

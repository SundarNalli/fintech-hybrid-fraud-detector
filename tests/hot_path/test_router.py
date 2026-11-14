import itertools

from hybrid_fraud.core.reason_codes import ReasonCode
from hybrid_fraud.core.schemas import Route
from hybrid_fraud.hot_path.router import route
from tests.helpers import make_features

# Features that land in each score band without tripping a hard rule.
GRAY = dict(account_age_days=25, beneficiary_age_hrs=3.0, avg_daily_volume_30d=5000)  # 0.30 + 0.25
HIGH = dict(account_age_days=25, beneficiary_age_hrs=3.0, shared_device_merchants=3, avg_daily_volume_30d=250,
            chargeback_rate_90d=0.03, support_2fa_ticket_48h=True)  # 1.0, no hard rule
HARD = dict(account_age_days=10, beneficiary_age_hrs=1.0, amount_usd=5000.0)


def test_a_hard_rule_blocks_an_ordinary_merchant(thresholds):
    assert route(make_features(**HARD), thresholds).route == Route.BLOCK


def test_a_hard_rule_sends_a_top_200_merchant_to_the_fast_human_lane(thresholds):
    r = route(make_features(**HARD, is_top_200=True), thresholds)
    assert r.route == Route.FAST_HUMAN_LANE
    assert ReasonCode.TOP_MERCHANT_FAST_LANE in r.reason_codes


def test_a_high_score_blocks_and_a_top_200_high_score_goes_to_the_fast_lane(thresholds):
    assert route(make_features(**HIGH), thresholds).route == Route.BLOCK
    assert route(make_features(**HIGH, is_top_200=True), thresholds).route == Route.FAST_HUMAN_LANE


def test_a_gray_score_holds_the_payout_for_review(thresholds):
    r = route(make_features(**GRAY), thresholds)
    assert r.route == Route.PENDING_REVIEW and r.reason_codes == [ReasonCode.GRAY_ZONE_SCORE]


def test_a_low_score_with_a_novel_payee_over_2500_dollars_is_held(thresholds):
    f = make_features(amount_usd=3000.0, first_time_payee=True, beneficiary_platform_age_hrs=20.0)
    assert route(f, thresholds).route == Route.PENDING_REVIEW


def test_a_low_score_with_a_novel_payee_under_2500_dollars_is_approved_with_a_flag(thresholds):
    f = make_features(amount_usd=900.0, first_time_payee=True, beneficiary_platform_age_hrs=20.0)
    r = route(f, thresholds)
    assert r.route == Route.APPROVE and r.novel_anomaly_flag


def test_an_ordinary_payout_is_approved(thresholds):
    r = route(make_features(), thresholds)
    assert r.route == Route.APPROVE and not r.novel_anomaly_flag


def test_every_combination_of_inputs_gets_exactly_one_route(thresholds):
    """The table is exhaustive: no input falls through."""
    bands = [{}, GRAY, HIGH, HARD]
    for band, top, novel, amount in itertools.product(bands, [False, True], [False, True], [900.0, 3000.0]):
        kw = {"amount_usd": amount, **band, "is_top_200": top, "first_time_payee": novel,
              "beneficiary_platform_age_hrs": 20.0 if novel else 20000.0}
        assert route(make_features(**kw), thresholds).route in set(Route)


def test_every_decision_carries_a_reason_and_evidence_built_from_real_values(thresholds):
    r = route(make_features(**HARD), thresholds)
    assert r.reason_codes and any("$5,000.00" in line for line in r.evidence_trace)

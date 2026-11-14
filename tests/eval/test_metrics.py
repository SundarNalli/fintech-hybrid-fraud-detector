import math

from hybrid_fraud.core.schemas import PayoutState as S
from hybrid_fraud.eval.metrics import Rate, Row, gray_summary, summarise, wilson


def row(pid, merchant, amount, fraud, state, gray=False, top=False):
    return Row(pid, merchant, amount, fraud, top, state, gray)


def test_the_wilson_interval_is_sensible_at_zero_and_at_all():
    lo, hi = wilson(0, 80)
    assert lo == 0.0 and 0.04 < hi < 0.05  # "zero failures in 80" still allows about 4%
    lo, hi = wilson(80, 80)
    assert hi == 1.0 and 0.95 < lo < 0.96


def test_the_wilson_interval_matches_a_known_value():
    lo, hi = wilson(5, 10)
    assert math.isclose(lo, 0.2366, abs_tol=1e-3) and math.isclose(hi, 0.7634, abs_tol=1e-3)


def test_a_rate_with_no_cases_says_so_instead_of_dividing_by_zero():
    assert Rate(0, 0).fmt() == "n/a"


def test_loss_in_bps_is_stolen_dollars_over_paid_out_dollars():
    rows = [row("a", "m1", 990.0, False, S.APPROVED), row("b", "m2", 10.0, True, S.APPROVED),
            row("c", "m3", 5000.0, True, S.BLOCKED)]  # a blocked payout loses nothing
    s = summarise(rows)
    assert s["stolen_usd"] == 10.0 and math.isclose(s["loss_bps"], 100.0)


def test_fraud_is_counted_blocked_held_or_missed_by_final_state():
    rows = [row("a", "m1", 1, True, S.BLOCKED), row("b", "m2", 1, True, S.ESCALATED),
            row("c", "m3", 1, True, S.APPROVED), row("d", "m4", 1, False, S.APPROVED)]
    s = summarise(rows)
    assert (s["fraud_blocked"].k, s["fraud_held"].k, s["fraud_approved"].k) == (1, 1, 1)
    assert s["fraud_caught_or_held"].k == 2 and s["fraud_blocked"].n == 3


def test_only_legitimate_payouts_count_toward_false_positives_and_by_merchant():
    rows = [row("a", "m1", 1, False, S.BLOCKED, top=True), row("b", "m1", 1, False, S.ESCALATED, top=True),
            row("c", "m2", 1, False, S.APPROVED), row("d", "m3", 1, True, S.BLOCKED)]
    s = summarise(rows)
    assert s["legit_blocked"].k == 1 and s["legit_held"].k == 1 and s["legit_blocked"].n == 3
    assert (s["merchants_hit"].k, s["merchants_hit"].n) == (1, 3)  # m1 only; m3's block was correct
    assert (s["top200_merchants_hit"].k, s["top200_merchants_hit"].n) == (1, 1)


def test_auto_resolved_excludes_anything_a_human_must_look_at():
    rows = [row("a", "m1", 1, False, S.APPROVED), row("b", "m2", 1, True, S.BLOCKED),
            row("c", "m3", 1, False, S.ESCALATED)]
    assert summarise(rows)["auto_resolved"].k == 2


def test_a_wrong_call_is_an_approved_fraud_or_a_blocked_legitimate_but_a_human_is_never_wrong():
    rows = [row("a", "m1", 1, True, S.APPROVED, gray=True), row("b", "m2", 1, False, S.BLOCKED, gray=True),
            row("c", "m3", 1, True, S.BLOCKED, gray=True), row("d", "m4", 1, True, S.ESCALATED, gray=True),
            row("e", "m5", 1, False, S.APPROVED)]  # not gray: ignored here
    g = gray_summary(rows)
    assert g["cases"] == 4 and g["wrong_of_all"].k == 2
    assert (g["wrong_of_decided"].k, g["wrong_of_decided"].n) == (2, 3)

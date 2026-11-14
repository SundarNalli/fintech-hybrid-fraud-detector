"""The four scenarios, hand-written. Every name and number is invented.

The client brief is not in this repo, so these four are defined from the
examples in the project notes and are open to correction (assumptions A-26).
Each one carries the text an investigator would read and the evidence records
the agent's tools would return, matching the field names in `core/repository.py`.

  1  hard-rule block     brand-new account, payee added minutes ago, large payout
  2  clear approve       established merchant, familiar payee, ordinary amount
  3  gray, really fraud  dental practice paying a crypto holding company, after a lockout ticket
  4  gray, legitimate    young ticketing company paying a stage-rental vendor
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from hybrid_fraud.core.schemas import AgentAction, EvidenceRecord, Payout, Route
from hybrid_fraud.hot_path.features import PayoutFeatures

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Scenario:
    name: str
    story: str
    payout: Payout
    features: PayoutFeatures
    evidence: list[EvidenceRecord]
    expected_route: Route
    expected_agent_action: AgentAction | None  # None: the agent is never called


def _payout(pid: str, mid: str, bid: str, amount: float, name: str, memo: str) -> Payout:
    return Payout(payout_id=pid, merchant_id=mid, beneficiary_id=bid, amount_usd=amount, rail="RTP",
                  beneficiary_name=name, payout_memo=memo, device_id=f"dev_{mid}", created_at=NOW)


def _features(p: Payout, **kw) -> PayoutFeatures:
    base = dict(
        payout_id=p.payout_id, merchant_id=p.merchant_id, amount_usd=p.amount_usd, is_top_200=False,
        account_age_days=800, avg_daily_volume_30d=6000, chargeback_rate_90d=0.005,
        beneficiary_age_hrs=3000, beneficiary_platform_age_hrs=20000, beneficiary_on_mule_list=False,
        first_time_payee=False, shared_device_merchants=1, support_2fa_ticket_48h=False,
        support_credential_ticket_48h=False, velocity_count_1h=1, velocity_usd_1h=p.amount_usd,
        velocity_usd_24h=p.amount_usd, beneficiary_distinct_merchants_24h=1, beneficiary_usd_24h=p.amount_usd,
    )
    return PayoutFeatures(**{**base, **kw})


def _evidence(mid: str, bid: str, *, age, sector, mcc, avg, cb, kyb, graph_clean=True, neighbours=0,
              tickets=0, t2fa=False, tcred=False, ticket_text="", bene_age, bene_merchants, bene_settled,
              bene_name) -> list[EvidenceRecord]:
    return [
        EvidenceRecord(evidence_id=f"merchant_profile:{mid}", source="merchant_profile",
                       fields={"account_age_days": age, "sector": sector, "mcc_code": mcc,
                               "avg_daily_volume_30d": avg, "chargeback_rate_90d": cb, "is_top_200": False,
                               "kyb_text": kyb}, merchant_authored=frozenset({"kyb_text"})),
        EvidenceRecord(evidence_id=f"entity_graph:{mid}", source="entity_graph",
                       fields={"shared_device_merchants": 1, "linked_merchants_2hop": neighbours,
                               "mule_flagged_neighbors": 0, "graph_clean": graph_clean}),
        EvidenceRecord(evidence_id=f"support_tickets:{mid}", source="support_tickets",
                       fields={"ticket_count_48h": tickets, "has_2fa_ticket_48h": t2fa,
                               "has_credential_ticket_48h": tcred, "ticket_text": ticket_text},
                       merchant_authored=frozenset({"ticket_text"})),
        EvidenceRecord(evidence_id=f"beneficiary_history:{bid}", source="beneficiary_history",
                       fields={"beneficiary_age_hrs": bene_age, "distinct_merchants_30d": bene_merchants,
                               "settled_payouts_30d": bene_settled, "on_mule_list": False,
                               "beneficiary_name": bene_name},
                       merchant_authored=frozenset({"beneficiary_name"})),
    ]


def scenarios() -> list[Scenario]:
    p1 = _payout("sc1_po", "sc1_m", "sc1_b", 9000.0, "Apex Digital Ventures", "urgent liquidity transfer")
    s1 = Scenario(
        "1 hard-rule block",
        "A 12-day-old account adds a payee 18 minutes ago and sends $9,000. No judgement needed.",
        p1,
        _features(p1, account_age_days=12, avg_daily_volume_30d=800, beneficiary_age_hrs=0.3,
                  beneficiary_platform_age_hrs=0.3, first_time_payee=True),
        _evidence("sc1_m", "sc1_b", age=12, sector="software company", mcc="5734", avg=800, cb=0.0,
                  kyb="Lumen Software is a software company in Leeds, registered 2026.", bene_age=0.3,
                  bene_merchants=1, bene_settled=0, bene_name="Apex Digital Ventures"),
        Route.BLOCK, None)

    p2 = _payout("sc2_po", "sc2_m", "sc2_b", 1200.0, "Patterson Dental Supply", "Inv #4471 dental supplies")
    s2 = Scenario(
        "2 clear approve",
        "An 800-day-old dental practice pays its usual supplier $1,200, a fifth of its daily volume.",
        p2, _features(p2),
        _evidence("sc2_m", "sc2_b", age=800, sector="dental practice", mcc="8021", avg=6000, cb=0.005,
                  kyb="Oakline Dental Practice, Austin. Registered 2024. Business licence verified.",
                  bene_age=3000, bene_merchants=240, bene_settled=1800, bene_name="Patterson Dental Supply"),
        Route.APPROVE, None)

    p3 = _payout("sc3_po", "sc3_m", "sc3_b", 4200.0, "CryptoBridge Holdings LLC", "urgent liquidity transfer")
    s3 = Scenario(
        "3 gray, really fraud",
        "A 45-day-old dental practice, locked out two hours ago, sends $4,200 to a crypto holding company "
        "added three hours ago. No single rule fires; the payee does not fit the business.",
        p3,
        _features(p3, account_age_days=45, avg_daily_volume_30d=700, beneficiary_age_hrs=3,
                  beneficiary_platform_age_hrs=3, first_time_payee=True, support_credential_ticket_48h=True),
        _evidence("sc3_m", "sc3_b", age=45, sector="dental practice", mcc="8021", avg=700, cb=0.0,
                  kyb="Redfern Dental Practice, Pune. Registered 2026. Owner-managed.", tcred=True, tickets=1,
                  ticket_text="Locked out of the dashboard, need a password reset urgently.",
                  bene_age=3, bene_merchants=1, bene_settled=0, bene_name="CryptoBridge Holdings LLC"),
        Route.PENDING_REVIEW, AgentAction.BLOCK)

    p4 = _payout("sc4_po", "sc4_m", "sc4_b", 900.0, "LiveSound Stage Rentals", "Venue deposit INV-4471")
    s4 = Scenario(
        "4 gray, legitimate",
        "A 25-day-old ticketing company pays $900 to a stage-rental vendor that 140 other merchants also pay. "
        "Young account and new payee raise the score; everything else is ordinary.",
        p4,
        _features(p4, account_age_days=25, avg_daily_volume_30d=400, beneficiary_age_hrs=20,
                  beneficiary_platform_age_hrs=4000, first_time_payee=True),
        _evidence("sc4_m", "sc4_b", age=25, sector="event ticketing", mcc="7922", avg=400, cb=0.005,
                  kyb="Marlow Event Ticketing, Toronto. Registered 2026. Sells tickets for local concerts.",
                  bene_age=20, bene_merchants=140, bene_settled=900, bene_name="LiveSound Stage Rentals"),
        Route.PENDING_REVIEW, AgentAction.APPROVE)
    return [s1, s2, s3, s4]

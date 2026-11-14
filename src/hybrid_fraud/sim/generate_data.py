"""Build the synthetic world: merchants, payees, devices, tickets, payouts, labels.

Everything is invented and seeded (same seed, same data). The one number that
is not invented is the fraud rate: 48 payouts in 10,000, the brief's baseline,
counted by payouts. Fraud loss in dollars comes out higher because fraud
payouts are larger; the manifest records it.

Four fraud shapes (so the problem is not only young merchants):
  bustout      young merchant, a few clean payouts, then one large cash-out
  takeover     established merchant, attacker logs in from a new device
  mule         several victims paying one new beneficiary, each under $2,500
  structuring  young merchant, four payouts of about $2,400 within the hour

`noise` smudges each fraud signal independently, so fraud is not always
obvious: some fraud looks coherent, and some legitimate merchants look odd.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from hybrid_fraud.core.schemas import Payout
from hybrid_fraud.sim import vocab
from hybrid_fraud.sim.models import (
    Beneficiary, BeneficiaryLink, Dataset, DeviceLink, FraudType, Label, Merchant, Ticket,
)

SEED = 20261114
N_PAYOUTS = 20000
FRAUD_BPS = 48
N_FRAUD = round(N_PAYOUTS * FRAUD_BPS / 10000)  # 96
START = datetime(2026, 10, 1, tzinfo=timezone.utc)
DAYS = 30
N_LEGIT_MERCHANTS = 3900
N_TOP = 200
RAILS = ["RTP", "FEDNOW", "SEPA_INSTANT", "PUSH_TO_CARD"]
LONG_AGO = START - timedelta(days=700)


@dataclass
class _Draft:
    ts: datetime
    merchant_id: str
    beneficiary_id: str
    amount: float
    memo: str
    device_id: str
    fraud_type: FraudType | None
    payee_age_hrs: float | None  # None: draw the legitimate way


class _World:
    def __init__(self, seed: int, noise: float):
        self.rng = random.Random(seed)
        self.seed, self.noise = seed, noise
        self.merchants: dict[str, Merchant] = {}
        self.beneficiaries: dict[str, Beneficiary] = {}
        self.device_links: list[DeviceLink] = []
        self.tickets: list[Ticket] = []
        self.drafts: list[_Draft] = []
        self.vendors: dict[str, list[Beneficiary]] = {}
        self._n_ticket = 0

    # ---- small helpers -------------------------------------------------
    def smudge(self) -> bool:
        """True when one fraud signal should look innocent this time."""
        return self.rng.random() < self.noise * 0.5

    def at(self, lo_day: float, hi_day: float) -> datetime:
        return START + timedelta(seconds=self.rng.uniform(lo_day * 86400, hi_day * 86400))

    def memo(self, sector_purposes: list[str]) -> str:
        return self.rng.choice(vocab.BENIGN_MEMO).format(
            n=self.rng.randint(1000, 9999), purpose=self.rng.choice(sector_purposes))

    def add_ticket(self, merchant_id: str, ts: datetime, category: str) -> None:
        self._n_ticket += 1
        text = self.rng.choice(vocab.TICKET_TEXT[category])
        self.tickets.append(Ticket(ticket_id=f"tk_{self._n_ticket:06d}", merchant_id=merchant_id,
                                   created_at=ts, category=category, text=text))

    def add_beneficiary(self, bid: str, name: str, first_seen: datetime, mule_list: bool = False) -> Beneficiary:
        b = Beneficiary(beneficiary_id=bid, name=name, first_seen_at=first_seen, on_mule_list=mule_list)
        self.beneficiaries[bid] = b
        return b

    def add_merchant(self, mid: str, age_days: float, sector_idx: int, avg_daily: float,
                     chargeback: float, top: bool = False) -> Merchant:
        sector, mcc, _ = vocab.SECTORS[sector_idx]
        name = f"{self.rng.choice(vocab.NAME_PREFIX)} {sector.title()}"
        city = self.rng.choice(vocab.CITIES)
        created = START - timedelta(days=age_days)
        kyb = self.rng.choice(vocab.KYB_TEMPLATES).format(
            name=name, sector=sector, city=city, year=created.year)
        m = Merchant(merchant_id=mid, created_at=created, legal_name=name, sector=sector, mcc_code=mcc,
                     avg_daily_volume_30d=round(avg_daily, 2), chargeback_rate_90d=round(chargeback, 4),
                     is_top_200=top, kyb_text=kyb)
        self.merchants[mid] = m
        return m

    def draft(self, **kw) -> None:
        self.drafts.append(_Draft(**kw))


def _legit_age(rng: random.Random, top: bool) -> float:
    if top:
        return rng.randint(401, 2500)
    return rng.choice([rng.randint(1, 90), rng.randint(91, 400), rng.randint(401, 2500)])


def _make_legit(w: _World) -> list[tuple[str, int]]:
    """Legitimate merchants (and the victims of takeovers). Returns (merchant_id, payout count)."""
    rng = w.rng
    for sector, _, _ in vocab.SECTORS:  # shared vendors: many merchants pay the same few
        w.vendors[sector] = [
            w.add_beneficiary(f"ben_{sector.split()[0]}_{k}", name, LONG_AGO)
            for k, name in enumerate(vocab.LEGIT_PAYEE[sector])
        ]
    shared_devices = [f"dev_shared_{k:03d}" for k in range(120)]  # offices and accountants
    out = []
    for i in range(N_LEGIT_MERCHANTS):
        top = i < N_TOP
        mid = f"m_{i:06d}"
        avg = rng.uniform(30000, 90000) if top else rng.uniform(500, 40000)
        w.add_merchant(mid, _legit_age(rng, top), rng.randrange(len(vocab.SECTORS)), avg, rng.uniform(0, 0.035), top)
        if rng.random() < 0.08:  # a minority share a device
            w.device_links.append(DeviceLink(merchant_id=mid, device_id=rng.choice(shared_devices), first_seen_at=LONG_AGO))
        w.device_links.append(DeviceLink(merchant_id=mid, device_id=f"dev_{mid}", first_seen_at=LONG_AGO))
        out.append((mid, rng.randint(12, 25) if top else rng.choices(range(1, 9), [26, 22, 16, 12, 9, 7, 5, 3])[0]))
        if rng.random() < 0.30:
            w.add_ticket(mid, w.at(0, DAYS), rng.choice(["billing", "other"]))
    return out


def _legit_payouts(w: _World, plan: list[tuple[str, int]], target: int) -> None:
    rng = w.rng
    total = sum(n for _, n in plan)
    non_top = [i for i, (mid, _) in enumerate(plan) if not w.merchants[mid].is_top_200]
    while total != target:  # trim or pad so the whole world has exactly N_PAYOUTS
        i = rng.choice(non_top)
        mid, n = plan[i]
        if total > target and n > 1:
            plan[i], total = (mid, n - 1), total - 1
        elif total < target:
            plan[i], total = (mid, n + 1), total + 1
    for mid, n in plan:
        m = w.merchants[mid]
        purposes = next(p for s, _, p in vocab.SECTORS if s == m.sector)
        vendor = rng.choice(w.vendors[m.sector])
        for _ in range(n):
            amount = min(18000.0, max(150.0, m.avg_daily_volume_30d * rng.uniform(0.05, 1.5)))
            if rng.random() < 0.07:  # a big supplier invoice: legitimate, but large for this merchant
                amount = min(18000.0, m.avg_daily_volume_30d * rng.uniform(2, 8))
            if rng.random() < 0.02:  # the occasional odd but legitimate payee
                payee = f"ben_odd_{mid}"
                w.add_beneficiary(payee, rng.choice(vocab.SUSPECT_PAYEE), LONG_AGO)
                memo = rng.choice(vocab.SUSPECT_MEMO)
            else:
                payee, memo = vendor.beneficiary_id, w.memo(purposes)
            ts = w.at(0, DAYS)
            w.draft(ts=ts, merchant_id=mid, beneficiary_id=payee, amount=round(amount, 2), memo=memo,
                    device_id=f"dev_{mid}", fraud_type=None, payee_age_hrs=None)


def _fraud_payee(w: _World, m: Merchant, tag: str, ts: datetime, age_hrs: float, mule_list_p: float = 0.0):
    """A payee for a fraud payout: usually a suspicious newcomer; sometimes one that looks coherent."""
    if w.smudge():  # looks coherent: a real vendor for this sector, plausible memo
        vendor = w.rng.choice(w.vendors[m.sector])
        purposes = next(p for s, _, p in vocab.SECTORS if s == m.sector)
        return vendor.beneficiary_id, w.memo(purposes), None
    bid = f"ben_x_{tag}"
    listed = w.rng.random() < mule_list_p
    w.add_beneficiary(bid, w.rng.choice(vocab.SUSPECT_PAYEE), ts - timedelta(hours=age_hrs), listed)
    return bid, w.rng.choice(vocab.SUSPECT_MEMO), age_hrs


def _bustout(w: _World, count: int = 30, payouts: int = 55) -> None:
    rng = w.rng
    for k in range(count):
        mid = f"m_f_b{k:03d}"
        w.add_merchant(mid, rng.randint(2, 75), rng.randrange(len(vocab.SECTORS)), rng.uniform(200, 3000),
                       rng.uniform(0, 0.02))
        w.device_links.append(DeviceLink(merchant_id=mid, device_id=f"dev_{mid}", first_seen_at=LONG_AGO))
        m = w.merchants[mid]
        purposes = next(p for s, _, p in vocab.SECTORS if s == m.sector)
        vendor = rng.choice(w.vendors[m.sector])
        for _ in range(rng.randint(2, 4)):  # behaves well first
            w.draft(ts=w.at(0, 17), merchant_id=mid, beneficiary_id=vendor.beneficiary_id,
                    amount=round(rng.uniform(150, 800), 2), memo=w.memo(purposes), device_id=f"dev_{mid}",
                    fraud_type=None, payee_age_hrs=None)
        n_fraud = 2 if k < payouts - count else 1
        t0 = w.at(18, 29)
        device = f"dev_{mid}" if w.smudge() else f"dev_atk_b{k % 6}"
        if device.startswith("dev_atk"):
            w.device_links.append(DeviceLink(merchant_id=mid, device_id=device, first_seen_at=t0 - timedelta(minutes=20)))
        age = rng.uniform(0.1, 22.0)
        bid, memo, payee_age = _fraud_payee(w, m, f"b{k}", t0, age, mule_list_p=0.15)
        for j in range(n_fraud):
            amount = rng.uniform(4000, 15000) if not w.smudge() else rng.uniform(900, 3000)
            w.draft(ts=t0 + timedelta(minutes=20 * j), merchant_id=mid, beneficiary_id=bid, amount=round(amount, 2),
                    memo=memo, device_id=device, fraud_type="bustout", payee_age_hrs=payee_age)


def _takeover(w: _World, count: int = 20, payouts: int = 25) -> None:
    rng = w.rng
    for k in range(count):
        mid = f"m_f_t{k:03d}"
        age = rng.randint(200, 2500)
        w.add_merchant(mid, age, rng.randrange(len(vocab.SECTORS)), rng.uniform(1500, 25000), rng.uniform(0, 0.03))
        w.device_links.append(DeviceLink(merchant_id=mid, device_id=f"dev_{mid}", first_seen_at=LONG_AGO))
        m = w.merchants[mid]
        purposes = next(p for s, _, p in vocab.SECTORS if s == m.sector)
        vendor = rng.choice(w.vendors[m.sector])
        for _ in range(rng.randint(3, 8)):  # an ordinary history
            w.draft(ts=w.at(0, DAYS), merchant_id=mid, beneficiary_id=vendor.beneficiary_id,
                    amount=round(min(18000, m.avg_daily_volume_30d * rng.uniform(0.05, 1.5)), 2),
                    memo=w.memo(purposes), device_id=f"dev_{mid}", fraud_type=None, payee_age_hrs=None)
        t0 = w.at(5, 29)
        device = f"dev_{mid}" if w.smudge() else f"dev_atk_t{k % 5}"
        if device.startswith("dev_atk"):
            w.device_links.append(DeviceLink(merchant_id=mid, device_id=device, first_seen_at=t0 - timedelta(minutes=15)))
        if rng.random() < 0.55:  # the account was just messed with
            w.add_ticket(mid, t0 - timedelta(hours=rng.uniform(0.5, 40)), rng.choice(["2fa", "credential"]))
        bid, memo, payee_age = _fraud_payee(w, m, f"t{k}", t0, rng.uniform(0.1, 12.0))
        for j in range(2 if k < payouts - count else 1):
            amount = min(15000, m.avg_daily_volume_30d * rng.uniform(2, 6)) if not w.smudge() else rng.uniform(1500, 3500)
            w.draft(ts=t0 + timedelta(minutes=25 * j), merchant_id=mid, beneficiary_id=bid, amount=round(amount, 2),
                    memo=memo, device_id=device, fraud_type="takeover", payee_age_hrs=payee_age)


def _mule(w: _World, victims: int = 4) -> None:
    rng = w.rng
    day = rng.uniform(10, 25)
    mule_first_seen = START + timedelta(days=day) - timedelta(hours=3)
    w.add_beneficiary("ben_x_mule", rng.choice(vocab.SUSPECT_PAYEE), mule_first_seen)
    for k in range(victims):
        mid = f"m_f_m{k:03d}"
        w.add_merchant(mid, rng.randint(300, 2000), rng.randrange(len(vocab.SECTORS)), rng.uniform(3000, 20000),
                       rng.uniform(0, 0.02))
        w.device_links.append(DeviceLink(merchant_id=mid, device_id=f"dev_{mid}", first_seen_at=LONG_AGO))
        purposes = next(p for s, _, p in vocab.SECTORS if s == w.merchants[mid].sector)
        vendor = rng.choice(w.vendors[w.merchants[mid].sector])
        for _ in range(rng.randint(3, 6)):
            w.draft(ts=w.at(0, DAYS), merchant_id=mid, beneficiary_id=vendor.beneficiary_id,
                    amount=round(rng.uniform(300, 4000), 2), memo=w.memo(purposes), device_id=f"dev_{mid}",
                    fraud_type=None, payee_age_hrs=None)
        t0 = START + timedelta(days=day, hours=k * 0.9)
        w.add_ticket(mid, t0 - timedelta(hours=rng.uniform(1, 30)), "credential")
        for j in range(2):  # each just under $2,500, so no single payout draws scrutiny
            w.draft(ts=t0 + timedelta(minutes=30 * j), merchant_id=mid, beneficiary_id="ben_x_mule",
                    amount=round(rng.uniform(1800, 2450), 2), memo=rng.choice(vocab.SUSPECT_MEMO),
                    device_id=f"dev_{mid}", fraud_type="mule", payee_age_hrs=rng.uniform(0.3, 3.0))


def _structuring(w: _World, count: int = 2) -> None:
    rng = w.rng
    for k in range(count):
        mid = f"m_f_s{k:03d}"
        w.add_merchant(mid, rng.randint(20, 60), rng.randrange(len(vocab.SECTORS)), rng.uniform(300, 2500),
                       rng.uniform(0, 0.02))
        w.device_links.append(DeviceLink(merchant_id=mid, device_id=f"dev_{mid}", first_seen_at=LONG_AGO))
        m = w.merchants[mid]
        purposes = next(p for s, _, p in vocab.SECTORS if s == m.sector)
        vendor = rng.choice(w.vendors[m.sector])
        for _ in range(rng.randint(2, 4)):
            w.draft(ts=w.at(0, 15), merchant_id=mid, beneficiary_id=vendor.beneficiary_id,
                    amount=round(rng.uniform(150, 600), 2), memo=w.memo(purposes), device_id=f"dev_{mid}",
                    fraud_type=None, payee_age_hrs=None)
        t0 = w.at(18, 29)
        bid, memo, payee_age = _fraud_payee(w, m, f"s{k}", t0, rng.uniform(1, 20))
        for j in range(4):
            w.draft(ts=t0 + timedelta(minutes=14 * j), merchant_id=mid, beneficiary_id=bid,
                    amount=round(rng.uniform(2350, 2450), 2), memo=memo, device_id=f"dev_{mid}",
                    fraud_type="structuring", payee_age_hrs=payee_age)


def _legit_ticket_noise(w: _World) -> None:
    """A few legitimate merchants really did just open a two-factor ticket."""
    for d in w.rng.sample([d for d in w.drafts if d.fraud_type is None], 120):
        w.add_ticket(d.merchant_id, d.ts - timedelta(hours=w.rng.uniform(1, 40)), "2fa")


def generate(seed: int = SEED, noise: float = 0.35) -> Dataset:
    w = _World(seed, noise)
    plan = _make_legit(w)
    _bustout(w), _takeover(w), _mule(w), _structuring(w)
    n_fraud_drafts = sum(1 for d in w.drafts if d.fraud_type)
    assert n_fraud_drafts == N_FRAUD, n_fraud_drafts
    # Legitimate payouts: pad the plan so that all payouts total exactly N_PAYOUTS.
    already = sum(1 for d in w.drafts if d.fraud_type is None)
    _legit_payouts(w, plan, N_PAYOUTS - N_FRAUD - already)
    _legit_ticket_noise(w)

    drafts = sorted(w.drafts, key=lambda d: (d.ts, d.merchant_id, d.beneficiary_id, d.amount))
    links: dict[tuple[str, str], BeneficiaryLink] = {}
    payouts, labels = [], []
    for i, d in enumerate(drafts):
        key = (d.merchant_id, d.beneficiary_id)
        if key not in links:  # the payee is added just before its first use by this merchant
            age = d.payee_age_hrs
            if age is None:
                age = w.rng.uniform(0.5, 96.0) if w.rng.random() < 0.15 else w.rng.uniform(200, 9000)
            added = max(w.merchants[d.merchant_id].created_at, d.ts - timedelta(hours=age))
            links[key] = BeneficiaryLink(merchant_id=d.merchant_id, beneficiary_id=d.beneficiary_id, added_at=added)
        b = w.beneficiaries[d.beneficiary_id]
        pid = f"po_{i:06d}"
        payouts.append(Payout(
            payout_id=pid, merchant_id=d.merchant_id, beneficiary_id=d.beneficiary_id, amount_usd=d.amount,
            rail=w.rng.choice(RAILS), beneficiary_name=b.name, payout_memo=d.memo, device_id=d.device_id,
            created_at=d.ts))
        labels.append(Label(payout_id=pid, is_fraud=d.fraud_type is not None, fraud_type=d.fraud_type))

    return Dataset(
        seed=seed, noise=noise,
        merchants=sorted(w.merchants.values(), key=lambda m: m.merchant_id),
        beneficiaries=sorted(w.beneficiaries.values(), key=lambda b: b.beneficiary_id),
        beneficiary_links=sorted(links.values(), key=lambda l: (l.merchant_id, l.beneficiary_id)),
        device_links=sorted(w.device_links, key=lambda l: (l.merchant_id, l.device_id)),
        tickets=sorted(w.tickets, key=lambda t: t.ticket_id),
        payouts=payouts, labels=labels,
    )


if __name__ == "__main__":
    ds = generate()
    fraud = [l for l in ds.labels if l.is_fraud]
    print(f"{len(ds.payouts)} payouts, {len(fraud)} fraudulent ({len(fraud) / len(ds.payouts) * 1e4:.1f} bps by count)")

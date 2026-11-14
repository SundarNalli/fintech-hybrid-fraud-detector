"""Run the evaluation and write the results.

    python -m hybrid_fraud.eval.run --provider scripted [--fault-rate 0.1] [--repeats 5]
    python -m hybrid_fraud.eval.run --provider replay   --replay-dir data/replay
    python -m hybrid_fraud.eval.run --provider live --confirm     # your own key; spends real money

Three systems are compared on the same 20,000 synthetic payouts:
  A  rules only          every held payout goes to the human queue
  B  rules + agent       held payouts go agent -> verifier -> policy wrapper
  C  perfect oracle      held payouts are decided correctly (the old ceiling, kept for comparison)

The harness drives the same service code the demo uses. Labels are read only here, at the end.
"""

from __future__ import annotations

import argparse
import os
import shutil
import statistics
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from hybrid_fraud.agent.budget import Prices
from hybrid_fraud.agent.providers import LlmProvider, make_provider
from hybrid_fraud.core.config import Thresholds, load_thresholds
from hybrid_fraud.core.schemas import PayoutState as S
from hybrid_fraud.eval.metrics import Row, gray_summary, summarise
from hybrid_fraud.eval.report import render
from hybrid_fraud.eval.scripted_investigator import ScriptedInvestigator
from hybrid_fraud.service.gray_zone import GrayZoneOutcome, GrayZoneProcessor
from hybrid_fraud.service.main import prices_from_env
from hybrid_fraud.service.payout_service import PayoutService
from hybrid_fraud.sim.dataset_io import read_dataset
from hybrid_fraud.sim.models import Dataset
from hybrid_fraud.store.db import connect, load_world


@dataclass
class EvalResult:
    systems: dict[str, list[Row]]
    outcomes: list[GrayZoneOutcome]  # from the first repeat
    repeat_agreement: float | None  # share of gray cases with the same final state in every repeat
    repeats: int
    stopped_for_budget: int  # held payouts left unprocessed because the run budget ran out


class _FixedClock:
    def __call__(self) -> float:
        return 1_800_000_000.0  # holds never expire during an evaluation


def _final_states(db_path: Path) -> dict[str, S]:
    conn = connect(db_path)
    try:
        return {pid: S(state) for pid, state in conn.execute("SELECT payout_id, state FROM payouts")}
    finally:
        conn.close()


def _rows(ds: Dataset, states: dict[str, S], gray_ids: set[str], top: set[str]) -> list[Row]:
    labels = {l.payout_id: l.is_fraud for l in ds.labels}
    return [Row(p.payout_id, p.merchant_id, p.amount_usd, labels[p.payout_id], p.merchant_id in top,
                states[p.payout_id], p.payout_id in gray_ids) for p in ds.payouts]


def evaluate(ds: Dataset, provider_factory, t: Thresholds, prices: Prices = Prices(), repeats: int = 1,
             max_usd: float | None = None, max_cases: int | None = None) -> EvalResult:
    top = {m.merchant_id for m in ds.merchants if m.is_top_200}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base = tmp / "base.db"
        conn = connect(base)
        load_world(conn, ds)
        service = PayoutService(conn, t, _FixedClock())
        for p in ds.payouts:  # the hot path decides everything; gray ones are left held
            service.submit(p, f"key_{p.payout_id}")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()

        after_rules = _final_states(base)
        gray_ids = {pid for pid, st in after_rules.items() if st == S.PENDING_REVIEW}
        gray_order = [p.payout_id for p in ds.payouts if p.payout_id in gray_ids][:max_cases]

        runs: list[dict[str, S]] = []
        outcomes: list[GrayZoneOutcome] = []
        spent, stopped = 0.0, 0
        for rep in range(repeats):
            path = tmp / f"run{rep}.db"
            shutil.copy(base, path)
            conn = connect(path)
            svc = PayoutService(conn, t, _FixedClock())
            processor = GrayZoneProcessor(svc, path, provider_factory(), t, prices)
            for pid in gray_order:
                if max_usd is not None and spent >= max_usd:
                    stopped += 1
                    continue
                out = processor.process(pid)
                if out:
                    spent += out.cost_usd
                    if rep == 0:
                        outcomes.append(out)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            runs.append(_final_states(path))

    labels = {l.payout_id: l.is_fraud for l in ds.labels}
    sys_a = {pid: (S.ESCALATED if st == S.PENDING_REVIEW else st) for pid, st in after_rules.items()}
    sys_b = {pid: (S.ESCALATED if st == S.PENDING_REVIEW else st) for pid, st in runs[0].items()}
    sys_c = {pid: (S.BLOCKED if labels[pid] else S.APPROVED) if pid in gray_ids else st
             for pid, st in after_rules.items()}
    agreement = None
    if repeats > 1 and gray_order:
        agreement = sum(1 for pid in gray_order if len({r[pid] for r in runs}) == 1) / len(gray_order)
    return EvalResult(
        {"A rules only": _rows(ds, sys_a, gray_ids, top), "B rules + agent": _rows(ds, sys_b, gray_ids, top),
         "C perfect oracle": _rows(ds, sys_c, gray_ids, top)},
        outcomes, agreement, repeats, stopped)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["scripted", "replay", "live"], default="scripted")
    ap.add_argument("--fault-rate", type=float, default=0.0, help="scripted only: share of cases made deliberately wrong")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--replay-dir", type=Path, default=Path("data/replay"))
    ap.add_argument("--max-cases", type=int, default=None)
    ap.add_argument("--max-usd", type=float, default=None, help="live only: stop when this much has been spent")
    ap.add_argument("--confirm", action="store_true", help="live only: required, because it spends money")
    ap.add_argument("--out", type=Path, default=None, help="write the markdown report here")
    args = ap.parse_args(argv)

    t, ds, prices = load_thresholds(), read_dataset(), prices_from_env()
    if args.provider == "scripted":
        factory, label = (lambda: ScriptedInvestigator(args.fault_rate)), \
            f"SCRIPTED STAND-IN (not a model), fault rate {args.fault_rate:.0%}"
    elif args.provider == "replay":
        factory, label = (lambda: make_provider(args.replay_dir, env={})), f"replay of recorded responses in {args.replay_dir}"
    else:
        key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
        if not key:
            print("No OPENROUTER_API_KEY or LLM_API_KEY in the environment; live mode needs your own key.")
            return 2
        if not (prices.input_per_token or prices.output_per_token):
            print("Set LLM_INPUT_USD_PER_MTOK and LLM_OUTPUT_USD_PER_MTOK first, so spend can be metered and capped.")
            return 2
        cap = args.max_usd if args.max_usd is not None else float(os.environ.get("MAX_USD_PER_EVAL_RUN") or 1.0)
        n = args.max_cases or 82
        print(f"Live run: up to {n} gray cases x {args.repeats} repeat(s), stopping at ${cap:.2f} spent "
              f"(per-case cap ${t.agent.max_usd_per_case}). Worst case is about ${n * args.repeats * t.agent.max_usd_per_case:.2f}.")
        if not args.confirm:
            print("Add --confirm to proceed. Nothing was sent.")
            return 2
        args.max_usd = cap
        factory = lambda: make_provider(args.replay_dir)
        label = f"LIVE model {os.environ.get('LLM_MODEL', 'default')} via {os.environ.get('LLM_BASE_URL', 'openrouter')}"

    result = evaluate(ds, factory, t, prices, args.repeats, args.max_usd, args.max_cases)
    text = render(result, label, str(date.today()), t)
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

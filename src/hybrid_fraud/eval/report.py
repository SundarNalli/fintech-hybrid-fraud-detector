"""Turn an EvalResult into the markdown results memo."""

from __future__ import annotations

import statistics
from collections import Counter

from hybrid_fraud.core.config import Thresholds
from hybrid_fraud.eval.metrics import Rate, gray_summary, summarise


def _pctile(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(len(s) * p))] if s else float("nan")


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in rows])


def render(result, label: str, today: str, t: Thresholds) -> str:
    names = list(result.systems)
    pop = {n: summarise(result.systems[n]) for n in names}
    gray = {n: gray_summary(result.systems[n]) for n in names}
    out = result.outcomes
    scripted = "SCRIPTED" in label
    n_gray = gray[names[0]]["cases"]
    n_fraud = pop[names[0]]["fraud_blocked"].n

    md = [f"# Evaluation results", "",
          f"Run on {today}. Agent: **{label}**. {result.repeats} repeat(s). Population: 20,000 synthetic payouts "
          f"({n_fraud} fraudulent). Held by the hot path: {n_gray}.", ""]
    if scripted:
        md += ["> **This run used a scripted stand-in, not a model.** It follows a fixed rule and reads the same tool "
               "output a model would. It checks that the pipeline and the guard work end to end, and it measures what "
               "the policy wrapper does to a sensible recommendation. It says nothing about how well a real model "
               "investigates. Column B below is the stand-in's score, not an AI result.", ""]
    if result.stopped_for_budget:
        md += [f"> The run stopped early on its spend cap; {result.stopped_for_budget} held payouts were left for humans.", ""]

    md += ["## 1. The whole population", "",
           "A: every held payout goes to the human queue. B: held payouts go agent, verifier, policy wrapper. "
           "C: the old perfect-oracle ceiling. Brackets are 95% intervals.", ""]
    keys = [("Fraud blocked", "fraud_blocked"), ("Fraud held for humans", "fraud_held"),
            ("Fraud approved (missed)", "fraud_approved"), ("Fraud caught or held", "fraud_caught_or_held"),
            ("Legitimate blocked", "legit_blocked"), ("Legitimate held for humans", "legit_held"),
            ("Merchants hit by a false block or hold", "merchants_hit"),
            ("  of which top-200 merchants", "top200_merchants_hit"), ("Auto-resolved (no human)", "auto_resolved")]
    rows = [[title] + [pop[n][k].fmt(2 if "legit" in k or "merchants" in k else 1) for n in names] for title, k in keys]
    rows.insert(4, ["Stolen dollars paid out"] + [f"${pop[n]['stolen_usd']:,.0f}" for n in names])
    rows.insert(5, ["Loss on paid-out dollars (bps)"] + [f"{pop[n]['loss_bps']:.1f}" for n in names])
    md += [_table(["Measure"] + names, rows), "",
           "Loss in bps is stolen dollars among paid-out dollars, times 10,000 (KPI 1). The brief's baseline is 48 and "
           "its target is 15 or less; the labels give full truth, so there is no 120-day maturity wait here.", ""]

    a, b, c = (pop[n] for n in names)
    missed = a["fraud_approved"]
    md += ["**What the agent cannot reach.** The agent only sees payouts the rules hold. "
           f"{missed.k} of {missed.n} fraud payouts ({missed.value:.0%}) were approved on the hot path, so they never "
           "reach it, and even the perfect oracle leaves them untouched. Closing that gap is a job for the rules, "
           "not the agent.", ""]
    if a["loss_bps"] < 15:
        md += [f"**Rules alone already beat the loss target in this synthetic world** ({a['loss_bps']:.1f} bps against 15). "
               "The generator's missed fraud is small-dollar, because the large fraud payouts are the ones the rules catch. "
               "So this world cannot show that the agent is needed to hit the target, and it should not be read as "
               "showing that it is not.", ""]

    md += ["## 2. The held payouts only", "",
           f"{n_gray} cases: {gray[names[0]]['fraud']} fraudulent, {gray[names[0]]['legit']} legitimate.", ""]
    g_rows = [[title] + [gray[n][k].fmt() for n in names[1:]] for title, k in [
        ("Approved", "approved"), ("Blocked", "blocked"), ("Sent to humans", "escalated"),
        ("Fraud blocked", "fraud_blocked"), ("Legitimate approved", "legit_approved"),
        ("Wrong, of those it decided", "wrong_of_decided"), ("Wrong, of all held", "wrong_of_all")]]
    md += [_table(["Measure"] + names[1:], g_rows), "",
           "A wrong call is an approved fraud or a blocked legitimate payout. Sending a case to a human is never counted "
           "wrong, which is why the rate is shown both ways.", ""]

    if out:
        flow = Counter((o.agent_action.value, o.final_state.value) for o in out)
        md += ["## 3. What the policy wrapper did to the agent's recommendations", ""]
        md += [_table(["Agent recommended", "Final state", "Cases"],
                      [[a, s, str(c)] for (a, s), c in sorted(flow.items())]), ""]
        guard = Counter(c for o in out for c in o.reason_codes if c.startswith("GUARD_"))
        if guard:
            md += ["Guard reasons behind downgrades and escalations:", ""]
            md += [f"- `{code}`: {c}" for code, c in guard.most_common()] + [""]
        cap = t.agent.ai_approval_cap_usd
        md += [f"The AI-approval cap is ${cap:,.0f} (an invented placeholder, A-19). Every `GUARD_APPROVE_OVER_CAP` "
               "above is a case where the agent recommended approval and the cap sent it to a human instead. "
               "Whether those approvals were right is not known from this table.", ""]

        calls = [o.tool_calls for o in out]
        lat = [o.latency_seconds for o in out]
        claims, bad = sum(o.claims_total for o in out), sum(o.claims_ungrounded for o in out)
        rejected = sum(o.verifier_rejected for o in out)
        leaked = sum(1 for o in out if o.claims_ungrounded and not o.verifier_rejected)
        cost = sum(o.cost_usd for o in out)
        fraud_caught = gray["B rules + agent"]["fraud_blocked"].k
        md += ["## 4. Agent mechanics", "", _table(["Measure", "Value"], [
            ["Tool calls per case (mean)", f"{statistics.fmean(calls):.1f}"],
            ["Latency per case, p50 / p95 (seconds)", f"{_pctile(lat, .5):.3f} / {_pctile(lat, .95):.3f}"],
            ["Cost per case (mean)", f"${cost / len(out):.4f}" if cost else "$0 (no priced model in this run)"],
            ["Cost per extra fraud caught", f"${cost / fraud_caught:.2f}" if cost and fraud_caught else "n/a"],
            ["Claims made", str(claims)],
            ["Ungrounded claims, before the verifier", Rate(bad, claims).fmt(1)],
            ["Cases the verifier rejected", Rate(rejected, len(out)).fmt(1)],
            ["Decisions built on an ungrounded claim", f"{leaked} (must be 0)"]]), ""]
        if scripted:
            md += ["Latency and cost here are those of a local script, so they say nothing about a real model. "
                   "The ungrounded-claim rate is the injected fault rate, not a model's behaviour.", ""]

    md += ["## 5. Repeatability", ""]
    if result.repeat_agreement is None:
        md += ["Not measured (one repeat)."]
    elif scripted:
        md += [f"{result.repeat_agreement:.1%} of held cases reached the same final state in all {result.repeats} runs. "
               "This is trivially 100% for a deterministic script and is not evidence about a model."]
    else:
        md += [f"{result.repeat_agreement:.1%} of held cases reached the same final state in all {result.repeats} runs."]

    md += ["", "## 6. Reading these results", "",
           "- **Synthetic data.** Every effect depends on how the generator was built. Legitimate friction here is far "
           "below the earlier test's 1.87% false blocks (A-34), so a real business would look different.",
           f"- **Small sample.** {n_gray} held cases and {n_fraud} fraud payouts make the intervals wide. A result of "
           "zero failures in 80 cases only shows the true rate is below about 4%.",
           "- **The cases are the generator's own gray zone**, not analyst-labelled ones. Templated text is cleaner than "
           "real attacker text, and the labels came from the same code that made the data, so a model could look better "
           "here than on real cases.",
           "- **Not run:** a real model, the tools-versus-no-tools comparison, comparing model sizes, and the "
           "cost-ratio threshold sliders. All need a live model."]
    return "\n".join(md) + "\n"

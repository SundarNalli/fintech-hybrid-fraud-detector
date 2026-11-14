"""Turn ledger rows into a readable evidence trace. Pure templating; no model involved."""

from __future__ import annotations

from datetime import datetime, timezone

from hybrid_fraud.audit.ledger import LedgerRow


def render_trace(rows: list[LedgerRow]) -> str:
    lines = []
    for r in rows:
        when = datetime.fromtimestamp(r.at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        step = f"{r.from_state or 'new'} -> {r.to_state}"
        lines.append(f"[{when}] {r.payout_id}: {step} (by {r.decided_by}) reasons: {', '.join(r.reason_codes) or 'none'}")
        lines += [f"    - {line}" for line in r.evidence_trace]
        if r.policy_note:
            lines.append(f"    policy: {r.policy_note}")
    return "\n".join(lines)

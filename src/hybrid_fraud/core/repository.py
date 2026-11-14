"""The read-only door the agent's tools go through.

The protocol has no write methods on purpose. The real implementation opens
SQLite with `mode=ro`, so a write fails at the database even if code tries.

Field names below are the contract. Tools, the verifier and the policy wrapper
all rely on them.
"""

from __future__ import annotations

from typing import Protocol

from hybrid_fraud.core.schemas import EvidenceRecord


class ReadOnlyRepository(Protocol):
    def merchant_profile(self, merchant_id: str) -> EvidenceRecord:
        """source "merchant_profile".
        fields: account_age_days, sector, mcc_code, avg_daily_volume_30d,
                chargeback_rate_90d, is_top_200, kyb_text.
        merchant_authored: {"kyb_text"}.
        """
        ...

    def entity_graph(self, merchant_id: str) -> EvidenceRecord:
        """source "entity_graph" (2-hop neighbourhood).
        fields: shared_device_merchants, linked_merchants_2hop,
                mule_flagged_neighbors, graph_clean (bool).
        merchant_authored: set().
        """
        ...

    def support_tickets(self, merchant_id: str) -> EvidenceRecord:
        """source "support_tickets" (last 48 hours).
        fields: ticket_count_48h, has_2fa_ticket_48h, has_credential_ticket_48h,
                ticket_text.
        merchant_authored: {"ticket_text"}.
        """
        ...

    def beneficiary_history(self, beneficiary_id: str) -> EvidenceRecord:
        """source "beneficiary_history" (across all merchants).
        fields: beneficiary_age_hrs, distinct_merchants_30d, settled_payouts_30d,
                on_mule_list (bool), beneficiary_name.
        merchant_authored: {"beneficiary_name"}.
        """
        ...

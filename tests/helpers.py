from hybrid_fraud.hot_path.features import PayoutFeatures


def make_features(**overrides) -> PayoutFeatures:
    """An ordinary, low-risk payout. Override a field to make it interesting."""
    base = dict(
        payout_id="po_test", merchant_id="m_test", amount_usd=1000.0, is_top_200=False,
        account_age_days=800, avg_daily_volume_30d=6000, chargeback_rate_90d=0.005,
        beneficiary_age_hrs=3000, beneficiary_platform_age_hrs=20000, beneficiary_on_mule_list=False,
        first_time_payee=False, shared_device_merchants=1, support_2fa_ticket_48h=False,
        support_credential_ticket_48h=False, velocity_count_1h=1, velocity_usd_1h=1000.0,
        velocity_usd_24h=1000.0, beneficiary_distinct_merchants_24h=1, beneficiary_usd_24h=1000.0,
    )
    return PayoutFeatures(**{**base, **overrides})

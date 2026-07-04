"""
Razorpay Plan sync — bridges AirPlan (our internal catalogue row) to a real
Razorpay Plan object, and derives the correct subscription `total_count` per
plan (CN-94 §1/§4: multi-month plans are a fixed-cycle commitment at a
discounted per-month rate, not an open-ended recurring charge).

Bug this closes: Subscriptions.create_link() previously passed AirPlan.plan_id
(our internal natural key, e.g. "companion_monthly") straight to Razorpay's
subscription.create as the plan_id — which only works if a Razorpay Plan
object with that EXACT id happens to exist. Razorpay auto-generates its own
plan ids ('plan_XXXXXXXXXXXX'); there was no code path anywhere that ever
created one. This module is that missing path: lazily create + cache the
real gateway plan id (AirPlan.gateway_plan_id) the first time a plan is used,
idempotent on every call after.

Also fixes: total_count was hardcoded to 12 regardless of billing_cycle, so
a 9-month prepay-at-discount plan would bill 12 cycles at the discounted
rate instead of exactly 9. commitment_cycles() reads AirPlan.metadata's
commitment_months (seeded by seed_tier_plans.py) for the correct count.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Razorpay requires total_count in [1, 100] (hard API limit). An open-ended
# "monthly, until cancelled" plan (no fixed commitment) uses the max — the
# member is never actually billed 100 times; cancel_subscription() (already
# wired, airpay.Subscriptions.cancel()) stops it at cycle end whenever the
# member cancels. This is the standard Razorpay pattern for "no fixed term".
_OPEN_ENDED_TOTAL_COUNT = 100


def commitment_cycles(air_plan) -> int:
    """How many billing cycles this plan's subscription should run for.

    Multi-month plans (5_month/9_month/3_month) have a fixed commitment —
    reads AirPlan.metadata['commitment_months'] (seeded exactly for this).
    'monthly' (no commitment) and any plan missing the metadata key fall back
    to the open-ended max, matching pre-CN-94 behavior for month-to-month.
    """
    metadata = air_plan.metadata or {}
    commitment = metadata.get("commitment_months")
    if commitment and int(commitment) > 0:
        return min(int(commitment), 100)
    return _OPEN_ENDED_TOTAL_COUNT


def get_or_create_gateway_plan(air_plan, backend=None) -> str:
    """Return the real Razorpay plan id for this AirPlan, creating it on
    Razorpay (and caching gateway_plan_id) on first use. Idempotent — a
    second call for the same AirPlan just returns the cached id, no new
    Razorpay Plan object is created.

    `backend` is injectable for tests; defaults to a fresh AirRazorpayBackend.
    """
    if air_plan.gateway_plan_id:
        return air_plan.gateway_plan_id

    if backend is None:
        from airpay.backends.razorpay_ import AirRazorpayBackend
        backend = AirRazorpayBackend()

    # Razorpay's `period`/`interval` describe how often ONE cycle bills;
    # total_count (set separately, at subscription-create time) is how many
    # cycles run before the subscription auto-completes. All our plans bill
    # monthly at the (possibly discounted) monthly_effective rate.
    amount_paise = int(round(air_plan.price * 100))
    plan = backend.create_plan(
        period="monthly",
        interval=1,
        amount=amount_paise,
        currency=air_plan.currency or "INR",
        name=air_plan.name,
        description=air_plan.description or air_plan.name,
    )
    gateway_plan_id = plan["id"]

    air_plan.gateway_plan_id = gateway_plan_id
    air_plan.save(update_fields=["gateway_plan_id"])
    logger.info(
        "razorpay_plan_sync.created plan_id=%s gateway_plan_id=%s amount_paise=%s",
        air_plan.plan_id, gateway_plan_id, amount_paise,
    )
    return gateway_plan_id

"""
Razorpay Plan sync — bridges AirPlan (internal catalogue row) to a real
Razorpay Plan object, and derives subscription `total_count` from plan
metadata (fixed-cycle multi-month commitments vs open-ended monthly).

Subscriptions.create_link() must pass a real Razorpay plan id, not the
internal AirPlan.plan_id natural key. This module lazily creates and caches
AirPlan.gateway_plan_id on first use.

commitment_cycles() reads AirPlan.metadata['commitment_months'] when set
(host seeders may populate that); otherwise it uses an open-ended max.
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

    Multi-month plans with metadata['commitment_months'] use that fixed
    cycle count. Plans without the key (typical month-to-month) fall back
    to the open-ended max.
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

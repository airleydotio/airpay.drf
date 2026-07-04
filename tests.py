from django.test import TestCase

# Create your tests here.

import pytest
from django.core.management import call_command
from io import StringIO


def _seed(*, dry_run=False, reprice_active_plans=False):
    out = StringIO()
    call_command(
        "seed_tier_plans", dry_run=dry_run,
        reprice_active_plans=reprice_active_plans, stdout=out,
    )
    return out.getvalue()


@pytest.mark.django_db
class TestSeedTierPlansCN94Grid:
    """CN-94 v1.0 locked pricing grid — seed_tier_plans safety-guard tests.

    Founder's explicit gating question before this reseed touches any real
    environment: "any live paying member on the wrong prices? If yes, stop
    and tell me — existing billing needs my ruling." These tests cover the
    guard that makes that check automatic and non-optional.
    """

    def test_seeds_all_nine_plans_on_empty_db(self):
        _seed()
        from airpay.models import AirPlan
        assert AirPlan.objects.filter(plan_id="companion_monthly").first().price == 599.0
        assert AirPlan.objects.filter(plan_id="companion_5month").first().price == 549.0
        assert AirPlan.objects.filter(plan_id="companion_9month").first().price == 499.0
        assert AirPlan.objects.filter(plan_id="guardian_monthly").first().price == 1899.0
        assert AirPlan.objects.filter(plan_id="guardian_5month").first().price == 1799.0
        assert AirPlan.objects.filter(plan_id="guardian_9month").first().price == 1699.0
        assert AirPlan.objects.filter(plan_id="medical_monthly").first().price == 8999.0
        assert AirPlan.objects.filter(plan_id="medical_5month").first().price == 8699.0
        assert AirPlan.objects.filter(plan_id="medical_9month").first().price == 8499.0

    def test_5_month_plans_flagged_gated_to_month_2_for_medical_only(self):
        _seed()
        from airpay.models import AirPlan
        companion = AirPlan.objects.get(plan_id="companion_5month")
        medical = AirPlan.objects.get(plan_id="medical_5month")
        assert not companion.metadata.get("gated_to_month_2")
        assert medical.metadata.get("gated_to_month_2") is True

    def test_dry_run_makes_no_db_changes(self):
        out = _seed(dry_run=True)
        from airpay.models import AirPlan
        assert "DRY RUN" in out
        assert not AirPlan.objects.filter(plan_id="companion_monthly").exists()

    def _make_active_subscription(self, plan):
        from django.contrib.auth import get_user_model
        from airpay.models import AirSeller, PaymentGateway, Subscriptions

        User = get_user_model()
        buyer = User.objects.create(username="buyer-" + plan.plan_id)
        seller_user = User.objects.create(username="seller-" + plan.plan_id)
        seller = AirSeller.objects.create(user=seller_user)
        gateway = PaymentGateway.objects.get(name="razorpay")
        return Subscriptions.objects.create(
            plan=plan, seller=seller, gateway=gateway, buyer=buyer, status="active",
        )

    def test_active_subscription_blocks_reprice_by_default(self):
        from airpay.models import AirPlan
        _seed()  # seeds CN-94 grid fresh (no prior rows) — simulate a stale
        # price by manually reverting one plan's price to the old CN-007 value,
        # as if it were seeded under the superseded seed before this session.
        plan = AirPlan.objects.get(plan_id="companion_monthly")
        plan.price = 499.0
        plan.save(update_fields=["price"])
        self._make_active_subscription(plan)

        out = _seed()  # re-run with the new CN-94 price target (599)
        plan.refresh_from_db()
        assert plan.price == 499.0  # untouched — the guard fired
        assert "SKIPPED companion_monthly" in out
        assert "1 subscription(s)" in out

    def test_reprice_active_plans_flag_forces_the_change(self):
        from airpay.models import AirPlan
        _seed()
        plan = AirPlan.objects.get(plan_id="guardian_monthly")
        plan.price = 1999.0
        plan.save(update_fields=["price"])
        self._make_active_subscription(plan)

        _seed(reprice_active_plans=True)
        plan.refresh_from_db()
        assert plan.price == 1899.0  # forced through

    def test_cancelled_subscription_does_not_block_reprice(self):
        from airpay.models import AirPlan
        _seed()
        plan = AirPlan.objects.get(plan_id="medical_monthly")
        plan.price = 4444.0
        plan.save(update_fields=["price"])
        sub = self._make_active_subscription(plan)
        sub.status = "cancelled"
        sub.save(update_fields=["status"])

        _seed()
        plan.refresh_from_db()
        assert plan.price == 8999.0  # no live subscriber, safe to reprice

    def test_superseded_plan_not_pruned_while_referenced(self):
        from airpay.models import AirPlan, PaymentGateway
        gateway, _ = PaymentGateway.objects.get_or_create(name="razorpay", defaults={"is_active": True})
        stale = AirPlan.objects.create(
            plan_id="medical_maintenance_monthly", name="Medical Maintenance",
            tier_level="medical", price=4444.0, currency="INR",
            billing_cycle="monthly", is_active=True, gateway=gateway,
            description="old", metadata={"source": "cn007_seed"},
        )
        self._make_active_subscription(stale)

        out = _seed()
        assert AirPlan.objects.filter(plan_id="medical_maintenance_monthly").exists()
        assert "NOT PRUNED medical_maintenance_monthly" in out

    def test_superseded_plan_pruned_when_unreferenced(self):
        from airpay.models import AirPlan, PaymentGateway
        gateway, _ = PaymentGateway.objects.get_or_create(name="razorpay", defaults={"is_active": True})
        AirPlan.objects.create(
            plan_id="medical_active_3m", name="Medical (3-month)",
            tier_level="medical", price=7777.0, currency="INR",
            billing_cycle="3_month", is_active=True, gateway=gateway,
            description="old", metadata={"source": "cn007_seed"},
        )
        _seed()
        assert not AirPlan.objects.filter(plan_id="medical_active_3m").exists()

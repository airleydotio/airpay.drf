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


class _FakeRazorpayBackend:
    """Stand-in for AirRazorpayBackend — no real Razorpay API calls."""

    def __init__(self):
        self.created_plans = []
        self.subscription_calls = []
        self._counter = 0

    def create_plan(self, *, period, interval, amount, currency, name, description=None):
        self._counter += 1
        gw_id = f"plan_FAKE{self._counter:06d}"
        self.created_plans.append({
            "id": gw_id, "period": period, "interval": interval,
            "amount": amount, "currency": currency, "name": name,
        })
        return {"id": gw_id}

    def create_subscription_link(self, plan_id, total_count, quantity=1, email=None,
                                  phone=None, start_at=None):
        self.subscription_calls.append({
            "plan_id": plan_id, "total_count": total_count, "start_at": start_at,
        })
        return {"id": "sub_FAKE001", "short_url": "https://rzp.io/fake"}

    def create_order(self, amount, currency):
        return {"id": "order_FAKE001"}


@pytest.mark.django_db
class TestRazorpayPlanSync:
    """Closes the confirmed bug: AirPlan.plan_id (our internal natural key)
    was passed directly to Razorpay's subscription.create as plan_id, which
    only works if a Razorpay Plan object with that exact id happens to
    exist — nothing ever created one."""

    def _plan(self, **overrides):
        from airpay.models import AirPlan, PaymentGateway
        gateway, _ = PaymentGateway.objects.get_or_create(name="razorpay", defaults={"is_active": True})
        defaults = dict(
            plan_id="companion_9month", name="Companion (9-month)", tier_level="companion",
            price=499.0, currency="INR", billing_cycle="9_month", is_active=True,
            gateway=gateway, description="test",
            metadata={"commitment_months": 9},
        )
        defaults.update(overrides)
        return AirPlan.objects.create(**defaults)

    def test_creates_real_gateway_plan_on_first_use(self):
        from airpay.razorpay_plan_sync import get_or_create_gateway_plan

        plan = self._plan()
        backend = _FakeRazorpayBackend()
        gw_id = get_or_create_gateway_plan(plan, backend=backend)

        assert gw_id.startswith("plan_FAKE")
        assert len(backend.created_plans) == 1
        assert backend.created_plans[0]["amount"] == 49900  # ₹499 in paise

        plan.refresh_from_db()
        assert plan.gateway_plan_id == gw_id

    def test_idempotent_second_call_reuses_cached_id(self):
        from airpay.razorpay_plan_sync import get_or_create_gateway_plan

        plan = self._plan()
        backend = _FakeRazorpayBackend()
        first = get_or_create_gateway_plan(plan, backend=backend)
        second = get_or_create_gateway_plan(plan, backend=backend)

        assert first == second
        assert len(backend.created_plans) == 1  # no duplicate Razorpay Plan created

    def test_commitment_cycles_reads_metadata(self):
        from airpay.razorpay_plan_sync import commitment_cycles

        nine_month = self._plan(plan_id="x9", metadata={"commitment_months": 9})
        five_month = self._plan(plan_id="x5", metadata={"commitment_months": 5})
        monthly = self._plan(plan_id="xm", billing_cycle="monthly", metadata={})

        assert commitment_cycles(nine_month) == 9
        assert commitment_cycles(five_month) == 5
        assert commitment_cycles(monthly) == 100  # open-ended max, not 12

    def test_commitment_cycles_handles_missing_metadata(self):
        from airpay.razorpay_plan_sync import commitment_cycles
        plan = self._plan(plan_id="xnull", metadata=None)
        assert commitment_cycles(plan) == 100


@pytest.mark.django_db
class TestSubscriptionCreateLinkFix:
    """Subscriptions.create_link() — verifies it now (a) uses the real
    gateway plan id instead of our internal natural key, and (b) uses the
    plan's actual commitment length instead of hardcoded 12."""

    def _subscription(self, *, billing_cycle, commitment_months, price=499.0):
        from django.contrib.auth import get_user_model
        from airpay.models import AirPlan, AirSeller, PaymentGateway, Subscriptions

        User = get_user_model()
        gateway, _ = PaymentGateway.objects.get_or_create(name="razorpay", defaults={"is_active": True})
        plan = AirPlan.objects.create(
            plan_id=f"test_{billing_cycle}", name="Test Plan", tier_level="companion",
            price=price, currency="INR", billing_cycle=billing_cycle, is_active=True,
            gateway=gateway, description="test",
            metadata={"commitment_months": commitment_months} if commitment_months else {},
        )
        buyer = User.objects.create(username="buyer-" + billing_cycle, email="b@example.com", mobile="+911234567890")
        seller_user = User.objects.create(username="seller-" + billing_cycle)
        seller = AirSeller.objects.create(user=seller_user)
        sub = Subscriptions.objects.create(plan=plan, seller=seller, gateway=gateway, buyer=buyer)
        return sub

    def test_9_month_plan_uses_9_cycles_not_12(self, monkeypatch):
        sub = self._subscription(billing_cycle="9_month", commitment_months=9)
        fake = _FakeRazorpayBackend()
        monkeypatch.setattr("airpay.models.get_gateway_backend", lambda name: fake)

        sub.create_link(trial_days=7)

        assert fake.subscription_calls[0]["total_count"] == 9
        assert fake.subscription_calls[0]["plan_id"].startswith("plan_FAKE")
        assert fake.subscription_calls[0]["plan_id"] != sub.plan.plan_id

    def test_monthly_plan_still_open_ended(self, monkeypatch):
        sub = self._subscription(billing_cycle="monthly", commitment_months=None)
        fake = _FakeRazorpayBackend()
        monkeypatch.setattr("airpay.models.get_gateway_backend", lambda name: fake)

        sub.create_link()

        assert fake.subscription_calls[0]["total_count"] == 100

    def test_yearly_plan_uses_single_cycle(self, monkeypatch):
        sub = self._subscription(billing_cycle="yearly", commitment_months=None)
        fake = _FakeRazorpayBackend()
        monkeypatch.setattr("airpay.models.get_gateway_backend", lambda name: fake)

        sub.create_link()

        assert fake.subscription_calls[0]["total_count"] == 1

    def test_gateway_plan_created_and_cached_across_subscriptions_on_same_plan(self, monkeypatch):
        sub1 = self._subscription(billing_cycle="5_month", commitment_months=5)
        fake = _FakeRazorpayBackend()
        monkeypatch.setattr("airpay.models.get_gateway_backend", lambda name: fake)
        sub1.create_link()

        # A second subscription referencing the SAME plan must reuse the cached
        # gateway_plan_id — no second Razorpay Plan object created.
        from airpay.models import AirSeller, PaymentGateway, Subscriptions
        from django.contrib.auth import get_user_model
        User = get_user_model()
        buyer2 = User.objects.create(username="buyer2", email="b2@example.com", mobile="+911234567891")
        gateway = PaymentGateway.objects.get(name="razorpay")
        seller = AirSeller.objects.first()
        sub2 = Subscriptions.objects.create(plan=sub1.plan, seller=seller, gateway=gateway, buyer=buyer2)
        sub2.create_link()

        assert len(fake.created_plans) == 1
        assert fake.subscription_calls[0]["plan_id"] == fake.subscription_calls[1]["plan_id"]

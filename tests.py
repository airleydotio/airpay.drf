"""Generic airpay plan-sync / create_link tests (no host catalogue)."""
from django.test import TestCase

import pytest


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
    """Gateway plan ids are created/cached; internal plan_id is never sent
    to Razorpay as the gateway plan_id."""

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

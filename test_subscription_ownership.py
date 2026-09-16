"""Ownership tests for the subscribe and cancel endpoints.

Two holes these cover:

1. ``CreateSubscriptions`` read the buyer from a ``buyer`` query parameter,
   defaulting to ``request.user.pk``. Any authenticated caller could raise a
   subscription against another member's id by passing it.

2. ``CancelSubscription`` looked the subscription up by a ``subscription_id``
   query parameter with no owner check at all -- and ignored the
   ``subscriptionId`` the URL already carries. Any authenticated caller could
   cancel anyone's subscription. The unguarded ``.get()`` also meant an
   unknown id surfaced as a 500.
"""
import uuid

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from airpay.views import CancelSubscription, CreateSubscriptions


class _FakeGatewayBackend:
    """Stand-in for AirRazorpayBackend -- no real Razorpay API calls."""

    def __init__(self):
        self.cancelled = []
        self._counter = 0

    def create_plan(self, **kwargs):
        self._counter += 1
        return {"id": f"plan_FAKE{self._counter:06d}"}

    def create_order(self, amount, currency):
        return {"id": "order_FAKE001"}

    def create_subscription_link(self, plan_id, total_count, quantity=1, email=None,
                                 phone=None, start_at=None):
        return {"id": "sub_FAKE001", "short_url": "https://rzp.io/fake"}

    def cancel_subscription(self, subscription_id):
        self.cancelled.append(subscription_id)
        return True


def _user(tag, **extra):
    from django.contrib.auth import get_user_model

    suffix = uuid.uuid4().hex[:8]
    return get_user_model().objects.create(
        username=f"{tag}_{suffix}",
        email=f"{tag}_{suffix}@example.com",
        mobile=f"+9190{suffix}"[:15],
        **extra,
    )


def _plan():
    from airpay.models import AirPlan, PaymentGateway

    gateway, _ = PaymentGateway.objects.get_or_create(
        name="razorpay", defaults={"is_active": True}
    )
    return AirPlan.objects.create(
        plan_id=f"plan_{uuid.uuid4().hex[:8]}", name="Test Plan",
        tier_level="companion", price=499.0, currency="INR",
        billing_cycle="monthly", is_active=True, gateway=gateway,
        description="test", metadata={},
    )


def _admin_seller():
    """CreateSubscriptions.get evaluates get_admin_seller_id() eagerly (it is
    the default argument of query_params.get), so one must always exist."""
    from airpay.models import AirSeller

    seller = AirSeller.objects.filter(is_super_admin=True).first()
    if seller is None:
        seller = AirSeller.objects.create(user=_user("seller"), is_super_admin=True)
    return seller


def _subscription_for(user):
    from airpay.models import PaymentGateway, Subscriptions

    plan = _plan()
    gateway = PaymentGateway.objects.get(name="razorpay")
    return Subscriptions.objects.create(
        plan=plan, seller=_admin_seller(), gateway=gateway,
        buyer=user, status="active", subscription_id="sub_LIVE001",
    )


@pytest.mark.django_db
class TestCreateSubscriptionBuyerIsTheCaller:
    def _call(self, caller, params):
        factory = APIRequestFactory()
        req = factory.get("/api/airpay/subscribe/", params)
        force_authenticate(req, user=caller)
        return CreateSubscriptions.as_view()(req)

    def test_buyer_query_param_cannot_bill_another_member(self, monkeypatch):
        from airpay.models import Subscriptions

        monkeypatch.setattr(
            "airpay.models.get_gateway_backend", lambda name: _FakeGatewayBackend()
        )
        caller = _user("caller")
        victim = _user("victim")
        plan = _plan()

        response = self._call(
            caller,
            {"seller_id": str(_admin_seller().pk), "plan_id": str(plan.pk),
             "gateway": "razorpay", "buyer": str(victim.pk)},
        )

        assert response.status_code == 200, response.data
        assert not Subscriptions.objects.filter(buyer=victim).exists(), (
            "the buyer query parameter billed a subscription to another member"
        )
        assert Subscriptions.objects.filter(buyer=caller).count() == 1

    def test_staff_may_still_set_buyer(self, monkeypatch):
        from airpay.models import Subscriptions

        monkeypatch.setattr(
            "airpay.models.get_gateway_backend", lambda name: _FakeGatewayBackend()
        )
        staff = _user("staff", is_staff=True)
        member = _user("member")
        plan = _plan()

        response = self._call(
            staff,
            {"seller_id": str(_admin_seller().pk), "plan_id": str(plan.pk),
             "gateway": "razorpay", "buyer": str(member.pk)},
        )

        assert response.status_code == 200, response.data
        assert Subscriptions.objects.filter(buyer=member).count() == 1

    def test_absent_buyer_param_still_bills_the_caller(self, monkeypatch):
        from airpay.models import Subscriptions

        monkeypatch.setattr(
            "airpay.models.get_gateway_backend", lambda name: _FakeGatewayBackend()
        )
        caller = _user("solo")
        plan = _plan()

        response = self._call(
            caller,
            {"seller_id": str(_admin_seller().pk), "plan_id": str(plan.pk),
             "gateway": "razorpay"},
        )

        assert response.status_code == 200, response.data
        assert Subscriptions.objects.filter(buyer=caller).count() == 1


@pytest.mark.django_db
class TestCancelSubscriptionOwnership:
    def _call(self, caller, subscription_id, query=None):
        factory = APIRequestFactory()
        req = factory.put("/api/airpay/subscription/x/cancel/", query or {})
        force_authenticate(req, user=caller)
        return CancelSubscription.as_view()(req, subscriptionId=str(subscription_id))

    def test_member_cannot_cancel_another_members_subscription(self, monkeypatch):
        fake = _FakeGatewayBackend()
        monkeypatch.setattr("airpay.models.get_gateway_backend", lambda name: fake)
        attacker = _user("attacker")
        victim_sub = _subscription_for(_user("victim"))

        response = self._call(attacker, victim_sub.pk)

        assert response.status_code == 404
        victim_sub.refresh_from_db()
        assert victim_sub.status == "active"
        assert fake.cancelled == [], "the gateway was asked to cancel someone else's subscription"

    def test_query_parameter_id_is_ignored(self, monkeypatch):
        """The old hole: the id came from ?subscription_id=, not the URL."""
        fake = _FakeGatewayBackend()
        monkeypatch.setattr("airpay.models.get_gateway_backend", lambda name: fake)
        attacker = _user("attacker2")
        own_sub = _subscription_for(attacker)
        victim_sub = _subscription_for(_user("victim2"))

        response = self._call(
            attacker, own_sub.pk, query={"subscription_id": str(victim_sub.pk)}
        )

        assert response.status_code == 200, response.data
        own_sub.refresh_from_db()
        victim_sub.refresh_from_db()
        assert own_sub.status == "cancelled"
        assert victim_sub.status == "active"

    def test_member_can_cancel_own_subscription(self, monkeypatch):
        fake = _FakeGatewayBackend()
        monkeypatch.setattr("airpay.models.get_gateway_backend", lambda name: fake)
        member = _user("owner")
        own_sub = _subscription_for(member)

        response = self._call(member, own_sub.pk)

        assert response.status_code == 200, response.data
        own_sub.refresh_from_db()
        assert own_sub.status == "cancelled"
        assert fake.cancelled == ["sub_LIVE001"]

    def test_unknown_id_is_404(self, monkeypatch):
        monkeypatch.setattr(
            "airpay.models.get_gateway_backend", lambda name: _FakeGatewayBackend()
        )
        response = self._call(_user("nobody"), uuid.uuid4())
        assert response.status_code == 404

    def test_malformed_id_is_404_not_500(self, monkeypatch):
        monkeypatch.setattr(
            "airpay.models.get_gateway_backend", lambda name: _FakeGatewayBackend()
        )
        response = self._call(_user("nobody2"), "not-a-uuid")
        assert response.status_code == 404

    def test_patch_is_scoped_too(self, monkeypatch):
        """UpdateAPIView exposes PUT and PATCH, and `partial_update`
        delegates to the same `update()`. PATCH must be scoped identically."""
        fake = _FakeGatewayBackend()
        monkeypatch.setattr("airpay.models.get_gateway_backend", lambda name: fake)
        attacker = _user("patcher")
        victim_sub = _subscription_for(_user("victim3"))

        factory = APIRequestFactory()
        req = factory.patch("/api/airpay/subscription/x/cancel/", {})
        force_authenticate(req, user=attacker)
        response = CancelSubscription.as_view()(req, subscriptionId=str(victim_sub.pk))

        assert response.status_code == 404
        victim_sub.refresh_from_db()
        assert victim_sub.status == "active"
        assert fake.cancelled == []

    def test_route_kwarg_name_matches_the_view(self, monkeypatch):
        """The fix couples the view to the URL converter's name. If the route
        ever renames `subscriptionId`, the scoped lookup silently misses and
        every cancel 404s -- so drive the view through the real URLconf, not
        a hand-passed kwarg. Skipped on hosts that do not mount airpay.urls.
        """
        from django.urls import NoReverseMatch, resolve, reverse

        fake = _FakeGatewayBackend()
        monkeypatch.setattr("airpay.models.get_gateway_backend", lambda name: fake)
        member = _user("routed")
        own_sub = _subscription_for(member)

        try:
            url = reverse(
                "airpay:cancel_subscription",
                kwargs={"subscriptionId": str(own_sub.pk)},
            )
        except NoReverseMatch:
            pytest.skip("host project does not mount airpay.urls")

        match = resolve(url)
        assert match.func.cls is CancelSubscription

        factory = APIRequestFactory()
        req = factory.put(url, {})
        force_authenticate(req, user=member)
        response = match.func(req, *match.args, **match.kwargs)

        assert response.status_code == 200, response.data
        own_sub.refresh_from_db()
        assert own_sub.status == "cancelled"

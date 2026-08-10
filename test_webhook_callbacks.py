"""Airpay webhook host-callback wiring — project-agnostic.

Airpay updates local subscription status itself, then optionally forwards the
raw Razorpay event to AIRPAY[<HANDLER>] settings callbacks. Host apps own all
product logic; this module must never import a host package.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from airpay.backends.razorpay_ import AirRazorpayBackend


def _backend():
    return AirRazorpayBackend.__new__(AirRazorpayBackend)


class TestSubscriptionWebhookCallback:
    def test_configured_handler_receives_raw_event_and_entity(self):
        backend = _backend()
        storage = MagicMock()
        handler = MagicMock()
        data = {
            "event": "subscription.activated",
            "payload": {
                "subscription": {
                    "entity": {"id": "sub_rzp1", "customer_id": "cust_1"}
                }
            },
        }
        with patch("django.utils.module_loading.import_string", return_value=handler), \
             patch("airpay.backends.razorpay_.settings") as mock_settings:
            mock_settings.AIRPAY = {
                "SUBSCRIPTION_WEBHOOK_HANDLER": "host.webhooks.on_subscription",
            }
            backend._handle_subscription_webhook(data, storage)

        storage.sync_subscription_status.assert_called_once_with(
            "sub_rzp1", "active", "cust_1"
        )
        handler.assert_called_once_with(
            event="subscription.activated",
            subscription={"id": "sub_rzp1", "customer_id": "cust_1"},
        )

    def test_host_handler_exception_is_swallowed(self):
        backend = _backend()
        with patch("django.utils.module_loading.import_string", side_effect=RuntimeError("boom")), \
             patch("airpay.backends.razorpay_.settings") as mock_settings:
            mock_settings.AIRPAY = {
                "SUBSCRIPTION_WEBHOOK_HANDLER": "host.webhooks.on_subscription",
            }
            # Must not raise — Razorpay needs a 200 after signature verify.
            backend._invoke_optional_webhook_handler(
                "SUBSCRIPTION_WEBHOOK_HANDLER",
                swallow_errors=True,
                event="subscription.activated",
                subscription={"id": "sub_x"},
            )

    def test_missing_handler_is_a_noop(self):
        backend = _backend()
        with patch("django.utils.module_loading.import_string") as import_string, \
             patch("airpay.backends.razorpay_.settings") as mock_settings:
            mock_settings.AIRPAY = {}
            backend._invoke_optional_webhook_handler(
                "SUBSCRIPTION_WEBHOOK_HANDLER",
                swallow_errors=True,
                event="subscription.activated",
                subscription={"id": "sub_x"},
            )
        import_string.assert_not_called()


class TestRefundWebhookCallback:
    def test_refund_entity_is_forwarded(self):
        backend = _backend()
        handler = MagicMock()
        data = {
            "event": "refund.created",
            "payload": {"refund": {"entity": {"id": "rfnd_1", "payment_id": "pay_1"}}},
        }
        with patch("django.utils.module_loading.import_string", return_value=handler), \
             patch("airpay.backends.razorpay_.settings") as mock_settings:
            mock_settings.AIRPAY = {
                "REFUND_WEBHOOK_HANDLER": "host.webhooks.on_refund",
            }
            backend._handle_refund_webhook(data)
        handler.assert_called_once_with(
            event="refund.created",
            refund={"id": "rfnd_1", "payment_id": "pay_1"},
        )

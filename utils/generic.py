from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model
from django.apps import apps as django_apps


from airpay.models import PaymentGateway, Subscriptions


def get_gateway(gateway) -> PaymentGateway or None:
    try:
        gateway, _ = PaymentGateway.objects.get_or_create(defaults={
            'name': gateway
        })
        return gateway
    except PaymentGateway.DoesNotExist:
        return None


def get_purchase_model() -> Model or None:
    try:
        return django_apps.get_model(settings.AIRPAY.get("PURCHASE_MODEL"), require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "PURCHASE_MODEL must be of the form 'app_label.model_name'"
        )

    except LookupError:
        raise ImproperlyConfigured(
            "PURCHASE_MODEL refers to model '%s' that has not been installed"
            % settings.AIRPAY.get("PURCHASE_MODEL")
        )

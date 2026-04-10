from django.conf import settings
from django.contrib import admin

from airpay.models import (
    AirPayTransferLogs,
    AirPlan,
    AirPlanFeatures,
    AirSeller,
    PaymentGateway,
    RazorpayOnboardingAddress,
    RazorpayRouteOnboardingDetails,
    Subscriptions,
)
from airpay.utils.generic import get_create_date_field, get_update_date_field

MODEL_ADMIN = admin.ModelAdmin

if getattr(settings, "AIRPAY", {}).get("USE_UNFOLD", None):
    from unfold.admin import ModelAdmin

    MODEL_ADMIN = ModelAdmin


# Register your models here.
@admin.register(PaymentGateway)
class PaymentGatewayAdmin(MODEL_ADMIN):
    list_display = [
        "name",
        "is_active",
        get_create_date_field(),
        get_update_date_field(),
    ]


@admin.register(AirSeller)
class AirSellerAdmin(MODEL_ADMIN):
    list_display = [
        "user",
        "needs_route",
        "needs_stripe",
        "razorpay_account_id",
        "stakeholder_id",
    ]


@admin.register(AirPlanFeatures)
class AirPlanFeaturesAdmin(MODEL_ADMIN):
    list_display = ["name", "description", "feature_type", "is_active"]


@admin.register(AirPlan)
class AirPlanAdmin(MODEL_ADMIN):
    list_display = ["name", "price", "description", "currency", "is_active", "plan_id"]


@admin.register(RazorpayRouteOnboardingDetails)
class RazorpayRouteOnboardingDetailsAdmin(MODEL_ADMIN):
    list_display = [
        "seller",
        "gateway",
        "razorpay_user_id",
        "phone_number",
        "legal_business_name",
    ]
    ordering = ["-" + get_create_date_field()]


@admin.register(Subscriptions)
class SubscriptionsAdmin(MODEL_ADMIN):
    list_display = [
        "seller",
        "plan",
        "status",
        get_create_date_field(),
        get_update_date_field(),
    ]


@admin.register(RazorpayOnboardingAddress)
class RazorpayOnboardingAddressAdmin(MODEL_ADMIN):
    list_display = [
        "razorpay_route_onboarding_details",
        "type",
        "street1",
        "street2",
        "city",
        "state",
        "country",
        "postal_code",
    ]


@admin.register(AirPayTransferLogs)
class AirPayTransferLogsAdmin(MODEL_ADMIN):
    list_display = [
        "seller",
        "amount",
        "settlement_status",
        get_create_date_field(),
        get_update_date_field(),
    ]
    ordering = ["-" + get_create_date_field()]

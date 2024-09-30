from django.contrib import admin
from unfold.admin import ModelAdmin

from airpay.models import PaymentGateway, Subscriptions, RazorpayRouteOnboardingDetails, AirPlan, AirPlanFeatures, \
    AirSeller, AirPayTransferLogs, RazorpayOnboardingAddress


# Register your models here.
@admin.register(PaymentGateway)
class PaymentGatewayAdmin(ModelAdmin):
    list_display = ['name', 'is_active', 'updated_at', 'created_at']


@admin.register(AirSeller)
class AirSellerAdmin(ModelAdmin):
    list_display = ['user', 'needs_route', 'needs_stripe', 'razorpay_account_id', 'stakeholder_id']


@admin.register(AirPlanFeatures)
class AirPlanFeaturesAdmin(ModelAdmin):
    list_display = ['name', 'description', 'feature_type', 'is_active']


@admin.register(AirPlan)
class AirPlanAdmin(ModelAdmin):
    list_display = ['name', 'price', 'description', 'currency', 'is_active', 'plan_id']


@admin.register(RazorpayRouteOnboardingDetails)
class RazorpayRouteOnboardingDetailsAdmin(ModelAdmin):
    list_display = ['seller', 'gateway', 'razorpay_user_id', 'phone_number', 'legal_business_name']


@admin.register(Subscriptions)
class SubscriptionsAdmin(ModelAdmin):
    list_display = ['seller', 'plan', 'status', 'created_at', 'updated_at']


@admin.register(RazorpayOnboardingAddress)
class RazorpayOnboardingAddressAdmin(ModelAdmin):
    list_display = ['razorpay_route_onboarding_details', 'type', 'street1', 'street2', 'city', 'state', 'country',
                    'postal_code']


@admin.register(AirPayTransferLogs)
class AirPayTransferLogsAdmin(ModelAdmin):
    list_display = ['seller', 'amount', 'settlement_status', 'created_at', 'updated_at']

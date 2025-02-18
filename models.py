import logging

from django.contrib.auth import get_user_model
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField
from airpay.razorpay_constants import BUSINESS_TYPE, BUSINESS_CATEGORY, BUSINESS_SUB_CATEGORY
from airpay.utils.gateway import get_gateway_backend


class PaymentGateway(models.Model):
    name = models.CharField(max_length=255, choices=[
        ('stripe', 'Stripe'),
        ('razorpay', 'Razorpay'), ], default='razorpay')
    is_active = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class AirSeller(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    needs_route = models.BooleanField(default=True)
    needs_stripe = models.BooleanField(default=False)
    is_super_admin = models.BooleanField(default=False)
    razorpay_account_id = models.CharField(max_length=255, blank=True, null=True)
    stakeholder_id = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.name or 'No Name' + " - " + self.razorpay_account_id or 'No Account ID'

    def can_accept_payments(self):
        return self.razorpay_account_id and self.stakeholder_id and self.onboardings.filter(status='activated').exists()


class AirPayTransferLogs(models.Model):
    seller = models.ForeignKey(AirSeller, on_delete=models.CASCADE)
    amount = models.FloatField()
    currency = models.CharField(max_length=255)
    payment_id = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(
        default=''
    )
    transfer_id = models.CharField(max_length=255, null=True, blank=True)
    transfer_status = models.CharField(max_length=255, default='pending')
    settlement_status = models.CharField(max_length=255, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.seller.user.name} - {self.amount} - {self.status}"


class AirPlanFeatures(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(
        blank=True, null=True
    )
    feature_type = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class AirPlan(models.Model):
    name = models.CharField(max_length=255)
    price = models.FloatField()
    description = models.TextField()
    currency = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    plan_id = models.CharField(max_length=255)
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE)
    features = models.ManyToManyField(AirPlanFeatures, related_name='features')
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RazorpayRouteOnboardingDetails(models.Model):
    seller = models.ForeignKey(AirSeller, on_delete=models.CASCADE, related_name='onboardings')
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE, related_name='onboardings')
    razorpay_user_id = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=255, blank=True, null=True)
    legal_business_name = models.CharField(max_length=255)
    customer_facing_business_name = models.CharField(max_length=255)
    email = models.EmailField(
        unique=True
    )
    business_type = models.CharField(max_length=255, choices=BUSINESS_TYPE, null=True, blank=True)
    business_category = models.CharField(max_length=255, choices=BUSINESS_CATEGORY, null=True, blank=True)
    sub_business_category = models.CharField(max_length=255, choices=[(x, x) for x in
                                                                      [x for key in BUSINESS_SUB_CATEGORY.values() for x
                                                                       in key]], null=True, blank=True)
    pan = EncryptedCharField(max_length=255, blank=True, null=True)
    gstin = EncryptedCharField(max_length=255, blank=True, null=True)
    bank_account_number = EncryptedCharField(max_length=255, blank=True, null=True)
    bank_name = EncryptedCharField(max_length=255, blank=True, null=True)
    bank_ifsc = EncryptedCharField(max_length=255, blank=True, null=True)
    bank_account_holder_name = EncryptedCharField(max_length=255, blank=True, null=True)
    business_pan = EncryptedCharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=255, default='pending')
    payment_gateway_configs = models.JSONField(blank=True, null=True)
    payment_link_configs = models.JSONField(blank=True, null=True)
    route_configs = models.JSONField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    notified_for = models.CharField(default=None, null=True, blank=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.seller.user.name} - {self.razorpay_user_id}"

    def complete_onboarding(self):
        try:
            from .tasks import (sync_details_to_razorpay)
            sync_details_to_razorpay.delay(self.id)

        except Exception as e:
            logging.error(f"Error completing onboarding: {e}\n {e.__traceback__}")
            print(
                e.__traceback__.tb_frame.f_globals['__name__'],
                e.__traceback__.tb_frame.f_globals['__file__'],
                e.__traceback__.tb_frame.f_globals['__package__'],
                # line number
                e.__traceback__.tb_lineno,
                # function name
                e.__traceback__.tb_frame.f_code.co_name,
            )
            self.status = 'failed'
            self.save()
            return False


class RazorpayOnboardingAddress(models.Model):
    razorpay_route_onboarding_details = models.ForeignKey(RazorpayRouteOnboardingDetails, on_delete=models.CASCADE,
                                                          related_name='addresses')
    street1 = models.TextField(
        blank=True, null=True
    )
    street2 = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=255, choices=[('registered', 'Registered'), ('individual', 'Individual'),
                                                     ('operations', 'Operations')])
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    country = models.CharField(max_length=255)
    postal_code = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.razorpay_route_onboarding_details.bank_account_holder_name} - {self.city}"


class Subscriptions(models.Model):
    subscription_id = models.CharField(max_length=255, null=True, blank=True)
    plan = models.ForeignKey(AirPlan, on_delete=models.CASCADE)
    seller = models.ForeignKey(AirSeller, on_delete=models.CASCADE)
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE)
    status = models.CharField(max_length=255, default='pending')

    order_id = models.CharField(max_length=255, null=True, blank=True)
    customer_id = models.CharField(max_length=255, null=True, blank=True)
    buyer = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='subscriptions')
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    payment_link = models.CharField(max_length=255, blank=True, null=True)
    payment_link_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.buyer.name} - {self.plan.name}"

    def create_order(self):
        gateway = get_gateway_backend(self.gateway.name)
        order = gateway.create_order(self.plan.price * 100, self.plan.currency)
        print(order)
        self.order_id = order['id']
        self.save()
        return self.order_id

    def create_link(self):
        gateway = get_gateway_backend(self.gateway.name)
        subscription = gateway.create_subscription_link(self.plan.plan_id, 12 * 30, self.buyer.email)
        self.payment_link = subscription['short_url']
        self.payment_link_id = subscription['id']
        self.subscription_id = subscription['id']
        self.save()
        return self.payment_link

from django.urls import path

from airpay.views import CreateSubscriptions, VerifySubscriptionPayment, AirRazorPayOnboarding, OpenPaymentGateway, \
    handle_razorpay_webhook, get_razorpay_kyc_form_requirements

app_name = "airpay"

urlpatterns = [
    path('payment/', OpenPaymentGateway.as_view(), name='payment'),
    path('webhook/', handle_razorpay_webhook, name='webhook'),
    path('onboarding/', AirRazorPayOnboarding.as_view(), name='onboarding'),
    path('subscribe/', CreateSubscriptions.as_view(), name='subscribe'),
    path('payment-success/', VerifySubscriptionPayment.as_view(), name='payment_success'),

    path('kyc-form/', get_razorpay_kyc_form_requirements, name='kyc-form')
]

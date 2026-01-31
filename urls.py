from django.urls import path

from airpay.views import CreateSubscriptions, GetSubscription, ListAirPlans, VerifySubscriptionPayment, AirRazorPayOnboarding, OpenPaymentGateway, \
        handle_razorpay_webhook, get_razorpay_kyc_form_requirements, CancelSubscription

app_name = "airpay"

urlpatterns = [
    # Payment Gateway URLs
    path('payment/', OpenPaymentGateway.as_view(), name='payment'),
    path('webhook/', handle_razorpay_webhook, name='webhook'),

    # Onboarding URLs
    path('onboarding/', AirRazorPayOnboarding.as_view(), name='onboarding'),
    
    path('plans/', ListAirPlans.as_view(), name='plans'),

    # Subscription URLs
    path('subscribe/', CreateSubscriptions.as_view(), name='subscribe'),
    path('subscription/', GetSubscription.as_view(), name='subscription'),
    path('subscription/<str:subscriptionId>/cancel/', CancelSubscription.as_view(), name='cancel_subscription'),
    path('payment-success/', VerifySubscriptionPayment.as_view(), name='payment_success'),
    path('kyc-form/', get_razorpay_kyc_form_requirements, name='kyc-form')
]

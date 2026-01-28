import http
import json

from django.conf import settings
import requests
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from rest_framework import generics
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny

from airpay.models import AirSeller, Subscriptions
from airpay.razorpay_constants import BUSINESS_TYPE, BUSINESS_CATEGORY, BUSINESS_SUB_CATEGORY, KYC_DOCUMENTS
from airpay.serializers import SubscriptionsSerializer, RazorpayRouteOnboardingDetailsSerializer
from airpay.utils.gateway import get_gateway_backend
from airpay.utils.generic import get_gateway
from api_views.generic import CreateUpdateAPIView, ListAPIView
from .helpers.generic import pickKeysFromDict
from .helpers.respones.response import SendResponse


class OpenPaymentGateway(generics.ListAPIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return render(request, 'payment.html', {
            "seller_id": request.query_params.get('seller_id'),
            "plan_id": request.query_params.get('plan_id'),
            "gateway": request.query_params.get('gateway'),
            "buyer": request.query_params.get('buyer')
        })


class AirRazorPayOnboarding(ListAPIView, CreateUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RazorpayRouteOnboardingDetailsSerializer
    required_fields = ['legal_business_name', 'customer_facing_business_name', 'phone_number', 'email',
                       'business_type', 'business_category',
                       'sub_business_category'
                       ]
    not_allowed_fields = ['razorpay_user_id', 'status']

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(seller__user_id=self.request.user.id)

    def get_object(self):
        try:
            return self.serializer_class.Meta.model.objects.get(seller__user_id=self.request.user.id)
        except self.serializer_class.Meta.model.DoesNotExist:
            return None

    def post(self, request, *args, **kwargs):
        try:
            self.check_keys()
            seller, _ = AirSeller.objects.get_or_create(user_id=request.user.id)
            request.data['seller'] = seller.id
            request.data['gateway'] = get_gateway('razorpay').id
            return super().post(request, *args, **kwargs)
        except Exception as e:
            return SendResponse(
                status_code=http.HTTPStatus.BAD_REQUEST,
                message=str(e),
                data={},
                error=True,
                success=False
            ).send()
    
    @staticmethod
    def has_address_fields(request):
        """
        Check if the request data has address fields
        """
        return any(
            field in request.data and request.data.get(field)
            for field in ['street1', 'street2', 'city', 'state', 'country', 'postal_code']
        )

    def patch(self, request, *args, **kwargs):
        try:
            object_ = self.get_object()
            self.check_keys()
            patched = super().patch(request, *args, **kwargs)
            if self.has_address_fields(request):
                from .tasks import create_address
                create_address.apply_async(
                    kwargs={
                        'pk': object_.id,
                        '_address': pickKeysFromDict(request.data, ['street1', 'street2', 'city', 'state',
                                                                    'country', 'postal_code'])
                    }
                )

            if request.data.get('finalize') is True:
                object_.complete_onboarding()
            return patched
        except Exception as e:
            print('Error patching onboarding details: ', e)
            return SendResponse(
                status_code=http.HTTPStatus.BAD_REQUEST,
                message=str(e),
                data={},
                error=True,
                success=False
            ).send()


# Create your views here.
class CreateSubscriptions(ListAPIView):
    serializer_class = SubscriptionsSerializer
    permission_classes = [IsAuthenticated]

    @staticmethod
    def get_admin_seller_id():
        admin_seller, _ = AirSeller.objects.get_or_create(
            defaults={
                'user__is_superuser': True,
                'user__is_staff': True,
                'is_super_admin': True
            }
        )
        return admin_seller

    def get(self, request, *args, **kwargs):
        try:
            seller_id = request.query_params.get('seller_id', self.get_admin_seller_id().id)
            plan_id = request.query_params.get('plan_id')
            gateway = request.query_params.get('gateway', 'razorpay')
            buyer = request.query_params.get('buyer', request.user.id)

            if not seller_id or not plan_id or not gateway or not buyer:
                raise Exception('Invalid request')
            AirSeller.objects.get(id=seller_id)
            subscription, created = Subscriptions.objects.get_or_create(seller_id=seller_id, plan_id=plan_id,
                                                                        gateway=get_gateway(gateway), buyer_id=buyer)

            if not created and subscription.status == 'cancelled':
                raise Exception('Subscription already exists')
            elif subscription.status == 'pending' and not subscription.order_id and not subscription.subscription_id:
                subscription.create_order()
                subscription.create_link()
                subscription.refresh_from_db()
            return SendResponse(
                status_code=http.HTTPStatus.OK,
                message='Subscription created',
                data=self.serializer_class(subscription).data,
                error=False,
                success=True
            ).send()
        except AirSeller.DoesNotExist:
            return SendResponse(
                status_code=http.HTTPStatus.NOT_FOUND,
                message='Seller not found',
                data=None,
                error=True,
                success=False
            ).send()
        except Exception as e:
            print('Error creating subscription: ', e)
            return SendResponse(
                status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR,
                message=str(e),
                data=None,
                error=True,
                success=False
            ).send()


class VerifySubscriptionPayment(CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubscriptionsSerializer

    def post(self, request, *args, **kwargs):
        print(request.data)
        payment_id = request.data.get('razorpay_payment_id')
        razorpay_subscription_id = request.data.get('razorpay_subscription_id')
        razorpay_signature = request.data.get('razorpay_signature')
        subscription = Subscriptions.objects.get(subscription_id=razorpay_subscription_id)
        if not subscription:
            return SendResponse(
                status_code=http.HTTPStatus.NOT_FOUND,
                message='Subscription not found',
                data=None,
                error=True,
                success=False
            ).send()
        gateway = get_gateway_backend(subscription.gateway.name)
        try:
            gateway.verify_subscription_payment(payment_id, razorpay_subscription_id, razorpay_signature)
            if settings.ONBOARDING_URL:
                return redirect(
                    settings.ONBOARDING_URL
                )
            else:
                return SendResponse(
                    status_code=http.HTTPStatus.ACCEPTED,
                    message='Payment verified',
                    data=None,
                    error=False,
                    success=True
                ).send()
        except requests.exceptions.HTTPError as e:
            return SendResponse(
                status_code=http.HTTPStatus.BAD_REQUEST,
                message='Error verifying payment',
                data=None,
                error=True,
                success=False
            ).send()


@csrf_exempt
@require_GET
def get_razorpay_kyc_form_requirements(request):
    """
    View to get the KYC form requirements for the Razorpay onboarding.
    """
    business_category = request.GET.get('business_category', None)
    business_type = request.GET.get('business_type', None)

    return HttpResponse(
        status=200,
        content_type='application/json',
        content=json.dumps(
            {
                'BUSINESS_TYPE': [{'label': y, 'value': x} for (x, y) in BUSINESS_TYPE],
                'BUSINESS_CATEGORY': [{'label': y, 'value': x} for (x, y) in BUSINESS_CATEGORY],
                'SUB_BUSINESS_CATEGORY': [{'label': x.replace('_', ' ').capitalize(), 'value': x} for x in
                                          BUSINESS_SUB_CATEGORY[
                                              business_category]] if business_category is not None else [],
                'REQUIRED_FIELDS': [doc for doc, data in KYC_DOCUMENTS.items() if
                                    business_type in data['business_types']] if business_type is not None else []
            }
        )
    )


@csrf_exempt
@require_POST
def handle_razorpay_webhook(request):
    """
    View to handle the Razorpay webhook.
    """
    try:
        signature = request.headers['x-razorpay-signature']
        get_gateway_backend('razorpay').process_webhook(request.body, signature)
        return HttpResponse(status=200)
    except Exception as e:
        # Log error to the console and propagate the exception
        print('Error handling Razorpay webhook: ', e)
        return HttpResponse(status=400)

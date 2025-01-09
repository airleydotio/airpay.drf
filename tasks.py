import django.conf
from airley.celery import BaseTaskWithRetry
from celery import shared_task
from django.contrib.auth import get_user_model
from airpay.utils.gateway import get_gateway_backend
from constants.constants import Constants
from .backends.razorpay_ import AirRazorpayBackend
from .models import AirPayTransferLogs, RazorpayOnboardingAddress, RazorpayRouteOnboardingDetails
from .utils.onboarding import get_onboarding_details
from .helpers.email.email import Email
from .helpers.fcm import FirebaseMessage
from .helpers.email.tasks import send_email

backend = AirRazorpayBackend()


@shared_task(
    name='sync_details_to_razorpay',
)
def sync_details_to_razorpay(razorpay_route_onboarding_details_id: int):
    onboarding_details = get_onboarding_details(razorpay_route_onboarding_details_id, 'razorpay')
    try:
        backend.create_linked_account(onboarding_details)
        backend.create_stakeholder(onboarding_details)
        backend.request_product_configurations(onboarding_details)
        backend.save_bank_account(onboarding_details)
       
    except Exception as e:
        onboarding_details.status = 'needs_clarification'
        onboarding_details.route_configs = {
            'requirements': [
                {
                    'field_reference': "Error due to:",
                    'reason_code': str(e.args[0])
                }
            ]
        }
        onboarding_details.save()
        send_email.delay(
            dict(
                to=onboarding_details.email,
                subject='Error completing Airley Payment onboarding',
                body=f"<html><body><p>There was an error completing your onboarding due to {e}."
                     f" Please update your details or contact support</p></body></html>",
            )
        )
        raise e


@shared_task(
    name='create_transfer'
)
def create_transfer(
        payment_id: str,
        seller_id: int,
        razorpay_account_id: str,
        description: str
):
    try:
        transfer = backend.create_transfer(payment_id, account_id=razorpay_account_id)
        print(transfer)
        AirPayTransferLogs.objects.create(
            seller_id=seller_id,
            payment_id=payment_id,
            currency=transfer['currency'],
            amount=transfer['amount'],
            transfer_status=transfer['status'] if 'transfer_status' in transfer else None,
            settlement_status=transfer['status'] if 'settlement_status' in transfer else None,
            transfer_id=transfer['id'],
            description=description
        )
    except Exception as e:
        print('Error creating transfer: ', e)
        raise


@shared_task(
    name='create_address')
def create_address(pk: int, _address: dict):
    try:
        for address in ['individual', 'registered']:
            RazorpayOnboardingAddress.objects.update_or_create(
                razorpay_route_onboarding_details=get_onboarding_details(pk, 'razorpay'),
                type=address, defaults={**_address, 'type': address})
    except Exception as e:
        raise e


@shared_task(
    name='notify_seller'
)
def notify_seller(message: str, email: str, tokens: [str]):
    try:
        messaging = FirebaseMessage()
        messaging.send(
            # use django settings to get the title
            title='Important update from {}'.format(django.conf.settings.APP_NAME),
            body=message,
            token_ids=tokens
        )
        email = Email(
            to=email,
            subject='Important update from Airley',
            body=f"<html><body><p>{message}</p></body></html>",
        )
        email.send()
        print('Seller notified successfully', message, email)

    except Exception as e:
        print('Error notifying seller: ', e)
        raise e

@shared_task(
    name='update_kyc_status'
)
def update_kyc_status():
    onboarding_details = RazorpayRouteOnboardingDetails.objects.filter(
        status__in=['under_review', 'needs_clarification']
    ).values_list('id', flat=True)
    for onboarding_detail in onboarding_details:
        request_product_configurations.delay(onboarding_detail)

@shared_task(
    name='request_product_configurations',
    base=BaseTaskWithRetry
)
def request_product_configurations(razorpay_route_onboarding_details_id: int):
    onboarding_details = get_onboarding_details(razorpay_route_onboarding_details_id, 'razorpay')
    backend = get_gateway_backend('razorpay')
    backend.request_product_configurations(onboarding_details, notify=False)

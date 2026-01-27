import traceback
import django.conf
from celery import shared_task
from django.contrib.auth import get_user_model
from airpay.utils.gateway import get_gateway_backend
from constants.constants import Constants
from .backends.razorpay_ import AirRazorpayBackend
from .models import AirPayTransferLogs, RazorpayOnboardingAddress, RazorpayRouteOnboardingDetails
from .utils.onboarding import get_onboarding_details
from .helpers.fcm import FirebaseMessage
from airpay.helpers.email.tasks import send_email
from airpay.helpers.email.tasks import BaseTaskWithRetry

# Initialize the Razorpay backend
backend = AirRazorpayBackend()

@shared_task(
    name='sync_details_to_razorpay',
)
def sync_details_to_razorpay(razorpay_route_onboarding_details_id: int):
    """
    Task to synchronize onboarding details with Razorpay.
    Calls methods to create linked account, stakeholder, request product configs, and save bank account.
    Updates onboarding status and sends error email if any exception occurs.
    """
    onboarding_details = get_onboarding_details(razorpay_route_onboarding_details_id, 'razorpay')
    try:
        backend.create_linked_account(onboarding_details)  # Create the linked Razorpay account
        backend.create_stakeholder(onboarding_details)     # Add stakeholder info
        backend.request_product_configurations(onboarding_details)  # Request product configuration
        backend.save_bank_account(onboarding_details)      # Save bank account details
        
    except Exception as e:
        traceback.print_exc()
        # Update onboarding status on error
        onboarding_details.status = 'needs_clarification'
        onboarding_details.route_configs = {
            'requirements': [
                {
                    'field_reference': "Error due to:",
                    'reason_code': str(e.args[0]),
                }
            ]
        }
        onboarding_details.save()
        # Send an error notification email to the user
        send_email.delay(
            data=dict(
                to=onboarding_details.email,
                subject='Oops! Error completing Airley Payment onboarding',
                template_id=Constants.EMAIL_TEMPLATES['RAZORPAY_ONBOARDING_ERROR'],
                dynamic_template_data={
                    'error': str(e.args[0]),
                    'contact.FIRSTNAME': onboarding_details.legal_business_name
                }
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
    """
    Task to create a transfer using the backend and save its log to AirPayTransferLogs.
    """
    try:
        transfer = backend.create_transfer(payment_id, account_id=razorpay_account_id)  # Perform the transfer
        AirPayTransferLogs.objects.create(
            seller_id=seller_id,
            payment_id=payment_id,
            currency=transfer['currency'],
            amount=transfer['amount'],
            # Store transfer and settlement statuses if available in the response
            transfer_status=transfer['status'] if 'transfer_status' in transfer else None,
            settlement_status=transfer['status'] if 'settlement_status' in transfer else None,
            transfer_id=transfer['id'],
            description=description
        )
    except Exception as e:
        # Log error to the console and propagate the exception
        print('Error creating transfer: ', e)
        raise


@shared_task(
    name='create_address')
def create_address(pk: int, _address: dict):
    """
    Task to create or update onboarding addresses (individual and registered) for the given pk.
    """
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
def notify_seller(message: str, email: str, tokens: list[str]): # type: ignore
    """
    Task to notify seller by FCM push notification and email about updates on their Airley payment setup.
    """
    try:
        messaging = FirebaseMessage()
        messaging.send(
            # Compose notification title from Django settings
            title='Important update from {}'.format(django.conf.settings.APP_NAME),
            body=message,
            token_ids=tokens
        )
        user = get_user_model().objects.get(email=email)
        send_email.delay(
            data=dict(  
                to=email,
                subject='Update on Your Airley Payment Provider Setup',
                template_id=Constants.EMAIL_TEMPLATES['RAZORPAY_PAYMENTS_NOTIFICATION'],
                dynamic_template_data={
                    'info': message,
                    "more_info": 'We recommend you to check the status of your payment provider setup by clicking the button below.',
                    'contact.FIRSTNAME': user.first_name,
                },
            )
        )
        print('Seller notified successfully', message, email)

    except Exception as e:
        print('Error notifying seller: ', e)
        raise e

@shared_task(
    name='update_kyc_status'
)
def update_kyc_status():
    """
    Task to update KYC status for onboarding details still under review or needing clarification,
    by scheduling product configuration requests for each one.
    """
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
    """
    Task to request product configurations from the Razorpay backend for a given onboarding detail.
    """
    onboarding_details = get_onboarding_details(razorpay_route_onboarding_details_id, 'razorpay')
    _backend = get_gateway_backend('razorpay')
    _backend.request_product_configurations(onboarding_details, notify=False)

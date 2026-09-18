import datetime
import json
import logging
import time
from django.conf import settings
import razorpay

from airpay.helpers.email.tasks import send_email
from constants.constants import Constants

logger = logging.getLogger(__name__)


def get_string_else_default(value, default):
    return value if value is not None else default


def get_first_present_value(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def format_for_log(value):
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return repr(value)


def exception_for_log(error):
    return {
        'type': error.__class__.__name__,
        'message': str(error),
        'args': error.args,
        'attributes': getattr(error, '__dict__', {}),
    }


class AirRazorpayBackend:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_base = 'https://api.razorpay.com/v2'
        self.api_key = settings.RAZORPAY_API_KEY
        self.api_secret = settings.RAZORPAY_API_SECRET
        self.client = razorpay.Client(auth=(self.api_key, self.api_secret), session=None)

    def create_linked_account(self, data):
        request_body_ = None
        try:
            data.refresh_from_db()
            if data.seller.razorpay_account_id:
                return print('Linked account already created')
            address = data.addresses.all()
            registered_address = address.filter(type='registered')
            operations_address = address.filter(type='individual')
            if not registered_address.exists():
                # wait for 10 seconds and try again
                time.sleep(5)
                return self.create_linked_account(data)
            registered_address = registered_address.first()
            operations_address = operations_address.first()

            registered_address.refresh_from_db()
            operations_address.refresh_from_db()

            if not registered_address or not operations_address:
                raise Exception('Address not found')

            # create a unique reference id
            def time_based_reference_id():
                return f'AIRPAY_SELLER_{data.seller.pk}_{int(time.time())}'[:19]

            pan = get_first_present_value(data.pan, data.business_pan)
            gstin = get_first_present_value(data.gstin)
            legal_info = {}
            if pan is not None:
                legal_info['pan'] = pan
                if gstin is not None:
                    legal_info['gst'] = gstin

            request_body_ = {
                'email': data.email,
                'phone': data.phone_number.replace("+91", '').replace(" ", ""),
                'type': 'route',
                'reference_id': time_based_reference_id(),
                'legal_business_name': data.legal_business_name,
                'customer_facing_business_name': data.customer_facing_business_name,
                'business_type': data.business_type,
                'profile': {
                    'category': data.business_category,
                    'subcategory': data.sub_business_category,
                    'addresses': {
                        'registered': {
                            'street1': get_string_else_default(registered_address.street1, 'Street 1'),
                            'street2': get_string_else_default(registered_address.street2, 'Street 2'),
                            'city': registered_address.city,
                            'state': registered_address.state,
                            'postal_code': registered_address.postal_code,
                            'country': 'IN'
                        },
                        'operation': {
                            'street1': get_string_else_default(operations_address.street1, 'Street 1'),
                            'street2': get_string_else_default(operations_address.street2, 'Street 2'),
                            'city': operations_address.city,
                            'state': operations_address.state,
                            'postal_code': operations_address.postal_code,
                            'country': 'IN'
                        }
                    }
                },
                'contact_name': data.bank_account_holder_name,
                'contact_info': {
                    'refund': {
                        'email': data.email,
                    },
                    'support': {
                        'email': data.email,
                        'phone': data.phone_number
                    },
                },
            }
            if legal_info:
                request_body_['legal_info'] = legal_info

            logger.info(
                'Razorpay linked account create request seller_id=%s onboarding_id=%s payload=%s',
                data.seller.pk,
                data.pk,
                format_for_log(request_body_),
            )
            account = self.client.account.create(request_body_)
            logger.info(
                'Razorpay linked account create response seller_id=%s onboarding_id=%s response=%s',
                data.seller.pk,
                data.pk,
                format_for_log(account),
            )
            data.seller.razorpay_account_id = account['id']
            data.razorpay_user_id = account['id']
            data.seller.save()
            data.status = account['status']
            data.save()
            print('Linked account created successfully')
        except Exception as e:
            logger.exception(
                'Razorpay linked account create failed seller_id=%s onboarding_id=%s request=%s error=%s',
                getattr(getattr(data, 'seller', None), 'pk', None),
                getattr(data, 'pk', None),
                format_for_log(request_body_),
                format_for_log(exception_for_log(e)),
            )
            print('Error creating razorpay linked account: ', e)
            raise e

    def sync_account_status(self, data):
        try:
            account = self.client.account.fetch(data.seller.razorpay_account_id)
            data.status = account['status']
            data.save()
            print('Account status synced successfully')
        except Exception as e:
            print('Error syncing account status: ', e)
            raise e

    def create_stakeholder(self, data):
        if data.seller.stakeholder_id:
            return print('Stakeholder already created')
        data.refresh_from_db()
        address = data.addresses.all()
        registered_address = address.filter(type='registered')
        if not registered_address.exists():
            raise Exception('Registered address not found')
        registered_address = registered_address.first()

        kyc_details = {
            'kyc': {
                'pan': data.pan,
            }
        } if data.pan is not None else {}

        stakeholder = self.client.stakeholder.create(data.seller.razorpay_account_id, {
            'percentage_ownership': 100,
            'name': data.bank_account_holder_name,
            "phone": {
                "primary": data.phone_number,
                "secondary": data.phone_number
            },
            'email': data.email,
            'addresses': {
                'residential': {
                    'street': registered_address.street1 + ' ' + registered_address.street2,
                    'city': registered_address.city,
                    'state': registered_address.state,
                    'postal_code': registered_address.postal_code,
                    'country': registered_address.country
                }
            },
            **kyc_details
        })
        data.seller.stakeholder_id = stakeholder['id']
        data.seller.save()
        print('Stakeholder created successfully')

    def request_product_configurations(self, data,
                                       product_type: str = 'route', notify: bool = True):
        try:
            data.refresh_from_db()
            product_configs = self.client.product.requestProductConfiguration(data.seller.razorpay_account_id, {
                'product_name': product_type,
                'tnc_accepted': True,
            })
            if 'payment_gateway' == product_type:
                data.payment_gateway_configs = product_configs
            elif 'payment_link' == product_type:
                data.payment_link_configs = product_configs
            elif 'route' == product_type:
                data.route_configs = product_configs
            data.status = product_configs['activation_status']
            if data.notified_for != data.status:
                from ..tasks import notify_seller
                tokens = []
                for token in data.seller.user.user_notification_tokens.values_list('token', flat=True):
                    tokens.append(token)
                if product_configs['activation_status'] == 'under_review' and notify:
                    notify_seller.delay(
                        f'Your razorpay {product_type} account is under review. We will notify you once it is activated.',
                        data.email,
                        tokens
                    )
                elif product_configs['activation_status'] == 'activated':
                    send_email.delay(dict(
                        to=data.email,
                        subject=f'Payment Setup Complete – You’re Ready to Set Cohort Pricing!',
                        template_id=Constants.EMAIL_TEMPLATES['PAYMENT_SETUP_SUCCESS'],
                        dynamic_template_data={
                            'contact.FIRSTNAME': data.seller.user.first_name,
                        }
                    ))
                elif product_configs['activation_status'] == 'suspended' and notify:
                    notify_seller.delay(
                        f'Your razorpay {product_type} account has been suspended. Please contact support for more details.',
                        data.email,
                        tokens
                    )
                elif product_configs['activation_status'] == 'needs_clarification' and data.notified_for != data.status and notify:
                    notify_seller.delay(
                        f'Your razorpay {product_type} account needs clarification. Please contact support for more details.',
                        data.email,
                        tokens
                    )
                data.notified_for = data.status
            data.save()
            print('Product configurations requested successfully')
        except Exception as e:
            print('Error requesting product configurations: ', e)
            raise e

    def save_bank_account(self, data):
        try:
            print("Saving bank account")
            data.refresh_from_db()
            products = [
                {'type': 'route', 'id': data.route_configs['id']}
            ]
            for product in products:
                self.client.product.edit(data.seller.razorpay_account_id, product['id'], {
                    "settlements": {
                        "account_number": data.bank_account_number,
                        "ifsc_code": data.bank_ifsc,
                        "beneficiary_name": data.bank_account_holder_name,
                    },
                })
                self.request_product_configurations(data, product_type=product['type'])
            print('Bank account saved successfully')
        except Exception as e:
            if str(e).__contains__("Merchant activation form has been locked for editing by admin"):
                self.request_product_configurations(data)
            else:
                print('Error saving bank account: ', e)
                raise e

    def create_payment_link(self, amount, currency, **kwargs):
        link = self.client.payment_link.create({
            'amount': int(amount),
            'currency': currency,
            **kwargs,
            "notify": {
                'email': True,
            },
            "reminder_enable": True,
            "callback_method": "get",
        })
        return link

    def get_payment_link(self, link_id):
        return self.client.payment_link.fetch(link_id)

    def create_plan(self, *, period, interval, amount, currency, name, description=None):
        """
        Create a Razorpay Plan object — required before create_subscription_link
        can reference it. Razorpay subscriptions bind to a real gateway-side plan
        id ('plan_XXXXXXXXXXXX'), never an arbitrary internal string; this was
        previously missing entirely (AirPlan.plan_id, our internal natural key
        like 'companion_monthly', was passed straight to subscription.create's
        plan_id, which would fail against the live API since it never matched
        an actual Razorpay Plan).

        period: 'daily' | 'weekly' | 'monthly' | 'yearly' (Razorpay period enum).
        interval: cycles per period unit (1 = every period, e.g. every month).
        amount: paise (integer).
        """
        plan = self.client.plan.create({
            'period': period,
            'interval': interval,
            'item': {
                'name': name,
                'amount': int(amount),
                'currency': currency,
                'description': description or name,
            },
        })
        return plan

    def fetch_plan(self, gateway_plan_id):
        return self.client.plan.fetch(gateway_plan_id)

    def create_subscription_link(self, plan_id, total_count, quantity=1, email=None,
                                 phone=None, start_at=None):
        """
        Create a Razorpay subscription auth link.

        start_at: optional Unix epoch (seconds) for the FIRST billing cycle. Set it
        in the future for a card-upfront free trial — the customer authorises the
        mandate now via short_url, and the first plan charge lands at start_at
        (e.g. a 7-day card-upfront trial). Omitted → billing starts immediately.
        """
        data = {
            'plan_id': plan_id,
            'quantity': quantity,
            'customer_notify': email is not None or phone is not None,
            'total_count': total_count,
            "notify_info": {
                "notify_phone": phone if phone is not None else None,
                "notify_email": email if email is not None else None
            }
        }
        if start_at:
            data['start_at'] = int(start_at)
        return self.client.subscription.create(data)

    def create_order(self, amount, currency):
        order = self.client.order.create(data={
            'amount': amount,
            'currency': currency,
        })
        return order

    def cancel_subscription(self, subscription_id):
        try:
            subscription = self.client.subscription.fetch(subscription_id)
            response = self.client.subscription.cancel(subscription['id'], {
                'cancel_at_cycle_end': True,
            })
            return response
        except Exception as e:
            print('Error canceling subscription: ', e)
            raise e

    def create_customer(self, data):
        try:
            customer = self.client.customer.create(data)
            return customer
        except Exception as e:
            print('Error creating customer: ', e)
            raise e

    def verify_subscription_payment(self, data):
        # Subscription signatures use payment_id|subscription_id, not the
        # order-payment verifier's order_id|payment_id message.
        payload = {key: data[key] for key in (
            'razorpay_payment_id', 'razorpay_subscription_id', 'razorpay_signature',
        )}
        return self.client.utility.verify_subscription_payment_signature(payload)

    def fetch_subscription(self, subscription_id):
        try:
            subscription = self.client.subscription.fetch(subscription_id)
            return subscription
        except Exception as e:
            print('Error fetching subscription: ', e)
            raise e

    def verify_payment_link_signature(self, data):
        try:
            self.client.utility.verify_payment_link_signature(data)
        except Exception as e:
            raise e

    def create_transfer(self, payment_id, account_id):
        try:
            payment = self.client.payment.fetch(payment_id)
            transfer = self.client.payment.transfer(
                payment_id=payment_id,
                data={
                    'transfers': [
                        {
                            'account': account_id,
                            'amount': payment['amount'],
                            'currency': payment['currency'],
                        }
                    ]
                }
            )
            return transfer['items'][0]
        except Exception as e:
            print('Error creating transfer: ', e)
            raise e

    def process_webhook(self, data, webhook_signature):
        try:
            from airpay.storage import RazorpayStorage
            storage = RazorpayStorage()

            # Verify webhook signature
            self.client.utility.verify_webhook_signature(
                data.decode(),
                webhook_signature,
                settings.RAZORPAY_WEBHOOK_SECRET
            )

            data = json.loads(data.decode('utf-8'))
            event = data.get('event')

            # Handle subscription webhooks
            if event and event.startswith('subscription.'):
                self._handle_subscription_webhook(data, storage)

            # Handle payment link webhooks
            elif event and event.startswith('payment_link.'):
                self._handle_payment_link_webhook(data)

            elif event and (event.startswith('refund.') or event.startswith('payment.disputed')):
                self._handle_refund_webhook(data)

            # Handle payment webhooks
            elif event and event.startswith('payment.'):
                self._handle_payment_webhook(data)

            else:
                print(f'Unhandled webhook event: {event}')

        except Exception as e:
            print('Error processing webhook: ', e)
            raise e

    def _handle_subscription_webhook(self, data, storage):
        """Handle subscription-related webhook events"""
        event = data.get('event')
        subscription = data['payload']['subscription']['entity']

        if event == 'subscription.activated' or event == 'subscription.authenticated':
            storage.sync_subscription_status(subscription['id'], 'active', subscription['customer_id'])
        elif event == 'subscription.completed':
            storage.sync_subscription_status(subscription['id'], 'completed', subscription['customer_id'])
        elif event == 'subscription.halted':
            storage.sync_subscription_status(subscription['id'], 'halted', subscription['customer_id'])
        elif event == 'subscription.pending':
            storage.sync_subscription_status(subscription['id'], 'pending', subscription['customer_id'])
        elif event == 'subscription.resumed':
            storage.sync_subscription_status(subscription['id'], 'active', subscription['customer_id'])
        elif event == 'subscription.paused':
            storage.sync_subscription_status(subscription['id'], 'active', subscription['customer_id'])
        elif event == 'subscription.cancelled':
            storage.sync_subscription_status(subscription['id'], 'cancelled', subscription['customer_id'])
        else:
            print(f'Unhandled subscription event: {event}')

        # Host apps may sync product state after airpay updates the local
        # Subscriptions row. Optional and best-effort: a host failure must not
        # turn a signature-verified delivery into a non-200 for Razorpay.
        self._invoke_optional_webhook_handler(
            'SUBSCRIPTION_WEBHOOK_HANDLER',
            event=event,
            subscription=subscription,
            swallow_errors=True,
        )

    def _invoke_optional_webhook_handler(self, setting_key, *, swallow_errors=False, **kwargs):
        """Call a host-configured AIRPAY[<setting_key>] callback if present."""
        callback_path = getattr(settings, 'AIRPAY', {}).get(setting_key)
        if not callback_path:
            return
        try:
            from django.utils.module_loading import import_string
            import_string(callback_path)(**kwargs)
        except Exception as exc:
            print(f'Error in AIRPAY.{setting_key}: {exc}')
            if not swallow_errors:
                raise

    def _handle_payment_link_webhook(self, data):
        """Handle payment link webhook events using configured callback"""
        event = data.get('event')
        payment_link = data['payload']['payment_link']['entity']
        payment = data['payload'].get('payment', {}).get('entity')
        callback_path = getattr(settings, 'AIRPAY', {}).get('PAYMENT_LINK_WEBHOOK_HANDLER')
        if not callback_path:
            print('AIRPAY.PAYMENT_LINK_WEBHOOK_HANDLER not configured, skipping payment_link webhook')
            return
        self._invoke_optional_webhook_handler(
            'PAYMENT_LINK_WEBHOOK_HANDLER',
            event=event,
            payment_link=payment_link,
            payment=payment,
        )

    def _handle_payment_webhook(self, data):
        """Handle direct payment webhook events using configured callback"""
        event = data.get('event')
        payment = data['payload']['payment']['entity']
        callback_path = getattr(settings, 'AIRPAY', {}).get('PAYMENT_WEBHOOK_HANDLER')
        if not callback_path:
            print('AIRPAY.PAYMENT_WEBHOOK_HANDLER not configured, skipping payment webhook')
            return
        self._invoke_optional_webhook_handler(
            'PAYMENT_WEBHOOK_HANDLER',
            event=event,
            payment=payment,
        )

    def _handle_refund_webhook(self, data):
        """Handle refund/dispute webhooks using configured callback."""
        event = data.get('event')
        payload = data.get('payload', {})
        # Razorpay refund events carry refund.payment_id; dispute events carry
        # the affected payment entity directly. Host handlers decide correlation.
        refund = (
            payload.get('refund', {}).get('entity')
            or payload.get('payment', {}).get('entity', {})
        )
        self._invoke_optional_webhook_handler(
            'REFUND_WEBHOOK_HANDLER',
            event=event,
            refund=refund,
        )

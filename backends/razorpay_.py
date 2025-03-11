import datetime
import json
import time
from django.conf import settings
import razorpay

from airpay.helpers.email.tasks import send_email
from constants.constants import Constants


def get_string_else_default(value, default):
    return value if value is not None else default


class AirRazorpayBackend:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_base = 'https://api.razorpay.com/v2'
        self.api_key = settings.RAZORPAY_API_KEY
        self.api_secret = settings.RAZORPAY_API_SECRET
        self.client = razorpay.Client(auth=(self.api_key, self.api_secret), session=None)

    def create_linked_account(self, data):
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
            
            print("data", data.__dict__)
            print("PAN", data.pan if data.pan is not None else data.business_pan)

            account = self.client.account.create({
                'email': data.email,
                'phone': data.phone_number.replace("+91", '').replace(" ", ""),
                'type': 'route',
                'reference_id': f'AIRPAY_SELLER_{data.seller.id}',
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
                'legal_info': {
                    'pan': data.pan if data.pan is not None else data.business_pan,
                } if data.gstin is None else {
                    'pan': data.pan if data.pan is not None else data.business_pan,
                    'gst': data.gstin
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
            })
            data.seller.razorpay_account_id = account['id']
            data.razorpay_user_id = account['id']
            data.seller.save()
            data.status = account['status']
            data.save()
            print('Linked account created successfully')
        except Exception as e:
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

    def create_subscription_link(self, plan_id, total_count, email, quantity=1):
        return self.client.subscription.create({
            'plan_id': plan_id,
            'quantity': quantity,
            'total_count': total_count,
            'start_at': datetime.now()
        })

    def create_order(self, amount, currency):
        order = self.client.order.create(data={
            'amount': amount,
            'currency': currency,
        })
        return order

    def create_customer(self, data):
        try:
            customer = self.client.customer.create(data)
            return customer
        except Exception as e:
            print('Error creating customer: ', e)
            raise e

    def verify_subscription_payment(self, data):
        try:
            self.client.utility.verify_payment_signature(data)
        except Exception as e:
            print('Error verifying subscription payment: ', e)
            raise e

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
            self.client.utility.verify_webhook_signature(data.decode(), webhook_signature,
                                                         settings.RAZORPAY_WEBHOOK_SECRET)
            data = json.loads(data.decode('utf-8'))
            subscription = data['payload']['subscription']['entity']
            if data['event'] == 'subscription.activated' or data['event'] == 'subscription.authenticated':
                storage.sync_subscription_status(subscription['id'], 'active')
            elif data['event'] == 'subscription.completed':
                storage.sync_subscription_status(subscription['id'], 'completed')
            elif data['event'] == 'subscription.halted':
                storage.sync_subscription_status(subscription['id'], 'halted')
            elif data['event'] == 'subscription.pending':
                storage.sync_subscription_status(subscription['id'], 'pending')
            elif data['event'] == 'subscription.resumed':
                storage.sync_subscription_status(subscription['id'], 'active')
            elif data['event'] == 'subscription.paused':
                storage.sync_subscription_status(subscription['id'], 'active')
            elif data['event'] == 'subscription.cancelled':
                storage.sync_subscription_status(subscription['id'], 'cancelled')
        except Exception as e:
            print('Error processing webhook: ', e)
            raise e

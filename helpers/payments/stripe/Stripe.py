import stripe
from django.conf import settings


def create_plan_array(plans):
    plan_array = []
    for plan in plans:
        plan_array.append({
            'plan': plan,
            'quantity': 1,
        })
    return plan_array


class StripeService:
    def __init__(self):
        self.api_key = settings.STRIPE_SECRET_KEY
        stripe.api_key = self.api_key
        self.stripe = stripe

    def create_charge(self, amount, currency, source, description):
        return self.stripe.Charge.create(
            amount=amount,
            currency=currency,
            source=source,
            description=description
        )

    def create_customer(self, email, source):
        return self.stripe.Customer.create(
            email=email,
            source=source
        )

    def create_subscription(self, customer, plans, coupon=None):
        plans = create_plan_array(plans)
        if coupon:
            return self.stripe.Subscription.create(
                customer=customer,
                items=plans,
                coupon=coupon
            )
        else:
            return self.stripe.Subscription.create(
                customer=customer,
                items=plans,
            )

    def cancel_subscription(self, subscription_id):
        return self.stripe.Subscription.delete(subscription_id)

    def get_subscription(self, subscription_id):
        return self.stripe.Subscription.retrieve(subscription_id)

    def get_customer(self, customer_id):
        return self.stripe.Customer.retrieve(customer_id)

    def get_plan(self, plan_id):
        return self.stripe.Plan.retrieve(plan_id)

    def get_charge(self, charge_id):
        return self.stripe.Charge.retrieve(charge_id)

    def get_all_plans(self):
        return self.stripe.Plan.list()

    def get_all_customers(self):
        return self.stripe.Customer.list()

    def get_all_subscriptions(self):
        return self.stripe.Subscription.list()

    def apply_coupon(self, coupon_id, subscription_id):
        return self.stripe.Subscription.modify(
            subscription_id,
            coupon=coupon_id
        )

    def get_coupon(self, coupon_id):
        return self.stripe.Coupon.retrieve(coupon_id)

    # create checkout session
    def create_checkout_session(self, customer_email, plans, coupon=None, mode='subscription'):
        plans = create_plan_array(plans)

        success_url = 'https://example.com/success'
        cancel_url = 'https://example.com/cancel'

        if coupon:
            return self.stripe.checkout.Session.create(
                payment_method_types=['card'],
                customer_email=customer_email,
                line_items=plans,
                mode=mode,
                success_url=success_url,
                cancel_url=cancel_url,
                coupon=coupon
            )
        else:
            return self.stripe.checkout.Session.create(
                payment_method_types=['card'],
                customer_email=customer_email,
                line_items=plans,
                mode=mode,
                success_url=success_url,
                cancel_url=cancel_url,
            )

    # get checkout session
    def get_checkout_session(self, session_id):
        return self.stripe.checkout.Session.retrieve(session_id)

    def verify_webhook_signature(self, payload, sig_header, endpoint_secret):
        return self.stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )

    def handle_webhook(self, payload, sig_header, endpoint_secret):
        event = self.verify_webhook_signature(payload, sig_header, endpoint_secret)
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            # Fulfill the purchase...
            print('Fulfilling purchase', session)
        elif event['type'] == 'checkout.session.async_payment_succeeded':
            session = event['data']['object']
            # Fulfill the purchase...
            print('Fulfilling purchase', session)
        elif event['type'] == 'checkout.session.async_payment_failed':
            session = event['data']['object']
            # Notify the customer that their order was not fulfilled
            print('Fulfilling purchase', session)
        else:
            print('Unhandled event type', event['type'])
        return event

# Airpay Webhook Handlers - Configuration Guide

## Overview

Airpay is a generic payment integration module that can be used in any Django project. To keep it project-agnostic, webhook handlers are **configurable** rather than hardcoded.

This allows projects to define their own business logic for handling payment events without modifying the airpay module itself.

## Configuration

### settings.py

Add webhook handler paths to your `AIRPAY` configuration:

```python
AIRPAY = dict(
    # ... other settings ...

    # Webhook handlers (optional)
    # These are called when Razorpay webhooks are received
    # Format: 'module.path.function_name'

    # Handler for payment link webhooks (payment_link.paid, payment_link.expired, etc.)
    PAYMENT_LINK_WEBHOOK_HANDLER='myapp.webhooks.handle_payment_link_webhook',

    # Handler for direct payment webhooks (payment.captured, payment.failed, etc.)
    PAYMENT_WEBHOOK_HANDLER='myapp.webhooks.handle_payment_webhook',
)
```

## Handler Functions

### Payment Link Webhook Handler

Create a function with this signature:

```python
def handle_payment_link_webhook(event, payment_link, payment):
    """
    Handle payment link webhook events from Razorpay.

    Args:
        event (str): The webhook event type (e.g., 'payment_link.paid')
        payment_link (dict): Payment link entity data from Razorpay
        payment (dict): Payment entity data from Razorpay (if available, can be None)

    Events:
        - payment_link.paid
        - payment_link.partially_paid
        - payment_link.expired
        - payment_link.cancelled
    """
    # Your business logic here
    pass
```

### Payment Webhook Handler

Create a function with this signature:

```python
def handle_payment_webhook(event, payment):
    """
    Handle direct payment webhook events from Razorpay.

    Args:
        event (str): The webhook event type (e.g., 'payment.captured')
        payment (dict): Payment entity data from Razorpay

    Events:
        - payment.captured
        - payment.authorized
        - payment.failed
    """
    # Your business logic here
    pass
```

## Example Implementation

### Example: fees/webhooks.py

```python
from django.utils import timezone
from myapp.models import Payment

def handle_payment_link_webhook(event, payment_link, payment):
    """Handle payment link events"""
    try:
        # Find your payment record by Razorpay payment link ID
        payment_record = Payment.objects.filter(
            razorpay_payment_link_id=payment_link['id']
        ).first()

        if not payment_record:
            print(f"Payment not found for link: {payment_link['id']}")
            return

        # Handle different events
        if event == 'payment_link.paid':
            payment_record.status = 'PAID'
            payment_record.paid_at = timezone.now()
            if payment:
                payment_record.razorpay_payment_id = payment.get('id')
            payment_record.save()
            print(f"✅ Payment link paid: {payment_link['id']}")

        elif event == 'payment_link.expired':
            if payment_record.status != 'PAID':
                payment_record.status = 'EXPIRED'
                payment_record.save()
            print(f"⏰ Payment link expired: {payment_link['id']}")

        elif event == 'payment_link.cancelled':
            if payment_record.status != 'PAID':
                payment_record.status = 'CANCELLED'
                payment_record.save()
            print(f"❌ Payment link cancelled: {payment_link['id']}")

    except Exception as e:
        print(f'Error in webhook handler: {e}')
        raise


def handle_payment_webhook(event, payment):
    """Handle payment events"""
    try:
        # Find payment by Razorpay payment ID or order ID
        payment_record = Payment.objects.filter(
            razorpay_payment_id=payment['id']
        ).first()

        if not payment_record:
            order_id = payment.get('order_id')
            if order_id:
                payment_record = Payment.objects.filter(
                    razorpay_order_id=order_id
                ).first()

        if not payment_record:
            print(f"Payment record not found: {payment['id']}")
            return

        # Handle different events
        if event in ['payment.captured', 'payment.authorized']:
            payment_record.status = 'PAID'
            payment_record.paid_at = timezone.now()
            payment_record.razorpay_payment_id = payment['id']
            payment_record.save()
            print(f"✅ Payment captured: {payment['id']}")

        elif event == 'payment.failed':
            payment_record.status = 'FAILED'
            payment_record.error_message = payment.get('error_description', 'Unknown error')
            payment_record.save()
            print(f"❌ Payment failed: {payment['id']}")

    except Exception as e:
        print(f'Error in webhook handler: {e}')
        raise
```

## Webhook Payload Examples

### Payment Link Paid

```python
event = 'payment_link.paid'

payment_link = {
    'id': 'plink_JEkUMxvYXBVHri',
    'status': 'paid',
    'amount': 100000,  # in paise (₹1000)
    'currency': 'INR',
    'description': 'Payment for order #123'
}

payment = {
    'id': 'pay_JEkUdWbFBUJQr6',
    'amount': 100000,
    'currency': 'INR',
    'status': 'captured',
    'method': 'upi',
    'email': 'customer@example.com',
    'contact': '+919876543210'
}
```

### Payment Captured

```python
event = 'payment.captured'

payment = {
    'id': 'pay_JEkUdWbFBUJQr6',
    'order_id': 'order_JEkUMxvYXBVHri',
    'amount': 100000,  # in paise
    'currency': 'INR',
    'status': 'captured',
    'method': 'upi',
    'email': 'customer@example.com',
    'contact': '+919876543210',
    'created_at': 1647849600
}
```

## Optional Configuration

If you don't need webhook handlers, simply omit them from settings:

```python
AIRPAY = dict(
    # ... other required settings ...
    # No webhook handlers configured
)
```

In this case, airpay will log a message and skip webhook processing:
```
AIRPAY.PAYMENT_LINK_WEBHOOK_HANDLER not configured, skipping payment_link webhook
```

## Testing Your Handlers

### 1. Unit Test

```python
from myapp.webhooks import handle_payment_link_webhook

def test_payment_link_paid():
    event = 'payment_link.paid'
    payment_link = {'id': 'plink_test123', 'status': 'paid'}
    payment = {'id': 'pay_test456', 'status': 'captured'}

    handle_payment_link_webhook(event, payment_link, payment)

    # Assert your business logic worked
    # ...
```

### 2. Integration Test with Webhook

```python
import json
from django.test import TestCase, Client

class WebhookTestCase(TestCase):
    def test_payment_link_webhook(self):
        client = Client()
        payload = {
            'event': 'payment_link.paid',
            'payload': {
                'payment_link': {'entity': {'id': 'plink_test'}},
                'payment': {'entity': {'id': 'pay_test'}}
            }
        }

        response = client.post(
            '/api/airpay/webhook/razorpay/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='test_signature'
        )

        self.assertEqual(response.status_code, 200)
```

## Best Practices

### 1. Idempotency

Always check if the payment is already processed:

```python
if payment_record.status == 'PAID':
    print(f"Already processed: {payment_link['id']}")
    return  # Don't process again
```

### 2. Database Transactions

Use transactions for consistency:

```python
from django.db import transaction

@transaction.atomic
def handle_payment_link_webhook(event, payment_link, payment):
    # All database operations in a single transaction
    # ...
```

### 3. Error Handling

Always raise exceptions for failed processing (Razorpay will retry):

```python
try:
    # Process webhook
except ValidationError as e:
    print(f"Validation error: {e}")
    return  # Don't retry validation errors
except Exception as e:
    print(f"Processing error: {e}")
    raise  # Razorpay will retry
```

### 4. Logging

Log all webhook events for debugging:

```python
import logging

logger = logging.getLogger(__name__)

def handle_payment_link_webhook(event, payment_link, payment):
    logger.info(f"Webhook received: {event} - {payment_link['id']}")
    # ... process ...
    logger.info(f"Webhook processed successfully")
```

### 5. Avoid Side Effects

Keep webhook handlers focused on payment state updates. Use Django signals for other actions:

```python
# In webhooks.py - just update payment state
def handle_payment_link_webhook(event, payment_link, payment):
    payment_record.status = 'PAID'
    payment_record.save()  # This triggers post_save signal

# In signals.py - handle side effects
@receiver(post_save, sender=Payment)
def on_payment_saved(sender, instance, **kwargs):
    if instance.status == 'PAID':
        # Send receipt, update inventory, etc.
        send_receipt.delay(instance.id)
```

## Troubleshooting

### Handler Not Called

**Check:**
1. Handler path is correct in settings
2. Function is importable (`python manage.py shell` → `from myapp.webhooks import handle_payment_link_webhook`)
3. Webhook secret is configured correctly
4. Razorpay webhook is active and events are selected

### Import Errors

```python
# ❌ Wrong
PAYMENT_LINK_WEBHOOK_HANDLER='myapp/webhooks.py/handle_payment_link_webhook'

# ✅ Correct
PAYMENT_LINK_WEBHOOK_HANDLER='myapp.webhooks.handle_payment_link_webhook'
```

### Handler Raises Exceptions

Check server logs for the error. Fix the issue and Razorpay will automatically retry failed webhooks.

## Architecture Benefits

### ✅ Separation of Concerns
- Airpay handles webhook authentication and routing
- Your project handles business logic

### ✅ Reusability
- Airpay can be used in multiple projects
- Each project defines its own handlers

### ✅ Maintainability
- Update handlers without modifying airpay
- Test handlers independently

### ✅ Flexibility
- Different handlers for different projects
- Optional webhook support

## See Also

- [Webhook Setup Guide](WEBHOOK_SETUP.md) - Complete Razorpay webhook configuration
- [Razorpay Webhooks Documentation](https://razorpay.com/docs/webhooks/)
- [Payment Links Webhooks](https://razorpay.com/docs/payment-links/webhooks/)

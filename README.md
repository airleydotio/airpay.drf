# Airpay - Payment Gateway Integration

Airpay is a Django app that provides payment gateway integration with support for multiple payment providers (currently Razorpay, with Stripe support planned).

## Features

- **Multi-Gateway Support** - Razorpay integration with Stripe planned
- **Payment Links** - Create and manage payment links
- **Subscriptions** - Full subscription lifecycle management
- **Seller Onboarding** - KYC and Route onboarding for Razorpay
- **Webhook Handlers** - Configurable webhook processing for payment events
- **Transfer Management** - Automatic payment routing to sellers
- **Project-Agnostic** - Configurable to work with any Django project structure
- **Secure** - Built-in webhook signature verification and field encryption

## Configuration

Add the following configuration to your Django `settings.py`:

```python
AIRPAY = {
    # Required: The model that represents purchases/payments in your system
    # Format: 'app_label.ModelName'
    'PURCHASE_MODEL': 'fees_collection.FeeCollection',
    
    # Required: The base model that all airpay models should inherit from
    # This should be an abstract base model with common fields
    # Format: 'app_label.ModelName'
    'BASE_MODEL': 'helpers.BaseModel',
    
    # Optional: Name of the creation timestamp field in your BASE_MODEL
    # Default: 'create_date'
    'CREATE_DATE_FIELD': 'create_date',
    
    # Optional: Name of the update timestamp field in your BASE_MODEL
    # Default: 'update_date'
    'UPDATE_DATE_FIELD': 'update_date',
    
    # Optional: Webhook handlers (for Razorpay payment events)
    # Format: 'module.path.function_name'
    
    # Handler for payment link webhooks (payment_link.paid, payment_link.expired, etc.)
    'PAYMENT_LINK_WEBHOOK_HANDLER': 'myapp.webhooks.handle_payment_link_webhook',
    
    # Handler for direct payment webhooks (payment.captured, payment.failed, etc.)
    'PAYMENT_WEBHOOK_HANDLER': 'myapp.webhooks.handle_payment_webhook',
}
```

## Base Model Requirements

Your `BASE_MODEL` should be an abstract Django model that includes at minimum:

1. **Primary Key field** - A unique identifier (can be UUID or auto-incrementing integer)
2. **Creation timestamp field** - The field specified in `CREATE_DATE_FIELD`
3. **Update timestamp field** - The field specified in `UPDATE_DATE_FIELD`

### Example Base Model

```python
# helpers/models.py
import uuid
from django.db import models
from django.utils import timezone as django_timezone

class BaseModel(models.Model):
    id = models.CharField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False, 
        max_length=36, 
        unique=True
    )
    create_date = models.DateTimeField(
        default=django_timezone.now,
    )
    update_date = models.DateTimeField(auto_now=True, editable=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True
        ordering = ["-create_date"]

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save()
        return True
```

## Models

### PaymentGateway
Represents payment gateway providers (Razorpay, Stripe, etc.)

### AirSeller
Represents sellers/merchants who can receive payments. Links to your User model.

### RazorpayRouteOnboardingDetails
KYC and onboarding details for Razorpay Route (payment routing to sellers).

### Subscriptions
Represents subscription plans and their purchases.

### AirPlan & AirPlanFeatures
Subscription plan definitions and their features.

## Environment Variables

Add these to your `.env` file:

```bash
# Razorpay Configuration
RAZORPAY_API_KEY='your_razorpay_key_id'
RAZORPAY_API_SECRET='your_razorpay_key_secret'
RAZORPAY_WEBHOOK_SECRET='your_webhook_secret'

# Field Encryption (for sensitive data like PAN, bank details)
FIELD_ENCRYPTION_KEY='your_encryption_key'
```

## Webhooks

Airpay supports automatic payment status updates via Razorpay webhooks. The webhook handlers are **configurable** to keep the module project-agnostic.

### Supported Events

- **Payment Link Events:** `payment_link.paid`, `payment_link.expired`, `payment_link.cancelled`, `payment_link.partially_paid`
- **Payment Events:** `payment.captured`, `payment.authorized`, `payment.failed`
- **Subscription Events:** `subscription.activated`, `subscription.cancelled`, `subscription.completed`, etc.

### Configuration

Define webhook handlers in your project and configure them in `settings.py`:

```python
# myapp/webhooks.py
def handle_payment_link_webhook(event, payment_link, payment):
    """
    Handle payment link webhook events from Razorpay.
    
    Args:
        event (str): Event type (e.g., 'payment_link.paid')
        payment_link (dict): Payment link entity from Razorpay
        payment (dict): Payment entity from Razorpay (if available)
    """
    # Your business logic here
    pass

def handle_payment_webhook(event, payment):
    """
    Handle payment webhook events from Razorpay.
    
    Args:
        event (str): Event type (e.g., 'payment.captured')
        payment (dict): Payment entity from Razorpay
    """
    # Your business logic here
    pass
```

### Documentation

- **[WEBHOOK_HANDLERS.md](WEBHOOK_HANDLERS.md)** - Complete guide to configuring webhook handlers
- **[WEBHOOK_SETUP.md](WEBHOOK_SETUP.md)** - Step-by-step Razorpay webhook setup

### Webhook Endpoint

```
POST /api/airpay/webhook/razorpay/
```

This endpoint automatically:
1. Verifies webhook signature
2. Routes events to appropriate handlers
3. Calls your configured webhook handlers

## Usage

### Creating an AirSeller

```python
from airpay.models import AirSeller
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username='merchant1')

seller = AirSeller.objects.create(
    user=user,
    needs_route=True,
    needs_stripe=False,
)
```

### Onboarding a Seller to Razorpay

```python
from airpay.models import RazorpayRouteOnboardingDetails

onboarding = RazorpayRouteOnboardingDetails.objects.create(
    seller=seller,
    legal_business_name='My Business',
    customer_facing_business_name='MyBiz',
    email='business@example.com',
    phone_number='1234567890',
    business_type='individual',
    business_category='education',
    # ... other required fields
)

# Complete onboarding (syncs with Razorpay)
onboarding.complete_onboarding()
```

## API Endpoints

- `POST /airpay/onboarding/` - Create/update Razorpay onboarding details
- `GET /airpay/onboarding/` - Get current user's onboarding status
- `POST /airpay/subscriptions/` - Create subscription
- `POST /airpay/verify-payment/` - Verify subscription payment

## Admin Interface

All models are registered in the Django admin with the Unfold theme. You can:

- View and manage payment gateways
- Create and manage sellers
- Track onboarding status
- Monitor subscriptions and payments
- View transfer logs

## Customization

The airpay app is designed to be flexible and work with your existing project structure by:

1. Using configurable base models
2. Supporting custom field names for timestamps
3. Linking to your existing User model
4. Integrating with your purchase/payment models

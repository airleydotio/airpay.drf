# Razorpay Webhook Integration

## Overview
This document explains how to set up and handle Razorpay webhooks for payment processing in the Feesbook application.

## Supported Webhook Events

### 1. Payment Link Events
- **`payment_link.paid`** - Payment link successfully paid
- **`payment_link.partially_paid`** - Payment link partially paid
- **`payment_link.expired`** - Payment link expired without payment
- **`payment_link.cancelled`** - Payment link cancelled

### 2. Payment Events
- **`payment.captured`** - Payment successfully captured
- **`payment.authorized`** - Payment authorized (pending capture)
- **`payment.failed`** - Payment failed

### 3. Subscription Events
- **`subscription.activated`** - Subscription activated
- **`subscription.authenticated`** - Subscription authenticated
- **`subscription.completed`** - Subscription completed
- **`subscription.halted`** - Subscription halted
- **`subscription.pending`** - Subscription pending
- **`subscription.resumed`** - Subscription resumed
- **`subscription.paused`** - Subscription paused
- **`subscription.cancelled`** - Subscription cancelled

## Webhook Flow

### Payment Link Flow (Parent Fee Payment)

```
1. Parent requests payment link
   ├─> POST /api/fees/collection/parent/pay/
   └─> Creates payment link in Razorpay

2. Parent pays via payment link
   ├─> Razorpay processes payment
   └─> Sends webhook to server

3. Webhook handler processes payment
   ├─> Verifies signature
   ├─> Updates FeeCollection status
   ├─> Stores payment_id
   └─> Triggers receipt generation

4. Django signals handle post-save
   ├─> Updates installment status
   ├─> Generates receipt
   └─> Sends receipt to parent (if enabled)
```

## Setting Up Webhooks in Razorpay Dashboard

### 1. Navigate to Webhooks
1. Log in to [Razorpay Dashboard](https://dashboard.razorpay.com/)
2. Go to **Settings** → **Webhooks**
3. Click **Create New Webhook**

### 2. Configure Webhook URL
```
Production URL: https://api.feesbook.in/api/airpay/webhook/razorpay/
Development URL: https://yourdomain.com/api/airpay/webhook/razorpay/
```

### 3. Select Events to Track

**For Fee Collection (Payment Links):**
- ✅ `payment_link.paid`
- ✅ `payment_link.partially_paid`
- ✅ `payment_link.expired`
- ✅ `payment_link.cancelled`

**For Direct Payments:**
- ✅ `payment.captured`
- ✅ `payment.authorized`
- ✅ `payment.failed`

**For Subscriptions:**
- ✅ `subscription.activated`
- ✅ `subscription.authenticated`
- ✅ `subscription.completed`
- ✅ `subscription.cancelled`
- ✅ `subscription.halted`
- ✅ `subscription.pending`
- ✅ `subscription.resumed`
- ✅ `subscription.paused`

### 4. Get Webhook Secret
1. After creating the webhook, copy the **Webhook Secret**
2. Add it to your environment variables:
   ```bash
   RAZORPAY_WEBHOOK_SECRET=your_webhook_secret_here
   ```

## Implementation Details

### Backend Implementation

#### File: `airpay/backends/razorpay_.py`

The webhook handler is split into three methods:

```python
def process_webhook(data, webhook_signature):
    # Main webhook processor
    # - Verifies signature
    # - Routes to appropriate handler based on event type

def _handle_payment_link_webhook(data):
    # Handles payment link events
    # Updates FeeCollection status based on payment link state

def _handle_payment_webhook(data):
    # Handles direct payment events
    # Updates FeeCollection status based on payment state

def _handle_subscription_webhook(data, storage):
    # Handles subscription events
    # Updates subscription status in database
```

### Payment Link Webhook Handler Logic

```python
payment_link.paid:
    ├─> status = 'PAID'
    ├─> paid_date = today
    ├─> razorpay_payment_id = payment.id
    ├─> offline = False
    └─> save()

payment_link.partially_paid:
    ├─> status = 'PENDING'
    ├─> razorpay_payment_id = payment.id
    └─> save()

payment_link.expired:
    ├─> status = 'FAILED'
    ├─> remarks = 'Payment link expired'
    └─> save()

payment_link.cancelled:
    ├─> status = 'CANCELLED'
    ├─> remarks = 'Payment link cancelled'
    └─> save()
```

### FeeCollection Status Flow

```
UPCOMING → PENDING → PAID ✓
                  ↓
              FAILED ✗
              CANCELLED ✗
```

## Testing Webhooks

### 1. Using Razorpay Webhook Test Mode

1. Go to **Webhooks** in Razorpay Dashboard
2. Click on your webhook
3. Click **Test Webhook**
4. Select event type (e.g., `payment_link.paid`)
5. Click **Send Test Webhook**

### 2. Using Ngrok for Local Testing

```bash
# Start your Django server
python manage.py runserver

# In another terminal, start ngrok
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Update Razorpay webhook URL to:
# https://abc123.ngrok.io/api/airpay/webhook/razorpay/
```

### 3. Manual Testing with cURL

```bash
# Test payment link paid webhook
curl -X POST https://yourdomain.com/api/airpay/webhook/razorpay/ \
  -H "Content-Type: application/json" \
  -H "X-Razorpay-Signature: your_test_signature" \
  -d '{
    "event": "payment_link.paid",
    "payload": {
      "payment_link": {
        "entity": {
          "id": "plink_test123",
          "status": "paid"
        }
      },
      "payment": {
        "entity": {
          "id": "pay_test456",
          "status": "captured"
        }
      }
    }
  }'
```

## Monitoring and Debugging

### 1. Check Webhook Logs in Razorpay

1. Go to **Webhooks** → Your webhook
2. Click **Logs** tab
3. View all webhook deliveries and responses

### 2. Server Logs

```bash
# View Django logs
tail -f /var/log/django/feesbook.log

# Look for webhook processing logs:
# ✅ Payment link paid: plink_xxx - FeeCollection: uuid
# ❌ Payment failed: pay_xxx
# ⏰ Payment link expired: plink_xxx
```

### 3. Common Issues

#### Issue: Signature Verification Failed
```
Error: signature verification failed
```
**Solution:** Check that `RAZORPAY_WEBHOOK_SECRET` matches the secret in Razorpay dashboard

#### Issue: FeeCollection Not Found
```
FeeCollection not found for payment link: plink_xxx
```
**Solution:** Ensure payment link was created via `/api/fees/collection/parent/pay/`

#### Issue: Webhook Not Received
```
No webhook received after payment
```
**Solutions:**
- Check webhook URL is correct
- Verify webhook is active in Razorpay dashboard
- Check firewall/security rules allow Razorpay IPs
- Enable webhook logs in Razorpay to see delivery status

## Security Best Practices

### 1. Signature Verification
✅ **Always verify** webhook signature before processing
```python
self.client.utility.verify_webhook_signature(
    data.decode(),
    webhook_signature,
    settings.RAZORPAY_WEBHOOK_SECRET
)
```

### 2. Use HTTPS Only
✅ **Production:** Only use HTTPS URLs for webhooks
❌ **Never use:** HTTP URLs in production

### 3. Idempotency
✅ **Handle duplicate webhooks** gracefully:
- Check if payment already processed
- Use transactions for database updates
- Log webhook IDs to prevent duplicate processing

### 4. Rate Limiting
✅ **Implement rate limiting** on webhook endpoint to prevent abuse

## Environment Variables

Add these to your `.env` or settings:

```bash
# Required
RAZORPAY_API_KEY=rzp_live_xxxxx
RAZORPAY_API_SECRET=your_api_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

# Optional
RAZORPAY_WEBHOOK_URL=https://api.feesbook.in/api/airpay/webhook/razorpay/
```

## Webhook Payload Examples

### Payment Link Paid Event
```json
{
  "event": "payment_link.paid",
  "payload": {
    "payment_link": {
      "entity": {
        "id": "plink_JEkUMxvYXBVHri",
        "status": "paid",
        "amount": 100000,
        "currency": "INR",
        "description": "Fees payment for Student Name"
      }
    },
    "payment": {
      "entity": {
        "id": "pay_JEkUdWbFBUJQr6",
        "amount": 100000,
        "currency": "INR",
        "status": "captured",
        "method": "upi",
        "email": "parent@example.com",
        "contact": "+919876543210"
      }
    }
  }
}
```

### Payment Captured Event
```json
{
  "event": "payment.captured",
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_JEkUdWbFBUJQr6",
        "order_id": "order_JEkUMxvYXBVHri",
        "amount": 100000,
        "currency": "INR",
        "status": "captured",
        "method": "upi"
      }
    }
  }
}
```

## Post-Webhook Processing

After webhook updates FeeCollection to PAID:

1. **Django Signal** (`fees/signals.py:44-51`):
   - Updates `installment.is_paid = True`
   - Checks if receipt generation is enabled
   - Triggers `generate_receipt` task

2. **Receipt Generation** (`fees/fees_collection/tasks.py:287-291`):
   - Generates PDF receipt
   - Saves to database
   - Optionally sends to parent via WhatsApp

3. **Cache Invalidation**:
   - Flushes analytics cache
   - Updates fee collection list cache

## Troubleshooting Checklist

- [ ] Webhook URL is correct and accessible
- [ ] HTTPS is enabled (production)
- [ ] Webhook secret is configured correctly
- [ ] Events are selected in Razorpay dashboard
- [ ] Webhook is active (not paused)
- [ ] Server can receive POST requests from Razorpay IPs
- [ ] Database has FeeCollection with matching `razorpay_order_id`
- [ ] Logs show webhook received but processing failed
- [ ] Signature verification is passing

## Support

For webhook-related issues:
1. Check Razorpay webhook logs first
2. Check Django server logs
3. Verify webhook secret matches
4. Test with Razorpay test mode
5. Contact Razorpay support if webhooks not being sent

## References

- [Razorpay Webhooks Documentation](https://razorpay.com/docs/webhooks/)
- [Payment Links Webhooks](https://razorpay.com/docs/payment-links/webhooks/)
- [Payment Webhooks](https://razorpay.com/docs/webhooks/payloads/payments/)

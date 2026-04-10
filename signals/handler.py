import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from ..models import Subscriptions
from ..tasks import create_transfer
from ..utils.generic import get_purchase_model

logger = logging.getLogger(__name__)


@receiver(post_save, sender=get_purchase_model())
def sync_transfer(sender, instance, created, **kwargs):
    # Skip if instance doesn't have the required airpay purchase attributes
    # FeeCollection uses razorpay_payment_id instead of payment_id
    if not hasattr(instance, 'cohort') or not hasattr(instance, 'payment_id'):
        return

    if created or not instance.payment_id or not instance.cohort.course.seller.can_accept_payments():
        return
    if instance.payment_id:
        if not instance.cohort.course.seller.razorpay_account_id:
            raise Exception('Seller does not have a razorpay account')
        create_transfer.delay(
            payment_id=instance.payment_id,
            seller_id=instance.cohort.course.seller.id,
            razorpay_account_id=instance.cohort.course.seller.razorpay_account_id,
            description=f"Transfer for {instance.cohort.profile.name} purchase"
        )


@receiver(pre_save, sender=Subscriptions)
def capture_subscription_previous_status(sender, instance, **kwargs):
    """Snapshot the current status before saving so post_save can detect transitions."""
    if instance.pk:
        try:
            instance._previous_status = Subscriptions.objects.get(pk=instance.pk).status
        except Subscriptions.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Subscriptions)
def cancel_previous_active_subscriptions(sender, instance, created, **kwargs):
    """
    When a subscription transitions to 'active', cancel every other active
    subscription belonging to the same buyer so only one plan is live at a time.
    """
    previous_status = getattr(instance, '_previous_status', None)

    if instance.status != 'active' or previous_status == 'active':
        return

    conflicting = Subscriptions.objects.filter(
        buyer=instance.buyer,
        status='active',
        is_deleted=False,
    ).exclude(pk=instance.pk)

    for subscription in conflicting:
        try:
            subscription.cancel()
            logger.info(
                "Cancelled subscription %s for buyer %s after new plan %s activated",
                subscription.subscription_id,
                instance.buyer_id,
                instance.plan_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to cancel subscription %s for buyer %s: %s",
                subscription.subscription_id,
                instance.buyer_id,
                exc,
            )

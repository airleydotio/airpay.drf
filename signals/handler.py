import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from ..models import Subscriptions
from ..tasks import create_transfer
from ..utils.generic import get_purchase_model

logger = logging.getLogger(__name__)


@receiver(post_save, sender=get_purchase_model())
def sync_transfer(sender, instance, created, **kwargs):
    # Skip if this is a new record
    if created:
        return

    # Check if this is a FeeCollection (has installment attribute)
    if hasattr(instance, 'installment'):
        # FeeCollection payment transfer
        if not instance.razorpay_payment_id or instance.status != 'PAID':
            return

        try:
            # Get institute owner from: fee_collection → installment → fee → institute → owned_by
            institute = instance.installment.fee.institute
            institute_owner = institute.owned_by

            # Get AirSeller for the institute owner
            from airpay.models import AirSeller
            seller = AirSeller.objects.filter(user=institute_owner).first()

            if not seller:
                logger.warning(f'No AirSeller found for institute owner: {institute_owner.id}')
                return

            if not seller.can_accept_payments():
                logger.warning(f'Seller {seller.id} cannot accept payments (not activated)')
                return

            if not seller.razorpay_account_id:
                raise Exception(f'Seller {seller.id} does not have a razorpay account')

            # Create transfer task
            create_transfer.delay(
                payment_id=instance.razorpay_payment_id,
                seller_id=seller.id,
                razorpay_account_id=seller.razorpay_account_id,
                description=f"Transfer for fee collection {instance.id} - {institute.name}"
            )
            logger.info(f'Transfer created for FeeCollection {instance.id} to seller {seller.id}')

        except Exception as e:
            logger.error(f'Error creating transfer for FeeCollection {instance.id}: {e}')
            raise e

    # Check if this is a cohort-based purchase (original airpay logic)
    elif hasattr(instance, 'cohort') and hasattr(instance, 'payment_id'):
        if not instance.payment_id or not instance.cohort.course.seller.can_accept_payments():
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

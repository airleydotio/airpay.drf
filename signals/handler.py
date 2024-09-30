from django.db.models.signals import post_save
from django.dispatch import receiver

from ..tasks import create_transfer
from ..utils.generic import get_purchase_model


@receiver(post_save, sender=get_purchase_model())
def sync_transfer(sender, instance, created, **kwargs):
    if created or not instance.payment_id or not instance.cohort.course.seller.can_accept_payments():
        return
    if instance.payment_id:
        if not instance.cohort.course.seller.razorpay_account_id:
            raise Exception('Seller does not have a razorpay account')
        print(instance.cohort.course.seller.razorpay_account_id)
        print(instance.cohort.course.seller.id)
        create_transfer.delay(
            payment_id=instance.payment_id,
            seller_id=instance.cohort.course.seller.id,
            razorpay_account_id=instance.cohort.course.seller.razorpay_account_id,
            description=f"Transfer for {instance.cohort.profile.name} purchase"
        )

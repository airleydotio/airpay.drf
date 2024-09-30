from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from airpay.models import Subscriptions


class RazorpayStorage:

    @staticmethod
    def sync_subscription_status(subscription_id, status):
        try:
            subscription = Subscriptions.objects.get(subscription_id=subscription_id)
            subscription.status = status
            subscription.save()
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"airpay_{subscription_id}",
                {
                    'type': 'subscription_status',
                    'status': status
                }
            )
            print('Subscription updated', f"airpay_{subscription_id}")
        except Subscriptions.DoesNotExist:
            print('Subscription not found')
        except Exception as e:
            print('Error updating subscription: ', e)
            raise e
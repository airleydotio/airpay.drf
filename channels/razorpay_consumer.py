import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer


class AirPayConsumer(WebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.subscription_id = None
        self.room_group_name = None

    def connect(self):
        self.user = self.scope["user"]
        self.subscription_id = self.scope['subscription_id']
        self.room_group_name = 'airpay_%s' % self.subscription_id
        print(self.room_group_name)

        if self.user.is_anonymous:
            print('inside user is anonymous')
            self.close()
            return
        # Join a room group
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )
        self.accept()

    def disconnect(self, close_code):
        # Leave a room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )
        self.close()

    def subscription_status(self, event):
        status = event['status']
        self.send(text_data=json.dumps({
            'status': status,
            'message': 'Subscription status updated.'
        }))

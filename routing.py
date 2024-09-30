from django.urls import re_path

from airpay.channels.razorpay_consumer import AirPayConsumer

websocket_urlpatterns = [
    # sub_OT44To7mG0n3Df
    re_path(r'ws/airpay/sub_(?P<subscription_id>[\w-]+)$', AirPayConsumer.as_asgi()),
]

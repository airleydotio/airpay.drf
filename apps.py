from django.apps import AppConfig


class AirpayConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'airpay'

    def ready(self):
        import airpay.signals.handler
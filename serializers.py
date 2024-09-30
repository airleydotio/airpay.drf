from rest_framework import serializers

from airpay.models import AirSeller, Subscriptions, RazorpayRouteOnboardingDetails, RazorpayOnboardingAddress


class AirSellerSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirSeller
        fields = '__all__'


class SubscriptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscriptions
        fields = '__all__'


class OnboardingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = RazorpayOnboardingAddress
        fields = '__all__'


class RazorpayRouteOnboardingDetailsSerializer(serializers.ModelSerializer):
    addresses = OnboardingAddressSerializer(
        many=True,
        required=False,
        read_only=True
    )

    class Meta:
        model = RazorpayRouteOnboardingDetails
        fields = '__all__'

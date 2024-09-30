from airpay.models import RazorpayRouteOnboardingDetails


def get_onboarding_details(
        pk: int,
        gateway: str,
) -> RazorpayRouteOnboardingDetails:
    """
    Get onboarding details for a gateway
    """
    try:
        onboarding_details = RazorpayRouteOnboardingDetails.objects.filter(
            id=pk,
            gateway__name=gateway,
            seller__needs_route=True, )

        if onboarding_details.exists():
            return onboarding_details.first()
        else:
            raise Exception('Onboarding details not found')
    except Exception as e:
        print('Error getting onboarding details: ', e)
        raise e

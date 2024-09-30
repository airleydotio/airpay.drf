from airpay.backends.razorpay_ import AirRazorpayBackend


def get_gateway_backend(gateway) -> AirRazorpayBackend or None:
    if gateway == 'razorpay':
        return AirRazorpayBackend()
    elif gateway == 'stripe':
        return None
    else:
        raise Exception('Invalid gateway')

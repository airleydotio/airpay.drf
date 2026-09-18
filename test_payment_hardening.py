"""Caller-owned onboarding, subscription HMAC verification, and inert page data."""
import hashlib
import hmac
import json
import subprocess
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.template.loader import render_to_string
from rest_framework.test import APIRequestFactory, force_authenticate
from razorpay.utility.utility import Utility
from razorpay.errors import SignatureVerificationError

from airpay.models import AirSeller, RazorpayRouteOnboardingDetails
from airpay.serializers import RazorpayRouteOnboardingDetailsSerializer
from airpay.views import AirRazorPayOnboarding, VerifySubscriptionPayment, OpenPaymentGateway
from airpay.backends.razorpay_ import AirRazorpayBackend
from airpay.test_subscription_ownership import _user, _subscription_for, _plan

pytestmark = pytest.mark.django_db


def test_onboarding_serializer_never_reparents():
    owner, other = _user('owner'), _user('other')
    own_seller = AirSeller.objects.create(user=owner)
    foreign_seller = AirSeller.objects.create(user=other)
    plan = _plan()
    row = RazorpayRouteOnboardingDetails.objects.create(
        seller=own_seller, gateway=plan.gateway, legal_business_name='Original',
        customer_facing_business_name='Original', email='original@example.test',
    )
    serializer = RazorpayRouteOnboardingDetailsSerializer(row, data={
        'seller': str(foreign_seller.pk), 'gateway': str(plan.gateway.pk),
        'razorpay_user_id': 'acct_not_allowed', 'status': 'complete',
        'legal_business_name': 'Updated',
    }, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    row.refresh_from_db()
    assert row.seller_id == own_seller.pk
    assert row.status == 'pending' and not row.razorpay_user_id
    assert row.legal_business_name == 'Updated'


def test_onboarding_patch_rejects_foreign_seller_before_finalize(monkeypatch):
    owner = _user('owner')
    seller = AirSeller.objects.create(user=owner)
    row = RazorpayRouteOnboardingDetails.objects.create(
        seller=seller, gateway=_plan().gateway, legal_business_name='Original',
        customer_facing_business_name='Original', email='patch@example.test',
    )
    finalize = Mock()
    monkeypatch.setattr(RazorpayRouteOnboardingDetails, 'complete_onboarding', finalize)
    request = APIRequestFactory().patch('/airpay/onboarding/', {'seller': str(seller.pk), 'finalize': True}, format='json')
    force_authenticate(request, user=owner)
    result = AirRazorPayOnboarding.as_view()(request)
    assert result.status_code == 400 and 'seller' in result.data['message']
    finalize.assert_not_called()
    row.refresh_from_db()
    assert row.seller_id == seller.pk


def test_onboarding_create_assigns_seller_and_partial_patch_works(monkeypatch):
    owner = _user('seller')
    plan = _plan()
    monkeypatch.setattr('airpay.views.get_gateway', lambda _: plan.gateway)
    payload = {
        'legal_business_name': 'Original', 'customer_facing_business_name': 'Original',
        'phone_number': '+919999999999', 'email': 'create@example.test',
        **{field: list(RazorpayRouteOnboardingDetails._meta.get_field(field).choices)[0][0]
           for field in ('business_type', 'business_category', 'sub_business_category')},
    }
    # Use real registered enum values; this is a valid onboarding request.
    request = APIRequestFactory().post('/airpay/onboarding/', payload, format='json')
    force_authenticate(request, user=owner)
    result = AirRazorPayOnboarding.as_view()(request)
    assert result.status_code == 201, result.data
    row = RazorpayRouteOnboardingDetails.objects.get(seller__user=owner)
    assert row.gateway_id == plan.gateway_id
    request = APIRequestFactory().patch('/airpay/onboarding/', {'legal_business_name': 'Updated'}, format='json')
    force_authenticate(request, user=owner)
    result = AirRazorPayOnboarding.as_view()(request)
    assert result.status_code == 200, result.data
    row.refresh_from_db()
    assert row.legal_business_name == 'Updated'


def _verify(user, data):
    request = APIRequestFactory().post('/airpay/payment-success/', data, format='json')
    force_authenticate(request, user=user)
    return VerifySubscriptionPayment.as_view()(request)


def _payload(subscription, secret='test-only-secret'):
    payment_id = 'pay_test'
    signature = hmac.new(secret.encode(), f'{payment_id}|{subscription.subscription_id}'.encode(), hashlib.sha256).hexdigest()
    return {'razorpay_payment_id': payment_id, 'razorpay_subscription_id': subscription.subscription_id,
            'razorpay_signature': signature}


def _backend():
    backend = AirRazorpayBackend.__new__(AirRazorpayBackend)
    backend.client = SimpleNamespace(utility=Utility(SimpleNamespace(auth=('test-only-key', 'test-only-secret'))))
    return backend


def test_real_sdk_subscription_signature_succeeds_and_secret_override_cannot(monkeypatch, settings):
    settings.ONBOARDING_URL = ''
    owner = _user('buyer')
    subscription = _subscription_for(owner)
    monkeypatch.setattr('airpay.views.get_gateway_backend', lambda _: _backend())
    assert _verify(owner, _payload(subscription)).status_code == 202
    forged = {**_payload(subscription, secret='attacker-secret'), 'secret': 'attacker-secret'}
    assert _verify(owner, forged).status_code == 400
    subscription.refresh_from_db()
    # Payment verification never creates a paid status; signed webhook owns it.
    assert subscription.status == 'active'


def test_foreign_or_missing_subscription_cannot_reach_verifier(monkeypatch):
    owner, other = _user('owner'), _user('other')
    subscription = _subscription_for(owner)
    gateway = Mock(side_effect=AssertionError('foreign subscription reached gateway'))
    monkeypatch.setattr('airpay.views.get_gateway_backend', gateway)
    assert _verify(other, _payload(subscription)).status_code == 404
    absent = {**_payload(subscription), 'razorpay_subscription_id': 'sub_missing'}
    assert _verify(owner, absent).status_code == 404
    gateway.assert_not_called()


def test_missing_signature_returns_named_validation_error():
    result = _verify(_user('buyer'), {'razorpay_payment_id': 'pay_test'})
    assert result.status_code == 400
    assert 'razorpay_signature' in result.data['message']


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.current = None
    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.current = {'attrs': dict(attrs), 'body': ''}
    def handle_data(self, data):
        if self.current is not None:
            self.current['body'] += data
    def handle_endtag(self, tag):
        if tag == 'script' and self.current is not None:
            self.scripts.append(self.current)
            self.current = None


def test_payment_page_executes_only_static_script_and_encodes_identifiers():
    attack = "${globalThis.compromised=true}`</script><script>globalThis.compromised=true</script>&buyer=foreign"
    request = APIRequestFactory().get('/airpay/payment/', {'seller_id': attack, 'plan_id': 'plan_1'})
    result = OpenPaymentGateway.as_view()(request)
    parser = _Scripts()
    parser.feed(result.content.decode())
    assert len(parser.scripts) == 2
    data = parser.scripts[0]
    assert data['attrs']['type'] == 'application/json'
    assert json.loads(data['body'])['seller_id'] == attack
    js = parser.scripts[1]['body']
    assert attack not in js
    # Execute the actual rendered JS against a local fake browser. No network.
    program = '''const vm = require('vm');
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
let fetched; let socket;
const context = {URL, encodeURIComponent, document: {getElementById: () => ({textContent: input.data})},
 window: {location: {protocol: 'https:', host: 'app.test', origin: 'https://app.test'}},
 fetch: async url => {fetched=url; return {ok: true, json:async()=>({data:{subscription_id:'sub_test'}})}},
 alert: ()=>{}, WebSocket: function(url){socket=url;}};
vm.createContext(context); vm.runInContext(input.js,context);
context.handlePayment().then(()=>process.stdout.write(JSON.stringify({fetched, socket, compromised:!!context.compromised})));
'''
    run = subprocess.run(['node', '-e', program], input=json.dumps({'data': data['body'], 'js': js}),
                         text=True, capture_output=True, check=True)
    browser = json.loads(run.stdout)
    from urllib.parse import urlparse, parse_qs
    assert not browser['compromised']
    url = urlparse(browser['fetched'])
    assert url.path == '/airpay/subscribe/'
    assert parse_qs(url.query)['seller_id'] == [attack]
    assert 'buyer' not in parse_qs(url.query)
    assert browser['socket'] == 'wss://app.test/ws/airpay/sub_test'

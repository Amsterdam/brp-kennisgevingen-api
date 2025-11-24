import time
from datetime import date

from authorization_django import jwks
from jwcrypto.jwt import JWT
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from brp_kennisgevingen.models import BSNMutation, Subscription


def api_request_with_scopes(scopes: list[str], data=None) -> Request:
    request = APIRequestFactory().get("/v1/dummy/", data=data)
    request.accept_crs = None  # for DSOSerializer, expects to be used with DSOViewMixin
    request.response_content_crs = None
    request.get_user_scopes = scopes  # a property in authorization_django

    # request.user_scopes = UserScopes(
    #     query_params=request.GET,
    #     request_scopes=scopes,
    # )
    return request


def to_drf_request(api_request):
    """Turns an API request into a DRF request."""
    request = Request(api_request)
    request.accepted_renderer = JSONRenderer()
    return request


def build_jwt_token(scopes, subject="test@example.com", appid="application_id"):
    now = int(time.time())

    kid = "2aedafba-8170-4064-b704-ce92b7c89cc6"
    key = jwks.get_keyset().get_key(kid)
    token = JWT(
        header={"alg": "ES256", "kid": kid},
        claims={"iat": now, "exp": now + 30, "scopes": scopes, "sub": subject, "appid": appid},
    )
    token.make_signed_token(key)
    return token.serialize()


def create_subscription_with_bsn(
    application_id: str, bsn: str, start_date: date, end_date: date | None = None
):
    # Make sure a BSN Mutation records exists
    _ = BSNMutation.objects.get_or_create(bsn=bsn)
    return Subscription.objects.create(
        application_id=application_id,
        bsn=bsn,
        start_date=start_date,
        end_date=end_date,
    )

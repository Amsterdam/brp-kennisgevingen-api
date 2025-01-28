import time

from authorization_django import jwks
from jwcrypto.jwt import JWT
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory


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


def build_jwt_token(scopes, subject="text@example.com"):
    now = int(time.time())

    kid = "2aedafba-8170-4064-b704-ce92b7c89cc6"
    key = jwks.get_keyset().get_key(kid)
    token = JWT(
        header={"alg": "ES256", "kid": kid},
        claims={"iat": now, "exp": now + 30, "scopes": scopes, "sub": subject},
    )
    token.make_signed_token(key)
    return token.serialize()

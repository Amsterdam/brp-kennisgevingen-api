from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema as _AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import exceptions, serializers, status

from brp_kennisgevingen.api.serializers import SubscriptionSerializer, UpdatesSerializer
from brp_kennisgevingen.views import STATUS_TO_URI


class AutoSchema(_AutoSchema):
    global_params = [
        OpenApiParameter(
            name="API-Version",
            type=str,
            location=OpenApiParameter.HEADER,
            description="",
            required=True,
            style="simple",
            explode=False,
            examples=[
                OpenApiExample(
                    name="API-Version",
                    value="1.0.0",
                    description="Geeft een specifieke API-versie aan in de context van "
                    "een specifieke aanroep.",
                )
            ],
            response=True,
        )
    ]

    def get_override_parameters(self):
        params = super().get_override_parameters()
        return params + self.global_params


class JWTTokenScheme(OpenApiAuthenticationExtension):
    target_class = "brp_kennisgevingen.api.authentication.JWTAuthentication"
    name = "JWTAuthentication"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
        }


class InvalidParamsSerializer(serializers.Serializer):
    type = serializers.CharField(required=False)
    name = serializers.CharField(required=False)
    code = serializers.CharField(required=False)
    reason = serializers.CharField(required=False)


class ErrorSerializer(serializers.Serializer):
    type = serializers.CharField()
    title = serializers.CharField()
    status = serializers.IntegerField()
    detail = serializers.CharField()
    instance = serializers.CharField()
    code = serializers.CharField()
    invalidParams = InvalidParamsSerializer(many=True, required=False)


default_error_responses = {
    (401, "application/problem+json"): OpenApiResponse(
        response=ErrorSerializer,
        examples=[
            OpenApiExample(
                "Error",
                value={
                    "type": STATUS_TO_URI[exceptions.NotAuthenticated.status_code],
                    "title": "Niet correct geauthenticeerd",
                    "status": exceptions.NotAuthenticated.status_code,
                    "detail": "The request requires user authentication. The response MUST "
                    "include a WWW-Authenticate header field (section 14.47) "
                    "containing a challenge applicable to the requested resource.",
                    "instance": "https://datapunt.voorbeeldgemeente.nl/api/v1/resourcenaam"
                    "?parameter=waarde",
                    "code": exceptions.NotAuthenticated.default_code,
                },
            )
        ],
    ),
    (403, "application/problem+json"): OpenApiResponse(
        response=ErrorSerializer,
        examples=[
            OpenApiExample(
                "Forbidden",
                description="Forbidden",
                value={
                    "type": STATUS_TO_URI[exceptions.PermissionDenied.status_code],
                    "title": "Niet correct geauthenticeerd",
                    "status": exceptions.PermissionDenied.status_code,
                    "detail": "The request requires user authentication. The response MUST "
                    "include a WWW-Authenticate header field (section 14.47) "
                    "containing a challenge applicable to the requested resource.",
                    "instance": "https://datapunt.voorbeeldgemeente.nl/api/v1/resourcenaam"
                    "?parameter=waarde",
                    "code": exceptions.PermissionDenied.default_code,
                },
            )
        ],
    ),
    (406, "application/problem+json"): OpenApiResponse(
        response=ErrorSerializer,
        examples=[
            OpenApiExample(
                "Not Acceptable.",
                description="Not Acceptable.",
                value={
                    "type": STATUS_TO_URI[exceptions.NotAcceptable.status_code],
                    "title": "Gevraagde contenttype wordt niet ondersteund.",
                    "status": exceptions.NotAcceptable.status_code,
                    "detail": "The resource identified by the request is only capable of "
                    "generating response entities which have content "
                    "characteristics not acceptable according to thr accept "
                    "headers sent in the request.",
                    "instance": "https://datapunt.voorbeeldgemeente.nl/api/v1/resourcenaam"
                    "?parameter=waarde",
                    "code": exceptions.NotAcceptable.default_code,
                },
            )
        ],
    ),
    (500, "application/problem+json"): OpenApiResponse(
        response=ErrorSerializer,
        examples=[
            OpenApiExample(
                "Internal Server Error.",
                description="Internal Server Error.",
                value={
                    "type": STATUS_TO_URI[status.HTTP_500_INTERNAL_SERVER_ERROR],
                    "title": "Interne server fout.",
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "detail": "The server encountered an unexpected condition which "
                    "prevented it from fulfilling the request.",
                    "instance": "https://datapunt.voorbeeldgemeente.nl/api/v1/resourcenaam"
                    "?parameter=waarde",
                    "code": "server_error",
                },
            )
        ],
    ),
    (503, "application/problem+json"): OpenApiResponse(
        response=ErrorSerializer,
        examples=[
            OpenApiExample(
                "Service Unavailable.",
                description="Service Unavailable.",
                value={
                    "type": STATUS_TO_URI[status.HTTP_503_SERVICE_UNAVAILABLE],
                    "title": "Interne server fout.",
                    "status": status.HTTP_503_SERVICE_UNAVAILABLE,
                    "detail": "The service is currently unable to handle the request due to "
                    "a temporary overloading or maintenance of the server.",
                    "instance": "https://datapunt.voorbeeldgemeente.nl/api/v1/resourcenaam"
                    "?parameter=waarde",
                    "code": "not_available",
                },
            )
        ],
    ),
}

default_error_responses_with_bad_request_bsn = {
    (400, "application/problem+json"): OpenApiResponse(
        response=ErrorSerializer,
        examples=[
            OpenApiExample(
                "Bad Request.",
                description="Bad Request.",
                value={
                    "type": STATUS_TO_URI[exceptions.ParseError.status_code],
                    "title": "Bad Request.",
                    "status": exceptions.ParseError.status_code,
                    "detail": "The request could not be understood by the server due to "
                    "malformed syntax. The client SHOULD NOT repeat the request "
                    "without modification.",
                    "instance": "https://datapunt.voorbeeldgemeente.nl/api/v1/resourcenaam"
                    "?parameter=waarde",
                    "code": exceptions.ParseError.default_code,
                    "invalidParams": [
                        {
                            "type": "https://www.vng.nl/realisatie/api/validaties/integer",
                            "name": "burgerservicenummer",
                            "code": "bsn",
                            "reason": "Waarde is geen geldig BSN.",
                        }
                    ],
                },
            )
        ],
    ),
    **default_error_responses,
}

default_error_responses_with_bad_request_start_date = {
    (400, "application/problem+json"): OpenApiResponse(
        response=ErrorSerializer,
        examples=[
            OpenApiExample(
                "Bad Request.",
                description="Bad Request.",
                value={
                    "type": STATUS_TO_URI[exceptions.ParseError.status_code],
                    "title": "Bad Request.",
                    "status": exceptions.ParseError.status_code,
                    "detail": "The request could not be understood by the server due to "
                    "malformed syntax. The client SHOULD NOT repeat the request "
                    "without modification.",
                    "instance": "https://datapunt.voorbeeldgemeente.nl/api/v1/resourcenaam"
                    "?parameter=waarde",
                    "code": exceptions.ParseError.default_code,
                    "invalidParams": [
                        {
                            "name": "vanaf",
                            "code": "vanaf",
                            "reason": "Vanaf moet in het verleden liggen.",
                        }
                    ],
                },
            )
        ],
    ),
    **default_error_responses,
}


list_subscriptions_schema = extend_schema(
    responses={
        200: SubscriptionSerializer,
        **default_error_responses,
    },
    tags=["Manage subscriptions"],
)

get_subscription_schema = extend_schema(
    description="Get a subscription for a specific person.",
    responses={
        200: SubscriptionSerializer,
        **default_error_responses_with_bad_request_bsn,
    },
    tags=["Manage subscriptions"],
)

put_subscription_schema = extend_schema(
    description="Create, update or delete subscriptions for a specific person.",
    responses={
        200: SubscriptionSerializer,
        201: SubscriptionSerializer,
        **default_error_responses_with_bad_request_bsn,
    },
    tags=["Manage subscriptions"],
)

list_updates_schema = extend_schema(
    parameters=[
        OpenApiParameter(
            name="vanaf",
            description="Alleen personen waarbij gegevens zijn gewijzigd op of na "
            "deze datum worden geleverd.",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=UpdatesSerializer,
            examples=[
                OpenApiExample(
                    "Update",
                    value={
                        "_links": {
                            "self": {
                                "href": "https://datapunt.voorbeeldgemeente.nl/api/"
                                "v{major-versie}/resourcename/{resource-identificatie}",
                                "templated": True,
                                "title": "string",
                            },
                            "ingeschrevenPersoon": {
                                "href": "https://datapunt.voorbeeldgemeente.nl/api/"
                                "v{major-versie}/resourcename/{resource-identificatie}",
                                "templated": True,
                                "title": "string",
                            },
                        },
                        "burgerservicenummers": ["555555021"],
                    },
                )
            ],
        ),
        **default_error_responses_with_bad_request_start_date,
    },
    tags=["List updates"],
)

list_new_residents_schema = extend_schema(
    parameters=[
        OpenApiParameter(
            name="vanaf",
            description="Alleen personen waarbij gegevens zijn gewijzigd op of na "
            "deze datum worden geleverd.",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=True,
        ),
        OpenApiParameter(
            name="maxLeeftijd",
            description="Alleen personen waarbij de leeftijd op de 'vanaf' datum kleiner is dan"
            "de maximale leeftijd worden geleverd.",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
        ),
    ],
    responses={
        200: UpdatesSerializer,
        **default_error_responses_with_bad_request_start_date,
    },
    tags=["List updates"],
)

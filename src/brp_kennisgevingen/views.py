from rest_framework import status
from rest_framework.exceptions import ErrorDetail
from rest_framework.views import exception_handler as drf_exception_handler

from brp_kennisgevingen.kennisgevingen.exceptions import ProblemJsonException

STATUS_TO_URI = {
    status.HTTP_400_BAD_REQUEST: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1",
    status.HTTP_401_UNAUTHORIZED: "https://datatracker.ietf.org/doc/html/rfc7235#section-3.1",
    status.HTTP_403_FORBIDDEN: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.3",
    status.HTTP_404_NOT_FOUND: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4",
    status.HTTP_405_METHOD_NOT_ALLOWED: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.5",
    status.HTTP_406_NOT_ACCEPTABLE: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.6",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.6.1",
    status.HTTP_502_BAD_GATEWAY: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.6.3",
    status.HTTP_503_SERVICE_UNAVAILABLE: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.6.4",
    status.HTTP_504_GATEWAY_TIMEOUT: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.6.5",
}


def _get_unique_trace_id(request):
    unique_id = request.headers.get("X-Unique-ID")  # X-Unique-ID wordt in haproxy gezet
    return f"X-Unique-ID:{unique_id}" if unique_id else request.build_absolute_uri()


def _to_camel_case(snake_str):
    """Simple to-camel-case, taken from DRF."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def exception_handler(exc, context):
    """Return the exceptions as 'application/problem+json'.

    See: https://datatracker.ietf.org/doc/html/rfc7807
    """
    request = context.get("request")
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    # Set the content-type for the response.
    # Only response.content_type is set, and response['content-type'] is untouched,
    # so it remains text/html for the browsable API. It would break browsing otherwise.
    response.content_type = "application/problem+json"

    if isinstance(exc, ProblemJsonException):
        # Raw problem json response forwarded.
        # Normalize the problem+json fields to be identical to how
        # our own API's would return these.
        normalized_fields = {
            "type": STATUS_TO_URI.get(exc.status_code),
            "title": str(exc.title),
            "status": int(exc.status_code),
            "detail": exc.detail if isinstance(exc.detail, list | dict) else str(exc.detail),
            "code": _to_camel_case(
                str(exc.code),
            ),  # permission_denied -> permissionDenied
            "instance": request.path if request else None,
        }
        if exc.invalid_params is not None:
            normalized_fields["invalidParams"] = exc.invalid_params

        # This merge strategy puts the normal fields first:
        response.data.update(normalized_fields)
        response.status_code = int(exc.status_code)
    elif isinstance(response.data.get("detail"), ErrorDetail):
        # DRF parsed the exception as API
        detail: ErrorDetail = response.data["detail"]
        default_detail = getattr(exc, "default_detail", None)
        response.data = {
            "type": STATUS_TO_URI.get(exc.status_code),
            "code": _to_camel_case(detail.code),  # permission_denied -> permissionDenied
            "title": default_detail if default_detail else str(exc),
            "detail": str(detail) if detail != default_detail else "",
            "status": response.status_code,
            "instance": request.path if request else None,
        }
    else:
        # Unknown exception format, pass native JSON what DRF has generated. Make sure
        # neither application/hal+json nor application/problem+json is returned here.
        response.content_type = "application/json; charset=utf-8"

    return response

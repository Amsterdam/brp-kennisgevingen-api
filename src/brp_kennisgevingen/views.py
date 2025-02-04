from django.http import JsonResponse
from django.views import View
from rest_framework import status
from rest_framework.exceptions import ErrorDetail
from rest_framework.views import exception_handler as drf_exception_handler

STATUS_TO_URI = {
    status.HTTP_400_BAD_REQUEST: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1",
    status.HTTP_403_FORBIDDEN: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.3",
    status.HTTP_404_NOT_FOUND: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4",
    status.HTTP_405_METHOD_NOT_ALLOWED: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.5",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.6.1",
    status.HTTP_502_BAD_GATEWAY: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.6.3",
    status.HTTP_503_SERVICE_UNAVAILABLE: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.6.4",
    status.HTTP_504_GATEWAY_TIMEOUT: "https://datatracker.ietf.org/doc/html/rfc7231#section-6.6.5",
}


class RootView(View):
    """Status page of the server."""

    def get(self, request, *args, **kwargs):
        return JsonResponse({"status": "online"})


def _get_unique_trace_id(request):
    unique_id = request.headers.get("X-Unique-ID")  # X-Unique-ID wordt in haproxy gezet
    return f"X-Unique-ID:{unique_id}" if unique_id else request.build_absolute_uri()


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

    if isinstance(response.data.get("detail"), ErrorDetail):
        # DRF parsed the exception as API
        detail: ErrorDetail = response.data["detail"]
        default_detail = getattr(exc, "default_detail", None)
        response.data = {
            "type": STATUS_TO_URI.get(exc.status_code),
            "code": detail.code,
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

import logging
import time
from fnmatch import fnmatch

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from django.urls import get_resolver
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views.decorators.cache import never_cache
from drf_spectacular.utils import extend_schema_view
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from brp_kennisgevingen.models import BSNChange, BSNMutation, NewResident, Subscription
from brp_kennisgevingen.openapi import schema

from . import authentication, permissions
from .exceptions import ProblemJsonException, raise_serializer_validation_error
from .renderers import HALJSONRenderer
from .serializers import (
    BSNChangesListSerializer,
    NewResidentsInputSerializer,
    SubscriptionSerializer,
    UpdatesInputSerializer,
    UpdatesSerializer,
    UpdateSubscriptionSerializer,
)
from .utils import is_valid_bsn

audit_log = logging.getLogger("brp_kennisgevingen.audit")


class IndexView(APIView):
    """Having some response on the /kennisgevingen/v1 path fixes the healthcheck."""

    def get(self, request):
        return Response(
            {
                "status": "online",
                "paths": self._list_urls(),
            }
        )

    def _list_urls(self):
        patterns = get_resolver().url_patterns
        return _extract_patterns(patterns, prefix="/", match="/kennisgevingen/v1/?*")


def _extract_patterns(patterns, prefix, match):
    urls = []
    for pattern in patterns:
        url = f"{prefix}{pattern.pattern}"
        if hasattr(pattern, "url_patterns") and match.startswith(url):
            urls.extend(_extract_patterns(pattern.url_patterns, url, match))
        elif fnmatch(url, match):
            urls.append(url)
    return urls


@method_decorator(never_cache, name="dispatch")
class BaseAPIView(APIView):
    authentication_classes = [authentication.JWTAuthentication]

    #: An random short-name for the service name in logging statements
    service_log_id: str = None

    #: The based scopes needed for all requests.
    needed_scopes: set = None

    def initial(self, request, *args, **kwargs):
        """DRF-level initialization for all request types."""
        self.start_time = time.perf_counter_ns()
        self.start_date = now()

        # Perform authorization, permission checks and throttles.
        super().initial(request, *args, **kwargs)

        # Options requests do not have a token in the header, so we'll return early
        if request.method == "OPTIONS":
            return

        # Token is validated, extract token scopes that are set by the middleware
        self.user_scopes = set(request.get_token_scopes)
        self.upn = request.get_token_claims.get("email", request.get_token_subject)
        self.appid = request.get_token_claims.get("appid")

        # request.data is only available in initial(), not in setup()
        self.default_log_fields = {
            "service": self.service_log_id,
            "upn": self.upn,
            "granted": sorted(self.user_scopes),
        }
        if self.appid:
            self.default_log_fields["appid"] = self.appid

    def finalize_response(self, request, response, *args, **kwargs):
        """DRF-level finalization for all request types."""

        if response.status_code not in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]:
            burgerservicenummers = self._extract_burgerservicenummers(response.data)
            self.log_access_granted(
                request,
                response.data,
                self.needed_scopes,
                extra={"burgerservicenummers": burgerservicenummers},
            )

        return super().finalize_response(request, response)

    def _extract_burgerservicenummers(self, response_data) -> list[str]:
        """Extract the list of burgerservicenummers from the response data."""
        if isinstance(response_data, list):
            return [
                x.get("burgerservicenummer")
                for x in response_data
                if isinstance(x, dict) and "burgerservicenummer" in x
            ]
        elif isinstance(response_data, dict) and "burgerservicenummer" in response_data:
            return [response_data["burgerservicenummer"]]
        return []

    def get_permissions(self):
        """Collect the DRF permission checks.
        DRF checks these in the initial() method, and will block view access
        if these permissions are not satisfied.
        """
        if not self.needed_scopes:
            raise ImproperlyConfigured("needed_scopes is not set")

        return super().get_permissions() + [permissions.IsUserScope(self.needed_scopes)]

    def log_access_denied(self) -> None:
        """Perform the audit logging for the denied request."""
        missing = sorted(self.needed_scopes - self.user_scopes)
        audit_log.info(
            "Denied access to '%(service)s' missing %(missing)s",
            {
                "service": self.service_log_id,
                "missing": ",".join(missing),
            },
            extra={
                **self.default_log_fields,
                "missing": missing,
                "requestStarted": self.start_date,
                "requestProcessed": now(),
                "processingTime": (time.perf_counter_ns() - self.start_time) * 1e-9,
            },
        )

    def log_access_granted(
        self,
        request,
        final_response,
        needed_scopes: set[str],
        exception: OSError | APIException | None = None,
        extra: dict | None = None,
    ) -> None:
        """Perform the audit logging for the request/response.

        This is a very basic global logging.
        Per service type, it may need more refinement.
        """
        extra = extra or {}

        extra.update(
            {
                **self.default_log_fields,
                "needed": sorted(needed_scopes),
                "request": request.data,
                "response": final_response,
                "requestStarted": self.start_date,
                "requestProcessed": now(),
                "processingTime": (time.perf_counter_ns() - self.start_time) * 1e-9,
            }
        )

        if exception is None:
            msg = (
                "Access granted for '%(service)s' to '%(upn)s'"
                " (full request/response in detail)"
            )
        else:
            msg = (
                "Access granted for '%(service)s' to '%(upn)s'"
                ", but error returned (full request/response in detail)"
            )
            extra["exception"] = str(exception)

        audit_log.info(
            msg,
            {
                "service": self.service_log_id,
                "upn": self.upn,
            },
            extra=extra,
        )


class SubscriptionAppIDFilterMixin:

    application_id: str = None

    def get_queryset(self, for_update=False):
        """
        When updating records we'll also have to look for (inactive) records from the same day
        to possibly re-activate them.
        """
        if for_update:
            queryset = Subscription.objects.updatable()
        else:
            queryset = Subscription.objects.active()
        self.application_id = self.request.get_token_claims.get("appid")
        return queryset.filter(application_id=self.application_id)


@extend_schema_view(get=schema.list_subscriptions_schema)
class SubscriptionListAPIView(SubscriptionAppIDFilterMixin, ListAPIView, BaseAPIView):
    """
    List all active subscriptions for an application user.
    """

    needed_scopes: set = {"benk-brp-volgindicaties-api"}
    serializer_class = SubscriptionSerializer
    service_log_id: str = "volgindicaties-list"


@extend_schema_view(
    get=schema.get_subscription_schema,
    put=schema.put_subscription_schema,
)
class SubscriptionsAPIView(SubscriptionAppIDFilterMixin, RetrieveUpdateAPIView, BaseAPIView):
    needed_scopes: set = {"benk-brp-volgindicaties-api"}
    http_method_names: list[str] = ["get", "put"]
    lookup_field: str = "bsn"
    service_log_id: str = "volgindicaties"

    def get_object(self, for_update: bool = False) -> Subscription | None:
        bsn = self.kwargs[self.lookup_field]
        if not is_valid_bsn(bsn):
            raise ProblemJsonException(
                title="Waarde is geen geldig BSN.",
                detail="The request could not be understood by the server due to malformed "
                "syntax. The client SHOULD NOT repeat the request without modification.",
                status=status.HTTP_400_BAD_REQUEST,
                invalid_params=[
                    {
                        "name": "burgerservicenummer",
                        "code": "bsn",
                        "reason": "Waarde is geen geldig BSN.",
                    }
                ],
            )

        queryset = self.filter_queryset(self.get_queryset(for_update))

        try:
            instance = queryset.get(bsn=bsn)
        except Subscription.DoesNotExist:
            return None

        return instance

    def get_serializer_class(self):
        if self.request.method == "PUT":
            return UpdateSubscriptionSerializer
        return SubscriptionSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        if not instance:
            raise ProblemJsonException(
                title="Opgevraagde resource bestaat niet.",
                detail="The server has not found anything matching the Request-URI.",
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        bsn = self.kwargs["bsn"]
        instance = self.get_object(for_update=True)

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            raise_serializer_validation_error(serializer)

        # Get the optional subscription end date
        end_date = serializer.validated_data.get("einddatum")

        if not instance:
            if end_date and end_date < timezone.now().date():
                raise ProblemJsonException(
                    title="Geen correcte waarde opgegeven.",
                    detail="The request could not be understood by the server due to malformed "
                    "syntax. The client SHOULD NOT repeat the request without modification.",
                    status=status.HTTP_400_BAD_REQUEST,
                    invalid_params=[
                        {
                            "name": "einddatum",
                            "code": "date",
                            "reason": "Voor een nieuwe volgindicatie kan de einddatum niet in "
                            "het verleden liggen.",
                        }
                    ],
                )

            instance = Subscription.objects.create(
                application_id=self.application_id,
                bsn=bsn,
                start_date=timezone.now().date(),
                end_date=end_date,
            )
            serializer = SubscriptionSerializer(instance)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            instance.set_end_date(end_date)

            serializer = SubscriptionSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)


class UpdatesAPIBaseView(BaseAPIView):
    queryset = None
    renderer_classes = [HALJSONRenderer]
    input_serializer = None

    bsn_field: str = "bsn"
    inserted_at_field: str = "inserted_at"

    def filter_queryset(self, queryset):
        # Validate URL query parameters
        query_serializer = self._validate_input_serializer(self.request.query_params)

        start_date = query_serializer.validated_data["vanaf"]

        filter_kwargs = {
            f"{self.inserted_at_field}__gte": start_date,
            f"{self.inserted_at_field}__lt": timezone.now(),
        }

        return queryset.filter(**filter_kwargs)

    def get_queryset(self):
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.all()
        return queryset

    def get(self, request, *args, **kwargs):
        # Validate URL query parameters
        query_serializer = UpdatesInputSerializer(data=self.request.query_params)
        if not query_serializer.is_valid():
            raise_serializer_validation_error(query_serializer)

        queryset = self.filter_queryset(self.get_queryset())

        serializer = UpdatesSerializer(
            {
                "burgerservicenummers": queryset.values_list(self.bsn_field, flat=True),
                "_links": {
                    "self": {"href": self.request.get_full_path()},
                    "ingeschrevenPersoon": {"href": "/bevragingen/v1/personen"},
                },
            }
        )
        return Response(serializer.data)

    def _extract_burgerservicenummers(self, response_data) -> list[str]:
        """Extract the list of burgerservicenummers from the response data."""
        return response_data.get("burgerservicenummers", [])

    def _validate_input_serializer(self, query_params):
        # Validate URL query parameters
        query_serializer = self.input_serializer(data=query_params)
        if not query_serializer.is_valid():
            raise_serializer_validation_error(query_serializer)
        return query_serializer


@extend_schema_view(get=schema.list_updates_schema)
class UpdatesAPIView(SubscriptionAppIDFilterMixin, UpdatesAPIBaseView):
    """
    Request a list of `burgerservicenummers` of persons with updated data.
    """

    needed_scopes: set = {"benk-brp-wijzigingen-api"}
    queryset = Subscription.objects.active()
    input_serializer = UpdatesInputSerializer
    service_log_id = "wijzigingen"

    def get_queryset(self):
        subscriptions = super().get_queryset().values_list("bsn", flat=True).distinct()
        return BSNMutation.objects.filter(bsn__in=subscriptions)


@extend_schema_view(get=schema.list_new_residents_schema)
class NewResidentsListAPIView(UpdatesAPIBaseView):
    """
    Request a list of `burgerservicenummers` of new residents.
    """

    needed_scopes: set = {"benk-brp-nieuwe-ingezetenen-api"}
    queryset = NewResident.objects.all()
    input_serializer = NewResidentsInputSerializer
    service_log_id = "nieuwe-ingezetenen"

    def filter_queryset(self, queryset):
        query_serializer = self._validate_input_serializer(self.request.query_params)
        queryset = super().filter_queryset(queryset)

        if max_age := query_serializer.validated_data.get("max_leeftijd"):

            start_date = query_serializer.validated_data["vanaf"]
            filter_kwargs = {}

            min_birthdate = start_date - relativedelta(years=max_age)
            filter_kwargs["birthdate__gte"] = min_birthdate

            return queryset.filter(**filter_kwargs)
        return queryset


# @extend_schema_view(get=schema.list_bsn_updates_schema)
class BSNChangesListAPIView(SubscriptionAppIDFilterMixin, UpdatesAPIBaseView):
    """
    Request a list of `burgerservicenummers` that changed into new `burgerservicenummers`.
    We use the UpdatesAPIBaseView for the filter_queryset function.
    """

    needed_scopes: set = {"benk-brp-bsn-wijzigingen-api"}
    input_serializer = UpdatesInputSerializer
    service_log_id = "bsn-wijzigingen"

    def get(self, request, *args, **kwargs):
        # Validate URL query parameters
        query_serializer = UpdatesInputSerializer(data=self.request.query_params)
        if not query_serializer.is_valid():
            raise_serializer_validation_error(query_serializer)
        queryset = self.filter_queryset(self.get_queryset())
        serializer = BSNChangesListSerializer(
            {
                "bsnWijzigingen": queryset,
                "_links": {
                    "self": {"href": self.request.get_full_path()},
                    "ingeschrevenPersoon": {"href": "/bevragingen/v1/personen"},
                },
            }
        )
        return Response(serializer.data)

    def get_queryset(self):
        subscriptions = super().get_queryset().values_list("bsn", flat=True).distinct()
        return BSNChange.objects.filter(old_bsn__in=subscriptions)

    def _extract_burgerservicenummers(self, response_data) -> list[str]:
        """Extract the list of burgerservicenummers from the response data."""
        burgerservicenummers = []
        for change in response_data.get("bsnWijzigingen", []):
            if isinstance(change, dict):
                old_bsn = change.get("burgerservicenummerOud")
                new_bsn = change.get("burgerservicenummerNieuw")
                if old_bsn:
                    burgerservicenummers.append(old_bsn)
                if new_bsn:
                    burgerservicenummers.append(new_bsn)
        return burgerservicenummers

import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from django.utils import timezone
from drf_spectacular.utils import extend_schema_view
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from brp_kennisgevingen.models import (
    BSNMutation,
    NewResident,
    Subscription,
    SubscriptionTooLongException,
)
from brp_kennisgevingen.openapi import schema

from . import authentication, permissions
from .exceptions import ProblemJsonException, raise_serializer_validation_error
from .renderers import HALJSONRenderer
from .serializers import (
    NewResidentsInputSerializer,
    SubscriptionSerializer,
    UpdatesInputSerializer,
    UpdatesSerializer,
    UpdateSubscriptionSerializer,
)
from .utils import is_valid_bsn

audit_log = logging.getLogger("brp_kennisgevingen.audit")


class BaseAPIView(APIView):
    needed_scopes: set = {"benk-brp-volgindicaties-api"}

    authentication_classes = [authentication.JWTAuthentication]

    def get_permissions(self):
        """Collect the DRF permission checks.
        DRF checks these in the initial() method, and will block view access
        if these permissions are not satisfied.
        """
        if not self.needed_scopes:
            raise ImproperlyConfigured("needed_scopes is not set")

        return super().get_permissions() + [permissions.IsUserScope(self.needed_scopes)]


class SubscriptionAppIDFilterMixin:
    queryset = Subscription.objects.active()
    application_id: str = None

    def get_queryset(self):
        self.application_id = self.request.get_token_claims.get("sub")
        return self.queryset.filter(application_id=self.application_id)


@extend_schema_view(get=schema.list_subscriptions_schema)
class SubscriptionListAPIView(SubscriptionAppIDFilterMixin, ListAPIView, BaseAPIView):
    """
    List all active subscriptions for an application user.
    """

    serializer_class = SubscriptionSerializer

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema_view(
    get=schema.get_subscription_schema,
    put=schema.put_subscription_schema,
)
class SubscriptionsAPIView(SubscriptionAppIDFilterMixin, RetrieveUpdateAPIView, BaseAPIView):
    http_method_names: list[str] = ["get", "put"]
    lookup_field: str = "bsn"

    def get_object(self) -> Subscription | None:
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

        queryset = self.filter_queryset(self.get_queryset())

        try:
            instance = queryset.get(bsn=bsn)
        except Subscription.DoesNotExist:
            return None

        return instance

    def get_serializer_class(self):
        if self.request.method == "PUT":
            return UpdateSubscriptionSerializer
        return SubscriptionSerializer

    def log_access(self, request, msg: str, bsn: str):
        user_scopes = set(request.get_token_scopes)
        user_id = request.get_token_claims.get("email", request.get_token_subject)
        extra = {
            "user": user_id,
            "granted": sorted(user_scopes),
            "needed": sorted(self.needed_scopes),
            "bsn": bsn,
            "request": request.data,
        }

        audit_log.info(
            msg,
            {
                "user": user_id,
                "bsn": bsn,
            },
            extra=extra,
        )

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
        instance = self.get_object()

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            msg = (
                "Access denied for 'update subscription' to '%(user)s' on '%(bsn)s'"
                " (full request/response in detail)"
            )
            self.log_access(request=request, msg=msg, bsn=bsn)
            raise_serializer_validation_error(serializer)

        # Get the subscription end date or set it to the max allowed if no end_date is supplied
        end_date = serializer.validated_data.get(
            "einddatum", timezone.now().date() + timedelta(days=182)
        )

        if not instance:
            msg = (
                "Access granted for 'new subscription' to '%(user)s' on '%(bsn)s'"
                " (full request/response in detail)"
            )
            self.log_access(request=request, msg=msg, bsn=bsn)

            instance = Subscription.objects.create_with_bsn(
                application_id=self.application_id,
                bsn=bsn,
                start_date=timezone.now().date(),
                end_date=end_date,
            )
            serializer = SubscriptionSerializer(instance)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            try:
                instance.set_end_date(end_date)
            except SubscriptionTooLongException as err:
                raise ProblemJsonException(
                    title="Geen correcte waarde opgegeven.",
                    detail="The request could not be understood by the server due to malformed "
                    "syntax. The client SHOULD NOT repeat the request without modification.",
                    status=status.HTTP_400_BAD_REQUEST,
                    invalid_params=[
                        {
                            "name": "einddatum",
                            "code": "date",
                            "reason": "Einddatum mag maximaal 6 maanden in de toekomst liggen.",
                        }
                    ],
                ) from err

            msg = (
                "Access granted for 'update subscription' to '%(user)s' on '%(bsn)s'"
                " (full request/response in detail)"
            )
            self.log_access(request=request, msg=msg, bsn=bsn)
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
                    "ingeschrevenPersoon": {
                        "href": "/ingeschrevenpersonen/{burgerservicenummer}",
                        "templated": True,
                    },
                },
            }
        )
        return Response(serializer.data)

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

    queryset = Subscription.objects.active()
    input_serializer = UpdatesInputSerializer

    def get_queryset(self):
        subscriptions = super().get_queryset().values_list("bsn", flat=True).distinct()
        return BSNMutation.objects.filter(bsn__in=subscriptions)


@extend_schema_view(get=schema.list_new_residents_schema)
class NewResidentsListAPIView(UpdatesAPIBaseView):
    """
    Request a list of `burgerservicenummers` of new residents.
    """

    queryset = NewResident.objects.all()
    input_serializer = NewResidentsInputSerializer

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

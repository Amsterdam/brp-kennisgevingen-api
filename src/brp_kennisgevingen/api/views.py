from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from brp_kennisgevingen.models import NewResident, Subscription, SubscriptionTooLongException

from . import permissions
from .exceptions import ProblemJsonException, raise_serializer_validation_error
from .renderers import HALJSONRenderer
from .serializers import (
    DateInputSerializer,
    SubscriptionSerializer,
    UpdatesSerializer,
    UpdateSubscriptionSerializer,
)
from .utils import is_valid_bsn


class BaseAPIView(APIView):
    needed_scopes: set = {"benk-brp-volgindicaties"}

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


class SubscriptionListAPIView(SubscriptionAppIDFilterMixin, ListAPIView, BaseAPIView):
    serializer_class = SubscriptionSerializer

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


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
            instance = queryset.get(bsn__bsn=bsn)
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
        instance = self.get_object()

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            raise_serializer_validation_error(serializer)

        if not instance:
            Subscription.objects.create_with_bsn(
                application_id=self.application_id,
                bsn=self.kwargs["bsn"],
                start_date=timezone.now().date(),
                end_date=serializer.validated_data["einddatum"],
            )
            return Response(status=status.HTTP_201_CREATED)
        else:
            # Set the new subscription date
            try:
                instance.set_end_date(serializer.validated_data["einddatum"])
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

            return Response(status=status.HTTP_200_OK)


class UpdatesAPIBaseView(BaseAPIView):
    queryset = None
    renderer_classes = [HALJSONRenderer]

    bsn_field: str = "bsn"
    mutation_date_field: str = "mutation_date"

    def get_queryset(self):
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.all()
        return queryset

    def get(self, request, *args, **kwargs):
        # Validate URL query parameters
        query_serializer = DateInputSerializer(data=self.request.query_params)
        if not query_serializer.is_valid():
            raise_serializer_validation_error(query_serializer)

        queryset = self.get_queryset()

        start_date = query_serializer.validated_data["vanaf"]
        filter_kwargs = {
            f"{self.mutation_date_field}__gte": start_date,
            f"{self.mutation_date_field}__lte": timezone.now(),
        }

        queryset = queryset.filter(**filter_kwargs)

        serializer = UpdatesSerializer(
            {
                "burgerservicenummers": queryset.values_list(self.bsn_field, flat=True),
                "self": request.get_full_path(),
            }
        )
        return Response(serializer.data)


class UpdatesAPIView(SubscriptionAppIDFilterMixin, UpdatesAPIBaseView):
    queryset = Subscription.objects.active()
    bsn_field: str = "bsn__bsn"
    mutation_date_field: str = "bsn__mutation_date"


class NewResidentsListAPIView(UpdatesAPIBaseView):
    queryset = NewResident.objects.all()

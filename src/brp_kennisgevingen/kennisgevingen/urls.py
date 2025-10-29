from django.urls import path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularJSONAPIView,
    SpectacularSwaggerView,
    SpectacularYAMLAPIView,
)

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="brp-kennisgevingen-index")),
    path("v1", views.IndexView.as_view(), name="brp-kennisgevingen-index"),
    path("v1/volgindicaties", views.SubscriptionListAPIView.as_view(), name="subscriptions-list"),
    path(
        "v1/volgindicaties/<str:bsn>",
        views.SubscriptionsAPIView.as_view(),
        name="subscriptions-detail",
    ),
    path("v1/wijzigingen", views.UpdatesAPIView.as_view(), name="updates-list"),
    path(
        "v1/nieuwe-ingezetenen", views.NewResidentsListAPIView.as_view(), name="new-residents-list"
    ),
    path("v1/bsn-wijzigingen", views.BSNChangesListAPIView.as_view(), name="bsn-updates-list"),
    path(
        "v1/schema",
        SpectacularSwaggerView.as_view(url_name="schema-json"),
        name="swagger-ui",
    ),
    path("v1/openapi.json", SpectacularJSONAPIView.as_view(), name="schema-json"),
    path("v1/openapi.yaml", SpectacularYAMLAPIView.as_view(), name="schema-yaml"),
]

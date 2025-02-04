from django.urls import path

from . import views

urlpatterns = [
    path("volgindicaties", views.SubscriptionListAPIView.as_view(), name="subscriptions-list"),
    path(
        "volgindicaties/<str:bsn>",
        views.SubscriptionsAPIView.as_view(),
        name="subscriptions-detail",
    ),
    path("wijzigingen", views.UpdatesAPIView.as_view(), name="updates-list"),
    path("nieuwe-ingezetenen", views.NewResidentsListAPIView.as_view(), name="new-residents-list"),
]

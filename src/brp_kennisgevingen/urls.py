from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularJSONAPIView,
    SpectacularSwaggerView,
    SpectacularYAMLAPIView,
)

import brp_kennisgevingen.api.urls

from . import views

urlpatterns = [
    path("v1/", include(brp_kennisgevingen.api.urls)),
    path("status", views.RootView.as_view()),
    path("schema", SpectacularSwaggerView.as_view(url_name="schema-json"), name="swagger-ui"),
    path("openapi.json", SpectacularJSONAPIView.as_view(), name="schema-json"),
    path("openapi.yaml", SpectacularYAMLAPIView.as_view(), name="schema-yaml"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns.append(path("__debug__/", include(debug_toolbar.urls)))

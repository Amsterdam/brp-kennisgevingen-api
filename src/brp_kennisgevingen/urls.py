from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

import brp_kennisgevingen.api.urls

from . import views

urlpatterns = [
    path("", include(brp_kennisgevingen.api.urls)),
    path("status", views.RootView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns.append(path("__debug__/", include(debug_toolbar.urls)))

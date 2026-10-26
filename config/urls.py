from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from core import views

admin.site.site_header = "Terry Jar — boshqaruv"
admin.site.site_title = "Terry Jar"
admin.site.index_title = "Xodimlar, ruxsatlar va audit"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="app", permanent=False)),
    path("app/", views.app_view, name="app"),
    path("sw.js", views.service_worker, name="sw"),
    path("healthz", views.healthz, name="healthz"),
    path("api/sync/state", views.api_state, name="api_state"),
    path("api/sync/pull", views.api_pull, name="api_pull"),
    path("api/sync/push", views.api_push, name="api_push"),
    path("accounts/login/", views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password/", views.PasswordChangeView.as_view(), name="password_change"),
    path(settings.ADMIN_URL, admin.site.urls),
]

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import AuditLog


def _ip(request):
    if not request:
        return None
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def on_login(sender, request, user, **kw):
    AuditLog.objects.create(user=user, username=user.username, action="login", ip=_ip(request))


@receiver(user_logged_out)
def on_logout(sender, request, user, **kw):
    if user:
        AuditLog.objects.create(user=user, username=user.username, action="logout", ip=_ip(request))

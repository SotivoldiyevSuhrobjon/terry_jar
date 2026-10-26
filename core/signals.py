import hashlib
import re

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import AuditLog


def _ip(request):
    if not request:
        return None
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")


def device_of(ua: str) -> str:
    """Brauzer satridan qisqa nom: «Windows · Chrome», «Android · Chrome», «iPhone · Safari»."""
    ua = ua or ""
    os_ = next((n for p, n in [(r"Android", "Android"), (r"iPhone|iPad", "iPhone/iPad"), (r"Windows", "Windows"),
                               (r"Mac OS X|Macintosh", "Mac"), (r"Linux", "Linux")] if re.search(p, ua)), "")
    br = next((n for p, n in [(r"Edg/", "Edge"), (r"OPR/|Opera", "Opera"), (r"YaBrowser", "Yandex"),
                              (r"Firefox/", "Firefox"), (r"Chrome/", "Chrome"), (r"Safari/", "Safari")]
               if re.search(p, ua)), "")
    return " · ".join(x for x in (os_, br) if x) or "noma'lum"


def session_tag(key: str | None) -> str:
    return hashlib.sha256((key or "").encode()).hexdigest()[:10] if key else ""


@receiver(user_logged_in)
def on_login(sender, request, user, **kw):
    ua = request.META.get("HTTP_USER_AGENT", "") if request else ""
    tag = session_tag(request.session.session_key) if request else ""
    AuditLog.objects.create(user=user, username=user.username, action="login", ip=_ip(request),
                            note=f"{device_of(ua)}|{tag}"[:300])


@receiver(user_logged_out)
def on_logout(sender, request, user, **kw):
    if user:
        ua = request.META.get("HTTP_USER_AGENT", "") if request else ""
        AuditLog.objects.create(user=user, username=user.username, action="logout", ip=_ip(request),
                                note=device_of(ua)[:300])

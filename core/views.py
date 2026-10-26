import json
import re
import threading

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import sync
from .models import AuditLog, Record
from .signals import session_tag


# ---------------------------------------------------------------- frontend (demo HTML o'zgarmasdan)
class _Front:
    """frontend/app.html — demo fayli. O'zgartirilmaydi, faqat boshiga va oxiriga ulanish skriptlari qo'shiladi."""

    lock = threading.Lock()
    mtime = None
    head = mid = tail = ""
    key, ver, appver = "terryJarDemo", 0, ""

    @classmethod
    def load(cls):
        p = settings.FRONTEND_HTML
        m = p.stat().st_mtime
        if m != cls.mtime:
            with cls.lock:
                html = p.read_text(encoding="utf-8")
                k = re.search(r"const KEY='([^']+)'", html)
                v = re.search(r"\bS=\{v:(\d+)", html)
                av = re.search(r"const VERSION='([^']+)'", html)
                cls.appver = av.group(1).replace(" demo", "") if av else ""
                cls.key = k.group(1) if k else "terryJarDemo"
                cls.ver = int(v.group(1)) if v else 0
                if "<head>" in html and "</body>" in html:
                    i = html.index("<head>") + len("<head>")
                    j = html.rindex("</body>")
                    cls.head, cls.mid, cls.tail = html[:i], html[i:j], html[j:]
                else:  # demo fayli bo'lak ko'rinishida (artifact) — to'liq sahifaga o'raladi
                    cls.head = ('<!doctype html>\n<html lang="uz">\n<head>\n<meta charset="utf-8">\n'
                                '<meta name="viewport" '
                                'content="width=device-width,initial-scale=1,viewport-fit=cover">')
                    cls.mid = "\n</head>\n<body>\n" + html + "\n"
                    cls.tail = "</body>\n</html>\n"
                cls.mtime = m
        return cls


def _json_script(obj) -> str:
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _ensure_me(user):
    if not Record.objects.filter(col="users", rid=user.rid, deleted=False).exists():
        sync.sync_user_record(user, note="birinchi kirish")


@login_required
@never_cache
def app_view(request):
    f = _Front.load()
    user = request.user
    _ensure_me(user)
    state, rev = sync.build_state()
    state["v"] = f.ver
    from django.middleware.csrf import get_token
    boot = {
        "key": f.key, "v": f.ver, "rev": rev, "me": user.rid, "state": state,
        "csrf": get_token(request), "desc": sync.DESC_COLS, "local": sorted(sync.LOCAL_ONLY),
        "api": "/api/sync/", "ws": "/ws/sync/", "logout": reverse("logout"), "login": reverse("login"),
        "pw": reverse("password_change"), "ro": user.readonly, "name": user.full_name,
        "debug": settings.DEBUG, "release": settings.APP_RELEASE, "role": user.role, "br": user.branch,
        "fresh": not request.session.get("tj_in"),
        "version": settings.APP_VERSION,
    }
    request.session["tj_in"] = 1
    return _front_page(f, boot)


def _front_page(f, boot, status=200):
    """Demo HTML + ulanish skriptlari (boot.js oldidan, sync.js oxirida)."""
    static = settings.STATIC_URL
    ver = f"{settings.APP_RELEASE}-{settings.APP_VERSION}"
    head_inject = (f'\n{PWA_HEAD}'
                   f'\n<script>window.TJ_BOOT={_json_script(boot)};</script>'
                   f'\n<script src="{static}tj/boot.js?v={ver}"></script>\n')
    tail_inject = f'<script src="{static}tj/sync.js?v={ver}"></script>\n'
    html = f.head + head_inject + f.mid + tail_inject + f.tail
    resp = HttpResponse(html, content_type="text/html; charset=utf-8", status=status)
    resp["Cache-Control"] = "no-store"
    return resp


PWA_HEAD = ('<link rel="manifest" href="/manifest.webmanifest">'
            '<meta name="theme-color" content="#1b2190">'
            '<meta name="mobile-web-app-capable" content="yes">'
            '<meta name="apple-mobile-web-app-capable" content="yes">'
            '<meta name="apple-mobile-web-app-title" content="Terry Jar">'
            '<link rel="apple-touch-icon" href="/static/tj/icon-180.png">'
            '<link rel="icon" type="image/png" sizes="32x32" href="/static/tj/favicon-32.png">')


def manifest(request):
    """Ilova sifatida o'rnatish (PWA): Chrome/Edge manzil satrida «O'rnatish», telefonda «Bosh ekranga qo'shish»."""
    s = settings.STATIC_URL + "tj/"
    data = {
        "id": "/app/", "name": "Terry Jar — ishlab chiqarish hisobi", "short_name": "Terry Jar",
        "description": "Perixod, rasxod, Jar sklad, rangxona, grafik va nomenklatura",
        "start_url": "/app/", "scope": "/", "display": "standalone", "orientation": "any",
        "background_color": "#121a6b", "theme_color": "#1b2190", "lang": "uz",
        "icons": [
            {"src": s + "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": s + "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": s + "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    resp = JsonResponse(data, json_dumps_params={"ensure_ascii": False})
    resp["Content-Type"] = "application/manifest+json"
    resp["Cache-Control"] = "public, max-age=3600"
    return resp


def service_worker(request):
    js = (settings.BASE_DIR / "core" / "static" / "tj" / "sw.js").read_text(encoding="utf-8")
    resp = HttpResponse(js.replace("__VERSION__", f"{settings.APP_RELEASE}-{settings.APP_VERSION}"),
                        content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"
    return resp


# ---------------------------------------------------------------- API
def _api_auth(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login"}, status=401)
    if not request.user.is_active:
        return JsonResponse({"error": "inactive"}, status=403)
    return None


@require_GET
@never_cache
def api_state(request):
    err = _api_auth(request)
    if err:
        return err
    state, rev = sync.build_state()
    state["v"] = _Front.load().ver
    return JsonResponse({"rev": rev, "state": state}, json_dumps_params={"ensure_ascii": False})


@require_GET
@never_cache
def api_pull(request):
    err = _api_auth(request)
    if err:
        return err
    try:
        since = int(request.GET.get("since", "0"))
    except ValueError:
        return JsonResponse({"error": "since"}, status=400)
    return JsonResponse(sync.pull(since), json_dumps_params={"ensure_ascii": False})


@require_POST
def api_push(request):
    err = _api_auth(request)
    if err:
        return err
    try:
        body = json.loads(request.body or b"{}")
        note = ""
        if body.get("by") and body.get("by") != request.user.rid:
            note = f"oflayn navbatdan (qurilmada boshqa xodim: {str(body.get('byName', ''))[:60]})"
        res = sync.push(request.user, str(body.get("op", "")), body.get("ch") or [],
                        ip=request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR"), note=note)
    except (ValueError, sync.PushError) as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse(res, json_dumps_params={"ensure_ascii": False})


# ---------------------------------------------------------------- Profilim
@require_GET
@never_cache
def api_me_logins(request):
    err = _api_auth(request)
    if err:
        return err
    me_tag = session_tag(request.session.session_key)
    rows = []
    for a in AuditLog.objects.filter(user=request.user, action__in=("login", "logout")).order_by("-ts")[:15]:
        dev, _, tag = (a.note or "").partition("|")
        rows.append({"t": timezone.localtime(a.ts).strftime("%d.%m.%Y %H:%M"), "a": a.action, "ip": a.ip or "",
                     "dev": dev, "cur": bool(tag and tag == me_tag)})
    return JsonResponse({"logins": rows}, json_dumps_params={"ensure_ascii": False})


@require_POST
def api_me_password(request):
    err = _api_auth(request)
    if err:
        return err
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"ok": False, "error": "Noto'g'ri so'rov"}, status=400)
    form = PasswordChangeForm(request.user, data={"old_password": body.get("old", ""),
                                                  "new_password1": body.get("new1", ""),
                                                  "new_password2": body.get("new2", "")})
    if not form.is_valid():
        if "old_password" in form.errors:
            msg = "Hozirgi parol noto'g'ri"
        else:
            msg = " ".join(str(e) for errs in form.errors.values() for e in errs)
        return JsonResponse({"ok": False, "error": msg})
    user = form.save()
    user.must_change_password = False
    user.save(update_fields=["must_change_password"])
    update_session_auth_hash(request, user)
    AuditLog.objects.create(user=user, username=user.username, action="update", col="users", rid=user.rid,
                            note="o'z parolini almashtirdi (Profilim)")
    return JsonResponse({"ok": True})


@require_POST
def api_me_logout_others(request):
    err = _api_auth(request)
    if err:
        return err
    from django.contrib.sessions.models import Session
    uid, cur, n = str(request.user.pk), request.session.session_key, 0
    for s in Session.objects.filter(expire_date__gt=timezone.now()).exclude(session_key=cur).iterator():
        try:
            data = s.get_decoded()
        except Exception:  # buzilgan sessiya
            continue
        if data.get("_auth_user_id") == uid:
            s.delete()
            n += 1
    AuditLog.objects.create(user=request.user, username=request.user.username, action="logout",
                            note=f"boshqa qurilmalardan chiqarildi: {n}")
    return JsonResponse({"ok": True, "n": n})


def healthz(request):
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
    except Exception:
        return JsonResponse({"ok": False}, status=503)
    return JsonResponse({"ok": True, "release": settings.APP_RELEASE, "build": settings.APP_VERSION})


# ---------------------------------------------------------------- auth pages
def version_label() -> str:
    return f"{settings.APP_RELEASE}"


class LoginView(auth_views.LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kw):
        return {**super().get_context_data(**kw), "version": version_label()}

    def render_to_response(self, context, **kw):
        # Demo bilan bir xil kirish oynasi (3D fon, logo). Demo fayli bo'lmasa — oddiy Django shabloni.
        try:
            f = _Front.load()
        except OSError:
            return super().render_to_response(context, **kw)
        from django.middleware.csrf import get_token
        form = context.get("form")
        boot = {
            "anon": True, "key": f.key, "v": f.ver, "csrf": get_token(self.request),
            "action": self.request.get_full_path(), "next": self.get_redirect_url() or reverse("app"),
            "error": bool(form is not None and form.errors),
            "username": (form.data.get("username", "") if form is not None and form.is_bound else "")[:150],
            "version": settings.APP_VERSION, "release": settings.APP_RELEASE,
        }
        return _front_page(f, boot, status=200)


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "registration/password_change.html"
    success_url = reverse_lazy("app")

    def get_context_data(self, **kw):
        return {**super().get_context_data(**kw), "version": version_label()}

    def form_valid(self, form):
        resp = super().form_valid(form)
        u = self.request.user
        u.must_change_password = False
        u.save(update_fields=["must_change_password"])
        messages.success(self.request, "Parol almashtirildi")
        return resp

import json
import re
from pathlib import Path

from django.conf import settings

from core import roles


def test_app_requires_login(client, db):
    r = client.get("/app/")
    assert r.status_code == 302 and "/accounts/login/" in r["Location"]


def test_app_page_wraps_demo(client, state, mk):
    u = mk("pl", "planner")
    client.force_login(u)
    r = client.get("/app/")
    html = r.content.decode()
    assert r.status_code == 200
    assert "window.TJ_BOOT=" in html and "/static/tj/boot.js" in html and "/static/tj/sync.js" in html
    assert html.index("boot.js") < html.index("const KEY=")  # boot demo skriptidan oldin
    assert html.index("const KEY=") < html.index("sync.js")
    boot = json.loads(re.search(r"window.TJ_BOOT=(\{.*?\});</script>", html).group(1))
    assert boot["me"] == u.rid and boot["state"]["designs"][0]["id"] == "d1"


def test_push_needs_csrf(client, state, mk):
    from django.test import Client
    c = Client(enforce_csrf_checks=True)
    c.force_login(mk("p", "perixod"))
    r = c.post("/api/sync/push", data=json.dumps({"op": "x", "ch": []}), content_type="application/json")
    assert r.status_code == 403


def test_api_unauthenticated(client, db):
    assert client.get("/api/sync/pull?since=0").status_code == 401


def test_force_password_change(client, state, mk):
    u = mk("yangi", "perixod")
    u.must_change_password = True
    u.save()
    client.force_login(u)
    assert client.get("/app/")["Location"] == "/accounts/password/"


def test_healthz(client, db):
    assert client.get("/healthz").json()["ok"] is True


def test_roles_match_frontend():
    html = Path(settings.FRONTEND_HTML).read_text(encoding="utf-8")
    js_perms = re.findall(r"^ \['(\w+)','", html[html.index("const PERMS=["):html.index("const ROLE_ALLOW")], re.M)
    assert js_perms == roles.PERM_KEYS
    allow = html[html.index("const ROLE_ALLOW={"):html.index("const ROLE_DEF")]
    for role, perms in roles.ROLE_ALLOW.items():
        if role == "admin":
            continue
        m = re.search(rf"\b{role}:\[([^\]]*)\]", allow)
        assert m and re.findall(r"'(\w+)'", m.group(1)) == perms, role

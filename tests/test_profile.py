import json

from django.test import Client


def _login(mk_user, pw="Parol-12345"):
    c = Client(HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) AppleWebKit Chrome/140.0 Safari/537.36")
    c.force_login(mk_user)
    return c


def test_logins_list_marks_current_device(state, mk):
    u = mk("pfx", "perixod")
    c = Client(HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) Chrome/140.0 Safari/537.36")
    r = c.post("/accounts/login/", {"username": "pfx", "password": "Parol-12345"})
    assert r.status_code == 302
    data = c.get("/api/me/logins").json()["logins"]
    assert data[0]["a"] == "login" and data[0]["dev"] == "Windows · Chrome" and data[0]["cur"] is True
    assert u.username


def test_password_change_via_profile(state, mk):
    u = mk("pfy", "perixod")
    c = _login(u)
    bad = c.post("/api/me/password", json.dumps({"old": "xato", "new1": "Yangi-Parol-77", "new2": "Yangi-Parol-77"}),
                 content_type="application/json").json()
    assert bad["ok"] is False and "noto'g'ri" in bad["error"]
    ok = c.post("/api/me/password", json.dumps({"old": "Parol-12345", "new1": "Yangi-Parol-77",
                                                "new2": "Yangi-Parol-77"}), content_type="application/json").json()
    assert ok["ok"] is True
    u.refresh_from_db()
    assert u.check_password("Yangi-Parol-77") and not u.must_change_password
    assert c.get("/api/me/logins").status_code == 200  # sessiya saqlanib qoldi


def test_logout_other_devices(state, mk):
    u = mk("pfz", "perixod")
    sex, phone = _login(u), _login(u)
    assert sex.get("/api/sync/pull?since=0").status_code == 200
    r = phone.post("/api/me/logout-others", "{}", content_type="application/json").json()
    assert r["n"] == 1
    assert sex.get("/api/sync/pull?since=0").status_code == 401  # sex kompyuteri chiqarildi
    assert phone.get("/api/sync/pull?since=0").status_code == 200  # o'zi qoldi

import uuid

import pytest

from core import sync
from core.models import AuditLog, Record, User


def op():
    return uuid.uuid4().hex


def ch(c, id, d, b=None, k="a"):
    return {"c": c, "k": k, "id": id, "d": d, "b": b}


def test_merge_fields_and_lists():
    base = {"a": 1, "b": 1, "rd": ["x"]}
    mine = {"a": 2, "b": 1, "rd": ["x", "me"]}
    theirs = {"a": 1, "b": 5, "rd": ["x", "other"]}
    out = sync.merge3(base, mine, theirs)
    assert out["a"] == 2 and out["b"] == 5
    assert sorted(out["rd"]) == ["me", "other", "x"]


def test_state_roundtrip(state):
    S, rev = sync.build_state()
    assert rev >= 1
    assert S["designs"][0]["name"] == "50X90"
    assert S["lm"]["jar:101"]["des"] == "d1"
    assert S["vals"] == [] and S["cfg"]["cap"] == 800 and S["v"] == 16


def test_push_pull_and_idempotency(state, mk):
    p = mk("p1", "perixod")
    rev0 = sync.current_rev()
    oid = op()
    val = {"id": "v1", "br": "jar", "code": "101/1"}
    r1 = sync.push(p, oid, [ch("vals", "v1", val)])
    r2 = sync.push(p, oid, [ch("vals", "v1", val)])  # internet uzilib takror yuborildi
    assert r1 == r2
    assert Record.objects.filter(col="vals", rid="v1").count() == 1
    pulled = sync.pull(rev0)
    assert [c["id"] for c in pulled["ch"] if c["c"] == "vals"] == ["v1"]
    sync.push(p, op(), [ch("vals", "v1", None, val)])
    S, _ = sync.build_state()
    assert S["vals"] == []


def test_concurrent_field_merge(state, mk):
    a, b = mk("pl1", "planner"), mk("pl2", "planner")
    base = state["designs"][0]
    sync.push(a, op(), [ch("designs", "d1", {**base, "kgDay": 777}, base)])
    res = sync.push(b, op(), [ch("designs", "d1", {**base, "cust": "B"}, base)])
    merged = res["res"][0]["d"]
    assert merged["kgDay"] == 777 and merged["cust"] == "B"


def test_readonly_director(state, mk):
    d = mk("katta", "director", branch="*", readonly=True)
    base = state["designs"][0]
    res = sync.push(d, op(), [ch("designs", "d1", {**base, "cust": "X"}, base)])
    assert res["res"][0]["st"] == "rej"
    assert Record.objects.get(col="designs", rid="d1").data["cust"] == "A"
    assert AuditLog.objects.filter(action="reject", user=d).exists()
    n = state["notif"][0]
    ok = sync.push(d, op(), [ch("notif", "n1", {**n, "rd": [d.rid]}, n)])
    assert ok["res"][0]["st"] == "ok"
    ok = sync.push(d, op(), [ch("log", "l1", {"u": d.full_name, "w": "Tizimga kirdi"})])
    assert ok["res"][0]["st"] == "ok"


def test_passport_number_conflict(state, mk):
    a, b = mk("rx1", "rasxod"), mk("rx2", "rasxod")
    p1 = {"id": "p1", "br": "jar", "month": "2026-10", "no": 112, "st": "sent"}
    p2 = {"id": "p2", "br": "jar", "month": "2026-10", "no": 112, "st": "sent"}
    sync.push(a, op(), [ch("passes", "p1", p1)])
    res = sync.push(b, op(), [ch("passes", "p2", p2)])
    assert res["res"][0]["d"]["no"] == 113
    assert "113" in res["res"][0]["msg"]


def test_branch_settings_need_permission(state, mk):
    p = mk("p2", "perixod")
    br = state["branches"][0]
    res = sync.push(p, op(), [ch("branches", "jar", {**br, "name": "Boshqa"}, br)])
    assert res["res"][0]["st"] == "rej"


def test_user_management(state, mk):
    boss = mk("boss1", "boss")
    new = {"id": "u9", "u": "yangi.xodim", "p": "Maxfiy-123", "name": "Yangi", "role": "perixod", "br": "jar",
           "perms": ["per_kirit"], "secs": [], "act": True}
    res = sync.push(boss, op(), [ch("users", "u9", new)])
    r = res["res"][0]
    assert r["st"] == "ok" and "p" not in r["d"]
    u = User.objects.get(username="yangi.xodim")
    assert u.check_password("Maxfiy-123") and u.must_change_password
    assert "Maxfiy" not in str(Record.objects.get(col="users", rid="u9").data)
    # boshliq o'zidan yuqori lavozim bera olmaydi
    bad = {**new, "id": "u10", "u": "direktor2", "role": "director"}
    assert sync.push(boss, op(), [ch("users", "u10", bad)])["res"][0]["st"] == "rej"
    # login band
    dup = {**new, "id": "u11"}
    assert sync.push(boss, op(), [ch("users", "u11", dup)])["res"][0]["msg"] == "Bu login band"


def test_self_escalation_rejected(state, mk):
    pl = mk("pl3", "planner")
    cur = Record.objects.get(col="users", rid=pl.rid).data
    res = sync.push(pl, op(), [ch("users", pl.rid, {**cur, "role": "boss"}, cur)])
    assert res["res"][0]["st"] == "rej"
    pl.refresh_from_db()
    assert pl.role == "planner"


def test_bad_packet(state, mk):
    p = mk("p3", "perixod")
    with pytest.raises(sync.PushError):
        sync.push(p, op(), [{"c": "../x", "k": "a", "id": "1", "d": {}}])

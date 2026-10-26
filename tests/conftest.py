import os

os.environ.setdefault("DJANGO_DEBUG", "1")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")

import pytest  # noqa: E402

from core import sync  # noqa: E402
from core.models import User  # noqa: E402
from core.roles import PERM_KEYS, ROLE_DEF, VIEW_PERMS  # noqa: E402


@pytest.fixture
def mk(db):
    def make(username, role, branch="jar", readonly=False, perms=None, pw="Parol-12345"):
        if perms is None:
            perms = VIEW_PERMS if readonly else (PERM_KEYS if role == "admin" else ROLE_DEF[role])
        u = User(username=username, full_name=username.title(), role=role, branch=branch, readonly=readonly,
                 perms=list(perms), must_change_password=False)
        u.set_password(pw)
        u.save()
        sync.sync_user_record(u)
        return u
    return make


@pytest.fixture
def state(db):
    S = {"v": 16, "cfg": {"cap": 800, "tola": ["16/1"]}, "branches": [{"id": "jar", "name": "Jar"}],
         "designs": [{"id": "d1", "br": "jar", "name": "50X90", "cust": "A", "kgDay": 1}],
         "vals": [], "passes": [], "notif": [{"id": "n1", "br": "jar", "text": "x", "rd": [], "roles": ["planner"]}],
         "log": [], "lm": {"jar:101": {"des": "d1", "act": True}}}
    sync.push(None, "init", sync.state_changes(S))
    return S

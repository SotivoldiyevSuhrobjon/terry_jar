"""Sinxronlash xizmati.

Frontend (demo) butun holatni `S` obyektida saqlaydi. Server uni yozuvlarga bo'lib saqlaydi:
  S.vals[i]       -> Record(col='vals',  kind='a', rid=val.id)
  S.lm['jar:101'] -> Record(col='lm',    kind='o', rid='jar:101')
  S.v             -> Record(col='_meta', kind='s', rid='v', data={'v': 16})

Qurilma faqat o'zgargan yozuvlarni yuboradi (push), boshqalarning o'zgarishlarini oladi (pull).
Bir vaqtda ikki kishi bitta yozuvni o'zgartirsa — maydon darajasida birlashtiriladi (3-way merge).
"""
from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import AuditLog, Counter, Record, SyncOp, User
from .roles import GLOBAL_ROLES, ROLE_ALLOW, ROLES, rank

log = logging.getLogger("tj.sync")

META = "_meta"
KINDS_RID = "_kinds"
LOCAL_ONLY = {"queue"}  # faqat shu qurilmaga tegishli (demo offline navbati)
DESC_COLS = ["log", "notif", "issues", "gsync", "transfers"]  # frontend .unshift() qiladi — yangisi boshida
NO_AUDIT = {"log"}  # tarixning o'zi — auditga qayta yozilmaydi
MAX_CHANGES = 20000
PULL_LIMIT = 20000
COL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,39}$")
LOGIN_RE = re.compile(r"^[a-z0-9_.]{3,150}$")
_MISSING = object()

PROTECTED_USER_FIELDS = ("u", "role", "br", "perms", "secs", "act")
NEED_PERMS = {"acl": {"xodim"}, "branches": {"filial"}, "sections": {"filial", "stanok"}}


class PushError(Exception):
    pass


# ---------------------------------------------------------------- actor
@dataclass
class Actor:
    user: User | None
    role: str = "admin"
    perms: set = field(default_factory=set)
    readonly: bool = False
    br: str = "*"
    rid: str = ""
    name: str = "tizim"

    @property
    def admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_global(self) -> bool:
        return self.role in GLOBAL_ROLES or self.br == "*"

    @classmethod
    def of(cls, user: User) -> Actor:
        return cls(user=user, role=user.role, perms=set(user.perms or []), readonly=user.readonly,
                   br=user.branch, rid=user.rid, name=user.full_name or user.username)

    @classmethod
    def system(cls) -> Actor:
        return cls(user=None)


# ---------------------------------------------------------------- merge
def merge3(base, mine, theirs):
    """Maydon darajasida birlashtirish: men o'zgartirgan maydon — meniki, qolgani — serverdagi."""
    if not (isinstance(base, dict) and isinstance(mine, dict) and isinstance(theirs, dict)):
        if mine == base:
            return theirs
        if theirs == base:
            return mine
        return _merge_list(base, mine, theirs)
    out = dict(theirs)
    for k in set(base) | set(mine) | set(theirs):
        bv, mv, tv = base.get(k, _MISSING), mine.get(k, _MISSING), theirs.get(k, _MISSING)
        if mv == bv:
            continue
        if tv == bv or tv == mv:
            val = mv
        elif isinstance(mv, dict) and isinstance(tv, dict):
            val = merge3(bv if isinstance(bv, dict) else {}, mv, tv)
        else:
            val = _merge_list(bv, mv, tv)
        if val is _MISSING:
            out.pop(k, None)
        else:
            out[k] = val
    return out


def _merge_list(bv, mv, tv):
    """Ikkala tomon ham ro'yxatni o'zgartirgan bo'lsa (masalan, xabarni o'qiganlar `rd`) — birlashtiriladi."""
    prim = (str, int, float, bool, type(None))
    if all(isinstance(x, list) and all(isinstance(e, prim) for e in x) for x in (mv, tv)):
        base = bv if isinstance(bv, list) else []
        removed = [e for e in base if e not in mv]
        out = [e for e in tv if e not in removed]
        out += [e for e in mv if e not in out and e not in base]
        return out
    return mv


# ---------------------------------------------------------------- state
def current_rev() -> int:
    c = Counter.objects.filter(pk=1).first()
    return c.rev if c else 0


def get_kinds() -> dict:
    r = Record.objects.filter(col=META, rid=KINDS_RID).first()
    return dict(r.data or {}) if r else {}


def build_state() -> tuple[dict, int]:
    """To'liq holat (sahifa ochilganda)."""
    with transaction.atomic():
        rev = current_rev()
        kinds = get_kinds()
        S: dict = {c: ([] if k == "a" else {}) for c, k in kinds.items()}
        rows = (Record.objects.filter(deleted=False).exclude(col=META)
                .order_by("col", "seq", "id").values_list("col", "kind", "rid", "data"))
        for col, kind, rid, data in rows:
            if kind == "o":
                S.setdefault(col, {})[rid] = data
            else:
                S.setdefault(col, []).append(data)
        for col in DESC_COLS:
            if isinstance(S.get(col), list):
                S[col].reverse()
        for rid, data in Record.objects.filter(col=META, deleted=False).exclude(rid=KINDS_RID).values_list(
                "rid", "data"):
            S[rid] = (data or {}).get("v")
    return S, rev


def pull(since: int) -> dict:
    rev = current_rev()
    qs = Record.objects.filter(rev__gt=since).exclude(col=META, rid=KINDS_RID).order_by("rev", "seq", "id")
    if qs.count() > PULL_LIMIT:
        return {"rev": rev, "reload": True}
    ch = []
    for col, kind, rid, data, deleted in qs.values_list("col", "kind", "rid", "data", "deleted"):
        if col == META:
            ch.append({"c": META, "k": "s", "id": rid, "d": None if deleted else data})
        else:
            ch.append({"c": col, "k": kind, "id": rid, "d": None if deleted else data})
    return {"rev": rev, "ch": ch}


# ---------------------------------------------------------------- permissions
def _strip(d, key):
    return {k: v for k, v in (d or {}).items() if k != key}


def check(actor: Actor, c: str, d, cur) -> tuple[bool, str]:
    if actor.admin:
        return True, ""
    if actor.readonly:
        if c == "log" and cur is None and isinstance(d, dict):
            return True, ""
        if c == "notif" and isinstance(cur, dict) and isinstance(d, dict):
            added = set(d.get("rd") or []) - set(cur.get("rd") or [])
            if _strip(d, "rd") == _strip(cur, "rd") and added <= {actor.rid}:
                return True, ""
        return False, "Sizda faqat ko'rish huquqi bor — o'zgartirish saqlanmadi"
    need = NEED_PERMS.get(c)
    if need and not (need & actor.perms):
        return False, "Bu bo'limni o'zgartirishga ruxsatingiz yo'q"
    if c == "acl" and rank(actor.role) > 2:
        return False, "Bo'lim ruxsatlarini faqat rahbarlar o'zgartiradi"
    return True, ""


def can_manage(actor: Actor, role: str, br: str) -> bool:
    if actor.admin:
        return True
    if actor.readonly or "xodim" not in actor.perms:
        return False
    if rank(role) <= rank(actor.role):
        return False
    return actor.is_global or br == actor.br


# ---------------------------------------------------------------- push
class _Ctx:
    def __init__(self, actor: Actor, rev: int, ip=None, note=""):
        self.actor, self.rev, self.ip, self.note = actor, rev, ip, note
        self.changed = False
        self.kinds = None
        self.kinds_rec = None


def push(user: User | None, op_id: str, changes: list, ip=None, note="") -> dict:
    if not isinstance(changes, list) or len(changes) > MAX_CHANGES:
        raise PushError("Noto'g'ri paket")
    if not op_id or len(op_id) > 64:
        raise PushError("op_id kerak")
    done = SyncOp.objects.filter(op_id=op_id).first()
    if done:
        return done.response
    actor = Actor.of(user) if user else Actor.system()
    try:
        with transaction.atomic():
            Counter.objects.get_or_create(pk=1)
            ctr = Counter.objects.select_for_update().get(pk=1)
            ctx = _Ctx(actor, ctr.rev + 1, ip, note)
            results = []
            for i, ch in enumerate(changes):
                r = _apply(ctx, ch, i)
                if r:
                    results.append(r)
            if ctx.kinds_rec is not None and ctx.kinds != (ctx.kinds_rec.data or {}):
                ctx.kinds_rec.data = ctx.kinds
                ctx.kinds_rec.rev = ctx.rev
                ctx.kinds_rec.save()
                ctx.changed = True
            if ctx.changed:
                ctr.rev = ctx.rev
                ctr.save(update_fields=["rev"])
            resp = {"rev": ctr.rev, "res": results}
            SyncOp.objects.create(op_id=op_id, user=user, rev=ctr.rev, response=resp)
            if ctx.changed:
                rev = ctr.rev
                transaction.on_commit(lambda: broadcast(rev))
    except IntegrityError:
        done = SyncOp.objects.filter(op_id=op_id).first()
        if done:
            return done.response
        raise
    return resp


def _load_kinds(ctx: _Ctx):
    if ctx.kinds is None:
        ctx.kinds_rec, _ = Record.objects.get_or_create(col=META, rid=KINDS_RID, defaults={"kind": "s", "data": {}})
        ctx.kinds = dict(ctx.kinds_rec.data or {})
    return ctx.kinds


def _apply(ctx: _Ctx, ch: dict, i: int):
    if not isinstance(ch, dict):
        raise PushError("Noto'g'ri o'zgarish")
    c, k, rid, d, b = ch.get("c"), ch.get("k"), ch.get("id"), ch.get("d"), ch.get("b")
    if not isinstance(c, str) or not COL_RE.match(c) or k not in ("a", "o", "s"):
        raise PushError(f"Noto'g'ri bo'lim: {c!r}")
    if c in LOCAL_ONLY:
        return None
    if k == "s":
        c = META
    elif c != META:
        kinds = _load_kinds(ctx)
        if kinds.get(c) != k:
            if ctx.actor.readonly:
                return None
            kinds[c] = k
    if ch.get("reg"):
        return None
    if rid is None or len(str(rid)) > 120:
        raise PushError("Noto'g'ri ID")
    rid = str(rid)
    if c == META and rid == KINDS_RID:
        raise PushError("Ruxsat yo'q")

    rec = Record.objects.filter(col=c, rid=rid).first()
    cur = rec.data if rec and not rec.deleted else None

    if c == "users":
        return _apply_user(ctx, rec, cur, rid, d, b, k, i)

    ok, msg = check(ctx.actor, c, d, cur)
    if not ok:
        _audit(ctx, c, rid, "reject", cur, d, msg)
        return {"c": c, "k": k, "id": rid, "st": "rej", "msg": msg, "d": cur}

    res = {"c": c, "k": k, "id": rid, "st": "ok"}
    if d is None:
        if cur is not None:
            rec.deleted, rec.data, rec.rev = True, None, ctx.rev
            rec.updated_by = ctx.actor.user
            rec.save()
            ctx.changed = True
            if c not in NO_AUDIT:
                _audit(ctx, c, rid, "delete", cur, None)
        return res

    new = d
    if cur is not None and b != cur:
        new = merge3(b if b is not None else {}, d, cur)
    if c == "passes" and isinstance(new, dict):
        new, msg = _fix_pass_no(new, rid)
        if msg:
            res["msg"] = msg
    if cur is not None and new == cur:
        if new != d:
            res["d"] = new
        return res
    _save(ctx, rec, c, k, rid, new, i)
    if c not in NO_AUDIT:
        _audit(ctx, c, rid, "create" if cur is None else "update", cur, new)
    if new != d:
        res["d"] = new
    return res


def _save(ctx: _Ctx, rec, c, k, rid, data, i):
    if rec is None:
        rec = Record(col=c, rid=rid, kind=k)
    if rec.pk is None or rec.deleted:
        rec.seq = ctx.rev * 100000 + i
    rec.kind, rec.data, rec.deleted, rec.rev = k, data, False, ctx.rev
    rec.updated_by = ctx.actor.user
    rec.save()
    ctx.changed = True
    return rec


def _fix_pass_no(p: dict, rid: str):
    """Ikki rasxodchi bir vaqtda bir xil pasport raqamini olsa — ikkinchisiga keyingi bo'sh raqam beriladi."""
    no, month, br = p.get("no"), p.get("month"), p.get("br")
    if not isinstance(no, int) or not month:
        return p, ""
    used = set(Record.objects.filter(col="passes", deleted=False, data__br=br, data__month=month)
               .exclude(rid=rid).values_list("data__no", flat=True))
    if no not in used:
        return p, ""
    n = no
    while n in used:
        n += 1
    return {**p, "no": n}, f"Pasport raqami {no} boshqa rasxodchida band edi — {n}-П berildi"


# ---------------------------------------------------------------- users
def _apply_user(ctx: _Ctx, rec, cur, rid, d, b, k, i):
    actor = ctx.actor
    target = User.objects.filter(rid=rid).first()

    def rej(msg):
        _audit(ctx, "users", rid, "reject", _nopass(cur), _nopass(d), msg)
        return {"c": "users", "k": k, "id": rid, "st": "rej", "msg": msg, "d": cur}

    if actor.readonly:
        return rej("Sizda faqat ko'rish huquqi bor — o'zgartirish saqlanmadi")
    self_edit = rid == actor.rid and not actor.admin
    if self_edit:
        if d is None or not isinstance(d, dict) or d.get("p") or any(
                d.get(f) != (cur or {}).get(f) for f in PROTECTED_USER_FIELDS):
            return rej("O'zingizning lavozim va ruxsatlaringizni o'zgartira olmaysiz")
    elif cur is not None and not can_manage(actor, cur.get("role", ""), cur.get("br", "")):
        return rej("Bu xodimni boshqarishga ruxsatingiz yo'q")

    if d is None:
        if target:
            target.is_active = False
            target.save(update_fields=["is_active"])
        if cur is not None:
            rec.deleted, rec.data, rec.rev = True, None, ctx.rev
            rec.updated_by = actor.user
            rec.save()
            ctx.changed = True
            _audit(ctx, "users", rid, "delete", cur, None, "xodim o'chirildi (hisob bloklandi)")
        return {"c": "users", "k": k, "id": rid, "st": "ok"}

    if not isinstance(d, dict):
        return rej("Noto'g'ri ma'lumot")
    d = dict(d)
    pw = d.pop("p", None) or ""
    login = str(d.get("u", "")).strip().lower()
    role = d.get("role")
    br = str(d.get("br") or "")
    perms = [p for p in (d.get("perms") or []) if isinstance(p, str)]
    if not LOGIN_RE.match(login):
        return rej("Login faqat lotin harf, raqam, nuqta va _ dan iborat, kamida 3 belgi bo'lsin")
    if role not in ROLES or not str(d.get("name", "")).strip():
        return rej("Ism va lavozim to'g'ri kiritilsin")
    if not self_edit and not can_manage(actor, role, br):
        return rej("Bu lavozimni yoki filialni bera olmaysiz")
    if not actor.admin and not self_edit and not set(perms) <= set(ROLE_ALLOW.get(role, [])):
        return rej("Bu lavozimga berilmaydigan ruxsat tanlangan")
    if User.objects.filter(username__iexact=login).exclude(rid=rid).exists():
        return rej("Bu login band")
    if target is None and not pw:
        return rej("Yangi xodimga parol kiriting")
    if pw and len(pw) < 6:
        return rej("Parol kamida 6 belgi bo'lsin")

    if target is None:
        target = User(rid=rid, username=login)
    target.username = login
    target.full_name = str(d.get("name")).strip()[:150]
    target.role = role
    target.branch = "*" if role == "director" else br
    target.perms = perms
    target.secs = d.get("secs") or []
    target.is_active = d.get("act") is not False
    if pw:
        target.set_password(pw)
        target.must_change_password = True
    target.save()

    d["u"] = login
    d["ro"] = target.readonly
    d["sm"] = target.smena
    new = d if cur is None or b == cur else merge3(_nopass(b) or {}, d, cur)
    _save(ctx, rec, "users", k, rid, new, i)
    _audit(ctx, "users", rid, "create" if cur is None else "update", _nopass(cur), new,
           "parol o'rnatildi" if pw else "")
    return {"c": "users", "k": k, "id": rid, "st": "ok", "d": new}


def _nopass(d):
    if isinstance(d, dict) and "p" in d:
        return {k: v for k, v in d.items() if k != "p"}
    return d


def user_record_data(u: User, old: dict | None = None) -> dict:
    data = dict(old or {})
    data.update({"id": u.rid, "u": u.username, "name": u.full_name or u.username, "role": u.role,
                 "br": "*" if u.role in GLOBAL_ROLES else u.branch, "secs": u.secs or [], "perms": u.perms or [],
                 "act": u.is_active, "sm": u.smena, "ro": u.readonly})
    data.setdefault("by", "admin panel")
    data.setdefault("t", timezone.localtime().strftime("%d.%m.%Y %H:%M"))
    data.pop("p", None)
    return data


def sync_user_record(u: User, by: User | None = None, note="admin panel"):
    """Django admin yoki buyruq orqali xodim o'zgarsa — ilovadagi ro'yxat ham yangilanadi."""
    with transaction.atomic():
        Counter.objects.get_or_create(pk=1)
        ctr = Counter.objects.select_for_update().get(pk=1)
        ctx = _Ctx(Actor.of(by) if by else Actor.system(), ctr.rev + 1, note=note)
        _load_kinds(ctx)
        if ctx.kinds.get("users") != "a":
            ctx.kinds["users"] = "a"
            ctx.kinds_rec.data = ctx.kinds
            ctx.kinds_rec.save()
        rec = Record.objects.filter(col="users", rid=u.rid).first()
        cur = rec.data if rec and not rec.deleted else None
        new = user_record_data(u, cur)
        if new != cur:
            _save(ctx, rec, "users", "a", u.rid, new, 0)
            _audit(ctx, "users", u.rid, "admin", cur, new, note)
            ctr.rev = ctx.rev
            ctr.save(update_fields=["rev"])
            rev = ctr.rev
            transaction.on_commit(lambda: broadcast(rev))


# ---------------------------------------------------------------- import
def state_changes(S: dict) -> list:
    """Python dagi holatni push paketiga aylantirish (boshlang'ich ma'lumot yuklash uchun)."""
    out = []
    for c, v in S.items():
        if c in LOCAL_ONLY:
            continue
        if isinstance(v, list) and all(isinstance(x, dict) for x in v):
            out.append({"c": c, "k": "a", "reg": True})
            items = list(reversed(v)) if c in DESC_COLS else v
            for x in items:
                key = x.get("id") or x.get("_k")
                if not key:
                    key = x["_k"] = secrets.token_hex(4)
                out.append({"c": c, "k": "a", "id": str(key), "d": x})
        elif isinstance(v, dict):
            out.append({"c": c, "k": "o", "reg": True})
            for key, val in v.items():
                out.append({"c": c, "k": "o", "id": str(key), "d": val})
        else:
            out.append({"c": META, "k": "s", "id": c, "d": {"v": v}})
    return out


# ---------------------------------------------------------------- misc
def _audit(ctx: _Ctx, c, rid, action, before, after, note=""):
    u = ctx.actor.user
    AuditLog.objects.create(user=u, username=(u.username if u else "tizim"), col=c, rid=rid, action=action,
                            before=_nopass(before), after=_nopass(after), note=(note or ctx.note)[:300], ip=ctx.ip)


def broadcast(rev: int):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)("sync", {"type": "rev", "rev": rev})
    except Exception:  # Redis vaqtincha ishlamasa ham yozuv saqlanadi — qurilmalar so'rov bilan oladi
        log.warning("broadcast failed", exc_info=True)

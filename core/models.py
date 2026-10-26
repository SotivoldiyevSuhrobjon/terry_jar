import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models

from .roles import ROLE_CHOICES


def new_rid() -> str:
    return secrets.token_hex(4)


class User(AbstractUser):
    """Xodim. `rid` — ilovadagi (S.users) yozuv identifikatori, ikkalasi doim bog'langan."""

    SMENA_CHOICES = [("", "—"), ("A", "A smena"), ("B", "B smena")]

    rid = models.CharField("Ilova ID", max_length=32, unique=True, default=new_rid, editable=False)
    full_name = models.CharField("F.I.Sh.", max_length=150)
    role = models.CharField("Lavozim", max_length=20, choices=ROLE_CHOICES, default="perixod")
    branch = models.CharField("Filial", max_length=32, default="jar", help_text="* — barcha filiallar")
    smena = models.CharField("Smena", max_length=1, choices=SMENA_CHOICES, blank=True)
    perms = models.JSONField("Ruxsatlar", default=list, blank=True)
    secs = models.JSONField("Uchastkalar", default=list, blank=True)
    readonly = models.BooleanField(
        "Faqat ko'rish", default=False,
        help_text="Belgilansa, xodim hamma narsani ko'radi, lekin hech narsani o'zgartira olmaydi.")
    must_change_password = models.BooleanField("Parolni almashtirishi shart", default=True)

    class Meta:
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar"

    def __str__(self):
        return f"{self.full_name or self.username} ({self.username})"


class Counter(models.Model):
    """Global o'zgarish raqami (rev). Har bir push shu qatorni qulflaydi — yozuvlar ketma-ket bo'ladi."""

    rev = models.BigIntegerField(default=0)


class Record(models.Model):
    """Ilova holatining bitta yozuvi (val, pasport, dizayn, stanok, sozlama ...).

    kind: a — massiv elementi (S.vals[...]), o — obyekt kaliti (S.lm['jar:101']), s — oddiy qiymat (S.v).
    """

    KIND_CHOICES = [("a", "massiv"), ("o", "obyekt"), ("s", "qiymat")]

    col = models.CharField("Bo'lim", max_length=40)
    rid = models.CharField("ID", max_length=120)
    kind = models.CharField(max_length=1, choices=KIND_CHOICES, default="a")
    data = models.JSONField(null=True, blank=True)
    seq = models.BigIntegerField("Tartib", default=0)
    rev = models.BigIntegerField(db_index=True, default=0)
    deleted = models.BooleanField(default=False)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ma'lumot yozuvi"
        verbose_name_plural = "Ma'lumot yozuvlari"
        constraints = [models.UniqueConstraint(fields=["col", "rid"], name="uniq_record_col_rid")]
        indexes = [models.Index(fields=["col", "deleted"])]

    def __str__(self):
        return f"{self.col}/{self.rid}"


class SyncOp(models.Model):
    """Qurilmadan kelgan har bir paket. Takror yuborilsa (internet uzilib qolganda) ikki marta yozilmaydi."""

    op_id = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)
    rev = models.BigIntegerField(default=0)
    response = models.JSONField(default=dict)


class AuditLog(models.Model):
    ACTIONS = [("create", "Qo'shildi"), ("update", "O'zgardi"), ("delete", "O'chirildi"), ("reject", "Rad etildi"),
               ("login", "Kirdi"), ("logout", "Chiqdi"), ("admin", "Admin panel")]

    ts = models.DateTimeField("Vaqt", auto_now_add=True, db_index=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Xodim")
    username = models.CharField(max_length=150, blank=True)
    col = models.CharField("Bo'lim", max_length=40, blank=True, db_index=True)
    rid = models.CharField("ID", max_length=120, blank=True)
    action = models.CharField("Amal", max_length=10, choices=ACTIONS)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Audit yozuvi"
        verbose_name_plural = "Audit (kim nima qildi)"
        ordering = ["-ts"]

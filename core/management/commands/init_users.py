import json
import os
import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import sync
from core.models import User
from core.roles import PERM_KEYS, ROLE_DEF, VIEW_PERMS

FIX = Path(__file__).resolve().parents[2] / "fixtures"


def temp_password() -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


class Command(BaseCommand):
    help = ("Administrator va xodimlarni yaratadi (staff.json). Har biriga vaqtinchalik parol beriladi, "
            "birinchi kirishda o'zgartiriladi. Mavjud xodimlarga tegmaydi.")

    def add_arguments(self, p):
        p.add_argument("--file", default=str(FIX / "staff.json"),
                       help="Xodimlar ro'yxati. Namuna: core/fixtures/staff.example.json (repo'da haqiqiy ismlar yo'q)")
        p.add_argument("--admin-username", default=os.environ.get("ADMIN_USERNAME", "admin"))
        p.add_argument("--admin-name", default=os.environ.get("ADMIN_FULL_NAME", "Administrator"))

    def handle(self, *a, **o):
        created = []
        admin = User.objects.filter(username=o["admin_username"]).first()
        if not admin:
            pw = os.environ.get("ADMIN_PASSWORD") or temp_password()
            admin = User(username=o["admin_username"], full_name=o["admin_name"], role="admin", branch="*",
                         perms=list(PERM_KEYS), is_staff=True, is_superuser=True,
                         must_change_password=not os.environ.get("ADMIN_PASSWORD"))
            admin.set_password(pw)
            admin.save()
            sync.sync_user_record(admin, note="init_users")
            created.append((admin, pw))

        path = Path(o["file"])
        if not path.exists():
            raise CommandError(f"{path} topilmadi. staff.example.json dan nusxa olib, xodimlarni yozing "
                               "(haqiqiy ismlar Git'ga tushmaydi).")
        staff = json.loads(path.read_text(encoding="utf-8"))
        for s in staff:
            if User.objects.filter(username=s["username"]).exists():
                continue
            role = s["role"]
            if s.get("readonly"):
                perms = list(VIEW_PERMS)
            elif s.get("perms") == "all":
                perms = list(PERM_KEYS)
            else:
                perms = list(s.get("perms") or ROLE_DEF[role])
            name = s["full_name"] + (f" · {s['smena']} smena" if s.get("smena") else "")
            u = User(username=s["username"], full_name=name, role=role,
                     branch="*" if role == "director" else s.get("branch", "jar"), smena=s.get("smena", ""),
                     readonly=bool(s.get("readonly")), perms=perms, must_change_password=True)
            pw = temp_password()
            u.set_password(pw)
            u.save()
            sync.sync_user_record(u, by=admin, note="init_users")
            created.append((u, pw))

        if not created:
            self.stdout.write("Yangi xodim yo'q — hammasi oldin yaratilgan.")
            return
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        out = settings.DATA_DIR / "boshlangich_parollar.txt"
        lines = ["Terry Jar — vaqtinchalik parollar (birinchi kirishda almashtiriladi).",
                 "Tarqatgach faylni o'chiring!", ""]
        for u, pw in created:
            lines.append(f"{u.full_name:<40} {u.get_role_display():<18} login: {u.username:<26} parol: {pw}")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(out, 0o600)
        self.stdout.write("\n".join(lines))
        self.stdout.write(self.style.SUCCESS(f"\n{len(created)} ta hisob yaratildi. Nusxa: {out}"))

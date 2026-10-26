import json
import uuid
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core import sync
from core.models import Record

FIX = Path(__file__).resolve().parents[2] / "fixtures"


class Command(BaseCommand):
    help = ("Boshlang'ich holatni yuklaydi: filiallar, uchastkalar, stanoklar, sozlamalar. "
            "--demo — demodagi barcha sinov ma'lumotlari bilan (faqat sinov serveri uchun).")

    def add_arguments(self, p):
        p.add_argument("--demo", action="store_true", help="Demo sinov ma'lumotlari (vallar, pasportlar ...)")
        p.add_argument("--file", help="Boshqa JSON fayl (masalan demodan olingan zaxira nusxa)")
        p.add_argument("--force", action="store_true", help="Baza bo'sh bo'lmasa ham yuklash (ustiga yozadi)")

    def handle(self, *a, **o):
        if Record.objects.exclude(col="users").exclude(col="_meta").exists() and not o["force"]:
            msg = "Bazada ma'lumot bor — o'tkazib yuborildi (--force bilan majburlash mumkin)."
            self.stdout.write(self.style.WARNING(msg))
            return
        path = Path(o["file"]) if o["file"] else FIX / ("demo_state.json" if o["demo"] else "base_state.json")
        if not path.exists():
            raise CommandError(f"Fayl topilmadi: {path}")
        S = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(S, dict) and "S" in S and isinstance(S["S"], dict):  # demo zaxira fayli {t, S}
            S = S["S"]
        S.pop("users", None)  # xodimlar faqat init_users / admin panel orqali
        S.pop("queue", None)
        ch = sync.state_changes(S)
        ch.append({"c": "users", "k": "a", "reg": True})
        res = sync.push(None, "init-" + uuid.uuid4().hex, ch, note=f"boshlang'ich yuklash: {path.name}")
        self.stdout.write(self.style.SUCCESS(f"Yuklandi: {path.name}, {len(ch)} yozuv, rev={res['rev']}"))

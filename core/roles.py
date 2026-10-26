"""Lavozimlar va ruxsatlar — frontend (demo) dagi ROLES / PERMS / ROLE_ALLOW / ROLE_DEF bilan bir xil.

Demo kodida o'zgarish bo'lsa, shu fayl ham yangilanadi (tests/test_roles.py ikkisini solishtiradi).
"""

ROLES = {
    "admin": ("Admin", 0),
    "director": ("Katta boshliq", 1),
    "boss": ("Filial boshlig'i", 2),
    "planner": ("Rejalashtirish", 3),
    "perixod": ("Perixod", 4),
    "rasxod": ("Rasxod", 4),
    "dye": ("Rangxona", 4),
    "sklad": ("Jar sklad", 4),
    "master": ("Master", 4),
}
ROLE_CHOICES = [(k, v[0]) for k, v in ROLES.items()]

PERMS = [
    ("filial", "Filiallarni boshqarish"),
    ("xodim", "Xodimlar va ruxsatlar"),
    ("stanok", "Stanoklar"),
    ("nom", "Nomenklatura"),
    ("biriktir", "Stanokka dizayn biriktirish"),
    ("grafik", "Grafik"),
    ("muammo", "Muammoli stanoklar"),
    ("zakaz", "Zakazlar"),
    ("per_kirit", "Perixod kiritish"),
    ("per_tahrir", "Perixodni to'liq tahrirlash"),
    ("rx", "Rasxod: pasport va yuborish"),
    ("pechat", "Pasportni pechat qilish"),
    ("sklad", "Jar sklad: qabul"),
    ("rang", "Rangxona: qabul qilish"),
    ("davomat", "Davomat va to'quvchilar"),
    ("brak", "Brak kiritish"),
    ("oy", "Oyni yakunlash"),
    ("excel", "Excel yuklab olish / yuklash"),
    ("hisobot", "Hisobotlar"),
    ("xabar", "Ogohlantirishlar"),
    ("tarix", "To'liq tarix"),
    ("jadval", "Tola va glatka jadvali"),
    ("sozlama", "Sozlamalar"),
]
PERM_KEYS = [p[0] for p in PERMS]

ROLE_ALLOW = {
    "admin": PERM_KEYS,
    "director": ["grafik", "muammo", "xodim", "stanok", "nom", "biriktir", "zakaz", "per_tahrir", "oy",
                 "excel", "jadval", "hisobot", "xabar", "tarix", "sozlama"],
    "boss": ["grafik", "muammo", "xodim", "stanok", "nom", "biriktir", "zakaz", "per_tahrir", "oy", "excel",
             "jadval", "hisobot", "xabar", "tarix"],
    "planner": ["grafik", "muammo", "xodim", "nom", "biriktir", "zakaz", "per_kirit", "per_tahrir", "oy",
                "excel", "jadval", "hisobot", "xabar", "tarix"],
    "master": ["davomat", "brak", "muammo", "hisobot"],
    "perixod": ["per_kirit", "excel"],
    "rasxod": ["rx", "pechat", "oy", "excel", "hisobot"],
    "dye": ["rang", "excel", "hisobot"],
    "sklad": ["sklad", "excel", "hisobot"],
}

ROLE_DEF = {
    "admin": ROLE_ALLOW["admin"],
    "director": ROLE_ALLOW["director"],
    "boss": ROLE_ALLOW["boss"],
    "planner": ["grafik", "muammo", "xodim", "nom", "biriktir", "zakaz", "per_kirit", "per_tahrir", "oy",
                "excel", "jadval", "hisobot", "xabar"],
    "master": ["davomat", "brak", "muammo"],
    "perixod": ["per_kirit"],
    "rasxod": ["rx", "pechat", "oy", "excel"],
    "dye": ["rang"],
    "sklad": ["sklad"],
}

# Faqat ko'rish huquqi (katta boshliq) uchun ruxsatlar: hech narsani o'zgartirmaydi
VIEW_PERMS = ["hisobot", "tarix", "xabar"]

GLOBAL_ROLES = {"admin", "director"}


def rank(role: str) -> int:
    return ROLES.get(role, ("", 9))[1]

# Terry Jar — ishlab chiqarish hisobi (backend)

Perixod, rasxod, Jar sklad, rangxona, grafik, nomenklatura, zakazlar, muammoli stanoklar — demo
(`frontend/app.html`) dagi **barcha** funksiyalar endi haqiqiy server, login-parol va umumiy baza bilan ishlaydi.

**Muallif:** Suhrobjon — [t.me/user0601](https://t.me/user0601)

## Qanday ishlaydi

```
Brauzer (demo HTML — o'zgarmagan)
  ├─ boot.js  — serverdagi holatni demoga beradi, kirgan xodimni tanlaydi
  └─ sync.js  — o'zgarganini serverga yuboradi, boshqalarnikini real vaqtda oladi
        │  HTTPS  /api/sync/push · /api/sync/pull         WSS /ws/sync/
        ▼
nginx (SSL, statik fayllar, limitlar) ──► Django 5.2 + Channels (uvicorn, 3 worker)
                                              ├─ PostgreSQL 16 — barcha ma'lumot, audit
                                              └─ Redis 7 — real vaqt xabarlari (worker'lar orasida)
```

- **Demo kodi bir harf ham o'zgarmaydi.** `frontend/app.html` — `terry_jar_demo.html` ning aynan nusxasi.
  Demo yangilansa, faylni almashtirish kifoya (pastga qarang).
- Ma'lumot yozuvlarga bo'linib saqlanadi (`Record`: har bir val, pasport, dizayn, stanok alohida qator).
  Qurilma faqat o'zgargan yozuvni yuboradi.
- **Ikki kishi bir vaqtda** bitta yozuvni o'zgartirsa — maydon darajasida birlashtiriladi
  (biri `kgDay`, ikkinchisi `due` ni o'zgartirsa, ikkalasi ham saqlanadi).
- **Pasport raqami poygasi:** ikki rasxodchi bir vaqtda bir xil raqam olsa, ikkinchisiga keyingi bo'sh
  raqam beriladi va ekranida xabar chiqadi.
- **Internet uzilsa:** o'zgarishlar qurilmadagi navbatda turadi (sahifa yopilsa ham), internet qaytganda
  o'zi yuboriladi; har paketning noyob raqami bor — ikki marta yozilmaydi.
- **Ruxsatlar serverda tekshiriladi:** faqat-ko'rish xodimi (katta boshliq) hech narsani o'zgartira olmaydi;
  xodimlar, filiallar, bo'lim ruxsatlari faqat tegishli huquq bilan; o'zidan yuqori lavozim berib bo'lmaydi.
- **Audit:** kim, qachon, nimani, oldin va keyin qanday edi — hammasi `AuditLog` da (admin panelda).
- Parollar faqat hash ko'rinishida (PBKDF2). 5 marta xato parol → 15 daqiqa blok (django-axes).
- **Ilova sifatida o'rnatish (PWA):** Chrome/Edge'da manzil satrida «O'rnatish» belgisi va sahifada «📲 Ilovani o'rnatish»
  tugmasi; Android'da «Bosh ekranga qo'shish»; iPhone'da Safari → «Ulashish» → «На экран Домой». O'rnatilgan ilova
  alohida oynada, o'z ikonkasi bilan ochiladi. Login formasi brauzerning «parolni saqlash» taklifi bilan ishlaydi.
- **Internet yoki server uzilsa** — 15 soniya ichida o'zi «Offline»ga o'tadi, sahifa tepasida qizil ogohlantirish chiqadi,
  ish to'xtamaydi (vallar kompyuterda saqlanadi). Aloqa tiklansa o'zi yuboradi va «Online»ga qaytadi.
- **«Online / Offline» belgisi bosilsa** — «Server bilan aloqa» oynasi: navbat, oxirgi aloqa vaqti, «Hozir yuborish»,
  `.json` fayldan qayta yuborish. «Oflaynni sinash» tugmasi faqat ishlab chiqish rejimida (DEBUG) ko'rinadi.
- **Kompyuterdagi papka** (Chrome/Edge, har kompyuterda bir marta): «Papkani ulash» → masalan `D:` tanlanadi →
  dastur `D:\perixod_fayllari` ni o'zi ochadi: `yuborilmagan\`, `yuborilgan\SANA\`, kunlik `vallar_SANA.csv`
  (Excel; «Holat»: yuborilmagan / yuborildi 14:32 / serverda) va `O'QING.txt`.

## Xodimlar va lavozimlar

| Lavozim | Nima qila oladi |
|---|---|
| Admin | Hammasi + Django admin panel (xodimlar, ruxsatlar, audit) |
| Katta boshliq | Barcha filiallarni **ko'radi, o'zgartirmaydi** («Faqat ko'rish» — serverda tekshiriladi) |
| Filial boshlig'i | O'z filiali; kerak bo'lsa barcha ruxsatlar |
| Rejalashtirish | Grafik, nomenklatura, zakazlar, perixodni tahrirlash |
| Perixod (A/B smena) | Val kiritish |
| Jar sklad | Filiallardan kelgan vallarni qabul qilish |
| Rasxod (A/B smena) | Pasport, pechat, yuborish |
| Master (A/B smena) | Davomat, brak, muammoli stanoklar |

Haqiqiy xodimlar ro'yxati **repo'da saqlanmaydi** (public): serverda `core/fixtures/staff.example.json` dan
`core/fixtures/staff.json` nusxasini olib to'ldiring (bu fayl `.gitignore` da). Parollar `init_users` buyrug'i
bilan **tasodifiy** yaratiladi, xodim birinchi kirishda o'z parolini qo'yadi (kamida 8 belgi).

Xodimlarni boshqarishning ikki yo'li bor, ikkalasi bir-biri bilan darhol sinxron:
1. **Ilova ichida** — «Xodimlar» bo'limi (demodagi kabi; Ibrohimjon va admin).
2. **Django admin** — `https://DOMEN/<DJANGO_ADMIN_URL>` (faqat administrator): lavozim, filial, smena,
   «faqat ko'rish», ruxsatlar, parolni tiklash, bloklash, audit va barcha yozuvlarni ko'rish.

## Kompyuterda ishlab chiqish (PyCharm, Windows)

Eng oddiy yo'l — Docker'siz (SQLite):

```powershell
cd terry_jar
python -m venv .venv; .venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.dev.example .env              # DJANGO_DEBUG=1 va kalit shu faylda — settings.py ni o'zgartirmang
python manage.py migrate
python manage.py init_state --demo      # demo sinov ma'lumotlari
python manage.py init_users             # xodimlar + vaqtinchalik parollar ekranga chiqadi
python manage.py runserver              # http://127.0.0.1:8000
```

- `.env` loyiha papkasida bo'lsa, sozlamalar uni **o'zi o'qiydi** — PyCharm'da muhit o'zgaruvchisi kiritish shart emas.
- `runserver` da real vaqt (WebSocket) yo'q, sahifalar har 20 soniyada yangilanadi. Real vaqtni sinash uchun:
  `uvicorn config.asgi:application --reload --port 8000`
- PostgreSQL + Redis bilan sinash: `docker compose -f docker-compose.dev.yml up -d` va `.env` dagi
  `DATABASE_URL`, `REDIS_URL` qatorlaridan `#` ni olib tashlang.
- Testlar: `pytest`, kod tekshiruvi: `ruff check .`

## Demo yangilanganda

1. Yangi `terry_jar_demo.html` ni `frontend/app.html` ga nusxalang.
2. `pytest` — `test_roles_match_frontend` demodagi rollar/ruxsatlar `core/roles.py` bilan mosligini tekshiradi.
3. `git commit` + `git push` — GitHub Actions test qiladi va serverga o'zi o'rnatadi.

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `init_state` | Toza boshlang'ich holat: filiallar, uchastkalar, stanoklar, sozlamalar |
| `init_state --demo` | Demodagi barcha sinov ma'lumotlari (faqat sinov serveri) |
| `init_state --file zaxira.json --force` | Demo «Zaxira» faylidan yuklash |
| `init_users` | Admin va `core/fixtures/staff.json` dagi xodimlar (mavjudlariga tegmaydi) |
| `axes_reset` | Bloklangan loginlarni ochish |

Server, SSL, zaxira, CI/CD — **[DEPLOY.md](DEPLOY.md)**.

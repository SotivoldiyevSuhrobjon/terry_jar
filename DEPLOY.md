# Serverga o'rnatish — Aeza VPS (Ubuntu 24.04)

Natija: `https://DOMEN` da ishlaydigan tizim. GitHub'ga `push` qilinsa — test, keyin serverga o'zi o'rnatiladi.
Har kecha soat 02:30 da baza zaxirasi olinadi.

## 0. Kerakli narsalar

- **VPS** (my.aeza.net): 4 vCPU, 8 GB RAM, 80+ GB NVMe, **Ubuntu 24.04**. IP manzil va root parol olinadi.
- **Domen**, masalan `terry.example.uz`. DNS: `A` yozuvi → server IP.
  Cloudflare ishlatilsa, SSL olguncha bulutcha **kulrang** (DNS only) tursin.
- **GitHub** repozitoriy (public bo'lishi mumkin: parollar, `.env`, xodimlar ro'yxati repo'da yo'q).

> ⚖️ **Shaxsiy ma'lumotlar qonuni:** O'zbekiston fuqarolarining shaxsiy ma'lumotlari (xodimlarning ism-familiyasi,
> logini) O'zbekiston hududidagi serverlarda saqlanishi talab qilinadi. Aeza serverlari xorijda.
> Ishga tushirishdan oldin buni yurist bilan aniqlang. Kerak bo'lsa, O'zbekistondagi VPS'ga xuddi shu
> qo'llanma bilan o'rnatiladi — hech narsa o'zgarmaydi.

## 1. Serverni himoyalash (bir marta, root sifatida)

```bash
ssh root@SERVER_IP
apt update && apt -y full-upgrade
timedatectl set-timezone Asia/Tashkent

# deploy foydalanuvchisi
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh && cp ~/.ssh/authorized_keys /home/deploy/.ssh/ 2>/dev/null || true
# o'z kompyuteringizdagi ochiq kalitni qo'shing (Windows: type $env:USERPROFILE\.ssh\id_ed25519.pub):
nano /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy

# faqat kalit bilan kirish, root bilan kirish yopiq
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/; s/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh

# firewall, fail2ban, avtomatik xavfsizlik yangilanishlari
apt -y install ufw fail2ban unattended-upgrades git
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
systemctl enable --now fail2ban
dpkg-reconfigure -f noninteractive unattended-upgrades

# 2 GB swap
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

**Yangi terminalda** `ssh deploy@SERVER_IP` ishlashini tekshiring, keyingina root sessiyani yoping.

## 2. Docker

```bash
ssh deploy@SERVER_IP
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy && exit      # qayta kiring
docker compose version
```

## 3. Kodni serverga olish

Serverda GitHub uchun faqat o'qish kaliti:
```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/github -C "terry-server"
sudo mkdir -p /opt/terry_jar && sudo chown deploy:deploy /opt/terry_jar
# public repo — kalitsiz:
git clone https://github.com/SIZNING_AKKAUNT/terry_jar.git /opt/terry_jar
# (private bo'lsa: ssh-keygen -t ed25519 -f ~/.ssh/github; .pub ni repo → Settings → Deploy keys ga; git@github.com:... bilan clone)
cd /opt/terry_jar
```

## 4. Sozlamalar

```bash
cp .env.example .env
python3 -c "import secrets;print(secrets.token_urlsafe(50))"   # -> DJANGO_SECRET_KEY
python3 -c "import secrets;print(secrets.token_urlsafe(24))"   # -> POSTGRES_PASSWORD
nano .env     # DOMAIN, CERTBOT_EMAIL, DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS, DJANGO_ADMIN_URL ...
chmod 600 .env
```

## 5. Ishga tushirish

Xodimlar ro'yxati (repo'da yo'q):
```bash
cp core/fixtures/staff.example.json core/fixtures/staff.json && nano core/fixtures/staff.json
```

**A) Server faqat shu loyiha uchun** (`.env`: `COMPOSE_PROFILES=proxy`) — quyidagi buyruqlar.
**B) Serverda nginx allaqachon bor** (boshqa saytlar) — pastdagi «Mavjud serverda subdomen» bo'limi.

```bash
./scripts/init-ssl.sh                 # SSL sertifikat + nginx + web (bir marta)
docker compose up -d                  # hamma servislar: db, redis, web, nginx, certbot, backup
docker compose ps                     # hammasi "running (healthy)"

docker compose exec web python manage.py init_state    # toza holat: filiallar, stanoklar, sozlamalar
docker compose exec web python manage.py init_users    # xodimlar va VAQTINCHALIK parollar ekranga chiqadi
```

`init_users` chiqargan ro'yxatni xodimlarga tarqating (nusxasi `appdata` hajmida
`/app/data/boshlangich_parollar.txt`). Tarqatgach o'chiring:
```bash
docker compose exec web rm /app/data/boshlangich_parollar.txt
```

Tekshirish: `https://DOMEN` → login sahifasi. Admin panel: `https://DOMEN/<DJANGO_ADMIN_URL>`.

> Demodagi ma'lumotlarni ko'chirish kerak bo'lsa: demoda «Sozlamalar → Zaxira → Faylga yuklab olish»,
> faylni serverga yuboring va `docker compose exec web python manage.py init_state --file /app/data/zaxira.json --force`.

## 5B. Mavjud serverda subdomen (nginx allaqachon bor)

Masalan serverda boshqa sayt ishlayapti va Terry Jar `terry.sizningdomen.uz` (yoki `terry-jar.duckdns.org`) da bo'ladi.

1. DNS: subdomen uchun `A` yozuvi → server IP (DuckDNS'da yangi subdomen yaratib, IP ni yozing).
2. `.env`: `COMPOSE_PROFILES=` (bo'sh), `WEB_PORT=8010` (band bo'lsa boshqa port), `DOMAIN=` subdomen,
   `DJANGO_ALLOWED_HOSTS` va `DJANGO_CSRF_TRUSTED_ORIGINS` ham subdomen bilan.
3. Ishga tushirish (nginx konteyneri ishlamaydi, 80/443 portlarga tegilmaydi):
   ```bash
   docker compose up -d --build
   docker compose exec web python manage.py init_state
   docker compose exec web python manage.py init_users
   curl -s http://127.0.0.1:8010/healthz      # {"ok": true ...}
   ```
4. Host nginx: `nginx/host-site.conf.example` ichidagi ko'rsatma bo'yicha (subdomen va port), so'ng
   `sudo certbot --nginx -d SUBDOMEN` — SSL ni certbot o'zi qo'shadi va yangilab turadi.

## 6. Avtomatik o'rnatish (CI/CD)

1. O'z kompyuteringizda Actions uchun alohida kalit: `ssh-keygen -t ed25519 -N "" -f gh_deploy`.
   `gh_deploy.pub` ni serverdagi `/home/deploy/.ssh/authorized_keys` ga qo'shing.
2. GitHub → repo → *Settings → Environments* → `production` yarating.
3. *Settings → Secrets and variables → Actions*:
   - **Secrets:** `SSH_KEY` (gh_deploy ichidagi maxfiy kalit), `SSH_HOST` (server IP), `SSH_USER` = `deploy`,
     `SSH_KNOWN_HOSTS` (o'z kompyuteringizda `ssh-keyscan SERVER_IP` natijasi), kerak bo'lsa `SSH_PORT`.
   - **Variables:** `DEPLOY_ENABLED` = `true`, `APP_DIR` = `/opt/terry_jar`.
4. Endi har `git push` (main) → **CI**: lint, migratsiya tekshiruvi, `check --deploy`, testlar, Docker yig'ish →
   **CD**: serverda `scripts/deploy.sh`: zaxira → yangi obraz → ishga tushirish → `/healthz` tekshiruvi →
   ishlamasa **avtomatik oldingi versiyaga qaytadi**.

Qo'lda o'rnatish: `cd /opt/terry_jar && ./scripts/deploy.sh`.

## 7. Zaxira nusxa

- Har kuni 02:30 → `/opt/terry_jar/backups/terry_YYYY-MM-DD_HHMM.sql.gz`, 14 kundan eskisi o'chadi.
- Har o'rnatishdan oldin ham alohida nusxa olinadi.
- Hozir qo'lda: `docker compose run --rm --entrypoint sh backup /backup.sh once`
- **Tiklash:** `./scripts/restore.sh backups/terry_2026-10-25_0230.sql.gz` (eski baza `_old` nomi bilan qoladi).
- **Serverdan tashqariga nusxa (tavsiya):** haftada bir `backups/` ni boshqa joyga (Google Drive, boshqa VPS)
  `rclone` bilan ko'chiring — server butunlay buzilsa ham ma'lumot qoladi:
  ```bash
  sudo apt -y install rclone && rclone config        # masalan "gdrive" nomi bilan
  (crontab -l; echo "0 4 * * 0 rclone copy /opt/terry_jar/backups gdrive:terry_backups --max-age 8d") | crontab -
  ```

## 7B. Telegram'ga zaxira (tavsiya etiladi)

Server butunlay buzilsa ham ma'lumot qolishi uchun har kechagi nusxa Telegram'ga ham yuboriladi (parol bilan shifrlangan).

1. Telegram'da **@BotFather** → `/newbot` → token oling.
2. **Yopiq kanal** (yoki guruh) yarating, botni unga **admin** qilib qo'shing va kanalga bitta xabar yozing.
3. Kanal ID sini oling: brauzerda `https://api.telegram.org/bot<TOKEN>/getUpdates` → `"chat":{"id":-100...}`.
4. Serverda `.env` ga qo'shing:
   ```
   TELEGRAM_BACKUP_BOT_TOKEN=123456:ABC...
   TELEGRAM_BACKUP_CHAT_ID=-1001234567890
   BACKUP_PASSPHRASE=uzun-maxfiy-ibora     # YO'QOTMANG — usiz zaxirani ochib bo'lmaydi
   ```
5. Qo'llash va sinash:
   ```bash
   docker compose up -d backup
   docker compose run --rm --entrypoint sh backup /backup.sh once    # kanalga darhol nusxa keladi
   ```

Fayl 47 MB dan katta bo'lsa bo'laklarga bo'linib yuboriladi (`cat *.part-* > fayl` bilan birlashtiriladi).
Telegram'dan olingan `.enc` faylni tiklash: `./scripts/restore.sh terry_SANA.sql.gz.enc` (parol so'raladi).

## 8. Kuzatish

- Holat: `docker compose ps`, loglar: `docker compose logs -f web` (nginx: `... logs -f nginx`).
- Tashqi kuzatuv: UptimeRobot yoki Uptime Kuma → `https://DOMEN/healthz` (server yoki baza to'xtasa xabar beradi).
- Disk: `df -h`, zaxiralar hajmi: `du -sh backups`.
- Bloklangan login: `docker compose exec web python manage.py axes_reset`.

## 9. Muhim eslatmalar

- `.env` va `backups/` Git'ga tushmaydi — ularni yo'qotmang.
- Migratsiyalar orqaga mos yozilsin (avtomatik qaytarishda eski kod yangi bazada ishlashi uchun):
  ustun o'chirish/qayta nomlashni ikki bosqichda qiling.
- Admin panel manzilini (`DJANGO_ADMIN_URL`) hech kimga bermang; xodimlar uni ishlatmaydi.

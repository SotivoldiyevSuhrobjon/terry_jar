/* Terry Jar — server bilan sinxronlash. Demo skriptidan KEYIN ishlaydi, demo kodiga tegmaydi.
   Ishlash tartibi:
   - demo save() qilganda: o'zgargan yozuvlar topiladi -> navbatga (outbox) qo'yiladi -> serverga yuboriladi;
   - internet bo'lmasa navbat qurilmada saqlanadi, internet qaytganda o'zi yuboriladi (takror yozilmaydi);
   - boshqa xodim o'zgartirsa server WebSocket orqali xabar beradi -> yangi yozuvlar olinadi -> ekran yangilanadi. */
(function () {
  'use strict';
  var B = window.TJ_BOOT, K = B.key, ls = window.localStorage;
  if (B.anon) { anonLogin(B); return; }
  var DESC = {}; (B.desc || []).forEach(function (c) { DESC[c] = 1; });
  var LOCAL = {}; (B.local || []).forEach(function (c) { LOCAL[c] = 1; });
  var SEP = '\u0001';
  var TJ = window.TJ = { rev: B.rev, down: false, userSim: false, wsOk: false, last: new Map(), outbox: [] };

  function lget(k, d) { try { var v = ls.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
  function lset(k, v) { try { Storage.prototype.setItem.call(ls, k, JSON.stringify(v)); } catch (e) {} }
  function rid() { return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4); }
  TJ.outbox = lget(K + '_outbox', []);

  /* ---------- holatni yozuvlarga bo'lish ---------- */
  function isRecArr(v) { if (!Array.isArray(v)) return false; for (var i = 0; i < v.length; i++) { var x = v[i]; if (!x || typeof x !== 'object' || Array.isArray(x)) return false; } return true; }
  function walk() {
    var M = new Map();
    Object.keys(S).forEach(function (c) {
      if (LOCAL[c]) return;
      var v = S[c];
      if (isRecArr(v)) {
        v.forEach(function (x) {
          if (x.id == null && !x._k) x._k = rid();
          var id = String(x.id != null ? x.id : x._k);
          M.set(c + SEP + id, { c: c, k: 'a', id: id, j: JSON.stringify(x) });
        });
      } else if (v && typeof v === 'object' && !Array.isArray(v)) {
        Object.keys(v).forEach(function (id) { M.set(c + SEP + id, { c: c, k: 'o', id: id, j: JSON.stringify(v[id]) }); });
      } else {
        M.set('_meta' + SEP + c, { c: '_meta', k: 's', id: c, j: JSON.stringify({ v: v === undefined ? null : v }) });
      }
    });
    return M;
  }
  function snap() { var L = new Map(); walk().forEach(function (r, key) { L.set(key, r.j); }); return L; }
  function parse(j) { return j == null ? null : JSON.parse(j); }

  function diff() {
    var cur = walk(), ch = [], newDesc = {};
    cur.forEach(function (r, key) {
      var old = TJ.last.get(key);
      if (old === r.j) return;
      var d = JSON.parse(r.j);
      if (r.c === 'users' && d && d.p) {
        // parol faqat serverga ketadi, qurilmada saqlanmaydi
        var u = (S.users || []).find(function (x) { return String(x.id) === r.id; });
        if (u) delete u.p;
        r.j = JSON.stringify(u || d);
      }
      var c = { c: r.c, k: r.k, id: r.id, d: d, b: parse(old) };
      if (old == null && DESC[r.c]) (newDesc[r.c] = newDesc[r.c] || []).push(c); else ch.push(c);
      TJ.last.set(key, r.j);
    });
    Object.keys(newDesc).forEach(function (c) { ch = ch.concat(newDesc[c].reverse()); });
    TJ.last.forEach(function (j, key) {
      if (cur.has(key)) return;
      var p = key.split(SEP), k = p[0] === '_meta' ? 's' : (Array.isArray(S[p[0]]) ? 'a' : 'o');
      ch.push({ c: p[0], k: k, id: p[1], d: null, b: parse(j) });
      TJ.last.delete(key);
    });
    if (ch.length) {
      var newOp = { op: rid() + rid(), by: B.me, byName: B.name, t: new Date().toISOString(), ch: ch };
      TJ.outbox.push(newOp);
      lset(K + '_outbox', TJ.outbox);
      try { fsQueued(newOp); } catch (e) {}
      pillRefresh(); barRefresh();
    }
    return ch.length;
  }

  /* ---------- serverdan kelgan yozuvni qo'llash ---------- */
  function applyRec(c, k, id, d) {
    var key = (k === 's' ? '_meta' : c) + SEP + id;
    if (k === 's') {
      if (id === 'v') return;
      if (d == null) delete S[id]; else S[id] = d.v;
      TJ.last.set(key, JSON.stringify({ v: S[id] === undefined ? null : S[id] }));
      return;
    }
    if (k === 'o') {
      if (!S[c] || typeof S[c] !== 'object' || Array.isArray(S[c])) S[c] = {};
      if (d == null) { delete S[c][id]; TJ.last.delete(key); } else { S[c][id] = d; TJ.last.set(key, JSON.stringify(d)); }
      return;
    }
    if (!Array.isArray(S[c])) S[c] = [];
    var A = S[c], i = -1;
    for (var n = 0; n < A.length; n++) { var x = A[n]; if (String(x.id != null ? x.id : x._k) === id) { i = n; break; } }
    if (d == null) { if (i >= 0) A.splice(i, 1); TJ.last.delete(key); return; }
    if (i >= 0) A[i] = d; else if (DESC[c]) A.unshift(d); else A.push(d);
    TJ.last.set(key, JSON.stringify(d));
  }
  function isDirty(c, k, id) {
    var key = (k === 's' ? '_meta' : c) + SEP + id, old = TJ.last.get(key), now;
    if (k === 's') now = JSON.stringify({ v: S[id] === undefined ? null : S[id] });
    else if (k === 'o') now = S[c] && S[c][id] !== undefined ? JSON.stringify(S[c][id]) : undefined;
    else { var x = (S[c] || []).find(function (e) { return String(e.id != null ? e.id : e._k) === id; }); now = x ? JSON.stringify(x) : undefined; }
    return now !== old;
  }

  var applying = false;
  function refreshUI() {
    applying = true;
    try { save(); } finally { applying = false; }
    if (typeof me !== 'undefined' && me) {
      var u = (S.users || []).find(function (x) { return x.id === me.id; });
      if (!u || u.act === false) { toast('Hisobingiz bloklandi'); setTimeout(postLogout, 1500); return; }
      me = u;
    }
    var a = document.activeElement;
    if (a && /INPUT|TEXTAREA|SELECT/.test(a.tagName) && a.closest('#view')) {
      ui.pendR = 1;
      return;
    }
    if (typeof me !== 'undefined' && me) render();
  }

  /* ---------- tarmoq ---------- */
  function api(path, body) {
    var opt = { credentials: 'same-origin', headers: { 'Accept': 'application/json' } };
    if (body) { opt.method = 'POST'; opt.headers['Content-Type'] = 'application/json'; opt.headers['X-CSRFToken'] = B.csrf; opt.body = JSON.stringify(body); }
    return fetch(B.api + path, opt).then(function (r) {
      if (r.status === 401) { location.href = B.login + '?next=/app/'; throw new Error('login'); }
      if (r.status === 403) return r.json().then(function (j) { if (j.error === 'password_change') location.href = B.pw; throw new Error(j.error || 'forbidden'); });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }
  function setDown(v) {
    if (TJ.down === v) return;
    if (v) TJ.downAt = new Date();
    var was = TJ.down;
    TJ.down = v;
    syncSim();
    barRefresh();
    if (v) toast("Server bilan aloqa uzildi — ish to'xtamaydi: kiritganlaringiz shu kompyuterda saqlanadi");
    else if (was) toast('Aloqa tiklandi — saqlangan o\'zgarishlar serverga yuborilmoqda');
    panelRefresh();
    if (typeof me !== 'undefined' && me && !applying) {
      var a = document.activeElement;
      if (!(a && /INPUT|TEXTAREA|SELECT/.test(a.tagName))) render();
    }
  }
  function pillRefresh() { var el = document.querySelector('.net'); if (el) { try { el.outerHTML = netPill(); } catch (e) {} } }
  function syncSim() { ui.simOff = TJ.down || TJ.userSim; }
  // Offline bo'lganda sahifa tepasida doim ko'rinadigan aniq ogohlantirish
  function barRefresh() {
    var bar = document.getElementById('tjBar'), off = isOff(), q = queueCount();
    if (!off) { if (bar) bar.remove(); document.body.classList.remove('tj-off'); return; }
    if (!bar) {
      bar = document.createElement('div'); bar.id = 'tjBar'; bar.setAttribute('role', 'status');
      bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:95;background:#b42318;color:#fff;font:600 13.5px/1.35 system-ui,sans-serif;padding:8px 14px;text-align:center;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25)';
      bar.onclick = function () { openPanel(); };
      document.body.appendChild(bar);
    }
    document.body.classList.add('tj-off');
    bar.textContent = (TJ.userSim ? 'OFLAYN SINOV — ' : 'INTERNET / SERVER ALOQASI YO\'Q — ') +
      'ishlashda davom eting: kiritganlar shu kompyuterda saqlanmoqda' + (q ? ' (' + q + ' ta o\'zgarish navbatda)' : '') +
      ', aloqa tiklanganda o\'zi yuboriladi.';
  }
  function offline() { return !navigator.onLine || TJ.userSim; }

  var running = false, again = false, needPull = true, retryT = null, backoff = 0;
  function schedule(ms) { clearTimeout(TJ._t); TJ._t = setTimeout(tick, ms == null ? 250 : ms); }
  window.__tjDirty = function () { if (!applying) schedule(250); };

  function tick() {
    if (running) { again = true; return; }
    running = true; again = false;
    try { diff(); } catch (e) { console.error('[tj] diff', e); }
    flush().then(function (ok) {
      if (!ok || TJ.outbox.length) return false;
      if (!needPull) return true;
      return pull();
    }).then(function (ok) {
      if (ok !== false) { backoff = 0; TJ.lastOk = new Date(); setDown(false); }
    }).catch(function (e) {
      console.warn('[tj]', e && e.message);
      setDown(true);
      backoff = Math.min(backoff ? backoff * 2 : 2000, 30000);
      clearTimeout(retryT); retryT = setTimeout(tick, backoff);
    }).then(function () {
      running = false;
      if (again) schedule(50);
    });
  }

  function flush() {
    if (!TJ.outbox.length) return Promise.resolve(true);
    if (offline()) return Promise.resolve(false);
    var op = TJ.outbox[0];
    return api('push', op).then(function (resp) {
      TJ.outbox.shift();
      lset(K + '_outbox', TJ.outbox);
      TJ.lastOk = new Date();
      try { fsSent(op, resp); } catch (e) {}
      pillRefresh(); barRefresh();
      var touched = false, msgs = [];
      (resp.res || []).forEach(function (r) {
        if (r.msg) msgs.push(r.msg);
        if (Object.prototype.hasOwnProperty.call(r, 'd')) { applyRec(r.c, r.k, r.id, r.d); touched = true; }
      });
      if (resp.rev > TJ.rev) needPull = true;
      if (touched) refreshUI();
      if (msgs.length) toast(msgs.filter(function (m, i) { return msgs.indexOf(m) === i; }).join(' · '));
      return flush();
    });
  }

  function pull() {
    return api('pull?since=' + TJ.rev).then(function (resp) {
      if (resp.reload) return api('state').then(function (st) { replaceAll(st.state, st.rev); return true; });
      var ch = resp.ch || [], touched = false;
      if (TJ.outbox.length) return true;
      try { diff(); } catch (e) {}
      if (TJ.outbox.length) { again = true; return true; }
      ch.forEach(function (r) {
        if (r.c === '_meta' && r.id === 'v') return;
        if (isDirty(r.c, r.k, r.id)) { again = true; return; }
        applyRec(r.c, r.k, r.id, r.d); touched = true;
      });
      TJ.rev = resp.rev; lset(K + '_rev', TJ.rev);
      needPull = false;
      if (touched) refreshUI();
      return true;
    });
  }

  function replaceAll(state, rev) {
    state.v = B.v;
    Object.keys(S).forEach(function (k) { if (!LOCAL[k]) delete S[k]; });
    Object.keys(state).forEach(function (k) { S[k] = state[k]; });
    TJ.last = snap(); TJ.rev = rev; lset(K + '_rev', rev); needPull = false;
    refreshUI();
  }

  /* ---------- real vaqt: WebSocket ---------- */
  var wsTry = 0;
  function connectWS() {
    if (!('WebSocket' in window)) return;
    var ws;
    try { ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + B.ws); } catch (e) { return; }
    TJ.ws = ws;
    ws.onopen = function () { TJ.wsOk = true; wsTry = 0; TJ.pongAt = Date.now(); needPull = true; schedule(0); };
    ws.onmessage = function (e) {
      TJ.pongAt = Date.now();
      try { var m = JSON.parse(e.data); if (m.t === 'rev' && m.rev > TJ.rev) { needPull = true; schedule(30); } } catch (x) {}
    };
    ws.onclose = function () {
      if (TJ.wsOk) { needPull = true; schedule(0); }
      TJ.wsOk = false;
      wsTry++;
      setTimeout(connectWS, Math.min(1000 * Math.pow(2, wsTry), 30000));
    };
  }
  setInterval(function () {
    var ws = TJ.ws;
    if (!ws || ws.readyState !== 1) return;
    if (TJ.pongAt && Date.now() - TJ.pongAt > 25000) { try { ws.close(); } catch (e) {} return; } // javob yo'q — aloqa o'lik
    try { ws.send('{"t":"ping"}'); } catch (e) {}
  }, 10000);
  setInterval(function () { needPull = true; schedule(0); }, 15000);
  window.addEventListener('online', function () { needPull = true; schedule(0); });
  window.addEventListener('offline', function () { setDown(true); });
  document.addEventListener('visibilitychange', function () { if (!document.hidden) { needPull = true; schedule(0); } });

  /* ---------- demo funksiyalarini server rejimiga moslash (demo fayli o'zgarmaydi) ---------- */
  function postLogout() {
    var f = document.createElement('form');
    f.method = 'POST'; f.action = B.logout;
    var i = document.createElement('input'); i.type = 'hidden'; i.name = 'csrfmiddlewaretoken'; i.value = B.csrf;
    f.appendChild(i); document.body.appendChild(f);
    try { var u = lget(K + '_ui', {}); delete u.u; lset(K + '_ui', u); } catch (e) {}
    try { if (window.caches) caches.keys().then(function (ks) { ks.forEach(function (k) { caches.open(k).then(function (c) { c.delete('/app/'); }); }); }); } catch (e) {}
    f.submit();
  }
  window.logout = function () {
    try { logA('Tizimdan chiqdi'); save(); } catch (e) {}
    try { diff(); } catch (e) {}
    if (offline()) {
      toast("Internet yo'q — yuborilmagan o'zgarishlar bor. Internet qaytgach chiqing.");
      return;
    }
    toast('Chiqilmoqda…');
    flush().then(function () { postLogout(); }, function () {
      toast("Server bilan aloqa yo'q — o'zgarishlar qurilmada saqlandi, keyin yuboriladi");
      setTimeout(postLogout, 1500);
    });
  };
  window.renderLogin = function () {
    // server rejimida login sahifasi Django'da; bu yerga faqat hisob ilovada topilmasa kelinadi
    document.getElementById('root').innerHTML = '<div style="padding:40px;font-family:sans-serif">Hisobingiz ilovada topilmadi yoki bloklangan. ' +
      '<button onclick="logout()">Chiqish</button></div>';
  };
  window.resetDemo = function () {
    ui.confirm = null;
    toast("Server rejimida demo ma'lumotlarni qayta yaratib bo'lmaydi");
    render();
  };
  var origRestore = window.restoreObj;
  if (typeof origRestore === 'function') {
    window.restoreObj = function (o, name) {
      // zaxiradan tiklashda xodimlar (va ularning parollari) tiklanmaydi — xodimlar faqat serverda boshqariladi
      var x = Object.assign({}, o); x.users = S.users; x.v = B.v;
      return origRestore.call(this, x, name);
    };
  }
  window.toggleSim = function () { openPanel(); };
  function queueCount() { return TJ.outbox.reduce(function (a, o) { return a + o.ch.length; }, 0); }
  window.netPill = function () {
    var q = queueCount(), fsW = FS.need ? ' ⚠' : '';
    if (isOff()) {
      var why = TJ.userSim ? ' (sinov)' : '';
      return '<button class="pill bad net" onclick="TJ.panel()" title="Server bilan aloqa yo\'q — o\'zgarishlar qurilmada saqlanmoqda. Batafsil uchun bosing">● Offline' + why + (q ? ' · ' + q + ' ta o\'zgarish navbatda' : '') + fsW + '</button>';
    }
    return '<button class="pill ok net" onclick="TJ.panel()" title="Server bilan ulangan' + (TJ.wsOk ? ', real vaqt' : '') + '. Batafsil uchun bosing">● Online' + (q ? ' · ' + q + ' yuborilmoqda' : '') + fsW + '</button>';
  };

  /* ---------- sinxronlash holati paneli ---------- */
  function hm(d) { return d ? String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0') + ':' + String(d.getSeconds()).padStart(2, '0') : '—'; }
  function esc2(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function panelHTML() {
    var q = queueCount(), off = isOff();
    var local = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);
    var st = off
      ? '<div class="notice bad"><div><b>Server bilan aloqa yo\'q (Offline).</b> ' + (TJ.userSim ? 'Oflayn sinov rejimi yoqilgan.' : (!navigator.onLine ? 'Kompyuterda internet yo\'q.' : 'Server javob bermayapti.')) + ' Ishlashda davom eting: vallar shu kompyuterda saqlanadi va aloqa tiklanganda <b>o\'zi</b> yuboriladi — hech narsa bosish shart emas.</div></div>'
      : '<div class="notice ok"><div><b>Server bilan ulangan (Online).</b> Kiritilgan har bir val darhol serverga yoziladi' + (TJ.wsOk ? ', boshqa xodimlarning o\'zgarishlari ham darhol ko\'rinadi.' : '.') + '</div></div>';
    st += '<p class="m" style="font-size:12.5px;margin:-4px 0 0">Bu belgi <b>server bilan aloqani</b> ko\'rsatadi. Internet yoki server uzilsa, 15 soniya ichida o\'zi «Offline»ga o\'tadi va sahifa tepasida qizil ogohlantirish chiqadi; aloqa tiklansa o\'zi «Online»ga qaytadi.' +
      (local ? ' <b>Hozir server shu kompyuterning o\'zida ishlayapti (' + esc2(location.host) + '), shuning uchun internet uzilsa ham aloqa bor — Online turishi to\'g\'ri.</b> Haqiqiy serverda internet uzilsa Offline bo\'ladi.' : '') + '</p>';
    var fs;
    if (!FS.supported) fs = '<p class="m" style="font-size:13px">Bu brauzer kompyuterdagi papkaga yoza olmaydi. Papka uchun kompyuterda <b>Chrome</b> yoki <b>Edge</b> ishlating.</p>';
    else if (FS.ok) fs = '<p style="font-size:13.5px;margin:0 0 8px">✓ Ulangan: <b>…\\' + esc2(FS.name) + '</b>. Ichida: <b>yuborilmagan</b> (serverga hali yetmagan), <b>yuborilgan</b> (kunlar bo\'yicha), <b>vallar_SANA.csv</b> (bugungi vallar, Excel\'da ochiladi) va <b>O\'QING.txt</b>.' + (FS.last ? ' Oxirgi yozuv: ' + hm(FS.last) + '.' : '') + '</p>' +
      '<div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn sm" onclick="TJ.fsResend()">Papkadagi yuborilmaganlarni yuborish</button><button class="btn sm ghost" onclick="TJ.fsPick()">Boshqa papka tanlash</button></div>';
    else if (FS.need) fs = '<div class="notice warn"><div>Papka <b>' + esc2(FS.name) + '</b> ulangan, brauzer qayta ochilgani uchun ruxsatni bir bosishda tasdiqlang. Chiqqan oynada <b>«Har safar ruxsat berish / Allow on every visit»</b> ni tanlasangiz, boshqa so\'ramaydi.</div></div><button class="btn p sm" onclick="TJ.fsGrant()">Papkaga ruxsat berish</button>';
    else fs = '<p class="m" style="font-size:13px;margin:0 0 8px">Har bir kompyuterda <b>bir marta</b> ulanadi. Tugmani bosing → ochilgan oynada <b>D:</b> diskini (yoki istalgan joyni) tanlang → «Выбрать папку / Select folder» → ruxsat bering. Dastur o\'sha joyda <b>perixod_fayllari</b> papkasini o\'zi ochadi.</p><button class="btn p sm" onclick="TJ.fsPick()">Papkani ulash</button>';
    if (FS.err) fs += '<p class="m" style="font-size:12px;color:var(--bad)">' + esc2(FS.err) + '</p>';
    return '<div class="mhead"><h2>Server bilan aloqa</h2><span class="sp"></span><button class="iconbtn" aria-label="Yopish" onclick="TJ.panelClose()">✕</button></div>' +
      '<div class="mbody" style="display:grid;gap:14px">' + st +
      '<div class="grid g3" style="gap:8px"><div class="card" style="padding:10px 12px"><div class="lbl">Navbatda</div><b class="num">' + q + '</b> <span class="m" style="font-size:12px">o\'zgarish (' + TJ.outbox.length + ' paket)</span></div>' +
      '<div class="card" style="padding:10px 12px"><div class="lbl">Oxirgi aloqa</div><b class="num">' + hm(TJ.lastOk) + '</b></div>' +
      '<div class="card" style="padding:10px 12px"><div class="lbl">Real vaqt</div><b>' + (TJ.wsOk ? 'ulangan' : 'yo\'q') + '</b></div></div>' +
      '<div class="row" style="gap:8px;flex-wrap:wrap"><button class="btn t sm" onclick="TJ.syncNow()"' + (q || !off ? '' : ' disabled') + '>Hozir yuborish / yangilash</button>' +
      (B.debug || TJ.userSim ? '<button class="btn sm" onclick="TJ.simToggle()" title="Faqat sinov uchun — ishlab chiqarish serverida ko\'rinmaydi">' + (TJ.userSim ? 'Oflayn sinovni o\'chirish' : 'Oflaynni sinash (test)') + '</button>' : '') +
      '<label class="btn sm ghost" style="cursor:pointer">Fayldan yuborish (.json)<input type="file" accept=".json,application/json" multiple hidden onchange="TJ.fileResend(this.files);this.value=\'\'"></label></div>' +
      '<div><div class="lbl" style="margin-bottom:6px">Kompyuterdagi papka</div>' + fs + '</div></div>';
  }
  var panelEl = null;
  function openPanel() {
    if (!panelEl) {
      panelEl = document.createElement('div');
      panelEl.className = 'modal'; panelEl.id = 'tjPanel';
      panelEl.addEventListener('click', function (e) { if (e.target === panelEl) closePanel(); });
      document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && panelEl && panelEl.parentNode) closePanel(); });
    }
    panelEl.innerHTML = '<div class="mbox" role="dialog" aria-label="Server bilan aloqa" style="width:min(620px,100%)">' + panelHTML() + '</div>';
    if (!panelEl.parentNode) document.body.appendChild(panelEl);
  }
  function closePanel() { if (panelEl && panelEl.parentNode) panelEl.parentNode.removeChild(panelEl); }
  function panelRefresh() { if (panelEl && panelEl.parentNode) openPanel(); }
  TJ.panel = openPanel; TJ.panelClose = closePanel;
  TJ.syncNow = function () { needPull = true; backoff = 0; schedule(0); setTimeout(panelRefresh, 1500); };
  TJ.simToggle = function () {
    TJ.userSim = !TJ.userSim; syncSim();
    if (!TJ.userSim) { needPull = true; schedule(0); }
    else toast('Oflayn sinov: kiritganlar qurilmada saqlanadi, sinov o\'chirilganda yuboriladi');
    render(); panelRefresh();
  };

  /* ---------- kompyuterdagi papka (Chrome/Edge: File System Access API) ---------- */
  var FS = TJ.fs = { ok: false, need: false, name: '', supported: !!(window.showDirectoryPicker && window.isSecureContext), err: '', h: null };
  function idb() {
    return new Promise(function (res, rej) {
      var r = indexedDB.open('terry-jar-fs', 1);
      r.onupgradeneeded = function () { r.result.createObjectStore('kv'); };
      r.onsuccess = function () { res(r.result); }; r.onerror = function () { rej(r.error); };
    });
  }
  function kvGet(k) { return idb().then(function (db) { return new Promise(function (res) { var g = db.transaction('kv').objectStore('kv').get(k); g.onsuccess = function () { res(g.result); }; g.onerror = function () { res(undefined); }; }); }); }
  function kvSet(k, v) { return idb().then(function (db) { return new Promise(function (res) { var tx = db.transaction('kv', 'readwrite'); tx.objectStore('kv').put(v, k); tx.oncomplete = res; tx.onerror = res; }); }); }
  function dsub(h, name) { return h.getDirectoryHandle(name, { create: true }); }
  function wfile(dh, name, text) {
    return dh.getFileHandle(name, { create: true }).then(function (fh) { return fh.createWritable(); })
      .then(function (w) { return w.write(text).then(function () { return w.close(); }); });
  }
  function fsFail(e) { FS.err = 'Papkaga yozib bo\'lmadi: ' + (e && e.message || e); console.warn('[tj fs]', e); if (e && e.name === 'NotAllowedError') { FS.ok = false; FS.need = true; } pillRefresh(); panelRefresh(); }
  function localDate(iso) { var d = iso ? new Date(iso) : new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  function opName(op) { var d = new Date(op.t || Date.now()); return localDate(op.t) + '_' + String(d.getHours()).padStart(2, '0') + '-' + String(d.getMinutes()).padStart(2, '0') + '-' + String(d.getSeconds()).padStart(2, '0') + '_' + op.op.slice(0, 8) + '.json'; }
  function valRows(op) {
    return op.ch.filter(function (c) { return c.c === 'vals' && c.d; }).map(function (c) {
      var v = c.d, cc = {}; try { cc = calc(v); } catch (e) {}
      var d = (S.designs || []).find(function (x) { return x.id === v.des; }) || {};
      return { id: v.id, kod: v.code || '', stanok: v.loom || '', sana: v.date || '', smena: v.shift || '', dizayn: d.name || '', brutto: v.brutto, tara: v.tara, sof_kg: cc.net != null ? +(+cc.net).toFixed(2) : '', dona: cc.pcs != null ? cc.pcs : (v.pcs || ''), brak: v.brak || 0, kiritgan: v.by || op.byName || '' };
    });
  }
  function opDoc(op, extra) {
    return JSON.stringify(Object.assign({ dastur: 'Terry Jar', op: op.op, by: op.by, byName: op.byName, yaratildi: op.t, vallar: valRows(op), ch: op.ch }, extra || {}), null, 1);
  }
  // kunlik vallar ro'yxati (CSV, Excel uchun): har val oxirgi holati bilan
  function vlogUpdate(op, holat) {
    var rows = valRows(op); if (!rows.length) return Promise.resolve();
    var key = 'vlog:' + localDate(op.t);
    return kvGet(key).then(function (L) {
      L = L || {};
      rows.forEach(function (r) { var o = L[r.id] || {}; L[r.id] = Object.assign(o, r, { op: op.op, holat: holat }); });
      Object.keys(L).forEach(function (id) { if (L[id].op === op.op) L[id].holat = holat; });
      return kvSet(key, L).then(function () { return L; });
    }).then(function (L) { if (FS.ok) return writeCsv(localDate(op.t), L); });
  }
  function writeCsv(day, L) {
    var H = ['Kod', 'Stanok', 'Sana', 'Smena', 'Dizayn', 'Brutto', 'Tara', 'Sof kg', 'Dona', 'Brak', 'Kiritgan', 'Holat'];
    var K2 = ['kod', 'stanok', 'sana', 'smena', 'dizayn', 'brutto', 'tara', 'sof_kg', 'dona', 'brak', 'kiritgan', 'holat'];
    var q = function (x) { x = x == null ? '' : String(x); if (typeof x === 'string' && /^\d+\.\d+$/.test(x)) x = x.replace('.', ','); return /[;"\n]/.test(x) ? '"' + x.replace(/"/g, '""') + '"' : x; };
    var rows = Object.keys(L).map(function (id) { return L[id]; }).sort(function (a, b) { return String(a.kod).localeCompare(String(b.kod), undefined, { numeric: true }); });
    var csv = '﻿' + H.join(';') + '\r\n' + rows.map(function (r) { return K2.map(function (k) { return q(r[k]); }).join(';'); }).join('\r\n') + '\r\n';
    return wfile(FS.h, 'vallar_' + day + '.csv', csv).then(function () { FS.last = new Date(); });
  }
  function fsQueued(op) {
    vlogUpdate(op, 'yuborilmagan').catch(fsFail);
    if (!FS.ok) return;
    dsub(FS.h, 'yuborilmagan').then(function (dh) { return wfile(dh, opName(op), opDoc(op, { holat: 'yuborilmagan' })); })
      .then(function () { FS.last = new Date(); }).catch(fsFail);
  }
  function fsSent(op, resp) {
    var t = new Date(), holat = 'yuborildi ' + hm(t).slice(0, 5);
    vlogUpdate(op, holat).catch(fsFail);
    if (!FS.ok) return;
    var name = opName(op);
    dsub(FS.h, 'yuborilgan').then(function (dh) { return dsub(dh, localDate(op.t)); })
      .then(function (dh) { return wfile(dh, name, opDoc(op, { holat: 'yuborildi', yuborildi: t.toISOString(), rev: resp && resp.rev })); })
      .then(function () { return dsub(FS.h, 'yuborilmagan'); })
      .then(function (dh) { return dh.removeEntry(name).catch(function () {}); })
      .then(function () { FS.last = new Date(); }).catch(fsFail);
  }
  function fsSyncPending() {
    // papka endi ulangan bo'lsa — navbatdagi barcha paketlar yuborilmagan/ ga, bugungi CSV qayta yoziladi
    TJ.outbox.forEach(function (op) { fsQueued(op); });
    kvGet('vlog:' + localDate()).then(function (L) { if (L && FS.ok) return writeCsv(localDate(), L); }).catch(fsFail);
  }
  var README_TXT = [
    'TERRY JAR — perixod fayllari (dastur o\'zi yozadi, qo\'lda o\'zgartirmang)', '',
    'vallar_SANA.csv   — shu kompyuterda o\'sha kuni kiritilgan/o\'zgartirilgan vallar. Excel\'da ochiladi.',
    '                    «Holat» ustuni: yuborilmagan / yuborildi 14:32 / serverda.',
    'yuborilmagan\\     — serverga hali yetib bormagan o\'zgarishlar (internet uzilganda shu yerda turadi).',
    '                    Aloqa tiklanganda dastur o\'zi yuboradi va faylni «yuborilgan» ga ko\'chiradi.',
    'yuborilgan\\SANA\\ — server qabul qilgan o\'zgarishlar.', '',
    'Agar brauzer xotirasi tozalanib ketsa: dasturda Online/Offline belgisini bosing →',
    '«Papkadagi yuborilmaganlarni yuborish». Oldin yetib borganlari ikki marta yozilmaydi.', ''
  ].join('\r\n');
  function fsInitFolder() {
    // ulanganda darhol tuzilma: papkalar, O'QING.txt va bugungi vallar ro'yxati
    return Promise.all([dsub(FS.h, 'yuborilmagan'), dsub(FS.h, 'yuborilgan')])
      .then(function () { return wfile(FS.h, "O'QING.txt", '\ufeff' + README_TXT); })
      .then(function () { return todayCsv(); })
      .then(function () { FS.last = new Date(); panelRefresh(); });
  }
  function todayCsv() {
    var day = localDate(), key = 'vlog:' + day;
    return kvGet(key).then(function (L) {
      L = L || {};
      (S.vals || []).forEach(function (v) {
        if (v.date !== day || (typeof BR === 'function' && v.br !== BR()) || L[v.id]) return;
        var r = valRows({ ch: [{ c: 'vals', d: v }], byName: '' })[0]; if (r) { r.holat = 'serverda'; L[v.id] = r; }
      });
      return writeCsv(day, L);
    });
  }
  function fsReady(h) { FS.h = h; FS.name = h.name; FS.ok = true; FS.need = false; FS.err = ''; fsInitFolder().catch(fsFail); fsSyncPending(); pillRefresh(); panelRefresh(); }
  TJ.fsPick = function () {
    if (!FS.supported) return;
    window.showDirectoryPicker({ id: 'terry-jar', mode: 'readwrite', startIn: 'desktop' }).then(function (h) {
      // foydalanuvchi qaysi joyni tanlasa (masalan D:), ichida perixod_fayllari ochiladi
      return (h.name === 'perixod_fayllari' ? Promise.resolve(h) : h.getDirectoryHandle('perixod_fayllari', { create: true }))
        .then(function (sub) { return kvSet('dir', sub).then(function () { fsReady(sub); toast('Papka ulandi: ' + h.name + '\\perixod_fayllari'); FS.name = h.name.replace(/\\$/, '') + '\\perixod_fayllari'; panelRefresh(); }); });
    }).catch(function (e) { if (e && e.name !== 'AbortError') fsFail(e); });
  };
  TJ.fsGrant = function () {
    if (!FS.h) return TJ.fsPick();
    FS.h.requestPermission({ mode: 'readwrite' }).then(function (p) { if (p === 'granted') fsReady(FS.h); else fsFail('ruxsat berilmadi'); }).catch(fsFail);
  };
  function resendDocs(docs, fromDir) {
    var known = {}; TJ.outbox.forEach(function (o) { known[o.op] = 1; });
    var list = docs.filter(function (x) { return x.doc && x.doc.op && Array.isArray(x.doc.ch) && !known[x.doc.op]; });
    if (!list.length) { toast('Yuboriladigan fayl topilmadi (navbatdagilar o\'zi yuboriladi)'); return Promise.resolve(); }
    var n = 0, chain = Promise.resolve();
    list.forEach(function (x) {
      chain = chain.then(function () {
        var op = { op: x.doc.op, by: x.doc.by, byName: x.doc.byName, t: x.doc.yaratildi, ch: x.doc.ch };
        return api('push', op).then(function (resp) {
          n++;
          (resp.res || []).forEach(function (r) { if (Object.prototype.hasOwnProperty.call(r, 'd') && !isDirty(r.c, r.k, r.id)) applyRec(r.c, r.k, r.id, r.d); });
          if (fromDir) fsSent(op, resp);
        });
      });
    });
    return chain.then(function () { toast(n + ' ta fayl serverga yuborildi (oldin yetib borganlari takrorlanmaydi)'); needPull = true; refreshUI(); schedule(0); panelRefresh(); })
      .catch(function (e) { toast('Yuborib bo\'lmadi: server bilan aloqa yo\'q'); console.warn(e); });
  }
  TJ.fileResend = function (files) {
    var arr = Array.prototype.slice.call(files || []);
    Promise.all(arr.map(function (f) { return f.text().then(function (t) { try { return { doc: JSON.parse(t) }; } catch (e) { return {}; } }); }))
      .then(function (docs) { return resendDocs(docs, false); });
  };
  TJ.fsResend = function () {
    if (!FS.ok) return;
    dsub(FS.h, 'yuborilmagan').then(function (dh) {
      var out = [], it = dh.values();
      function next() {
        return it.next().then(function (r) {
          if (r.done) return out;
          if (r.value.kind === 'file' && /\.json$/.test(r.value.name)) {
            return r.value.getFile().then(function (f) { return f.text(); }).then(function (t) { try { out.push({ doc: JSON.parse(t) }); } catch (e) {} return next(); });
          }
          return next();
        });
      }
      return next();
    }).then(function (docs) { return resendDocs(docs, true); }).catch(fsFail);
  };
  TJ._fsUse = fsReady; // avtotestlar uchun (brauzer ichki papkasi bilan)
  function fsInit() {
    if (!FS.supported) return;
    kvGet('dir').then(function (h) {
      if (!h) return;
      FS.h = h; FS.name = h.name;
      return h.queryPermission({ mode: 'readwrite' }).then(function (p) { if (p === 'granted') fsReady(h); else { FS.need = true; pillRefresh(); } });
    }).catch(function (e) { console.warn('[tj fs init]', e); });
  }

  /* ---------- ishga tushirish ---------- */
  TJ.last = snap();
  if (B.useLocal) {
    // qurilmada yuborilmagan o'zgarishlar bilan ochildi: oxirgi tasdiqlangan holat noma'lum,
    // shuning uchun navbat yuborilgach serverdan to'liq holat olinadi
    TJ.rev = Math.min(TJ.rev, lget(K + '_rev', 0));
  }
  syncSim();
  fsInit();
  (function () { var st = document.createElement('style'); st.textContent = 'body.tj-off{padding-top:40px}body.tj-off .side,body.tj-off aside.nav{top:40px}'; document.head.appendChild(st); })();
  setTimeout(barRefresh, 0);
  if (B.fresh && typeof me !== 'undefined' && me) { try { logA('Tizimga kirdi'); checkAll(); save(); render(); } catch (e) {} }
  connectWS();
  schedule(0);
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register('/sw.js').catch(function () {});
  }

  /* ---------- kirish oynasi (server rejimi): demodagi dizayn, xodimlar ro'yxati va tezkor kirishsiz ---------- */
  function anonLogin(B) {
    var e = function (t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
    window.renderLogin = function () {
      try { stop3D('hero'); stop3D('login'); } catch (x) {}
      var eye = typeof pwBtn === 'function' ? pwBtn('lp') : '';
      document.getElementById('root').innerHTML =
        '<div class="login"><canvas id="loginCanvas" aria-hidden="true"></canvas><div class="lpanel">' +
        '<div class="lbrand"><div class="pl8"><img class="e" src="' + LOGO.emb + '" alt="Terry Jar Textile emblemasi"><img class="w" src="' + LOGO.jar + '" alt="Terry Jar Textile"></div>' +
        '<p>Jar filiali uchun perixod, rasxod va rangxona hisobi. Har bir xodim faqat o\'z ishini ko\'radi, ruxsatlarni rahbar beradi.</p></div>' +
        '<form class="lcard" method="post" action="' + e(B.action) + '" onsubmit="this.querySelector(\'button.p\').disabled=true">' +
        '<h2 style="font-size:20px">Tizimga kirish</h2>' +
        '<input type="hidden" name="csrfmiddlewaretoken" value="' + e(B.csrf) + '"><input type="hidden" name="next" value="' + e(B.next) + '">' +
        '<div class="fld"><label class="lbl" for="lu">Login</label><input class="in" id="lu" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required value="' + e(B.username) + '" placeholder="masalan: ism.familiya"></div>' +
        '<div class="fld"><label class="lbl" for="lp">Parol</label><div class="pwf"><input class="in" id="lp" name="password" type="password" autocomplete="current-password" required placeholder="••••••••">' + eye + '</div></div>' +
        '<div class="err" id="le" role="alert">' + (B.error ? 'Login yoki parol noto\'g\'ri. Qaytadan kiriting.' : '') + '</div>' +
        '<button class="btn p" style="justify-content:center;padding:11px">Kirish</button>' +
        '<div class="m" style="font-size:12px">Parolni unutsangiz administratorga murojaat qiling. 5 marta xato kiritilsa, kirish 15 daqiqaga bloklanadi.</div>' +
        '</form>' +
        '<button class="btn ghost" style="color:#fff;align-self:flex-start" onclick="ui.modal={k:\'about\'};renderLogin()">' + ic('info') + ' Dastur haqida</button>' +
        '</div><div></div></div>' + (ui.modal ? modalHTML() : '');
      try { mount3D('login', document.getElementById('loginCanvas'), { rolls: 7, cotton: 6 }); } catch (x) {}
      var h = document.getElementById('tjHide'); if (h) h.remove();
      var f = document.getElementById(B.username ? 'lp' : 'lu'); if (f && !ui.modal) f.focus();
    };
    window.logout = function () { location.href = B.next || '/app/'; };
    try { me = null; ui.modal = null; renderLogin(); } catch (x) { console.error(x); }
  }
})();

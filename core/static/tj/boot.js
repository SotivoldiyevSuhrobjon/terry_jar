/* Terry Jar — server rejimi: demo skriptidan OLDIN ishlaydi.
   1) Serverdagi holatni demo o'qiydigan joyga (localStorage) qo'yadi — demo kodi o'zgarmaydi.
   2) Kirgan xodimni demo "me" sifatida tanlaydi.
   3) Demo saqlaganda (localStorage.setItem) sinxronlashni uyg'otadi. */
(function () {
  'use strict';
  var B = window.TJ_BOOT, K = B.key, ls = window.localStorage;
  if (B.anon) {
    // Kirish sahifasi: demo faqat oynani chizadi. Qurilmadagi ma'lumot va navbatga (outbox) tegilmaydi —
    // demo yaratadigan namunaviy holat faqat xotirada qoladi.
    var g0 = Storage.prototype.getItem, s0 = Storage.prototype.setItem;
    var guard = function (k) { return this === ls && (k === K || k === K + '_ui'); };
    Storage.prototype.getItem = function (k) { return guard.call(this, k) ? null : g0.call(this, k); };
    Storage.prototype.setItem = function (k, v) { if (!guard.call(this, k)) s0.call(this, k, v); };
    // demo o'zining (namunaviy xodimlar ro'yxatli) kirish oynasini chizib ulgurmasin
    document.write('<style id="tjHide">#root{visibility:hidden}</style>');
    return;
  }
  function get(k, d) { try { var v = ls.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
  function set(k, v) { try { Storage.prototype.setItem.call(ls, k, JSON.stringify(v)); return true; } catch (e) { return false; } }

  var outbox = get(K + '_outbox', []);
  var local = outbox.length ? get(K, null) : null;
  B.useLocal = !!(local && local.v === B.v);
  if (B.useLocal) {
    // Yuborilmagan o'zgarishlar bor (internet uzilgan edi) — qurilmadagi holat bilan ochiladi,
    // avval ular yuboriladi, keyin serverdagi yangiliklar olinadi.
    B.rev = Math.min(B.rev, get(K + '_rev', 0));
  } else {
    B.state.v = B.v;
    if (!set(K, B.state)) {
      try { ls.removeItem(K + '_snap'); } catch (e) {}
      set(K, B.state);
    }
    set(K + '_rev', B.rev);
    try { ls.removeItem(K + '_outbox'); } catch (e) {}
  }
  B.state = null;
  var ui = get(K + '_ui', {}) || {};
  if (ui.u !== B.me || B.fresh) {
    // yangi kirish: xodim o'z bo'limida ochiladi (demo login() dagidek)
    var tab = { perixod: 'per', rasxod: 'rx', dye: 'dye', master: 'dav', sklad: 'skl' }[B.role] || 'home';
    ui = { u: B.me, theme: ui.theme || '', tab: tab, br: B.br && B.br !== '*' ? B.br : (ui.br || 'jar') };
  }
  set(K + '_ui', ui);

  var orig = Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) {
    orig.call(this, k, v);
    if (this === ls && k === K && window.__tjDirty) window.__tjDirty();
  };
})();

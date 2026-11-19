// Запис екрана справжнього сайту (ZAVDANNYA-129): накладка тексту (стилі stsena.css) і керування сайтом у рамці.
// Кадр ставить window.kadrZapysu(t); дії над сайтом викликає video/vau/zapys_saitu.py. Час сайту — віртуальний:
// init-скрипт підміняє performance.now, Date.now, requestAnimationFrame і таймери, тож карта й переходи йдуть рівно, кадр за кадром.
(function () {
  'use strict';
  var S = null;
  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function lerp(a, b, k) { return a + (b - a) * k; }
  var oo = function (k) { return 1 - Math.pow(1 - k, 5); }, back = function (k) { var c = 1.70158, c3 = c + 1; return 1 + c3 * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2); };
  var Y = { verkh: 330, tsentr: 800, niz: 1200 };
  var LOGO = '<svg class="logo" viewBox="0 0 48 48"><path class="z1" d="M24 2 43 13v22L24 46 5 35V13z"/><path class="z2" d="M24 15 32 19.5v9L24 33l-8-4.5v-9z"/></svg>';
  function chyslo(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
  function vidm(n, f) { n = Math.abs(Math.round(n)); var o = n % 10, d = n % 100; return o === 1 && d !== 11 ? f[0] : (o >= 2 && o <= 4 && !(d >= 12 && d <= 14)) ? f[1] : f[2]; }

  function zbuduvaty(it) {
    var el = document.createElement('div');
    el.className = 't ' + it.styl + (it.c ? ' c' : '') + (it.klas ? ' ' + it.klas : '');
    el.style.top = (typeof it.y === 'number' ? it.y : Y[it.y || 'verkh']) + 'px';
    if (it.styl === 'baner') el.innerHTML = LOGO + '<div><b>' + it.zag + '</b><span>' + (it.knopka || '') + '</span></div>';
    else if (it.styl === 'lich') el.innerHTML = '<span class="n"></span><small>' + (it.pidpys || '') + '</small>';
    else el.innerHTML = String(it.tekst).split('\n').map(function (r) {
      return r.replace(/\*([^*]+)\*/g, '<span class="w a">$1</span>');
    }).join('<br>');
    document.getElementById('tekst').appendChild(el);
    it.el = el;
  }
  function onovyty(it, t) {
    var el = it.el;
    if (t < it.t0 || t > it.t1) { el.style.opacity = 0; return; }
    var odrazu = it.t0 <= 0.0001 || it.odrazu;
    var a = odrazu ? 1 : clamp((t - it.t0) / 0.22, 0, 1), z = clamp((it.t1 - t) / 0.18, 0, 1);
    el.style.opacity = Math.min(a, z);
    if (it.styl === 'baner') el.style.transform = 'translateY(' + lerp(220, 0, back(a)) + 'px)';
    else el.style.transform = 'scale(' + lerp(1.25, 1, oo(a)) + ')';
    el.style.transformOrigin = 'left center';
    if (it.styl === 'lich') {
      var v = lerp(it.vid || 0, it.do, oo(clamp((t - it.t0) / (it.tryv || 1.2), 0, 1)));
      el.querySelector('.n').textContent = chyslo(v);
      if (it.formy) el.querySelector('small').textContent = it.pidpys.replace('{f}', vidm(v, it.formy));
    }
  }

  window.zapusk = function (s) {
    S = s;
    var dz = document.getElementById('dzherelo');
    dz.innerHTML = '<span>' + S.dzherelo + '</span>' + (S.holos_poznaka ? '<span class="hp">' + S.holos_poznaka + '</span>' : '');
    S.tekst.forEach(zbuduvaty);
    return document.fonts.ready.then(function () { return true; });
  };
  // палець: кружечок у координатах кадру 1080×1920
  window.kadrZapysu = function (t) {
    S.tekst.forEach(function (it) { onovyty(it, t); });
    var p = document.getElementById('palets'), op = 0, x = 0, y = 0;
    (S.paltsi || []).forEach(function (f) {
      var a = t - f.t;
      if (a > -0.35 && a < 0.45) { x = f.x; y = f.y; op = a < 0 ? clamp(1 + a / 0.35, 0, 1) : clamp(1 - a / 0.45, 0, 1); p.style.transform = 'scale(' + (a < 0 ? 1.2 : lerp(0.85, 1.4, a / 0.45)) + ')'; }
    });
    p.style.left = x + 'px'; p.style.top = y + 'px'; p.style.opacity = op;
  };
  window.dodatyPalets = function (f) { (S.paltsi = S.paltsi || []).push(f); };
  // координати елемента сайту → кадр 1080×1920 (рамка: 70, 272 у вікні 540×960)
  window.dePalets = function (sel) {
    var f = document.getElementById('sait'), el = f.contentDocument.querySelector(sel);
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return [(70 + r.left + r.width / 2) * 2, (272 + r.top + r.height / 2) * 2];
  };
})();

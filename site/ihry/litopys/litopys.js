// «Літопис міста» — гра (ZAVDANNYA-140; ZAVDANNYA-141: соковитість, темп, у карті). Логіка й числа — litopys-yadro.js;
// тут — панель, шари на карті, звук і збереження на пристрої. Вигляд — docs/STYL.md («зовні гра»: клавіші, приціл, рух
// для всіх); без емодзі, без червоного, без випадковості.
//
// Один модуль на два місця: панель «Ігри» карти сайту (site/ihry/ihry.js) і окрема перевірочна сторінка (index.html).
//   MvLitopys.zapustyty({ korin, karta, dani, panel, tost, bali, vlasnyiKlik }) → { klik(lngLat), zupynyty() }
//     korin — куди малювати гру; karta — карта MapLibre (може бути null); dani — адреса litopys.json;
//     panel — елемент, що закриває карту (щоб переліт не ховав вулицю під панель); tost(t, мс) — повідомлення;
//     bali(очки) → нараховані бали спільної скарбнички ігор (або без балів); vlasnyiKlik — гра сама слухає дотики карти;
//     prykhovaty — початки id шарів карти, які на час гри ховаються (у сайті — соти «k-»); ochky — очки за задачі дня.
// Прогрес — на пристрої (localStorage «mv-ihry-litopys»: «Скинути» в налаштуваннях ігор стирає й його).
// Для перевірки й знімків: ?zsuv=<годин> — годинник гри вперед; ?novyi=1 — почати з нуля (стерти прогрес на пристрої).
(function (korin) {
  'use strict';
  var Y = korin.MvLitopysYadro;
  var q = new URLSearchParams(location.search);
  var ZSUV = (Number(q.get('zsuv')) || 0) * 3600e3;
  function teper() { return Date.now() + ZSUV; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function slovo(n, f) { n = Math.abs(Math.floor(n)) % 100; var d = n % 10; return (n > 10 && n < 20) ? f[2] : d === 1 ? f[0] : (d >= 2 && d <= 4) ? f[1] : f[2]; }
  var STOR = ['сторінка', 'сторінки', 'сторінок'];
  var VULS = ['вулиця', 'вулиці', 'вулиць'];
  var PODS = ['подія', 'події', 'подій'];
  var ch = function (n) { return Y.chyslo(n); };
  var POVAZHNO = 'Подію підтверджено рішенням суду. Подробиць про потерпілих гра не показує.';

  // ---------------------------------------------------------------- звук (вимикається; без файлів — синтез у браузері)
  // Короткі тихі тони; висота дотику росте з темпом дотиків (детерміновано, без випадку). Події з потерпілими — без «фанфар».
  var ZV = { ctx: null, uvimk: true, kliuch: 'mv-ihry-litopys-zvuk' };
  try { ZV.uvimk = localStorage.getItem(ZV.kliuch) !== 'ni'; } catch (e) { /* без пам'яті — увімкнено */ }
  function audio() {
    if (!ZV.uvimk) return null;
    if (!ZV.ctx) { var A = korin.AudioContext || korin.webkitAudioContext; if (!A) return null; try { ZV.ctx = new A(); } catch (e) { return null; } }
    if (ZV.ctx.state === 'suspended') ZV.ctx.resume();
    return ZV.ctx;
  }
  function ton(c, f, pochatok, tryv, typ, guchn) {
    var o = c.createOscillator(), g = c.createGain(), t = c.currentTime + pochatok;
    o.type = typ || 'sine'; o.frequency.setValueAtTime(f, t);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(guchn || 0.06, t + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t + tryv);
    o.connect(g); g.connect(c.destination); o.start(t); o.stop(t + tryv + 0.02);
  }
  var NOTY = {
    dotyk: function (c, temp) { ton(c, 440 * Math.pow(2, Math.min(temp || 0, 12) / 24), 0, 0.06, 'triangle', 0.05); },
    kup: function (c) { ton(c, 587, 0, 0.08, 'triangle'); ton(c, 880, 0.06, 0.12, 'triangle'); },
    vulytsia: function (c) { [523, 659, 784, 1047].forEach(function (f, i) { ton(c, f, i * 0.07, 0.22, 'sine', 0.07); }); },
    tykho: function (c) { ton(c, 392, 0, 0.3, 'sine', 0.04); },
    karta: function (c) { ton(c, 1175, 0, 0.5, 'sine', 0.05); ton(c, 1568, 0.09, 0.6, 'sine', 0.04); },
    rayon: function (c) { [392, 523, 659, 784, 1047].forEach(function (f, i) { ton(c, f, i * 0.09, 0.3, 'triangle', 0.05); }); },
    tak: function (c) { ton(c, 659, 0, 0.12, 'triangle'); ton(c, 988, 0.1, 0.25, 'triangle'); },
    ni: function (c) { ton(c, 330, 0, 0.18, 'sine', 0.05); ton(c, 262, 0.12, 0.25, 'sine', 0.04); },
    poshta: function (c) { ton(c, 587, 0, 0.15, 'sine'); ton(c, 740, 0.12, 0.25, 'sine'); },
    ne_mozhna: function (c) { ton(c, 196, 0, 0.09, 'triangle', 0.04); }
  };
  function zvuk(nazva, arg) { var c = audio(); if (c && NOTY[nazva]) NOTY[nazva](c, arg); }
  function vibro(ms) { if (ZV.uvimk && navigator.vibrate) { try { navigator.vibrate(ms); } catch (e) { /* немає */ } } }

  // ---------------------------------------------------------------- гра
  function zapustyty(o) {
    var KLIUCH = o.kliuch || 'mv-ihry-litopys';
    if (q.get('novyi') === '1') { try { localStorage.removeItem(KLIUCH); } catch (e) { /* без пам'яті */ } }
    var karta = o.karta || null;
    var D = null, S = null, VUL = {};
    var vkladka = 'chytaty', obrana = null, zhyve = true;
    var svizhe = {};           // що щойно сталося — анімується один раз (вулиця, картки, район, помічник, задача)
    var taimery = [], MARKERY = [];

    o.korin.innerHTML = '<div class="lit"><div class="lit-shapka"><div class="lit-verkh">' +
      '<div class="lit-lich"><b data-lich="storinky">0</b><span>сторінок</span><small><span data-lich="za_sek">0</span> за секунду</small></div>' +
      '<div class="lit-lich lit-lich--mal" title="Серія днів"><b data-lich="seriia">0</b><span>серія</span></div>' +
      '<button type="button" class="lit-zvuk klavisha" data-lit="zvuk"></button></div>' +
      '<div class="lit-vkladky" role="tablist">' +
      '<button type="button" role="tab" data-v="chytaty" aria-selected="true">Читати</button><button type="button" role="tab" data-v="vulytsi" aria-selected="false">Вулиці</button>' +
      '<button type="button" role="tab" data-v="karty" aria-selected="false">Картки</button><button type="button" role="tab" data-v="den" aria-selected="false">День</button></div></div>' +
      '<div class="lit-vmist"></div><div class="lit-tost" role="status" aria-live="polite"></div></div>';
    var EL = o.korin.querySelector('.lit');
    var VM = EL.querySelector('.lit-vmist');
    function $(s) { return EL.querySelector(s); }
    function zvukKnopka() {
      var b = $('[data-lit="zvuk"]'); b.setAttribute('aria-pressed', ZV.uvimk ? 'true' : 'false');
      b.textContent = ZV.uvimk ? 'Звук' : 'Без звуку'; b.title = ZV.uvimk ? 'Вимкнути звук' : 'Увімкнути звук';
    }
    zvukKnopka();

    var tostT = 0;
    function tost(t, ms) {
      if (o.tost) { o.tost(t, ms); return; }
      var el = $('.lit-tost'); el.textContent = t; el.classList.add('vyd'); clearTimeout(tostT);
      tostT = setTimeout(function () { el.classList.remove('vyd'); }, ms || 3200);
    }
    function zberehty() { if (!S) return; try { localStorage.setItem(KLIUCH, JSON.stringify(S)); } catch (e) { /* приватний режим */ } }
    function prochytaty() { try { return JSON.parse(localStorage.getItem(KLIUCH)); } catch (e) { return null; } }

    // ---------- лічильники, що біжать: показане число наздоганяє справжнє ----------
    var LICH = { storinky: { pokaz: 0, tsil: 0 } };
    function lich(nazva, n) { var l = LICH[nazva] || (LICH[nazva] = { pokaz: n, tsil: n }); l.tsil = n; }
    var ostanniiKadr = 0;
    function kadr(t) {
      if (!zhyve) return;
      var dt = Math.min(0.1, (t - (ostanniiKadr || t)) / 1000); ostanniiKadr = t;
      Object.keys(LICH).forEach(function (k) {
        var l = LICH[k], r = l.tsil - l.pokaz;
        l.pokaz = Math.abs(r) < 0.5 ? l.tsil : l.pokaz + r * Math.min(1, dt * 9);
        // «за секунду» до 10 — з десятими (читач дає 0,2 — «0» вводить в оману)
        var tekst = k === 'za_sek' && l.pokaz > 0 && l.pokaz < 10 ? (Math.round(l.pokaz * 10) / 10).toFixed(1).replace('.', ',') : ch(l.pokaz);
        EL.querySelectorAll('[data-lich="' + k + '"]').forEach(function (e) { e.textContent = tekst; });
      });
      // смуга до наступної вулиці — плавно, за показаним (а не стрибком)
      var sm = EL.querySelector('.lit-smuha i');
      if (sm && S) { var tv = Y.tsinaVulytsi(S); sm.style.width = Math.min(100, 100 * LICH.storinky.pokaz / tv).toFixed(2) + '%'; }
      requestAnimationFrame(kadr);
    }
    // Числа на щойно відкритій картці вулиці — від нуля до справжнього (раз).
    function pidrakhunok(el) {
      var tsil = Number(el.getAttribute('data-do')), pochatok = performance.now();
      (function krok(t) {
        var k = Math.min(1, (t - pochatok) / 700); k = 1 - Math.pow(1 - k, 3);
        el.textContent = ch(tsil * k);
        if (k < 1 && zhyve) requestAnimationFrame(krok);
      })(pochatok);
    }

    // ---------- дані ----------
    fetch(o.dani, { credentials: 'omit' }).then(function (v) { if (!v.ok) throw new Error(v.status); return v.json(); })
      .then(start).catch(function () {
        VM.innerHTML = '<h2>Немає даних гри</h2><p class="lit-tykho">Файл літопису не завантажився. Зберіть його: <code>python site/ihry/litopys/litopys.py --baza events-&lt;дата&gt;.db --koloda koloda-&lt;дата&gt;.json</code>.</p>';
      });

    function start(dani) {
      if (!zhyve) return;
      D = dani;
      D.vulytsi = D.vulytsi.map(function (v) { var x = { slug: v[0], nazva: v[1], rayon: v[2], n: v[3], hrupa: v[4], lat: v[5], lon: v[6], podii: v[7] }; VUL[x.slug] = x; return x; });
      D.uKolodi = {}; Object.keys(D.podii).forEach(function (id) { D.uKolodi[D.podii[id][0]] = 1; });
      S = Y.pryniaty(prochytaty(), teper());
      shary();
      if (!S) vybirRayonu(); else povernennia(true);
      taimery.push(setInterval(tik, 250), setInterval(zberehty, 5000));
      requestAnimationFrame(kadr);
    }

    // Повернення після перерви: «поки вас не було…» і «Пошта архіву».
    function povernennia(pershe) {
      if (!S) return;
      var vid = S.chas, r = Y.plyn(S, D.vydy, teper());
      var t = [];
      if (r.sekund > 120 && r.storinok >= 1) {
        var hod = Math.round((teper() - vid) / 36e5 * 10) / 10;
        t.push('Поки вас не було (' + String(hod).replace('.', ',') + ' год), помічники прочитали ' + ch(r.storinok) + ' ' + slovo(r.storinok, STOR) +
          (r.obrizano ? ' — більше ' + Y.N.offlain_hodyn + ' годин вони без вас не читають' : '') + '.');
      }
      var pt = Y.poshta(S, teper());
      if (pt > 0) { t.push('Пошта архіву: ' + ch(pt) + ' ' + slovo(pt, STOR) + ' — вистачить на ' + Y.N.poshta_vulyts + ' наступні вулиці.'); zvuk('poshta'); }
      if (t.length) tost(t.join(' '), 7000);
      Y.den(S, teper());
      if (pershe) { LICH.storinky.pokaz = 0; letityDoRayonu(S.rayony, 0); }
      lich('storinky', S.storinky);
      malyuvaty(true);
    }

    function vybirRayonu() {
      var r = Object.keys(D.rayony).sort(function (a, b) { return a.localeCompare(b, 'uk'); });
      vkladka = 'start';
      VM.innerHTML = '<div class="lit-start"><h2>Де ви живете?</h2>' +
        '<p class="lit-tykho">Літопис починається з вашого району. Торкайтеся «Прочитати сторінку», наймайте помічників і відкривайте вулиці — кожна з числами й подіями, як їх описав суд. Інші райони відкриються згодом. Район можна обрати й дотиком на карті.</p>' +
        '<div class="lit-rayony">' + r.map(function (x) { return '<button type="button" class="klavisha" data-rayon-start="' + esc(x) + '">' + esc(x) + '</button>'; }).join('') + '</div>' +
        '<p class="lit-tykho lit-vidstup">Прогрес — лише на цьому пристрої. Гра нічого не продає.</p></div>';
      EL.classList.add('lit--start');
      letityDoRayonu(Object.keys(D.rayony), 0);
      onovytyKartu();
    }
    function pochaty(rayon) {
      S = Y.novyi(teper(), rayon);
      Y.den(S, teper()); Y.poshta(S, teper());
      EL.classList.remove('lit--start'); vkladka = 'chytaty';
      svizhe.rayon = rayon; zvuk('rayon'); vibro(15);
      zberehty();
      letityDoRayonu([rayon], 1200);
      setTimeout(function () { spalakhRayonu(rayon); }, 900);
      tost('Торкайтеся «Прочитати сторінку». Перша вулиця — ' + Y.tsinaVulytsi(S) + ' сторінок.', 4500);
      lich('storinky', 0);
      perekliuchyty('chytaty');
    }

    // ---------------------------------------------------------------- карта
    function zminna(n) { return getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim(); }
    function kolory() {
      var k = {};
      ['ground', 'surface', 'accent', 'mezha', 'line-strong', 'pk-2', 'karta-za-mezhamy', 'karta-tlo'].forEach(function (n) { k[n] = zminna(n); });
      k.zakryto = k['karta-za-mezhamy'] || k['karta-tlo'] || k.ground;
      return k;
    }
    function porozhnio() { return { type: 'FeatureCollection', features: [] }; }
    var SHARY = ['lit-rayony-zakryti', 'lit-rayony-vidkryti', 'lit-rayony-mezha', 'lit-vulytsi-zakryti', 'lit-vulytsi-oreol', 'lit-vulytsi-vidkryti'];
    var znimokKarty = '';
    var chekaie = false;
    function shary() {
      if (!karta || !zhyve) return;
      if (!karta.isStyleLoaded()) { if (!chekaie) { chekaie = true; karta.once('idle', function () { chekaie = false; shary(); }); } return; }
      if (karta.getSource('lit-vulytsi')) return;
      var k = kolory();
      karta.addSource('lit-rayony', { type: 'geojson', data: porozhnio() });
      karta.addSource('lit-vulytsi', { type: 'geojson', data: porozhnio() });
      // Закриті райони притінені; відкриті — легка вуаль і межа accent. Колір — стан гри, а не «небезпека».
      karta.addLayer({ id: 'lit-rayony-zakryti', type: 'fill', source: 'lit-rayony', filter: ['==', ['get', 'v'], 0], paint: { 'fill-color': k.zakryto, 'fill-opacity': 0.72 } });
      karta.addLayer({ id: 'lit-rayony-vidkryti', type: 'fill', source: 'lit-rayony', filter: ['==', ['get', 'v'], 1], paint: { 'fill-color': k.surface, 'fill-opacity': 0.35 } });
      karta.addLayer({ id: 'lit-rayony-mezha', type: 'line', source: 'lit-rayony', paint: { 'line-color': ['case', ['==', ['get', 'v'], 1], k.accent, k['line-strong']], 'line-width': ['case', ['==', ['get', 'v'], 1], 2, 1] } });
      // Закриті вулиці: коли сторінок досить — обведені м'ятним (можна відкрити), більші.
      karta.addLayer({ id: 'lit-vulytsi-zakryti', type: 'circle', source: 'lit-vulytsi', filter: ['==', ['get', 'v'], 0], paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, ['case', ['==', ['get', 'm'], 1], 3.5, 2.5], 14, ['case', ['==', ['get', 'm'], 1], 8, 6]],
        'circle-color': k.surface, 'circle-stroke-color': ['case', ['==', ['get', 'm'], 1], k['pk-2'], k.mezha], 'circle-stroke-width': ['case', ['==', ['get', 'm'], 1], 2.5, 1.5] } });
      karta.addLayer({ id: 'lit-vulytsi-oreol', type: 'circle', source: 'lit-vulytsi', filter: ['==', ['get', 'v'], 1], paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, ['+', 5, ['*', 6, ['get', 'shchil']]], 14, ['+', 12, ['*', 14, ['get', 'shchil']]]], 'circle-color': k.accent, 'circle-opacity': 0.18 } });
      karta.addLayer({ id: 'lit-vulytsi-vidkryti', type: 'circle', source: 'lit-vulytsi', filter: ['==', ['get', 'v'], 1], paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, ['+', 3, ['*', 3, ['get', 'shchil']]], 14, ['+', 6, ['*', 6, ['get', 'shchil']]]], 'circle-color': k.accent, 'circle-stroke-color': k.surface, 'circle-stroke-width': 1.5 } });
      znimokKarty = '';
      tyshaKarty(true);
      onovytyKartu();
    }
    // Поки йде гра, власні шари карти (у сайті — соти й стовпчики, «k-…») сховані: на карті лише літопис. Після гри — назад.
    function tyshaKarty(tak) {
      if (!karta || !o.prykhovaty || !karta.style) return;
      (karta.getStyle().layers || []).forEach(function (l) {
        if (!o.prykhovaty.some(function (p) { return l.id.indexOf(p) === 0; })) return;
        karta.setLayoutProperty(l.id, 'visibility', tak ? 'none' : 'visible');
      });
    }
    function prybratyShary() {
      if (!karta || !karta.style) return;
      SHARY.forEach(function (id) { if (karta.getLayer(id)) karta.removeLayer(id); });
      ['lit-rayony', 'lit-vulytsi'].forEach(function (id) { if (karta.getSource(id)) karta.removeSource(id); });
    }
    // Тема змінилась або карта перемалювала стиль (день/ніч сайту) — шари з новими кольорами.
    function pryTemi() { setTimeout(function () { if (!zhyve) return; prybratyShary(); shary(); pryts(); }, 80); }
    // Карта сайту міняє стиль трохи згодом після події теми (setStyle) — шари гри зникають; повертаємо, щойно стиль готовий.
    function pryStyli() { if (zhyve && karta && karta.style && !karta.getSource('lit-vulytsi')) { shary(); pryts(); } }
    document.addEventListener('mv-tema', pryTemi);
    if (karta) karta.on('styledata', pryStyli);
    var smTema = korin.matchMedia ? korin.matchMedia('(prefers-color-scheme: dark)') : null;
    if (smTema && smTema.addEventListener) smTema.addEventListener('change', pryTemi);

    function onovytyKartu() {
      if (!karta || !D || !karta.getSource('lit-vulytsi')) return;
      var vidkr = {}, rayony = S ? S.rayony : [], mozhna = S && S.storinky >= Y.tsinaVulytsi(S) ? 1 : 0;
      if (S) S.vulytsi.forEach(function (s) { vidkr[s] = 1; });
      var kl = (S ? S.vulytsi.length : -1) + '|' + rayony.join(',') + '|' + mozhna;
      if (kl === znimokKarty) return; znimokKarty = kl;
      var maks = 1; D.vulytsi.forEach(function (v) { if (v.n > maks) maks = v.n; });
      var f = [];
      D.vulytsi.forEach(function (v) {
        if (rayony.indexOf(v.rayon) < 0) return;
        f.push({ type: 'Feature', properties: { slug: v.slug, v: vidkr[v.slug] ? 1 : 0, m: vidkr[v.slug] ? 0 : mozhna, shchil: Math.sqrt(v.n / maks) }, geometry: { type: 'Point', coordinates: [v.lon, v.lat] } });
      });
      karta.getSource('lit-vulytsi').setData({ type: 'FeatureCollection', features: f });
      var r = [];
      Object.keys(D.mezhi || {}).forEach(function (n) {
        r.push({ type: 'Feature', properties: { nazva: n, v: rayony.indexOf(n) >= 0 ? 1 : 0 }, geometry: { type: 'MultiPolygon', coordinates: D.mezhi[n].map(function (pl) { return [pl.concat([pl[0]])]; }) } });
      });
      karta.getSource('lit-rayony').setData({ type: 'FeatureCollection', features: r });
    }

    // Межа щойно відкритого району «спалахує» (товщає й повертається) — 1,2 с.
    function spalakhRayonu(nazva) {
      if (!karta || !karta.getLayer('lit-rayony-mezha')) return;
      var t0 = performance.now();
      (function krok(t) {
        if (!zhyve || !karta.getLayer('lit-rayony-mezha')) return;
        var k = Math.min(1, (t - t0) / 1200), w = 2 + 6 * Math.sin(Math.PI * k);
        karta.setPaintProperty('lit-rayony-mezha', 'line-width', ['case', ['==', ['get', 'nazva'], nazva], w, ['==', ['get', 'v'], 1], 2, 1]);
        if (k < 1) requestAnimationFrame(krok);
        else karta.setPaintProperty('lit-rayony-mezha', 'line-width', ['case', ['==', ['get', 'v'], 1], 2, 1]);
      })(t0);
    }
    function mitka(lat, lon, klas, html, ms) {
      if (!karta || !korin.maplibregl) return null;
      var el = document.createElement('div'); el.className = klas; el.innerHTML = html || '';
      var m = new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([lon, lat]).addTo(karta);
      if (ms) setTimeout(function () { m.remove(); }, ms); else MARKERY.push(m);
      return m;
    }
    // «Приціл» на обраній вулиці (як виділена сота сайту): кутики кольору vyd.
    var PRYTS = null;
    function pryts() {
      if (PRYTS) { PRYTS.remove(); PRYTS = null; }
      var v = obrana && VUL[obrana]; if (!v || !zhyve) return;
      PRYTS = mitka(v.lat, v.lon, 'lit-pryts', '<b><i></i><i></i><i></i><i></i></b>');
    }
    function spalakh(v) { mitka(v.lat, v.lon, 'lit-spalakh', '<i></i><i></i>', 1600); }

    function vidstup() {
      var p = { top: 70, bottom: 40, left: 40, right: 40 };
      if (!karta || !o.panel) return p;
      var k = karta.getContainer().getBoundingClientRect(), r = o.panel.getBoundingClientRect();
      if (!r.width || !r.height) return p;
      if (r.width < k.width * 0.6) p.right = Math.max(40, k.right - r.left + 24);
      else p.bottom = Math.max(40, k.bottom - r.top + 24);
      return p;
    }
    function letityDoRayonu(rayony, ms) {
      if (!karta || !korin.maplibregl) return;
      var vs = D.vulytsi.filter(function (v) { return rayony.indexOf(v.rayon) >= 0; });
      if (!vs.length) return;
      var b = new maplibregl.LngLatBounds();
      vs.forEach(function (v) { b.extend([v.lon, v.lat]); });
      karta.fitBounds(b, { padding: vidstup(), duration: ms == null ? 1200 : ms, maxZoom: 13.5, pitch: 0, bearing: 0 });
    }
    function letityDoVulytsi(v) {
      if (!karta || !v) return;
      var p = vidstup();
      karta.flyTo({ center: [v.lon, v.lat], zoom: Math.max(karta.getZoom(), 14), duration: 900, pitch: 0,
        offset: [(p.left - p.right) / 2, (p.top - p.bottom) / 2] });
    }

    // Дотик по карті: вулиця — її картка; на старті — район. Повертає true, якщо дотик забрала гра.
    function klik(ll) {
      if (!karta || !D || !zhyve || !karta.getSource('lit-vulytsi')) return false;
      var pt = karta.project(ll);
      if (!S) {
        var r = karta.queryRenderedFeatures(pt, { layers: ['lit-rayony-zakryti'] })[0];
        if (r) { pochaty(r.properties.nazva); return true; }
        return false;
      }
      var f = karta.queryRenderedFeatures([[pt.x - 12, pt.y - 12], [pt.x + 12, pt.y + 12]], { layers: ['lit-vulytsi-vidkryti', 'lit-vulytsi-zakryti'] });
      if (!f.length) return false;
      function vidst(a) { var p = karta.project(a.geometry.coordinates); return (p.x - pt.x) * (p.x - pt.x) + (p.y - pt.y) * (p.y - pt.y); }
      f.sort(function (a, b) { return vidst(a) - vidst(b); });
      obrana = f[0].properties.slug; zvuk('dotyk', 0); vibro(6);
      perekliuchyty('vulytsi'); pryts();
      return true;
    }
    if (karta && o.vlasnyiKlik) {
      karta.on('click', function (e) { klik(e.lngLat); });
      karta.on('mouseenter', 'lit-vulytsi-zakryti', function () { karta.getCanvas().style.cursor = 'pointer'; });
      karta.on('mouseleave', 'lit-vulytsi-zakryti', function () { karta.getCanvas().style.cursor = ''; });
    }

    // ---------------------------------------------------------------- панель
    function perekliuchyty(v) {
      vkladka = v;
      EL.querySelectorAll('.lit-vkladky button').forEach(function (b) { b.setAttribute('aria-selected', b.getAttribute('data-v') === v ? 'true' : 'false'); });
      if (v !== 'vulytsi') { obrana = null; pryts(); }
      malyuvaty(true);
      VM.scrollTop = 0;
      if (o.pryZmini) o.pryZmini();
    }

    var ostanniiZnimok = '';
    // Перемальовує панель, лише коли змінилось те, що на ній видно (щоб дотик не «губився» між перемальовуваннями).
    function malyuvaty(zavzhdy) {
      if (!S || !D) return;
      var tv = Y.tsinaVulytsi(S);
      var dostupno = vkladka === 'chytaty' ? Y.vydniPomichnyky(S).map(function (p) { return S.storinky >= Y.tsinaPomichnyka(S, p) ? 1 : 0; }).join('') + (S.storinky >= tv ? 'v' : '') + Y.mozhnaVydannia(S) + (S.natkhnennia_do > teper())
        : vkladka === 'vulytsi' ? (S.storinky >= tv ? 1 : 0) : '';
      var zn = vkladka + '|' + obrana + '|' + S.vulytsi.length + '|' + S.rayony.length + '|' + JSON.stringify(S.pomichnyky) + '|' + dostupno + '|' + JSON.stringify(S.den) + '|' + S.vydannia + '|' + S.seriia.dniv;
      onovytyKartu();
      if (!zavzhdy && zn === ostanniiZnimok) return;
      ostanniiZnimok = zn;
      var h = vkladka === 'chytaty' ? panelChytaty() : vkladka === 'vulytsi' ? panelVulytsi() : vkladka === 'karty' ? panelKarty() : panelDen();
      var skrol = VM.scrollTop; VM.innerHTML = h; if (!zavzhdy) VM.scrollTop = skrol;
      VM.querySelectorAll('[data-w]').forEach(function (el) { el.style.width = el.getAttribute('data-w') + '%'; });   // без вбудованих стилів у розмітці
      VM.querySelectorAll('[data-do]').forEach(pidrakhunok);
      svizhe = {};
      var d = Y.den(S, teper());
      var tochka = Y.ZADACHI.some(function (z) { return !d.zrobleno[z.id]; });
      $('.lit-vkladky [data-v="den"]').innerHTML = 'День' + (tochka ? '<span class="lit-tochka" title="Є задачі на сьогодні"></span>' : '');
      var vsiKarty = Object.keys(D.vydy).filter(function (k) { return !povazhna(k); });
      $('.lit-vkladky [data-v="karty"]').textContent = 'Картки ' + vsiKarty.filter(function (k) { return S.karty[k]; }).length + '/' + vsiKarty.length;
    }

    function panelChytaty() {
      var t = teper(), natkh = S.natkhnennia_do > t, tv = Y.tsinaVulytsi(S);
      var h = '<button type="button" class="klavisha klavisha--holovna lit-chytaty' + (natkh ? ' lit-chytaty--natkh' : '') + '" id="lit-chytaty"><span class="lit-chytaty__t">Прочитати сторінку</span><small>+' + ch(Math.max(1, Y.zaDotyk(S, D.vydy, t))) + ' за дотик' + (natkh ? ' · натхнення ×2' : '') + '</small></button>';
      var mozhna = S.storinky >= tv;
      h += '<div class="lit-nastupna' + (mozhna ? ' lit-nastupna--gotova' : '') + '"><div class="lit-nastupna__t"><b>Наступна вулиця</b><span>' + ch(tv) + ' ' + slovo(tv, STOR) + '</span></div>' +
        '<div class="lit-smuha"><i></i></div>' +
        (mozhna ? '<button type="button" class="klavisha lit-mozhna lit-shyroka" data-lit="do-vulyts">Можна відкрити — обрати вулицю</button>' : '<p class="lit-tykho lit-bez">Кружечки на карті — вулиці. Обведені м\'ятним — можна відкрити.</p>') + '</div>';
      h += '<h3>Помічники</h3>';
      Y.vydniPomichnyky(S).forEach(function (p) {
        var c = Y.tsinaPomichnyka(S, p), mozh = S.storinky >= c;
        h += '<div class="lit-riadok' + (svizhe.pomichnyk === p.id ? ' lit-svizhe' : '') + '"><span class="lit-lichylnyk">' + Y.kilkist(S, p.id) + '</span><div class="lit-riadok__tekst"><div class="lit-riadok__nazva">' + esc(p.nazva) + '</div><div class="lit-riadok__opys">' + esc(p.opys) + ' · ' + String(p.za_sek).replace('.', ',') + ' стор./с</div></div>' +
          '<button type="button" class="klavisha' + (mozh ? ' lit-mozhna' : ' lit-tsina') + '" data-naiaty="' + p.id + '">' + ch(c) + '</button></div>';
      });
      var mn = Y.mnozhnyk(S, D.vydy);
      h += '<p class="lit-tykho lit-vidstup">Множник читання ×' + mn.toFixed(2).replace('.', ',') + ': вулиці, картки видів' + (S.seriia.dniv ? ', серія днів' : '') + (S.avtorytet ? ', авторитет' : '') + '.</p>';
      var a = Y.avtorytetZa(S);
      h += '<h3>Нове видання літопису</h3><p class="lit-tykho">Почати читання заново (сторінки й помічники — з нуля) і отримати авторитет: +' + Math.round(Y.N.avtorytet_bonus * 100) + ' % до читання назавжди за кожен пункт. Вулиці, райони й картки лишаються.' +
        (a ? '' : ' Відкриється, коли за це видання прочитаєте ' + ch(Y.porihVydannia(S)) + ' сторінок (зараз ' + ch(S.za_vydannia) + ').') + '</p>';
      h += '<button type="button" class="klavisha lit-shyroka" data-lit="vydannia"' + (a ? '' : ' disabled') + '>' + (a ? 'Видати ' + (S.vydannia + 2) + '-е видання: +' + a + ' авторитету' : 'Ще рано') + '</button>';
      if (S.vydannia) h += '<p class="lit-tykho lit-vidstup">Видань: ' + (S.vydannia + 1) + ', авторитет: ' + S.avtorytet + '.</p>';
      return h;
    }

    function nazvaVydu(k) { return D.vydy[k] ? D.vydy[k].nazva : k; }
    function povazhna(k) { return !!(D.vydy[k] && D.vydy[k].povazhna); }

    function kartkaVulytsi(v) {
      var vidkr = S.vulytsi.indexOf(v.slug) >= 0, tv = Y.tsinaVulytsi(S), nova = svizhe.vulytsia === v.slug;
      var h = '<div class="lit-kartka' + (vidkr ? ' lit-kartka--vidkryta' : '') + (nova ? ' lit-rozhortaietsia' : '') + '"><div class="lit-kartka__rayon">' + esc(v.rayon) + ' район</div><h2>' + esc(v.nazva) + '</h2>';
      if (!vidkr) {
        h += '<p class="lit-tykho">Відкрийте вулицю — побачите її числа й події, як їх описав суд.</p>';
        if (v.podii.length) {
          h += '<div class="lit-tykho lit-bez">Що запише вулиця (видно наперед):</div><div class="lit-pigulky">' + v.podii.map(function (id) {
            var k = D.podii[id][0], nv = !S.karty[k] && !povazhna(k);
            return '<span class="lit-pigulka' + (nv ? ' lit-pigulka--nova' : '') + '">' + esc(nazvaVydu(k)) + (nv ? ' · нова' : '') + '</span>';
          }).join('') + '</div>';
        } else h += '<p class="lit-tykho">Подій для гри на цій вулиці немає — лише числа.</p>';
        if (S.rayony.indexOf(v.rayon) < 0) h += '<p class="lit-tykho">' + esc(v.rayon) + ' район ще не відкрито: новий район — за кожні ' + Y.N.rayon_kozhni + ' вулиць.</p>';
        else h += '<button type="button" class="klavisha klavisha--holovna lit-shyroka' + (S.storinky >= tv ? ' lit-mozhna' : ' lit-tsina') + '" data-vidkryty="' + esc(v.slug) + '">' +
          (S.storinky >= tv ? 'Відкрити за ' + ch(tv) + ' ' + slovo(tv, STOR) : 'Ще ' + ch(tv - S.storinky) + ' ' + slovo(tv - S.storinky, STOR)) + '</button>';
        return h + '</div>';
      }
      h += '<div class="lit-kartka__chysla"><div><b' + (nova ? ' data-do="' + v.n + '"' : '') + '>' + ch(v.n) + '</b><span>' + slovo(v.n, PODS) + ' за ' + esc(D.roky) + '</span></div>' +
        (v.hrupa ? '<div><b class="lit-mensh">' + esc((D.hrupy || {})[v.hrupa] || v.hrupa) + '</b><span>найчастіше</span></div>' : '') + '</div>';
      v.podii.forEach(function (id, i) {
        var p = D.podii[id], pov = povazhna(p[0]);
        h += '<div class="lit-podiia' + (pov ? ' lit-podiia--povazhna' : '') + (nova ? ' lit-poiava lit-poiava--' + (i + 1) : '') + '"><div class="lit-podiia__vyd">' + esc(nazvaVydu(p[0])) + ', ' + p[1] + '</div><div class="lit-podiia__opys">' + (p[2] ? esc(p[2]) : POVAZHNO) + '</div>' +
          '<div class="lit-podiia__adresa">' + esc(p[3]) + ' · <a href="' + esc(p[6]) + '" target="_blank" rel="noopener nofollow">рішення суду</a></div></div>';
      });
      h += '<p class="lit-tykho lit-vidstup">Числа — з відкритих даних сайту; події — з колоди гри. Усі події вулиці за 10 років з описами — у підписці «Мій район».</p>';
      return h + '</div>';
    }

    function panelVulytsi() {
      var h = '';
      if (obrana && VUL[obrana]) return kartkaVulytsi(VUL[obrana]) + '<button type="button" class="klavisha lit-shyroka" data-lit="nazad">До списку вулиць</button>';
      var mozhna = Y.skilkyRayoniv(S, Object.keys(D.rayony).length);
      if (S.rayony.length < mozhna) {
        var vilni = Object.keys(D.rayony).filter(function (r) { return S.rayony.indexOf(r) < 0; }).sort(function (a, b) { return a.localeCompare(b, 'uk'); });
        h += '<div class="lit-kartka lit-kartka--vidkryta lit-kartka--klych"><h2>Можна відкрити новий район</h2><p class="lit-tykho">За кожні ' + Y.N.rayon_kozhni + ' вулиць — ще один район. Оберіть:</p><div class="lit-rayony">' +
          vilni.map(function (r) { return '<button type="button" class="klavisha" data-rayon-novyi="' + esc(r) + '">' + esc(r) + '</button>'; }).join('') + '</div></div>';
      }
      var mozh = S.storinky >= Y.tsinaVulytsi(S);
      function novi(v) { return v.podii.filter(function (id) { var k = D.podii[id][0]; return !S.karty[k] && !povazhna(k); }).length; }
      S.rayony.forEach(function (r) {
        var vs = D.vulytsi.filter(function (v) { return v.rayon === r; });
        var vidkr = vs.filter(function (v) { return S.vulytsi.indexOf(v.slug) >= 0; }).length;
        h += '<h3' + (svizhe.rayon === r ? ' class="lit-svizhe"' : '') + '>' + esc(r) + ' район: ' + vidkr + ' з ' + vs.length + ' ' + slovo(vs.length, VULS) + '</h3><div class="lit-prohres"><i data-w="' + (100 * vidkr / vs.length).toFixed(1) + '"></i></div>';
        // Спершу — ще не відкриті вулиці з новими картками, потім решта; відкриті — внизу.
        var zakr = vs.filter(function (v) { return S.vulytsi.indexOf(v.slug) < 0; });
        zakr.sort(function (a, b) { return novi(b) - novi(a) || (b.podii.length > 0) - (a.podii.length > 0) || b.n - a.n; });
        zakr.slice(0, 5).forEach(function (v) {
          var n = novi(v);
          h += '<div class="lit-riadok"><div class="lit-riadok__tekst"><div class="lit-riadok__nazva">' + esc(v.nazva) + '</div><div class="lit-riadok__opys">' + ch(v.n) + ' ' + slovo(v.n, PODS) + (n ? ' · нових карток: ' + n : v.podii.length ? '' : ' · лише числа') + '</div></div>' +
            '<button type="button" class="klavisha' + (mozh ? ' lit-mozhna' : '') + '" data-obraty="' + esc(v.slug) + '">Дивитись</button></div>';
        });
        if (zakr.length > 5) h += '<p class="lit-tykho">Ще ' + (zakr.length - 5) + ' — кружечками на карті.</p>';
        var vid = vs.filter(function (v) { return S.vulytsi.indexOf(v.slug) >= 0; });
        if (vid.length) h += '<p class="lit-tykho">Відкриті: ' + vid.map(function (v) { return '<a href="#" data-obraty="' + esc(v.slug) + '">' + esc(v.nazva) + '</a>'; }).join(', ') + '</p>';
      });
      return h;
    }

    function panelKarty() {
      var vsi = Object.keys(D.vydy).sort(function (a, b) { return D.vydy[b].n - D.vydy[a].n; });
      var pov = vsi.filter(povazhna); vsi = vsi.filter(function (k) { return !povazhna(k); });
      var ie = vsi.filter(function (k) { return S.karty[k]; }).length;
      var h = '<h2>Картки видів подій: ' + ie + ' з ' + vsi.length + '</h2><p class="lit-tykho">Рідкість — справжня частка виду серед ' + ch(vsi.concat(pov).reduce(function (a, k) { return a + D.vydy[k].n; }, 0)) +
        ' подій випуску, а не випадок. Що дасть вулиця, видно до відкриття. Рівень картки росте з кожною подією цього виду (1, 2, 4, 8, 16). Рідкісне — не значить страшне: лише рідше доходить до суду.</p><div class="lit-sitka">';
      vsi.forEach(function (k) {
        var v = D.vydy[k], n = S.karty[k] || 0, r = Y.rivenKarty(n);
        h += '<div class="lit-vyd ' + (n ? 'lit-vyd--ie' : 'lit-vyd--nema') + (svizhe.karty && svizhe.karty.indexOf(k) >= 0 ? ' lit-pereverty' : '') + '" data-r="' + v.ridkist + '"><div class="lit-vyd__nazva">' + esc(n ? v.nazva : '?') + '</div>' +
          '<div class="lit-vyd__ridkist">' + esc(D.ridkist[v.ridkist]) + ' · ' + String(v.chastka < 0.1 ? v.chastka.toFixed(2) : v.chastka.toFixed(1)).replace('.', ',') + ' %</div>' +
          (n || D.uKolodi[k] ? '<div class="lit-vyd__riven">' + [1, 2, 3, 4, 5].map(function (i) { return '<i class="' + (i <= r ? 'tak' : '') + '"></i>'; }).join('') + '</div>' : '<div class="lit-vyd__ridkist">у грі поки немає подій</div>') + '</div>';
      });
      h += '</div><h3>Події з потерпілими</h3><p class="lit-tykho">Записані в літопис, як їх підтвердив суд: вид, рік, адреса й рішення. Без бонусів і без рівнів — це не трофеї.</p><div class="lit-sitka">';
      pov.forEach(function (k) {
        var v = D.vydy[k], n = S.karty[k] || 0;
        h += '<div class="lit-vyd lit-vyd--povazhna ' + (n ? 'lit-vyd--ie' : 'lit-vyd--nema') + '"><div class="lit-vyd__nazva">' + esc(n ? v.nazva : '?') + '</div>' +
          '<div class="lit-vyd__ridkist">' + (n ? 'у літописі: ' + n : D.uKolodi[k] ? 'ще не записано' : 'у грі поки немає подій') + '</div></div>';
      });
      return h + '</div>';
    }

    function panelDen() {
      var t = teper(), d = Y.den(S, t), sp = Y.spravaDnia(d.data, D);
      var h = '<h2>Сьогодні, ' + d.data.split('-').reverse().join('.') + '</h2><p class="lit-tykho">Три задачі на день, однакові для всіх. Кожна — година натхнення (читання ×2)' + (o.bali ? ' і бали в скарбничку ігор' : '') + '. Усі три — день у серію: +' + Math.round(Y.N.seriia_bonus_den * 100) + ' % за кожен день, до +' + Math.round(Y.N.seriia_bonus_max * 100) + ' %. Один пропущений день на тиждень серію не рве.</p>';
      if (sp) {
        var p = D.podii[sp.id];
        h += '<div class="lit-opys-spravy"><b>Справа дня.</b> ' + esc(p[2]) + '</div>';
        h += zadacha('sprava', 'Який це вид події?', sp.varianty_vydu, sp.vyd, nazvaVydu, d);
        if (sp.varianty_rayonu.length) h += zadacha('rayon', 'У якому районі це було?', sp.varianty_rayonu, sp.rayon, function (x) { return x; }, d);
        if (d.vidpovidi.sprava != null && d.vidpovidi.rayon != null) {
          h += '<p class="lit-tykho">' + esc(p[3]) + ' · ' + p[1] + ' · <a href="' + esc(p[6]) + '" target="_blank" rel="noopener nofollow">рішення суду</a>' +
            (sp.vulytsia && VUL[sp.vulytsia] ? ' · <a href="#" data-obraty="' + esc(sp.vulytsia) + '">вулиця на карті</a>' : '') + '</p>';
        }
      }
      var z3 = Y.ZADACHI[2];
      h += '<div class="lit-zadacha' + (d.zrobleno.vulytsi ? ' lit-zadacha--zrobleno' : '') + '"><div class="lit-zadacha__nazva">' + esc(z3.nazva) + '<span class="lit-zadacha__mitka">' + (d.zrobleno.vulytsi ? 'зроблено' : Math.min(3, d.vulyts || 0) + ' з 3') + '</span></div>' +
        '<div class="lit-prohres"><i data-w="' + (100 * Math.min(3, d.vulyts || 0) / 3).toFixed(0) + '"></i></div></div>';
      var zv = Y.zavtra(S, D.vydy, t);
      var hod = Math.floor(zv.khv_do_novoho_dnia / 60), khv = zv.khv_do_novoho_dnia % 60;
      var poshta = Y.skilkyNaVulytsi(S, Y.N.poshta_vulyts);
      h += '<div class="lit-zavtra"><b>Завтра</b> (через ' + hod + ' год ' + khv + ' хв): нова справа дня й ще три задачі' + (Y.vseZrobleno(S, t) ? '; серія — ' + S.seriia.dniv + ' ' + slovo(S.seriia.dniv, ['день', 'дні', 'днів']) + ', завтра стане ' + (S.seriia.dniv + 1) : '; зробіть сьогоднішні, щоб почати серію') +
        '. Пошта архіву принесе ≈ ' + ch(poshta) + ' ' + slovo(poshta, STOR) + ' — на ' + Y.N.poshta_vulyts + ' вулиці. За ніч помічники прочитають ≈ ' + ch(zv.za_nich) + ' (до ' + Y.N.offlain_hodyn + ' год і повільніше, ніж при вас).</div>';
      h += '<div class="lit-pidpyska"><b>З підпискою «Мій район»</b> (зараз вимкнено): усі події кожної відкритої вулиці за 10 років з описами, друга справа дня, помічники читають без вас до 24 годин. Гра без підписки — повна: нічого не закрито назавжди.</div>';
      return h;
    }

    function zadacha(id, nazva, varianty, pravylna, nazvaF, d) {
      var vid = d.vidpovidi[id];
      var h = '<div class="lit-zadacha' + (vid != null ? ' lit-zadacha--zrobleno' : '') + (svizhe.zadacha === id ? (vid === pravylna ? ' lit-svizhe' : ' lit-khytannia') : '') + '"><div class="lit-zadacha__nazva">' + esc(nazva) + '<span class="lit-zadacha__mitka">' +
        (vid == null ? 'одна спроба' : vid === pravylna ? 'так · година натхнення' : 'ні · правильну позначено') + '</span></div><div class="lit-varianty">';
      varianty.forEach(function (v) {
        var kl = vid == null ? '' : v === pravylna ? ' lit-pravylno' : v === vid ? ' lit-ni' : '';
        h += '<button type="button" class="klavisha' + kl + '" data-zadacha="' + id + '" data-v="' + esc(v) + '"' + (vid != null ? ' disabled' : '') + '>' + esc(nazvaF(v)) + '</button>';
      });
      return h + '</div></div>';
    }

    // ---------------------------------------------------------------- дії
    var temp = 0, ostanniiDotyk = 0;
    function prochytatyStorinku(b, x, y) {
      var n = Y.dotyk(S, D.vydy, teper());
      var zaraz = performance.now();
      temp = zaraz - ostanniiDotyk < 450 ? temp + 1 : 0; ostanniiDotyk = zaraz;
      zvuk('dotyk', temp); vibro(5);
      lich('storinky', S.storinky);
      // «+N» вилітає з місця дотику; хвиля від пальця; клавіша пружно «підстрибує».
      var r = b.getBoundingClientRect();
      var px = x == null ? r.width / 2 : x - r.left, py = y == null ? r.height / 2 : y - r.top;
      var s = document.createElement('span'); s.className = 'lit-vylit' + (temp % 2 ? ' lit-vylit--l' : ''); s.textContent = '+' + ch(Math.max(1, n));
      s.style.left = px + 'px'; s.style.top = py + 'px';
      var kh = document.createElement('span'); kh.className = 'lit-khvylia'; kh.style.left = px + 'px'; kh.style.top = py + 'px';
      b.appendChild(s); b.appendChild(kh);
      setTimeout(function () { s.remove(); kh.remove(); }, 900);
      b.classList.remove('lit-pruzhyna'); void b.offsetWidth; b.classList.add('lit-pruzhyna');
      malyuvaty();
    }
    function neMozhna(b, tekst) { zvuk('ne_mozhna'); b.classList.remove('lit-khytannia'); void b.offsetWidth; b.classList.add('lit-khytannia'); if (tekst) tost(tekst, 2200); }

    // «Прочитати» — на pointerdown (миттєвий відгук); клавіатура (Enter, пробіл) — через click з detail 0.
    VM.addEventListener('pointerdown', function (e) {
      var b = e.target.closest('#lit-chytaty'); if (!b || !S) return;
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      e.preventDefault(); prochytatyStorinku(b, e.clientX, e.clientY);
    });
    EL.addEventListener('click', function (e) {
      var t = teper(), b;
      if ((b = e.target.closest('[data-lit="zvuk"]'))) {
        ZV.uvimk = !ZV.uvimk; try { localStorage.setItem(ZV.kliuch, ZV.uvimk ? 'tak' : 'ni'); } catch (x) { /* без пам'яті */ }
        zvukKnopka(); if (ZV.uvimk) zvuk('kup'); return;
      }
      if ((b = e.target.closest('.lit-vkladky [data-v]'))) { if (S) { zvuk('dotyk', 0); perekliuchyty(b.getAttribute('data-v')); } return; }
      if ((b = e.target.closest('[data-rayon-start]'))) { pochaty(b.getAttribute('data-rayon-start')); return; }
      if (!S) return;
      if ((b = e.target.closest('#lit-chytaty'))) { if (e.detail === 0) prochytatyStorinku(b); return; }
      if ((b = e.target.closest('[data-naiaty]'))) {
        var id = b.getAttribute('data-naiaty');
        if (Y.naiaty(S, id)) { svizhe.pomichnyk = id; zvuk('kup'); vibro(10); lich('storinky', S.storinky); zberehty(); malyuvaty(true); }
        else neMozhna(b, 'Ще бракує сторінок.');
        return;
      }
      if ((b = e.target.closest('[data-obraty]'))) {
        e.preventDefault(); obrana = b.getAttribute('data-obraty'); zvuk('dotyk', 0);
        if (vkladka !== 'vulytsi') perekliuchyty('vulytsi'); else { malyuvaty(true); VM.scrollTop = 0; }
        letityDoVulytsi(VUL[obrana]); pryts(); return;
      }
      if ((b = e.target.closest('[data-lit="do-vulyts"]'))) { perekliuchyty('vulytsi'); return; }
      if ((b = e.target.closest('[data-lit="nazad"]'))) { obrana = null; pryts(); malyuvaty(true); return; }
      if ((b = e.target.closest('[data-rayon-novyi]'))) {
        var r = b.getAttribute('data-rayon-novyi');
        if (Y.vidkrytyRayon(S, r)) { svizhe.rayon = r; zberehty(); zvuk('rayon'); vibro(20); tost(r + ' район відкрито.'); letityDoRayonu([r]); setTimeout(function () { spalakhRayonu(r); }, 900); malyuvaty(true); }
        return;
      }
      if ((b = e.target.closest('[data-vidkryty]'))) {
        var v = VUL[b.getAttribute('data-vidkryty')];
        var res = Y.vidkrytyVulytsiu(S, v, D.podii);
        if (!res.ok) { neMozhna(b, res.chomu === 'malo' ? 'Ще бракує сторінок — торкайтеся «Прочитати сторінку».' : ''); return; }
        var dn = Y.perevirytyVulytsi(S, t);
        var nk = res.novi_karty.filter(function (k) { return !povazhna(k); });
        var lyshePov = !nk.length && v.podii.some(function (pid) { return povazhna(D.podii[pid][0]); });
        svizhe.vulytsia = v.slug; svizhe.karty = res.novi_karty;
        zvuk(lyshePov ? 'tykho' : 'vulytsia'); vibro(18);
        if (nk.length) setTimeout(function () { zvuk('karta'); }, 380);
        spalakh(v); letityDoVulytsi(v);
        var bl = dn ? baly('vulytsi') : 0;
        lich('storinky', S.storinky); zberehty();
        tost(v.nazva + ' — у літописі.' + (nk.length ? ' Нові картки: ' + nk.map(nazvaVydu).join(', ') + '.' : '') + (res.novyi_rayon ? ' Можна відкрити новий район.' : '') +
          (dn ? ' Задачу дня виконано: година натхнення' + (bl ? ', +' + bl + ' ' + slovoBaly(bl) : '') + '.' : ''), 5000);
        malyuvaty(true);
        return;
      }
      if ((b = e.target.closest('[data-lit="vydannia"]'))) {
        var a = Y.noveVydannia(S); if (a) { zberehty(); zvuk('rayon'); lich('storinky', 0); tost('Нове видання: +' + a + ' авторитету. Читання тепер ×' + Y.mnozhnyk(S, D.vydy).toFixed(2).replace('.', ',') + '.'); malyuvaty(true); }
        return;
      }
      if ((b = e.target.closest('[data-zadacha]'))) {
        var d = Y.den(S, t), sp = Y.spravaDnia(d.data, D), zid = b.getAttribute('data-zadacha');
        var ok = Y.vidpovisty(S, t, zid, b.getAttribute('data-v'), zid === 'sprava' ? sp.vyd : sp.rayon);
        if (ok != null) {
          var bb = ok ? baly(zid) : 0;
          svizhe.zadacha = zid; zberehty(); zvuk(ok ? 'tak' : 'ni'); vibro(ok ? 15 : 8);
          tost(ok ? 'Так. Година натхнення: читання ×2' + (bb ? ', +' + bb + ' ' + slovoBaly(bb) : '') + '.' : 'Ні — правильну відповідь позначено. Задачу зараховано.');
          malyuvaty(true);
        }
        return;
      }
    });

    // Бали в спільну скарбничку ігор — лише за задачі дня, однакові для всіх (MV-138, MV-165). Обмін вимкнено.
    var OCHKY = o.ochky || { sprava: 500, rayon: 500, vulytsi: 300 };
    function baly(zadacha) { return o.bali ? (o.bali(OCHKY[zadacha] || 0) || 0) : 0; }
    function slovoBaly(n) { n = Math.abs(n) % 100; var d = n % 10; return (n > 10 && n < 15) ? 'балів' : d === 1 ? 'бал' : (d >= 2 && d <= 4) ? 'бали' : 'балів'; }

    // ---------------------------------------------------------------- годинник
    function tik() {
      if (!S || document.hidden || !zhyve) return;
      Y.plyn(S, D.vydy, teper());
      lich('storinky', S.storinky); lich('za_sek', Y.zaSek(S, D.vydy, teper())); lich('seriia', S.seriia.dniv);
      malyuvaty();
    }
    function pryVydymosti() { if (!zhyve) return; if (document.hidden) zberehty(); else povernennia(false); }
    document.addEventListener('visibilitychange', pryVydymosti);
    korin.addEventListener('pagehide', zberehty);

    function zupynyty() {
      if (!zhyve) return;
      zberehty(); zhyve = false;
      taimery.forEach(clearInterval);
      document.removeEventListener('visibilitychange', pryVydymosti);
      document.removeEventListener('mv-tema', pryTemi);
      korin.removeEventListener('pagehide', zberehty);
      if (smTema && smTema.removeEventListener) smTema.removeEventListener('change', pryTemi);
      if (karta) karta.off('styledata', pryStyli);
      if (PRYTS) PRYTS.remove();
      MARKERY.forEach(function (m) { m.remove(); });
      prybratyShary();
      tyshaKarty(false);
    }
    return { klik: klik, zupynyty: zupynyty, stan: function () { return S; } };
  }

  korin.MvLitopys = { zapustyty: zapustyty };
})(typeof window !== 'undefined' ? window : this);

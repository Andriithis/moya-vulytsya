// «Літопис міста» — сторінка прототипу (ZAVDANNYA-140). Логіка й числа — litopys-yadro.js; тут лише карта, панель і
// збереження на пристрої. Вигляд — docs/STYL.md. Без емодзі, без червоного, без звуків.
// Для перевірки й знімків: ?zsuv=<годин> — зсуває годинник гри (побачити «завтра» й «поки вас не було»);
// ?novyi=1 — почати з нуля (стерти прогрес на пристрої).
(function () {
  'use strict';
  var Y = window.MvLitopysYadro;
  var KLIUCH = 'mv-litopys';
  var q = new URLSearchParams(location.search);
  var ZSUV = (Number(q.get('zsuv')) || 0) * 3600e3;
  function teper() { return Date.now() + ZSUV; }
  if (q.get('novyi') === '1') { try { localStorage.removeItem(KLIUCH); } catch (e) { /* без пам'яті */ } }

  var D = null;          // дані гри
  var S = null;          // стан гравця
  var VUL = {};          // slug → вулиця
  var vkladka = 'chytaty';
  var obrana = null;     // slug вулиці, відкритої на панелі
  var karta = null;

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  var ch = function (n) { return Y.chyslo(n); };
  function slovo(n, f) { n = Math.abs(Math.floor(n)) % 100; var d = n % 10; return (n > 10 && n < 20) ? f[2] : d === 1 ? f[0] : (d >= 2 && d <= 4) ? f[1] : f[2]; }
  var STOR = ['сторінка', 'сторінки', 'сторінок'];
  var VULS = ['вулиця', 'вулиці', 'вулиць'];
  var PODS = ['подія', 'події', 'подій'];

  function zberehty() { try { localStorage.setItem(KLIUCH, JSON.stringify(S)); } catch (e) { /* приватний режим */ } }
  function prochytaty() { try { return JSON.parse(localStorage.getItem(KLIUCH)); } catch (e) { return null; } }

  var tostT = 0;
  function tost(t, ms) { var el = $('tost'); el.textContent = t; el.classList.add('vyd'); clearTimeout(tostT); tostT = setTimeout(function () { el.classList.remove('vyd'); }, ms || 3200); }

  // ---------------------------------------------------------------- дані
  fetch('litopys.json', { credentials: 'omit' }).then(function (v) { if (!v.ok) throw new Error(v.status); return v.json(); })
    .then(start).catch(function () {
      $('vmist').innerHTML = '<h2>Немає даних гри</h2><p class="tykho">Зберіть файл: <code>python site/ihry/litopys/litopys.py --baza events-2026-11-08.db --koloda koloda-2026-11-08.json</code> і відкрийте сторінку через локальний сервер з теки <code>site/</code>.</p>';
    });

  function start(dani) {
    D = dani;
    D.vulytsi = D.vulytsi.map(function (v) { var o = { slug: v[0], nazva: v[1], rayon: v[2], n: v[3], hrupa: v[4], lat: v[5], lon: v[6], podii: v[7] }; VUL[o.slug] = o; return o; });
    D.hrupyNazvy = D.hrupy || {};
    S = Y.pryniaty(prochytaty(), teper());
    stvorytyKartu();
    if (!S) { vybirRayonu(); } else { povernennia(); }
    pidpysaty();
    setInterval(tik, 250);
    setInterval(zberehty, 5000);
    document.addEventListener('visibilitychange', function () { if (document.hidden) zberehty(); else povernennia(); });
    window.addEventListener('pagehide', zberehty);
  }

  // Повернення після перерви: «поки вас не було…» (межа й половинна швидкість — чесно написані).
  function povernennia() {
    if (!S) return;
    var vid = S.chas, r = Y.plyn(S, D.vydy, teper());
    if (r.sekund > 120 && r.storinok >= 1) {
      var hod = Math.round((teper() - vid) / 36e5 * 10) / 10;
      tost('Поки вас не було (' + String(hod).replace('.', ',') + ' год), помічники прочитали ' + ch(r.storinok) + ' ' + slovo(r.storinok, STOR) +
        (r.obrizano ? '. Більше ' + Y.N.offlain_hodyn + ' годин вони без вас не читають.' : '.'), 6000);
    }
    Y.den(S, teper());
    malyuvaty();
  }

  function vybirRayonu() {
    var r = Object.keys(D.rayony).sort(function (a, b) { return a.localeCompare(b, 'uk'); });
    var v = $('vikno');
    v.innerHTML = '<div class="vikno__vnutri"><h1>Де ви живете?</h1>' +
      '<p class="tykho">Літопис починається з вашого району. Ви читаєте сторінки судових справ, наймаєте помічників і відкриваєте вулиці — кожна з числами й подіями, як їх описав суд. Інші райони відкриються згодом.</p>' +
      '<div class="rayony">' + r.map(function (x) { return '<button class="klavisha" data-rayon="' + esc(x) + '">' + esc(x) + '</button>'; }).join('') + '</div>' +
      '<p class="tykho vidstup">Прогрес зберігається лише на цьому пристрої. Гра нічого не продає.</p></div>';
    v.hidden = false;
    v.onclick = function (e) {
      var b = e.target.closest('[data-rayon]'); if (!b) return;
      S = Y.novyi(teper(), b.getAttribute('data-rayon'));
      Y.den(S, teper());
      v.hidden = true; zberehty();
      letityDoRayonu(S.dim);
      tost('Торкайтеся «Прочитати сторінку». Перша вулиця коштує ' + Y.tsinaVulytsi(S) + ' сторінок.');
      malyuvaty();
    };
  }

  // ---------------------------------------------------------------- карта
  function zminna(n) { return getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim(); }
  function kolory() {
    var k = {};
    ['ground', 'surface', 'ink', 'ink-2', 'muted', 'line', 'line-strong', 'accent', 'accent-soft', 'mezha', 'pk-2', 'data-1', 'data-3', 'data-5',
      'karta-voda', 'karta-zelen', 'karta-zabudova', 'karta-vulytsia', 'karta-vulytsia-ramka', 'karta-za-mezhamy'].forEach(function (n) { k[n] = zminna(n); });
    return k;
  }
  function porozhnio() { return { type: 'FeatureCollection', features: [] }; }

  function stvorytyKartu() {
    if (!window.maplibregl || !window.MvHraKarta) return;
    maplibregl.setWorkerUrl('../../hra/biblioteka/maplibre-gl-csp-worker.js');
    var k = kolory();
    var st = window.MvHraKarta.styl(k, null, { liniya: porozhnio(), spravzhnie: porozhnio(), vasha: porozhnio() });
    st.layers = st.layers.filter(function (l) { return ['liniya', 'spravzhnie-oreol', 'spravzhnie', 'vasha', 'za-mezhamy', 'mezha'].indexOf(l.id) < 0; });
    st.sources.rayony = { type: 'geojson', data: porozhnio() };
    st.sources.vulytsi = { type: 'geojson', data: porozhnio() };
    st.layers.push(
      // Закриті райони — тихо притінені; відкриті — прозорі з межею accent. Колір — стан гри, не «небезпека».
      { id: 'rayony-zakryti', type: 'fill', source: 'rayony', filter: ['==', ['get', 'vidkrytyi'], 0], paint: { 'fill-color': k['karta-za-mezhamy'], 'fill-opacity': 0.75 } },
      { id: 'rayony-mezha', type: 'line', source: 'rayony', paint: { 'line-color': ['case', ['==', ['get', 'vidkrytyi'], 1], k.accent, k['line-strong']], 'line-width': ['case', ['==', ['get', 'vidkrytyi'], 1], 2, 1] } },
      { id: 'vulytsi-zakryti', type: 'circle', source: 'vulytsi', filter: ['==', ['get', 'v'], 0], paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 2.5, 14, 6], 'circle-color': k.surface, 'circle-stroke-color': k.mezha, 'circle-stroke-width': 1.5 } },
      { id: 'vulytsi-vidkryti-oreol', type: 'circle', source: 'vulytsi', filter: ['==', ['get', 'v'], 1], paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, ['+', 5, ['*', 6, ['get', 'shchil']]], 14, ['+', 12, ['*', 14, ['get', 'shchil']]]], 'circle-color': k.accent, 'circle-opacity': 0.16 } },
      { id: 'vulytsi-vidkryti', type: 'circle', source: 'vulytsi', filter: ['==', ['get', 'v'], 1], paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, ['+', 3, ['*', 3, ['get', 'shchil']]], 14, ['+', 6, ['*', 6, ['get', 'shchil']]]], 'circle-color': k.accent, 'circle-stroke-color': k.surface, 'circle-stroke-width': 1.5 } },
      { id: 'vulytsia-obrana', type: 'circle', source: 'vulytsi', filter: ['==', ['get', 'o'], 1], paint: { 'circle-radius': 13, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': k.ink, 'circle-stroke-width': 2.5 } }
    );
    var telefon = window.matchMedia('(max-width: 600px)').matches;
    try {
      karta = new maplibregl.Map({ container: 'karta', style: st, bounds: window.MvHraKarta.KYIV, fitBoundsOptions: { padding: telefon ? { top: 40, bottom: 320, left: 10, right: 10 } : { top: 70, bottom: 20, left: 20, right: 440 } },
        minZoom: 8.5, maxZoom: 17, dragRotate: false, pitchWithRotate: false, touchPitch: false, attributionControl: false, renderWorldCopies: false, fadeDuration: 0 });
    } catch (e) { karta = null; return; }
    karta.touchZoomRotate.disableRotation();
    karta.addControl(new maplibregl.NavigationControl({ showCompass: false }), telefon ? 'top-left' : 'bottom-left');
    karta.addControl(new maplibregl.AttributionControl({ compact: telefon, customAttribution: '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© учасники OpenStreetMap</a>' }), 'bottom-right');
    karta.on('load', function () { karta.loaded_ = true; onovytyKartu(); });
    karta.on('error', function () { /* без підкладки гра працює: райони й вулиці — наші шари */ });
    karta.on('click', function (e) {
      var f = karta.queryRenderedFeatures(e.point, { layers: ['vulytsi-vidkryti', 'vulytsi-zakryti'] })[0];
      if (!f) {
        var bbox = [[e.point.x - 10, e.point.y - 10], [e.point.x + 10, e.point.y + 10]];
        f = karta.queryRenderedFeatures(bbox, { layers: ['vulytsi-vidkryti', 'vulytsi-zakryti'] })[0];
      }
      if (f) { obrana = f.properties.slug; perekliuchyty('vulytsi'); }
    });
    karta.on('mouseenter', 'vulytsi-zakryti', function () { karta.getCanvas().style.cursor = 'pointer'; });
    karta.on('mouseleave', 'vulytsi-zakryti', function () { karta.getCanvas().style.cursor = ''; });
  }

  var znimokKarty = '';
  function onovytyKartu() {
    if (!karta || !karta.loaded_ || !S) return;
    var vidkr = {}; S.vulytsi.forEach(function (s) { vidkr[s] = 1; });
    var kl = S.vulytsi.length + '|' + S.rayony.join(',') + '|' + obrana;
    if (kl === znimokKarty) return; znimokKarty = kl;
    var maks = 1; D.vulytsi.forEach(function (v) { if (v.n > maks) maks = v.n; });
    var f = [];
    D.vulytsi.forEach(function (v) {
      if (S.rayony.indexOf(v.rayon) < 0) return;
      f.push({ type: 'Feature', properties: { slug: v.slug, v: vidkr[v.slug] ? 1 : 0, o: v.slug === obrana ? 1 : 0, shchil: Math.sqrt(v.n / maks) }, geometry: { type: 'Point', coordinates: [v.lon, v.lat] } });
    });
    karta.getSource('vulytsi').setData({ type: 'FeatureCollection', features: f });
    var r = [];
    Object.keys(D.mezhi || {}).forEach(function (n) {
      r.push({ type: 'Feature', properties: { nazva: n, vidkrytyi: S.rayony.indexOf(n) >= 0 ? 1 : 0 }, geometry: { type: 'MultiPolygon', coordinates: D.mezhi[n].map(function (pl) { return [pl.concat([pl[0]])]; }) } });
    });
    karta.getSource('rayony').setData({ type: 'FeatureCollection', features: r });
  }

  function letityDoRayonu(rayon) {
    if (!karta) return;
    var vs = D.vulytsi.filter(function (v) { return v.rayon === rayon; });
    if (!vs.length) return;
    var b = new maplibregl.LngLatBounds();
    vs.forEach(function (v) { b.extend([v.lon, v.lat]); });
    var telefon = window.matchMedia('(max-width: 600px)').matches;
    karta.fitBounds(b, { padding: telefon ? { top: 60, bottom: 330, left: 20, right: 20 } : { top: 90, bottom: 40, left: 40, right: 460 }, duration: 1200, maxZoom: 13.5 });
  }
  function letityDoVulytsi(v) { if (karta) karta.flyTo({ center: [v.lon, v.lat], zoom: Math.max(karta.getZoom(), 13.5), duration: 900 }); }

  // ---------------------------------------------------------------- панель
  function perekliuchyty(v) {
    vkladka = v;
    document.querySelectorAll('.vkladky button').forEach(function (b) { b.setAttribute('aria-selected', b.getAttribute('data-v') === v ? 'true' : 'false'); });
    $('panel').classList.remove('zhorn');
    malyuvaty(true);
  }
  document.querySelector('.vkladky').addEventListener('click', function (e) { var b = e.target.closest('[data-v]'); if (b) { if (b.getAttribute('data-v') !== 'vulytsi') obrana = null; perekliuchyty(b.getAttribute('data-v')); } });

  var ostanniiZnimok = '';
  // Перемальовує панель, лише коли змінилось те, що на ній видно (щоб дотик не «губився» між перемальовуваннями).
  function malyuvaty(zavzhdy) {
    if (!S) return;
    var dostupno = vkladka === 'chytaty' ? Y.vydniPomichnyky(S).map(function (p) { return S.storinky >= Y.tsinaPomichnyka(S, p) ? 1 : 0; }).join('') + (S.storinky >= Y.tsinaVulytsi(S) ? 'v' : '') + Y.mozhnaVydannia(S)
      : vkladka === 'vulytsi' ? (S.storinky >= Y.tsinaVulytsi(S) ? 1 : 0) : '';
    var zn = vkladka + '|' + obrana + '|' + S.vulytsi.length + '|' + S.rayony.length + '|' + JSON.stringify(S.pomichnyky) + '|' + dostupno + '|' + JSON.stringify(S.den) + '|' + S.vydannia;
    if (!zavzhdy && zn === ostanniiZnimok) return;
    ostanniiZnimok = zn;
    var h = vkladka === 'chytaty' ? panelChytaty() : vkladka === 'vulytsi' ? panelVulytsi() : vkladka === 'karty' ? panelKarty() : panelDen();
    var vm = $('vmist'); var skrol = vm.scrollTop; vm.innerHTML = h; if (!zavzhdy) vm.scrollTop = skrol;
    vm.querySelectorAll('[data-w]').forEach(function (el) { el.style.width = el.getAttribute('data-w') + '%'; });   // політика безпеки: без вбудованих стилів у розмітці
    var d = Y.den(S, teper());
    var tochka = Y.ZADACHI.some(function (z) { return !d.zrobleno[z.id]; });
    var bDen = document.querySelector('.vkladky [data-v="den"]'); bDen.innerHTML = 'День' + (tochka ? '<span class="tochka" title="Є задачі на сьогодні"></span>' : '');
    var nemaKart = Object.keys(S.karty).length;
    document.querySelector('.vkladky [data-v="karty"]').textContent = 'Картки ' + nemaKart + '/' + Object.keys(D.vydy).length;
    onovytyKartu();
  }

  function panelChytaty() {
    var t = teper();
    var natkh = S.natkhnennia_do > t;
    var tv = Y.tsinaVulytsi(S);
    var h = '<button class="klavisha klavisha--holovna chytaty" id="chytaty">Прочитати сторінку<small>+' + ch(Math.max(1, Y.zaDotyk(S, D.vydy, t))) + ' за дотик' + (natkh ? ' · натхнення ×2' : '') + '</small></button>';
    h += '<h3>Наступна вулиця — ' + ch(tv) + ' ' + slovo(tv, STOR) + '</h3>';
    h += '<div class="prohres"><i data-w=\"' + Math.min(100, 100 * S.storinky / tv).toFixed(1) + '\"></i></div>';
    h += '<p class="tykho">Оберіть кружечок на карті або відкрийте вкладку «Вулиці». Кожна вулиця додає +' + Math.round(Y.N.bonus_vulytsi * 100) + ' % до читання.</p>';
    h += '<h3>Помічники</h3>';
    Y.vydniPomichnyky(S).forEach(function (p) {
      var c = Y.tsinaPomichnyka(S, p);
      h += '<div class="riadok"><span class="lichylnyk">' + Y.kilkist(S, p.id) + '</span><div class="riadok__tekst"><div class="riadok__nazva">' + esc(p.nazva) + '</div><div class="riadok__opys">' + esc(p.opys) + ' · ' + String(p.za_sek).replace('.', ',') + ' стор./с</div></div>' +
        '<button class="klavisha" data-naiaty="' + p.id + '"' + (S.storinky < c ? ' disabled' : '') + '>' + ch(c) + '</button></div>';
    });
    var mn = Y.mnozhnyk(S, D.vydy);
    h += '<p class="tykho vidstup">Множник читання ×' + mn.toFixed(2).replace('.', ',') + ': вулиці, картки видів' + (S.seriia.dniv ? ', серія днів' : '') + (S.avtorytet ? ', авторитет' : '') + '.</p>';
    var a = Y.avtorytetZa(S);
    h += '<h3>Нове видання літопису</h3><p class="tykho">Почати читання заново (сторінки й помічники — з нуля) і отримати авторитет: +' + Math.round(Y.N.avtorytet_bonus * 100) + ' % до читання назавжди за кожен пункт. Вулиці, райони й картки лишаються.' +
      (a ? '' : ' Відкриється, коли за це видання прочитаєте ' + ch(Y.porihVydannia(S)) + ' сторінок (зараз ' + ch(S.za_vydannia) + ').') + '</p>';
    h += '<button class="klavisha klavisha--shyroka" id="vydannia"' + (a ? '' : ' disabled') + '>' + (a ? 'Видати ' + (S.vydannia + 2) + '-е видання: +' + a + ' авторитету' : 'Ще рано') + '</button>';
    if (S.vydannia) h += '<p class="tykho vidstup">Видань: ' + (S.vydannia + 1) + ', авторитет: ' + S.avtorytet + '.</p>';
    return h;
  }

  function nazvaVydu(k) { return D.vydy[k] ? D.vydy[k].nazva : k; }

  function kartkaVulytsi(v) {
    var vidkr = S.vulytsi.indexOf(v.slug) >= 0;
    var tv = Y.tsinaVulytsi(S);
    var h = '<div class="kartka' + (vidkr ? ' kartka--vidkryta' : '') + '"><div class="kartka__rayon">' + esc(v.rayon) + ' район</div><h2>' + esc(v.nazva) + '</h2>';
    if (!vidkr) {
      h += '<p class="tykho">Відкрийте вулицю — побачите її числа й події, як їх описав суд.</p>';
      if (v.podii.length) {
        h += '<div class="tykho bez-vidstupu">Картки, які дасть вулиця (видно наперед):</div><div class="pigulky">' + v.podii.map(function (id) { var k = D.podii[id][0]; return '<span class="pigulka' + (S.karty[k] ? '' : ' pigulka--nova') + '">' + esc(nazvaVydu(k)) + (S.karty[k] ? '' : ' · нова') + '</span>'; }).join('') + '</div>';
      } else h += '<p class="tykho">Подій для гри на цій вулиці немає — лише числа.</p>';
      if (S.rayony.indexOf(v.rayon) < 0) h += '<p class="tykho">' + esc(v.rayon) + ' район ще не відкрито: новий район — за кожні ' + Y.N.rayon_kozhni + ' вулиць.</p>';
      else h += '<button class="klavisha klavisha--holovna klavisha--shyroka" data-vidkryty="' + esc(v.slug) + '"' + (S.storinky < tv ? ' disabled' : '') + '>Відкрити за ' + ch(tv) + ' ' + slovo(tv, STOR) + '</button>';
      return h + '</div>';
    }
    h += '<div class="kartka__chysla"><div><b>' + ch(v.n) + '</b><span>' + slovo(v.n, PODS) + ' за ' + esc(D.roky) + '</span></div>' +
      (v.hrupa ? '<div><b class="mensh">' + esc(D.hrupyNazvy[v.hrupa] || v.hrupa) + '</b><span>найчастіше</span></div>' : '') + '</div>';
    v.podii.forEach(function (id) {
      var p = D.podii[id];
      h += '<div class="podiia"><div class="podiia__vyd">' + esc(nazvaVydu(p[0])) + ', ' + p[1] + '</div><div>' + esc(p[2]) + '</div>' +
        '<div class="podiia__adresa">' + esc(p[3]) + ' · <a href="' + esc(p[6]) + '" target="_blank" rel="noopener nofollow">рішення суду</a></div></div>';
    });
    h += '<p class="tykho vidstup">Числа — з відкритих даних сайту; події — з колоди гри. Усі події вулиці за 10 років з описами — у підписці «Мій район».</p>';
    return h + '</div>';
  }

  function panelVulytsi() {
    var h = '';
    if (obrana && VUL[obrana]) {
      h += kartkaVulytsi(VUL[obrana]);
      h += '<button class="klavisha klavisha--shyroka" id="nazad">До списку вулиць</button>';
      return h;
    }
    var mozhna = Y.skilkyRayoniv(S, Object.keys(D.rayony).length);
    if (S.rayony.length < mozhna) {
      var vilni = Object.keys(D.rayony).filter(function (r) { return S.rayony.indexOf(r) < 0; }).sort(function (a, b) { return a.localeCompare(b, 'uk'); });
      h += '<div class="kartka kartka--vidkryta"><h2>Можна відкрити новий район</h2><p class="tykho">За кожні ' + Y.N.rayon_kozhni + ' вулиць — ще один район. Оберіть:</p><div class="rayony">' +
        vilni.map(function (r) { return '<button class="klavisha" data-rayon-novyi="' + esc(r) + '">' + esc(r) + '</button>'; }).join('') + '</div></div>';
    }
    S.rayony.forEach(function (r) {
      var vs = D.vulytsi.filter(function (v) { return v.rayon === r; });
      var vidkr = vs.filter(function (v) { return S.vulytsi.indexOf(v.slug) >= 0; }).length;
      h += '<h3>' + esc(r) + ' район: ' + vidkr + ' з ' + vs.length + ' ' + slovo(vs.length, VULS) + '</h3><div class="prohres"><i data-w=\"' + (100 * vidkr / vs.length).toFixed(1) + '\"></i></div>';
      // Спершу — ще не відкриті вулиці з подіями гри (нові картки), потім решта; відкриті — внизу.
      var zakr = vs.filter(function (v) { return S.vulytsi.indexOf(v.slug) < 0; });
      zakr.sort(function (a, b) { return (b.podii.length > 0) - (a.podii.length > 0) || b.n - a.n; });
      zakr.slice(0, 5).forEach(function (v) {
        var novi = v.podii.filter(function (id) { return !S.karty[D.podii[id][0]]; }).length;
        h += '<div class="riadok"><div class="riadok__tekst"><div class="riadok__nazva">' + esc(v.nazva) + '</div><div class="riadok__opys">' + ch(v.n) + ' ' + slovo(v.n, PODS) + (novi ? ' · нових карток: ' + novi : v.podii.length ? '' : ' · лише числа') + '</div></div>' +
          '<button class="klavisha" data-obraty="' + esc(v.slug) + '">Дивитись</button></div>';
      });
      if (zakr.length > 5) h += '<p class="tykho">Ще ' + (zakr.length - 5) + ' — кружечками на карті.</p>';
      var vid = vs.filter(function (v) { return S.vulytsi.indexOf(v.slug) >= 0; });
      if (vid.length) h += '<p class="tykho">Відкриті: ' + vid.map(function (v) { return '<a href="#" data-obraty="' + esc(v.slug) + '">' + esc(v.nazva) + '</a>'; }).join(', ') + '</p>';
    });
    return h;
  }

  function panelKarty() {
    var vsi = Object.keys(D.vydy).sort(function (a, b) { return D.vydy[b].n - D.vydy[a].n; });
    var ie = Object.keys(S.karty).length;
    var h = '<h2>Картки видів подій: ' + ie + ' з ' + vsi.length + '</h2><p class="tykho">Рідкість — справжня частка виду серед ' + ch(vsi.reduce(function (a, k) { return a + D.vydy[k].n; }, 0)) +
      ' подій пробного випуску, а не випадок. Що дасть вулиця, видно до відкриття. Рівень картки росте з кожною подією цього виду (1, 2, 4, 8, 16). Рідкісне — не значить страшне: лише рідше доходить до суду.</p><div class="sitka">';
    vsi.forEach(function (k) {
      var v = D.vydy[k], n = S.karty[k] || 0, r = Y.rivenKarty(n);
      h += '<div class="vyd ' + (n ? 'vyd--ie' : 'vyd--nema') + '" data-r="' + v.ridkist + '"><div class="vyd__nazva">' + esc(n ? v.nazva : '?') + '</div>' +
        '<div class="vyd__ridkist">' + esc(D.ridkist[v.ridkist]) + ' · ' + String(v.chastka < 0.1 ? v.chastka.toFixed(2) : v.chastka.toFixed(1)).replace('.', ',') + ' %</div>' +
        '<div class="vyd__riven">' + [1, 2, 3, 4, 5].map(function (i) { return '<i class="' + (i <= r ? 'tak' : '') + '"></i>'; }).join('') + '</div></div>';
    });
    return h + '</div>';
  }

  function panelDen() {
    var t = teper(), d = Y.den(S, t), sp = Y.spravaDnia(d.data, D);
    var h = '<h2>Сьогодні, ' + d.data.split('-').reverse().join('.') + '</h2><p class="tykho">Три задачі на день, однакові для всіх. Кожна — година натхнення (читання ×2). Усі три — день у серію: +' + Math.round(Y.N.seriia_bonus_den * 100) + ' % за кожен день, до +' + Math.round(Y.N.seriia_bonus_max * 100) + ' %. Один пропущений день на тиждень серію не рве.</p>';
    if (sp) {
      var p = D.podii[sp.id];
      h += '<div class="opys-spravy"><b>Справа дня.</b> ' + esc(p[2]) + '</div>';
      h += zadacha('sprava', 'Який це вид події?', sp.varianty_vydu, sp.vyd, nazvaVydu, d);
      if (sp.varianty_rayonu.length) h += zadacha('rayon', 'У якому районі це було?', sp.varianty_rayonu, sp.rayon, function (x) { return x; }, d);
      if (d.vidpovidi.sprava != null && d.vidpovidi.rayon != null) {
        h += '<p class="tykho">' + esc(p[3]) + ' · ' + p[1] + ' · <a href="' + esc(p[6]) + '" target="_blank" rel="noopener nofollow">рішення суду</a>' +
          (sp.vulytsia && VUL[sp.vulytsia] ? ' · <a href="#" data-obraty="' + esc(sp.vulytsia) + '">вулиця на карті</a>' : '') + '</p>';
      }
    }
    var z3 = Y.ZADACHI[2];
    h += '<div class="zadacha' + (d.zrobleno.vulytsi ? ' zadacha--zrobleno' : '') + '"><div class="zadacha__nazva">' + esc(z3.nazva) + '<span class="zadacha__mitka">' + (d.zrobleno.vulytsi ? 'зроблено' : Math.min(3, d.vulyts || 0) + ' з 3') + '</span></div></div>';
    var zv = Y.zavtra(S, D.vydy, t);
    var hod = Math.floor(zv.khv_do_novoho_dnia / 60), khv = zv.khv_do_novoho_dnia % 60;
    h += '<div class="zavtra"><b>Завтра</b> (через ' + hod + ' год ' + khv + ' хв): нова справа дня й ще три задачі' + (Y.vseZrobleno(S, t) ? '; серія — ' + S.seriia.dniv + ' ' + slovo(S.seriia.dniv, ['день', 'дні', 'днів']) + ', завтра стане ' + (S.seriia.dniv + 1) : '; зробіть сьогоднішні, щоб почати серію') +
      '. За ніч помічники прочитають ≈ ' + ch(zv.za_nich) + ' ' + slovo(zv.za_nich, STOR) + ' (до ' + Y.N.offlain_hodyn + ' год, удвічі повільніше, ніж при вас) — вистачить на ' + vulytsZa(zv.za_nich + S.storinky) + '.</div>';
    h += '<div class="pidpyska"><b>З підпискою «Мій район»</b> (у прототипі вимкнено): усі події кожної відкритої вулиці за 10 років з описами, друга справа дня, помічники читають без вас до 24 годин. Гра без підписки — повна: нічого не закрито назавжди.</div>';
    return h;
  }

  function vulytsZa(n) {
    var k = 0, s = { vulytsi: S.vulytsi.slice() };
    while (k < 50) { var c = Y.tsinaVulytsi(s); if (n < c) break; n -= c; s.vulytsi.push('x' + k); k++; }
    return k + ' ' + slovo(k, VULS);
  }

  function zadacha(id, nazva, varianty, pravylna, nazvaF, d) {
    var vid = d.vidpovidi[id];
    var h = '<div class="zadacha' + (vid != null ? ' zadacha--zrobleno' : '') + '"><div class="zadacha__nazva">' + esc(nazva) + '<span class="zadacha__mitka">' +
      (vid == null ? 'одна спроба' : vid === pravylna ? 'так · година натхнення' : 'ні · правильно позначено') + '</span></div><div class="varianty">';
    varianty.forEach(function (v) {
      var kl = vid == null ? '' : v === pravylna ? ' pravylno' : v === vid ? ' ni' : '';
      h += '<button class="klavisha' + kl + '" data-zadacha="' + id + '" data-v="' + esc(v) + '"' + (vid != null ? ' disabled' : '') + '>' + esc(nazvaF(v)) + '</button>';
    });
    return h + '</div></div>';
  }

  // ---------------------------------------------------------------- дії
  $('vmist').addEventListener('click', function (e) {
    var t = teper(), b;
    if ((b = e.target.closest('#chytaty'))) {
      var n = Y.dotyk(S, D.vydy, t);
      var s = document.createElement('span'); s.className = 'vylit'; s.textContent = '+' + ch(Math.max(1, n));
      b.appendChild(s); setTimeout(function () { s.remove(); }, 800);
      pidpysaty(); malyuvaty(); return;
    }
    if ((b = e.target.closest('[data-naiaty]'))) { if (Y.naiaty(S, b.getAttribute('data-naiaty'))) { zberehty(); malyuvaty(true); } return; }
    if ((b = e.target.closest('[data-obraty]'))) { e.preventDefault(); obrana = b.getAttribute('data-obraty'); if (vkladka !== 'vulytsi') perekliuchyty('vulytsi'); else malyuvaty(true); letityDoVulytsi(VUL[obrana]); return; }
    if ((b = e.target.closest('#nazad'))) { obrana = null; malyuvaty(true); return; }
    if ((b = e.target.closest('[data-rayon-novyi]'))) { var r = b.getAttribute('data-rayon-novyi'); if (Y.vidkrytyRayon(S, r)) { zberehty(); tost(r + ' район відкрито.'); letityDoRayonu(r); malyuvaty(true); } return; }
    if ((b = e.target.closest('[data-vidkryty]'))) {
      var v = VUL[b.getAttribute('data-vidkryty')];
      var res = Y.vidkrytyVulytsiu(S, v, D.podii);
      if (res.ok) {
        var dn = Y.perevirytyVulytsi(S, t);
        zberehty();
        tost(v.nazva + ' — у літописі.' + (res.novi_karty.length ? ' Нові картки: ' + res.novi_karty.map(nazvaVydu).join(', ') + '.' : '') + (res.novyi_rayon ? ' Можна відкрити новий район.' : '') + (dn ? ' Задачу дня виконано: година натхнення.' : ''), 4500);
        malyuvaty(true);
      }
      return;
    }
    if ((b = e.target.closest('#vydannia'))) {
      var a = Y.noveVydannia(S); if (a) { zberehty(); tost('Нове видання: +' + a + ' авторитету. Читання тепер ×' + Y.mnozhnyk(S, D.vydy).toFixed(2).replace('.', ',') + '.'); malyuvaty(true); }
      return;
    }
    if ((b = e.target.closest('[data-zadacha]'))) {
      var d = Y.den(S, t), sp = Y.spravaDnia(d.data, D), id = b.getAttribute('data-zadacha');
      var ok = Y.vidpovisty(S, t, id, b.getAttribute('data-v'), id === 'sprava' ? sp.vyd : sp.rayon);
      if (ok != null) { zberehty(); tost(ok ? 'Так. Година натхнення: читання ×2.' : 'Ні — правильну відповідь позначено. Задачу зараховано.'); malyuvaty(true); }
      return;
    }
  });

  // ---------------------------------------------------------------- годинник
  var ostanniiPidpys = 0;
  function pidpysaty() {
    if (!S) return;
    $('storinky').textContent = ch(S.storinky);
    $('za-sek').textContent = ch(Y.zaSek(S, D.vydy, teper()));
    $('seriia').textContent = S.seriia.dniv;
  }
  function tik() {
    if (!S || document.hidden) return;
    Y.plyn(S, D.vydy, teper());
    pidpysaty();
    var t = Date.now(); if (t - ostanniiPidpys > 500) { ostanniiPidpys = t; malyuvaty(); }
  }
})();

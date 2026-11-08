// Карти сайту «Моя вулиця» (ZAVDANNYA-10): карта Києва шестикутниками і карта вулиці з точками.
//
// Вигляд — лише з системи дизайну: кольори з CSS-змінних (data-1…5, accent, ink), шрифти — наші.
// Підкладка — OpenFreeMap (відкрита, без ключа, дані OpenStreetMap) з власним тихим стилем.
// Якщо підкладка не вантажиться (немає мережі), видно межу Києва з власного файлу й дані.
// Чутливі справи (MV-4) — лише в числі сот рівня 8, у групі «Насильство».
(function () {
  'use strict';

  var PIDKLADKA = 'https://tiles.openfreemap.org/planet';
  var SHRYFTY = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf';
  var OSM = '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© учасники OpenStreetMap</a>';
  var KYIV = [[30.2361, 50.2132], [30.8264, 50.5908]];
  var RAMKA = [[29.90, 50.08], [31.16, 50.72]];
  var KOREN = document.documentElement.getAttribute('data-koren') || '/';

  function zminna(n) { return getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim(); }
  function porozhnio() { return { type: 'FeatureCollection', features: [] }; }
  function chyslo(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
  function el(teg, klas, tekst) { var e = document.createElement(teg); if (klas) e.className = klas; if (tekst != null) e.textContent = tekst; return e; }

  function maska(mezha) {
    var zovni = [[RAMKA[0][0] - 2, RAMKA[0][1] - 2], [RAMKA[1][0] + 2, RAMKA[0][1] - 2],
      [RAMKA[1][0] + 2, RAMKA[1][1] + 2], [RAMKA[0][0] - 2, RAMKA[1][1] + 2], [RAMKA[0][0] - 2, RAMKA[0][1] - 2]];
    var g = mezha && mezha.geometry;
    var poly = !g ? [] : g.type === 'MultiPolygon' ? g.coordinates : [g.coordinates];
    return { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [zovni].concat(poly.map(function (p) { return p[0]; })) } };
  }

  function osnova(k) {
    var dorohy = function (klasy) { return ['all', ['==', ['geometry-type'], 'LineString'], ['in', ['get', 'class'], ['literal', klasy]]]; };
    var shyryna = function (a, b, c) { return ['interpolate', ['exponential', 1.6], ['zoom'], 10, a, 14, b, 18, c]; };
    var nazva = ['coalesce', ['get', 'name:uk'], ['get', 'name']];
    return [
      { id: 'tlo', type: 'background', paint: { 'background-color': k.ground } },
      { id: 'zelen', type: 'fill', source: 'osnova', 'source-layer': 'park', paint: { 'fill-color': k.zelen } },
      { id: 'voda', type: 'fill', source: 'osnova', 'source-layer': 'water', paint: { 'fill-color': k.voda } },
      { id: 'budynky', type: 'fill', source: 'osnova', 'source-layer': 'building', minzoom: 14, paint: { 'fill-color': k.zabudova, 'fill-outline-color': k.line } },
      { id: 'vulytsi-ramka', type: 'line', source: 'osnova', 'source-layer': 'transportation', minzoom: 12, filter: dorohy(['minor', 'service', 'tertiary', 'secondary']), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': k.vulytsiaRamka, 'line-width': shyryna(0.5, 4, 18) } },
      { id: 'vulytsi', type: 'line', source: 'osnova', 'source-layer': 'transportation', minzoom: 12, filter: dorohy(['minor', 'service', 'tertiary', 'secondary']), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': k.vulytsia, 'line-width': shyryna(0.3, 2.6, 15) } },
      { id: 'magistrali', type: 'line', source: 'osnova', 'source-layer': 'transportation', filter: dorohy(['motorway', 'trunk', 'primary']), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': k.lineStrong, 'line-width': shyryna(0.8, 4.4, 20) } },
      { id: 'za-mezhamy', type: 'fill', source: 'maska', paint: { 'fill-color': k.zaMezhamy, 'fill-opacity': 0.72 } },
      { id: 'mezha', type: 'line', source: 'mezha', paint: { 'line-color': k.lineStrong, 'line-width': 1.5 } },
      { id: 'pidpysy', type: 'symbol', source: 'osnova', 'source-layer': 'transportation_name', minzoom: 14, layout: { 'symbol-placement': 'line', 'text-field': nazva, 'text-font': ['Noto Sans Regular'], 'text-size': 11 }, paint: { 'text-color': k.muted, 'text-halo-color': k.ground, 'text-halo-width': 1.5 } }
    ];
  }

  function kolory() {
    return {
      ground: zminna('ground'), surface: zminna('surface'), ink: zminna('ink'), muted: zminna('muted'), line: zminna('line'),
      lineStrong: zminna('line-strong'), accent: zminna('accent'), voda: zminna('karta-voda'), zelen: zminna('karta-zelen'),
      zabudova: zminna('karta-zabudova'), vulytsia: zminna('karta-vulytsia'), vulytsiaRamka: zminna('karta-vulytsia-ramka'),
      zaMezhamy: zminna('karta-za-mezhamy'),
      d: [zminna('data-1'), zminna('data-2'), zminna('data-3'), zminna('data-4'), zminna('data-5')]
    };
  }

  function stvoryty(konteiner, sharyDanykh, dzherelaDanykh, ramka, vidstup) {
    maplibregl.setWorkerUrl(KOREN + 'sait/biblioteka/maplibre-gl-csp-worker.js');
    var k = kolory();
    var dzherela = {
      osnova: { type: 'vector', url: PIDKLADKA },
      mezha: { type: 'geojson', data: porozhnio(), attribution: OSM },
      maska: { type: 'geojson', data: porozhnio() }
    };
    Object.keys(dzherelaDanykh).forEach(function (n) { dzherela[n] = dzherelaDanykh[n]; });
    var telefon = window.matchMedia('(max-width: 600px)').matches;
    var karta = new maplibregl.Map({
      container: konteiner,
      style: { version: 8, glyphs: SHRYFTY, sources: dzherela, layers: osnova(k).concat(sharyDanykh(k)) },
      bounds: ramka || KYIV, fitBoundsOptions: { padding: 24, maxZoom: 14.5 },
      maxBounds: RAMKA, minZoom: 8.5, maxZoom: 18,
      dragRotate: false, pitchWithRotate: false, touchPitch: false,
      attributionControl: false, renderWorldCopies: false, fadeDuration: 0, cooperativeGestures: false
    });
    karta.touchZoomRotate.disableRotation();
    // Розмір рамки міг змінитися після створення (шрифти, кнопки в кілька рядків) — підлаштовуємо карту.
    if (window.ResizeObserver) {
      new ResizeObserver(function () { karta.resize(); }).observe(konteiner);
    }
    karta.once('load', function () { karta.resize(); if (!ramka) karta.fitBounds(KYIV, { padding: vidstup || 24, duration: 0 }); });
    karta.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    karta.addControl(new maplibregl.AttributionControl({ compact: telefon }), 'bottom-right');

    var zboi = konteiner.parentNode.querySelector('.karta__zboi');
    karta.on('error', function (e) {
      var t = String((e && e.error && e.error.message) || '');
      if ((e && e.sourceId === 'osnova') || t.indexOf('openfreemap') !== -1 || t.indexOf('Failed to fetch') !== -1) {
        if (zboi) zboi.hidden = false;
      }
    });
    fetch(KOREN + 'sait/mezha-kyieva.geojson', { credentials: 'omit' })
      .then(function (v) { return v.ok ? v.json() : null; })
      .then(function (g) {
        if (!g) return;
        var z = function () { karta.getSource('mezha').setData(g); karta.getSource('maska').setData(maska(g)); };
        if (karta.loaded()) z(); else karta.once('load', z);
      }).catch(function () {});
    window.MvKarta = { karta: karta };
    return karta;
  }

  // ---------- Карта Києва шестикутниками ----------
  // Поведінка — як у навчальній карті Києва (SPECYFIKATSIYA S-К.4, S-К.6, S-К.13, S-К.18, S-К.21),
  // вигляд — наш. Дві сітки H3: рівень 8 (≈0,7 км²) до z12,3, рівень 9 (≈0,1 км²) далі; у смузі
  // навколо порогу великі соти плавно гаснуть, малі проступають, а стовпчики 3D осідають і виростають
  // (висота — interpolate за зумом, поза смугою — рівно один шар). Колір — вид з найбільшим
  // «частка тут ÷ частка по Києву» (≥ max(3, 10%) подій), інакше найчисленніший. Прозорість — ранг
  // кількості: прозоріше — менше подій.
  var HRUPY = [['dtp', 'ДТП'], ['dor', 'Дороги'], ['hp', 'Громадський порядок'], ['mai', 'Майно'],
    ['nar', 'Наркотики'], ['alk', 'Алкоголь'], ['nas', 'Насильство']];
  var NAZVA = {}; HRUPY.forEach(function (h) { NAZVA[h[0]] = h[1]; });
  var RIVNI = [{ r: 8, id: 'L', R: 330, ploshcha: '≈0,7 км²' }, { r: 9, id: 'S', R: 130, ploshcha: '≈0,1 км²' }];
  var PORIH = 12.3, SMUHA = 0.4;
  var FADE = { L: [[0, 1], [12.3, 1], [12.8, 0]], S: [[12.0, 0], [12.4, 1]] };
  var COL_ZUM = { L: [0, PORIH + SMUHA], S: [PORIH - SMUHA, 24] };
  var TSIL_PIDPYS = { mai: 'беруть', dtp: 'зіткнення з', nar: 'речовина', alk: 'продають', hp: 'на кого' };

  function fadeBy(id, v) {
    var st = [];
    FADE[id].forEach(function (x) { st.push(x[0], x[1] ? v : 0); });
    return ['interpolate', ['linear'], ['zoom']].concat(st);
  }
  function colVysota(id) {
    var a = COL_ZUM[id][0], b = COL_ZUM[id][1], h = ['get', 'h'], st = [];
    if (a > 0) st.push(a, 0, a + 2 * SMUHA, h); else st.push(0, h);
    if (b < 24) st.push(b - 2 * SMUHA, h, b, 0);
    return st.length > 2 ? ['interpolate', ['linear'], ['zoom']].concat(st) : h;
  }
  function pitch3d(z) { return Math.round(55 - 35 * Math.min(1, Math.max(0, (z - 11) / 5))); }
  function temna() { return window.matchMedia('(prefers-color-scheme: dark)').matches; }
  function telefon() { return window.matchMedia('(max-width: 700px)').matches; }

  function kolirMistsia(g, mg, mn) {
    var best = null, bn = 0, n = 0;
    HRUPY.forEach(function (h) { var v = g[h[0]] || 0; n += v; if (v > bn) { bn = v; best = h[0]; } });
    if (!mn) return best;
    var min = Math.max(3, 0.1 * n), br = 0;
    HRUPY.forEach(function (h) {
      var v = g[h[0]] || 0;
      if (v < min || !mg[h[0]]) return;
      var r = (v / n) / (mg[h[0]] / mn);
      if (r > br) { br = r; best = h[0]; }
    });
    return best;
  }

  function zmenshyty(kontur, k) {
    var cx = 0, cy = 0, m = kontur.length - 1;
    for (var i = 0; i < m; i++) { cx += kontur[i][0]; cy += kontur[i][1]; }
    cx /= m; cy /= m;
    return kontur.map(function (p) { return [cx + (p[0] - cx) * k, cy + (p[1] - cy) * k]; });
  }

  function kartaMista(konteiner) {
    var panel = document.getElementById('panel');
    var pidkazka = document.getElementById('pidkazka');
    var stan = { vydy: {}, period: '3', tryD: false, obrana: null };
    HRUPY.forEach(function (h) { stan.vydy[h[0]] = true; });
    var dani = {}, obrakhovano = {}, karta = null, kol = null;

    function chysloG(p, g) { return Number(p[g + stan.period] || 0); }
    function chysloSoty(p) { var n = 0; HRUPY.forEach(function (h) { if (stan.vydy[h[0]]) n += chysloG(p, h[0]); }); return n; }

    function obrakhuvaty(rv) {
      var d = dani[rv.r]; if (!d) return null;
      var fs = d.soty.features, mg = {}, mn = 0;
      HRUPY.forEach(function (h) { mg[h[0]] = 0; });
      var ryad = fs.map(function (f) {
        var g = {}, n = 0;
        HRUPY.forEach(function (h) { var v = stan.vydy[h[0]] ? chysloG(f.properties, h[0]) : 0; g[h[0]] = v; n += v; mg[h[0]] += v; });
        mn += n;
        return { f: f, g: g, n: n };
      }).filter(function (x) { return x.n > 0; });
      var ns = ryad.map(function (x) { return x.n; }).sort(function (a, b) { return a - b; });
      var p95 = Math.max(1, ns.length ? ns[Math.min(ns.length - 1, Math.floor(ns.length * 0.95))] : 1);
      var med = ns.length ? ns[ns.length >> 1] : 0;
      var poriadok = ryad.slice().sort(function (a, b) { return a.n - b.n; });
      var L = poriadok.length, d1 = temna();
      poriadok.forEach(function (x, i) {
        var rank = L > 1 ? i / (L - 1) : 1;
        // прозоріше, ніж у навчальній карті: підкладку видно крізь соти
        x.a = d1 ? Math.min(0.55, 0.1 + 0.5 * rank * rank) : Math.min(0.5, 0.04 + 0.5 * rank * rank);
        x.gi = kolirMistsia(x.g, mg, mn);
      });
      var soty = { type: 'FeatureCollection', features: ryad.map(function (x) {
        return { type: 'Feature', geometry: x.f.geometry, properties: { id: x.f.properties.id, c: kol[x.gi], a: x.a, n: x.n } };
      }) };
      var stovp = { type: 'FeatureCollection', features: ryad.filter(function (x) { return x.n >= med; }).map(function (x) {
        return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [zmenshyty(x.f.geometry.coordinates[0], 0.62)] },
          properties: { id: x.f.properties.id, c: kol[x.gi], n: x.n, h: rv.R * 7 * (0.12 + 0.88 * Math.sqrt(Math.min(1, x.n / p95))) } };
      }) };
      var ser = ns.length ? ns.reduce(function (a, b) { return a + b; }, 0) / ns.length : 0;
      return { soty: soty, stovp: stovp, ser: ser, mg: mg, mn: mn, ryad: ryad };
    }

    function onovyty() {
      if (!karta || !karta.getSource('soty-L')) return;
      RIVNI.forEach(function (rv) {
        var o = obrakhuvaty(rv);
        if (!o) return;
        obrakhovano[rv.r] = o;
        karta.getSource('soty-' + rv.id).setData(o.soty);
        karta.getSource('stovp-' + rv.id).setData(o.stovp);
        karta.setLayoutProperty('soty-' + rv.id, 'visibility', stan.tryD ? 'none' : 'visible');
        karta.setLayoutProperty('sotyl-' + rv.id, 'visibility', stan.tryD ? 'none' : 'visible');
        karta.setLayoutProperty('stovp-' + rv.id, 'visibility', stan.tryD ? 'visible' : 'none');
      });
      var o8 = obrakhovano[8];
      if (o8) {
        document.getElementById('vsogo-podii').textContent = chyslo(o8.mn);
        document.getElementById('vsogo-pidpys').textContent = slovo(o8.mn, ['подія на карті', 'події на карті', 'подій на карті']) + (stan.period === '3' ? ' за останні 3 роки' : ' за всі роки');
        HRUPY.forEach(function (h) {
          var b = document.querySelector('[data-chyslo="' + h[0] + '"]');
          var v = 0; dani[8].soty.features.forEach(function (f) { v += chysloG(f.properties, h[0]); });
          if (b) b.textContent = chyslo(v);
        });
      }
      if (stan.obrana) pokazatyPanel(stan.obrana, false);
    }

    function shary(k) {
      var L = [];
      RIVNI.forEach(function (rv) {
        var id = rv.id;
        L.push({ id: 'soty-' + id, type: 'fill', source: 'soty-' + id, paint: { 'fill-color': ['get', 'c'], 'fill-opacity': fadeBy(id, ['get', 'a']) } });
        L.push({ id: 'sotyl-' + id, type: 'line', source: 'soty-' + id, paint: { 'line-color': temna() ? 'rgba(0,0,0,.35)' : 'rgba(255,255,255,.55)', 'line-width': 0.6, 'line-opacity': fadeBy(id, 1) } });
        L.push({ id: 'stovp-' + id, type: 'fill-extrusion', source: 'stovp-' + id, minzoom: COL_ZUM[id][0], maxzoom: COL_ZUM[id][1],
          layout: { visibility: 'none' }, paint: { 'fill-extrusion-color': ['get', 'c'], 'fill-extrusion-height': colVysota(id), 'fill-extrusion-opacity': 0.82 } });
      });
      L.push({ id: 'obrana-oreol', type: 'line', source: 'obrana', paint: { 'line-color': k.surface, 'line-width': 5 } });
      L.push({ id: 'obrana', type: 'line', source: 'obrana', paint: { 'line-color': k.ink, 'line-width': 2 } });
      return L;
    }

    function zavantazhyty(r) {
      return fetch(konteiner.getAttribute('data-soty-' + r), { credentials: 'omit' }).then(function (v) { return v.json(); })
        .then(function (d) { dani[r] = d; return d; });
    }

    kol = {};
    HRUPY.forEach(function (h) { kol[h[0]] = zminna('vyd-' + h[0]); });
    var dzherela = { obrana: { type: 'geojson', data: porozhnio() } };
    RIVNI.forEach(function (rv) { dzherela['soty-' + rv.id] = { type: 'geojson', data: porozhnio() }; dzherela['stovp-' + rv.id] = { type: 'geojson', data: porozhnio() }; });
    // Старт — увесь Київ з урахуванням панелі (S-К.23): на ПК панель праворуч, на телефоні — смуга внизу.
    var keruvannia = document.getElementById('keruvannia');
    var vidstup = telefon() ? { top: 20, left: 20, right: 20, bottom: (keruvannia ? keruvannia.offsetHeight : 0) + 20 }
      : { top: 30, left: 30, bottom: 30, right: (keruvannia ? keruvannia.offsetWidth : 0) + 50 };
    karta = stvoryty(konteiner, shary, dzherela, null, vidstup);
    window.MvKarta.gotovo = false;
    karta.once('load', function () {
      zavantazhyty(8).then(function () { onovyty(); window.MvKarta.gotovo = true; return zavantazhyty(9); }).then(onovyty);
    });
    karta.on('zoomend', function () {
      if (stan.tryD && Math.abs(karta.getPitch() - pitch3d(karta.getZoom())) > 2) karta.easeTo({ pitch: pitch3d(karta.getZoom()), duration: 300 });
    });

    function rivenZaraz() { return karta.getZoom() < PORIH ? RIVNI[0] : RIVNI[1]; }
    function znaity(tochka) {
      var rv = rivenZaraz();
      var shar = (stan.tryD ? 'stovp-' : 'soty-') + rv.id;
      var f = karta.queryRenderedFeatures(tochka, { layers: [shar] })[0];
      if (!f) return null;
      var id = f.properties.id;
      var dzh = dani[rv.r] && dani[rv.r].soty.features.filter(function (x) { return x.properties.id === id; })[0];
      return dzh ? { rv: rv, f: dzh } : null;
    }

    karta.on('click', function (e) {
      var z = znaity(e.point);
      if (!z) { zakryty(); return; }
      stan.obrana = z;
      pokazatyPanel(z, true);
    });
    karta.on('mousemove', function (e) {
      if (telefon()) return;
      var z = znaity(e.point);
      karta.getCanvas().style.cursor = z ? 'pointer' : '';
      if (!z) { pidkazka.hidden = true; return; }
      var n = chysloSoty(z.f.properties);
      pidkazka.textContent = chyslo(n) + ' ' + slovo(n, ['подія', 'події', 'подій']);
      pidkazka.style.left = (e.point.x + 14) + 'px'; pidkazka.style.top = (e.point.y + 14) + 'px';
      pidkazka.hidden = false;
    });
    karta.on('mouseout', function () { pidkazka.hidden = true; });

    function zakryty() {
      panel.hidden = true; stan.obrana = null;
      document.body.classList.remove('kartka-vidkryta');
      if (karta.getSource('obrana')) karta.getSource('obrana').setData(porozhnio());
    }
    document.getElementById('panel-zakryty').addEventListener('click', zakryty);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !panel.hidden) zakryty(); });

    document.querySelectorAll('[data-hrupa]').forEach(function (b) {
      b.addEventListener('click', function () {
        var g = b.getAttribute('data-hrupa');
        stan.vydy[g] = !stan.vydy[g];
        if (!HRUPY.some(function (h) { return stan.vydy[h[0]]; })) stan.vydy[g] = true;   // хоч один вид
        b.setAttribute('aria-pressed', String(stan.vydy[g]));
        onovyty();
      });
    });
    document.querySelectorAll('[data-period]').forEach(function (b) {
      b.addEventListener('click', function () {
        stan.period = b.getAttribute('data-period');
        document.querySelectorAll('[data-period]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        onovyty();
      });
    });
    var rozg = document.getElementById('vydy-rozgornuty');
    rozg.addEventListener('click', function () {
      var t = rozg.getAttribute('aria-expanded') !== 'true';
      rozg.setAttribute('aria-expanded', String(t));
      document.getElementById('keruvannia').classList.toggle('rozgornuto', t);
    });
    var k3 = document.getElementById('knopka-3d');
    k3.addEventListener('click', function () {
      stan.tryD = !stan.tryD;
      k3.setAttribute('aria-pressed', String(stan.tryD));
      k3.textContent = stan.tryD ? '2D' : '3D';
      k3.setAttribute('aria-label', stan.tryD ? 'Показати плоскими сотами' : 'Показати стовпчиками');
      karta.easeTo({ pitch: stan.tryD ? pitch3d(karta.getZoom()) : 0, duration: 700 });
      onovyty();
    });

    function masyv(x) { return typeof x === 'string' ? JSON.parse(x) : (x || []); }
    function obiekt(x) { return typeof x === 'string' ? JSON.parse(x) : (x || {}); }

    function pokazatyPanel(z, zsunuty) {
      var p = z.f.properties, rv = z.rv;
      var o = obrakhovano[rv.r];
      var vmist = document.getElementById('panel-vmist');
      vmist.textContent = '';
      var n = chysloSoty(p);
      vmist.appendChild(el('p', 'mikro', 'Шестикутник ' + rv.ploshcha + ' · ' + (stan.period === '3' ? 'останні 3 роки' : 'усі роки')));
      var h = el('p', 'kartka-soty__chyslo');
      h.appendChild(el('b', 'chyslo-velyke', chyslo(n)));
      h.appendChild(el('span', null, ' ' + slovo(n, ['подія', 'події', 'подій']) + ' у даних'));
      vmist.appendChild(h);
      if (o) vmist.appendChild(el('p', 'kartka-soty__porivn', porivniannia(n, o.ser)));

      // Усі 7 груп числами
      var tabl = el('table', 'tablytsia-vydiv');
      var cap = el('caption', 'mikro', 'За видами'); tabl.appendChild(cap);
      var maks = 1; HRUPY.forEach(function (x) { maks = Math.max(maks, chysloG(p, x[0])); });
      var tb = el('tbody');
      HRUPY.forEach(function (x) {
        var v = chysloG(p, x[0]);
        var tr = el('tr'); if (!stan.vydy[x[0]]) tr.className = 'vymkneno';
        var td1 = el('th'); td1.scope = 'row';
        td1.appendChild(el('i', 'vyd-krapka vyd-' + x[0])); td1.appendChild(document.createTextNode(x[1]));
        var td2 = el('td', 'tablytsia-vydiv__smuha'); var sm = el('i', 'vyd-' + x[0]); sm.style.width = Math.round(v / maks * 100) + '%'; td2.appendChild(sm);
        var td3 = el('td', null, v ? chyslo(v) : '—');
        tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3); tb.appendChild(tr);
      });
      tabl.appendChild(tb); vmist.appendChild(tabl);
      if (rv.r === 9) vmist.appendChild(el('p', 'prymitka-mala', 'Справи про домашнє насильство й щодо дітей — лише у великих сотах.'));

      var pr = masyv(p.p);
      if (pr.length) {
        var bl = el('div', 'problema');
        bl.appendChild(el('p', 'mikro', 'Повторюється тут'));
        pr.forEach(function (x) { bl.appendChild(el('p', null, x)); });
        vmist.appendChild(bl);
      }
      var t = obiekt(p.t), ryadky = [];
      HRUPY.forEach(function (x) {
        if (!t[x[0]]) return;
        ryadky.push([x[0], x[1] + ' · ' + TSIL_PIDPYS[x[0]] + ': ' + t[x[0]].map(function (y) { return y[0] + ' (' + y[1] + ')'; }).join(', ')]);
      });
      if (ryadky.length) {
        vmist.appendChild(el('p', 'mikro', 'Що найчастіше в рішеннях · усі роки'));
        var ul = el('ul', 'tsili');
        ryadky.forEach(function (r) { var li = el('li'); li.appendChild(el('i', 'vyd-krapka vyd-' + r[0])); li.appendChild(document.createTextNode(r[1])); ul.appendChild(li); });
        vmist.appendChild(ul);
      }
      if (p.h) {
        var ph = el('p', 'kartka-soty__pik'); ph.appendChild(el('span', 'mikro', 'Година-пік · усі роки'));
        ph.appendChild(el('b', null, p.h)); vmist.appendChild(ph);
      }
      var y = masyv(p.y);
      if (y.length) {
        vmist.appendChild(el('p', 'mikro', 'За роками · усі види'));
        var mk = Math.max.apply(null, y.concat([1]));
        var r = el('div', 'roky-mali');
        y.forEach(function (v, i) {
          var c = el('span'); c.title = (2016 + i) + ': ' + v;
          var st = el('i'); st.style.height = Math.max(v ? 2 : 1, Math.round(v / mk * 48)) + 'px'; c.appendChild(st); r.appendChild(c);
        });
        vmist.appendChild(r);
        var ps = el('div', 'roky-mali__vis'); ps.appendChild(el('span', null, '2016')); ps.appendChild(el('span', null, '2021')); ps.appendChild(el('span', null, '2026'));
        vmist.appendChild(ps);
      }
      var vul = masyv(p.u);
      if (vul.length) {
        vmist.appendChild(el('p', 'mikro', 'Вулиці в соті'));
        var u2 = el('p', 'vulytsi-soty');
        vul.forEach(function (v, i) { var a = el('a', null, v[1]); a.href = KOREN + 'vulytsia/' + v[0] + '/'; if (i) u2.appendChild(document.createTextNode(' · ')); u2.appendChild(a); });
        vmist.appendChild(u2);
      }
      if (Number(p.a) > 0) {
        var zm = el('p', 'zamok', chyslo(Number(p.a)) + ' ' + slovo(Number(p.a), ['подія', 'події', 'подій']) + ' з адресами й описами — у підписці');
        zm.setAttribute('aria-disabled', 'true');
        vmist.appendChild(zm);
      }
      panel.hidden = false;
      document.body.classList.add('kartka-vidkryta');
      karta.getSource('obrana').setData({ type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: z.f.geometry }] });
      if (zsunuty) {
        // Обрана сота лишається видимою: на ПК — праворуч від картки, на телефоні — над шторкою.
        var c = z.f.geometry.coordinates[0][0];
        var pad = telefon() ? { top: 40, bottom: panel.offsetHeight + 20, left: 20, right: 20 } : { left: panel.offsetWidth + 40, right: 340, top: 40, bottom: 40 };
        var pt = karta.project(c), w = karta.getContainer();
        var vydno = pt.x > pad.left && pt.x < w.clientWidth - pad.right && pt.y > pad.top && pt.y < w.clientHeight - pad.bottom;
        // Зсув (offset), а не padding: padding у MapLibre лишається назавжди й разом із межами руху
        // карти (maxBounds) зсуває огляд. На огляді міста карта впирається в межі — тож трохи наближаємо.
        if (!vydno) {
          var zsuv = [(pad.left - pad.right) / 2, (pad.top - pad.bottom) / 2];
          karta.easeTo({ center: c, zoom: Math.max(karta.getZoom(), 10.5), offset: zsuv, duration: 450 });
        }
      }
    }
  }

  function porivniannia(n, ser) {
    if (!ser) return '';
    var r = n / ser;
    if (r >= 0.8 && r <= 1.25) return 'Приблизно як у середній соті Києва.';
    var t = (r > 1 ? r : 1 / r).toFixed(1).replace('.', ',');
    return r > 1 ? 'У ' + t + ' раза більше, ніж у середній соті Києва.' : 'У ' + t + ' раза менше, ніж у середній соті Києва.';
  }

  function slovo(n, f) {
    var m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return f[0];
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return f[1];
    return f[2];
  }

  // ---------- Карта вулиці: соти рівня 9 з числом подій, без будинків ----------
  function kartaVulytsi(konteiner) {
    var soty = JSON.parse(document.getElementById('soty-vulytsi').textContent);
    var ramka = null;
    soty.features.forEach(function (f) {
      f.geometry.coordinates[0].forEach(function (c) {
        if (!ramka) ramka = [[c[0], c[1]], [c[0], c[1]]];
        ramka[0][0] = Math.min(ramka[0][0], c[0]); ramka[0][1] = Math.min(ramka[0][1], c[1]);
        ramka[1][0] = Math.max(ramka[1][0], c[0]); ramka[1][1] = Math.max(ramka[1][1], c[1]);
      });
    });
    stvoryty(konteiner, function (k) {
      return [
        { id: 'soty', type: 'fill', source: 'soty', paint: { 'fill-color': ['match', ['get', 'k'], 1, k.d[0], 2, k.d[1], 3, k.d[2], 4, k.d[3], k.d[4]], 'fill-opacity': 0.9 } },
        { id: 'soty-mezha', type: 'line', source: 'soty', paint: { 'line-color': k.d[4], 'line-width': 1, 'line-opacity': 0.5 } }
      ];
    }, { soty: { type: 'geojson', data: soty } }, ramka);
  }

  var m = document.getElementById('karta-mista');
  if (m) kartaMista(m);
  var v = document.getElementById('karta-vulytsi');
  if (v) kartaVulytsi(v);
})();

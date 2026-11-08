// Сцена ролика «Моєї вулиці» (ZAVDANNYA-11).
//
// Ідея — «тур» з навчальної карти Києва (karta-kyiv-kod, site_src/tur.js): камера летить дугою
// від зупинки до зупинки з нахилом ~50°, на зупинці повільно обертається, знизу — картка.
// Тут те саме, але покадрово: window.kadr(t) ставить камеру й картки на момент t (секунди),
// чекає, доки карта домалюється, — і рендер робить знімок. Тому ролик однаковий за будь-якої
// швидкості комп'ютера, і жоден кадр не «пропадає».
//
// Два вигляди карти (?rezhym=):
//   skhema    — без підкладки: межа Києва (OpenStreetMap), соти з кількістю подій, точки. Без мережі.
//   pidkladka — те саме поверх вулиць OpenFreeMap (потрібна мережа до tiles.openfreemap.org).
(function () {
  'use strict';

  var P = new URLSearchParams(location.search);
  var REZHYM = P.get('rezhym') === 'pidkladka' ? 'pidkladka' : 'skhema';
  var STSENARII = P.get('s');

  var OSNOVA = 'https://tiles.openfreemap.org/planet';
  var SHRYFTY = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf';
  var MISTO = { center: [30.523, 50.452], zoom: 9.75, pitch: 0, bearing: 0 };
  var ZUM_ZUPYNKY = REZHYM === 'skhema' ? 12.8 : 15.4;
  var ZUM_VULYTSI = REZHYM === 'skhema' ? 13.4 : 14.4;
  var VIDSTUP = { top: 260, bottom: 1000, left: 0, right: 140 };   // точка — над карткою, лівіше правих 15 %
  var LIT = 1.8;           // політ між зупинками, с
  var POYAVA = 0.35;       // поява картки, с

  function zminna(n) { return getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim(); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function zatysk(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function plavno(u) { u = zatysk(u, 0, 1); return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; }
  function lerp(a, b, u) { return a + (b - a) * u; }
  function fc(features) { return { type: 'FeatureCollection', features: features || [] }; }
  function tochka(lon, lat) { return { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [lon, lat] } }; }

  function kolo(lon, lat, m) {
    var c = [], kx = 111320 * Math.cos(lat * Math.PI / 180), ky = 110540;
    for (var i = 0; i <= 96; i++) { var a = i / 96 * 2 * Math.PI; c.push([lon + m * Math.cos(a) / kx, lat + m * Math.sin(a) / ky]); }
    return { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: c } };
  }

  function maska(mezha) {
    var z = [[26, 47], [36, 47], [36, 54], [26, 54], [26, 47]];
    var g = mezha.geometry, p = g.type === 'MultiPolygon' ? g.coordinates : [g.coordinates];
    // світ мінус Київ; «дірки» в межі Києва (анклави) — теж поза містом, тож їх зафарбовуємо окремо
    var dirky = [];
    p.forEach(function (x) { x.slice(1).forEach(function (r) { dirky.push([r]); }); });
    return { type: 'Feature', properties: {}, geometry: { type: 'MultiPolygon', coordinates: [[z].concat(p.map(function (x) { return x[0]; }))].concat(dirky) } };
  }

  // ---------- стиль карти ----------
  function styl(mezha, soty) {
    var k = {};
    ['ground', 'surface', 'ink', 'muted', 'line', 'line-strong', 'accent', 'accent-soft', 'data-1', 'data-2', 'data-3', 'data-4', 'data-5',
      'karta-voda', 'karta-zelen', 'karta-zabudova', 'karta-vulytsia', 'karta-vulytsia-ramka', 'karta-za-mezhamy']
      .forEach(function (n) { k[n] = zminna(n); });
    var kolirSoty = ['match', ['get', 'k'], 1, k['data-1'], 2, k['data-2'], 3, k['data-3'], 4, k['data-4'], k['data-5']];
    var dzherela = {
      mezha: { type: 'geojson', data: mezha, attribution: '© учасники OpenStreetMap' },
      maska: { type: 'geojson', data: maska(mezha) },
      soty: { type: 'geojson', data: soty },
      kolo: { type: 'geojson', data: fc() },
      adresa: { type: 'geojson', data: fc() },
      tochka: { type: 'geojson', data: fc() }
    };
    var shary = [{ id: 'tlo', type: 'background', paint: { 'background-color': k.ground } }];
    if (REZHYM === 'pidkladka') {
      dzherela.osnova = { type: 'vector', url: OSNOVA, attribution: 'OpenFreeMap · © OpenMapTiles' };
      var dorohy = function (kl) { return ['all', ['==', ['geometry-type'], 'LineString'], ['in', ['get', 'class'], ['literal', kl]]]; };
      var shyr = function (a, b, c) { return ['interpolate', ['exponential', 1.6], ['zoom'], 10, a, 14, b, 18, c]; };
      shary = shary.concat([
        { id: 'zelen', type: 'fill', source: 'osnova', 'source-layer': 'park', paint: { 'fill-color': k['karta-zelen'] } },
        { id: 'voda', type: 'fill', source: 'osnova', 'source-layer': 'water', paint: { 'fill-color': k['karta-voda'] } },
        { id: 'budynky', type: 'fill', source: 'osnova', 'source-layer': 'building', minzoom: 14, paint: { 'fill-color': k['karta-zabudova'], 'fill-outline-color': k.line } },
        { id: 'vulytsi', type: 'line', source: 'osnova', 'source-layer': 'transportation', minzoom: 12, filter: dorohy(['minor', 'service', 'tertiary', 'secondary']), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': k['karta-vulytsia'], 'line-width': shyr(0.3, 2.6, 15) } },
        { id: 'magistrali', type: 'line', source: 'osnova', 'source-layer': 'transportation', filter: dorohy(['motorway', 'trunk', 'primary']), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': k['line-strong'], 'line-width': shyr(1.2, 5, 22) } }
      ]);
    }
    shary = shary.concat([
      { id: 'soty', type: 'fill', source: 'soty', paint: { 'fill-color': kolirSoty, 'fill-opacity': REZHYM === 'pidkladka' ? 0.55 : 0.92 } },
      { id: 'soty-ramka', type: 'line', source: 'soty', paint: { 'line-color': k.surface, 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.6, 14, 2.5] } },
      { id: 'za-mezhamy', type: 'fill', source: 'maska', paint: { 'fill-color': k['karta-za-mezhamy'], 'fill-opacity': 0.85 } },
      { id: 'mezha', type: 'line', source: 'mezha', layout: { 'line-join': 'round' }, paint: { 'line-color': k['line-strong'], 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 2.5, 14, 5] } },
      { id: 'kolo', type: 'line', source: 'kolo', paint: { 'line-color': k.ink, 'line-width': 4, 'line-dasharray': [2, 1.5] } },
      { id: 'adresa', type: 'circle', source: 'adresa', paint: { 'circle-radius': 16, 'circle-color': k.ink, 'circle-stroke-color': k.surface, 'circle-stroke-width': 6 } },
      { id: 'tochka-oreol', type: 'circle', source: 'tochka', paint: { 'circle-radius': ['get', 'r'], 'circle-color': k.accent, 'circle-opacity': 0.18 } },
      { id: 'tochka-ramka', type: 'circle', source: 'tochka', paint: { 'circle-radius': 30, 'circle-color': k.ink } },
      { id: 'tochka', type: 'circle', source: 'tochka', paint: { 'circle-radius': 20, 'circle-color': k.accent, 'circle-stroke-color': k.surface, 'circle-stroke-width': 7 } }
    ]);
    var s = { version: 8, sources: dzherela, layers: shary };
    if (REZHYM === 'pidkladka') s.glyphs = SHRYFTY;
    return s;
  }

  // ---------- часова шкала ----------
  // Кожен відрізок: {t0, t1, kam(t) → камера, kartka: html, klas, kroky, tochka:[lon,lat]|null, ...}
  function kamZupynky(p, i) { return { center: [p.lon, p.lat], zoom: ZUM_ZUPYNKY, pitch: 50, bearing: -12 + 9 * i }; }

  function polit(a, b, t0, tryv) {
    // дуга як у flyTo: віддаляємось, летимо, наближаємось
    var dx = (b.center[0] - a.center[0]) * 71, dy = (b.center[1] - a.center[1]) * 111;
    var km = Math.sqrt(dx * dx + dy * dy);
    var gorb = Math.min(2.2, Math.max(0, Math.log2(1 + km / 1.5) * 0.9) - Math.max(0, (Math.min(a.zoom, b.zoom) < 11 ? 1 : 0)));
    gorb = Math.max(0, gorb);
    return function (t) {
      var u = zatysk((t - t0) / tryv, 0, 1), e = plavno(u);
      return {
        center: [lerp(a.center[0], b.center[0], e), lerp(a.center[1], b.center[1], e)],
        zoom: lerp(a.zoom, b.zoom, e) - gorb * Math.sin(Math.PI * u),
        pitch: lerp(a.pitch, b.pitch, e),
        bearing: lerp(a.bearing, b.bearing, e)
      };
    };
  }

  function dreif(c, t0, tryv, dBearing, dZoom) {
    return function (t) {
      var u = zatysk((t - t0) / tryv, 0, 1);
      return { center: c.center, zoom: c.zoom + (dZoom || 0) * u, pitch: c.pitch, bearing: c.bearing + (dBearing || 0) * u };
    };
  }

  function zlyty(polit_, lit, dreif_) { return function (t) { return t < lit ? polit_(t) : dreif_(t); }; }

  function kartkaVstupu(v) {
    return '<div class="mitka">' + esc(v.mitka || '') + '</div><div class="zahol">' + esc(v.tekst) + '</div>' +
      (v.pidtekst ? '<div class="pidtekst">' + esc(v.pidtekst) + '</div>' : '');
  }
  function kartkaPodii(p, zAdresoyu) {
    return '<div class="mitka">' + esc(p.koly + ' · ' + p.vyd) + '</div><div class="istoriia">' + esc(p.tekst) + '</div>' +
      (zAdresoyu ? '<div class="adresa">' + esc(p.adresa) + '</div>' : '');
  }

  function zibraty(S) {
    var V = [], t = 0, kam = MISTO;
    function dodaty(v) { v.t0 = t; v.t1 = t + v.tryv; V.push(v); t = v.t1; }
    var v0 = S.vstup;
    // вступ: місто згори, ледь наближаємось
    dodaty({ tryv: v0.tryvalist, kam: dreif(MISTO, t, v0.tryvalist, 0, 0.25), kartka: kartkaVstupu(v0) });
    kam = { center: MISTO.center, zoom: MISTO.zoom + 0.25, pitch: 0, bearing: 0 };

    if (S.shablon === 'tur') {
      S.tochky.forEach(function (p, i) {
        var c = kamZupynky(p, i), d = p.tryvalist;
        dodaty({ tryv: d, kam: zlyty(polit(kam, c, t, LIT), t + LIT, dreif(c, t + LIT, d - LIT, 7, 0.15)),
          kartka: kartkaPodii(p, true), kartkaVid: LIT * 0.55, kroky: (i + 1) + ' / ' + S.tochky.length, tochka: [p.lon, p.lat], tochkaVid: LIT * 0.8 });
        kam = { center: c.center, zoom: c.zoom + 0.15, pitch: c.pitch, bearing: c.bearing + 7 };
      });
    } else if (S.shablon === 'vhadai') {
      S.tochky.forEach(function (p, i) {
        var nm = 'Раунд ' + (i + 1) + ' / ' + S.tochky.length;
        var misto = { center: MISTO.center, zoom: MISTO.zoom, pitch: 0, bearing: 0 };
        var lit0 = i === 0 ? 0.01 : LIT;
        // питання: місто згори, без точки
        dodaty({ tryv: p.pytannya, kam: zlyty(polit(kam, misto, t, lit0), t + lit0, dreif(misto, t + lit0, p.pytannya - lit0, 0, 0.1)),
          kartka: '<div class="mitka">' + esc(p.koly + ' · ' + p.vyd) + '</div><div class="istoriia">' + esc(p.tekst) + '</div><div class="prymitka">Де це було?</div>',
          kroky: nm });
        var m2 = { center: misto.center, zoom: misto.zoom + 0.1, pitch: 0, bearing: 0 };
        // пауза: «Ваш варіант?» і відлік
        var tp = t;
        dodaty({ tryv: p.pauza, kam: dreif(m2, t, p.pauza, 0, 0.08), kroky: nm,
          kartkaF: function (tt) { var n = Math.max(1, Math.ceil(p.pauza - (tt - tp) - 1e-6)); return '<div class="pauza"><div class="zahol">Ваш варіант?</div><div class="vidlik">' + n + '</div></div>'; } });
        var m3 = { center: m2.center, zoom: m2.zoom + 0.08, pitch: 0, bearing: 0 };
        // відповідь: летимо до точки, адреса великим
        var c = kamZupynky(p, i), d = p.tryvalist;
        dodaty({ tryv: d, kam: zlyty(polit(m3, c, t, LIT), t + LIT, dreif(c, t + LIT, d - LIT, 6, 0.12)),
          kartka: '<div class="vidpovid"><div class="mitka">Відповідь</div><div class="adresa">' + esc(p.adresa) + '</div><div class="prymitka">Київ · ' + esc(p.koly) + '</div></div>',
          kartkaVid: LIT * 0.6, kroky: nm, tochka: [p.lon, p.lat], tochkaVid: LIT * 0.7 });
        kam = { center: c.center, zoom: c.zoom + 0.12, pitch: c.pitch, bearing: c.bearing + 6 };
      });
    } else if (S.shablon === 'tsyfry') {
      var C = S.tsentr, c0 = { center: [C.lon, C.lat], zoom: ZUM_VULYTSI, pitch: 45, bearing: -20 };
      S.tochky.forEach(function (f, i) {
        var a = { center: c0.center, zoom: c0.zoom, pitch: c0.pitch, bearing: c0.bearing + 6 * i };
        var lit = i === 0 ? LIT : 0.01, d = f.tryvalist;
        dodaty({ tryv: d, kam: zlyty(polit(kam, a, t, lit), t + lit, dreif(a, t + lit, d - lit, 6, 0.1)),
          kartka: '<div class="mitka">' + esc(C.adresa) + ' · радіус 1 км</div><div class="chyslo">' + esc(f.chyslo) + '</div><div class="chyslo-tekst">' + esc(f.tekst) + '</div>',
          kartkaVid: i === 0 ? LIT * 0.6 : 0, kroky: (i + 1) + ' / ' + S.tochky.length, kolo: C });
        kam = { center: a.center, zoom: a.zoom + 0.1, pitch: a.pitch, bearing: a.bearing + 6 };
      });
    }
    // кінцівка: назад до міста
    var k0 = S.kinets, misto2 = { center: MISTO.center, zoom: MISTO.zoom, pitch: 0, bearing: 0 };
    dodaty({ tryv: k0.tryvalist, kam: zlyty(polit(kam, misto2, t, LIT), t + LIT, dreif(misto2, t + LIT, k0.tryvalist - LIT, 0, 0.1)),
      kartka: '<div class="mitka">Моя вулиця</div><div class="zahol">' + esc(k0.tekst) + '</div>' + (k0.pidtekst ? '<div class="pidtekst">' + esc(k0.pidtekst) + '</div>' : ''),
      kartkaVid: 0.5, ostannii: true });
    return { vidrizky: V, tryvalist: t };
  }

  // ---------- стан кадру ----------
  var karta, SHKALA, el = {};
  var ostannie = { kartka: null, klas: null, kroky: null, tochka: null, kolo: null };

  function prozorist(v, t, vid) {
    var a = zatysk((t - v.t0 - (vid || 0)) / POYAVA, 0, 1);
    var b = v.ostannii ? 1 : zatysk((v.t1 - t) / 0.25, 0, 1);
    return Math.min(a, b);
  }

  function postavyty(t) {
    var V = SHKALA.vidrizky, v = V[V.length - 1];
    for (var i = 0; i < V.length; i++) { if (t < V[i].t1) { v = V[i]; break; } }
    karta.jumpTo(Object.assign({ padding: VIDSTUP }, v.kam(t)));

    var html = v.kartkaF ? v.kartkaF(t) : (v.kartka || '');
    if (html !== ostannie.kartka) { el.kartka.innerHTML = html; ostannie.kartka = html; }
    var klas = v.klas || '';
    if (klas !== ostannie.klas) { el.kartka.className = 'shar ' + klas; ostannie.klas = klas; }
    var a = prozorist(v, t, v.kartkaVid);
    el.kartka.style.opacity = a;
    el.kartka.style.transform = 'translateY(' + Math.round((1 - a) * 40) + 'px)';
    var kr = v.kroky || '';
    if (kr !== ostannie.kroky) { el.kroky.textContent = kr; ostannie.kroky = kr; }

    var tk = v.tochka && t >= v.t0 + (v.tochkaVid || 0) ? v.tochka : null;
    var kTochky = tk ? tk.join(',') : '';
    var u = tk ? zatysk((t - v.t0 - v.tochkaVid) / 0.6, 0, 1) : 0;
    if (tk) {
      var f = tochka(tk[0], tk[1]); f.properties.r = 20 + 46 * plavno(u);
      karta.getSource('tochka').setData(fc([f]));
    } else if (ostannie.tochka !== '') karta.getSource('tochka').setData(fc());
    ostannie.tochka = kTochky;

    var kl = v.kolo ? v.kolo.lat + ',' + v.kolo.lon : '';
    if (kl !== ostannie.kolo) {
      karta.getSource('kolo').setData(v.kolo ? fc([kolo(v.kolo.lon, v.kolo.lat, v.kolo.radius_m)]) : fc());
      karta.getSource('adresa').setData(v.kolo ? fc([tochka(v.kolo.lon, v.kolo.lat)]) : fc());
      ostannie.kolo = kl;
    }
  }

  function pislyaMaliuvannia() {
    return new Promise(function (gotovo) {
      var zrobleno = false;
      function kinets() { if (!zrobleno) { zrobleno = true; gotovo(); } }
      karta.once('idle', kinets);
      setTimeout(kinets, 4000);
      karta.triggerRepaint();
    });
  }

  window.vidrizky = function () { return SHKALA.vidrizky.map(function (v) { return { t0: v.t0, t1: v.t1 }; }); };
  window.kadr = function (t) { postavyty(t); return pislyaMaliuvannia(); };

  function vantazhyty(u) { return fetch(u).then(function (r) { if (!r.ok) throw new Error(u + ': ' + r.status); return r.json(); }); }

  window.gotovo = Promise.all([vantazhyty(STSENARII), vantazhyty('../site/hra/mezha-kyieva.geojson'), vantazhyty('dani/soty-kyiv.geojson'), document.fonts.ready])
    .then(function (r) {
      var S = r[0];
      SHKALA = zibraty(S);
      el.kartka = document.getElementById('kartka');
      el.kroky = document.getElementById('kroky');
      document.getElementById('dzherelo').textContent = 'Дані: судові рішення ЄДРСР · темніше — більше подій у даних · карта: © OpenStreetMap' + (REZHYM === 'pidkladka' ? ', OpenFreeMap' : '');
      maplibregl.setWorkerUrl('../site/hra/biblioteka/maplibre-gl-csp-worker.js');
      karta = new maplibregl.Map({
        container: 'karta', style: styl(r[1], r[2]), center: MISTO.center, zoom: MISTO.zoom,
        interactive: false, attributionControl: false, fadeDuration: 0, preserveDrawingBuffer: true,
        pixelRatio: 1, maxPitch: 70
      });
      return new Promise(function (ok, ni) {
        karta.on('load', ok);
        // підкладка недоступна (немає мережі) — кажемо прямо, а не чекаємо вічно
        karta.on('error', function (e) { if (!karta.loaded()) ni(new Error('Карта не завантажилась' + (REZHYM === 'pidkladka' ? ' (підкладка OpenFreeMap недоступна? спробуйте --rezhym skhema)' : '') + ': ' + (e && e.error && e.error.message || e))); });
      })
        .then(function () { return Promise.all([document.fonts.load('800 50px Manrope', 'Київ'), document.fonts.load('400 30px Inter', 'Київ'), document.fonts.load('600 30px Inter', 'Київ')]); })
        .then(function () { return { tryvalist: SHKALA.tryvalist, nazva: S.nazva, rezhym: REZHYM }; });
    });
})();

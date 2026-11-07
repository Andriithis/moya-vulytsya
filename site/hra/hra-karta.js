// Карта гри «Вгадай, де це було» (ZAVDANNYA-07) на MapLibre GL (файл бібліотеки — з сайту).
//
// Підкладка — OpenFreeMap (безкоштовна, відкрита ліцензія, без ключа; дані OpenStreetMap).
// Це єдиний сторонній домен гри: tiles.openfreemap.org (тайли, шрифти підписів).
// Стиль підкладки — власний, світлий і тихий, з кольорів системи дизайну;
// у темній темі — темний. Якщо підкладка не завантажилась, гра працює далі:
// межу Києва ми малюємо з власного файлу mezha-kyieva.geojson (OpenStreetMap, ODbL).
(function () {
  'use strict';

  var PIDKLADKA = 'https://tiles.openfreemap.org/planet';
  var SHRYFTY = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf';
  var OSM = '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© учасники OpenStreetMap</a>';
  // Межі Києва (з mezha-kyieva.geojson) і дозволена рамка руху карти — трохи ширше.
  var KYIV = [[30.2361, 50.2132], [30.8264, 50.5908]];
  var RAMKA = [[29.90, 50.08], [31.16, 50.72]];

  function zminna(nazva) {
    return getComputedStyle(document.documentElement).getPropertyValue('--' + nazva).trim();
  }

  function kolory() {
    var k = {};
    ['ground', 'surface', 'ink', 'ink-2', 'muted', 'line', 'line-strong', 'accent', 'accent-soft',
      'karta-voda', 'karta-zelen', 'karta-zabudova', 'karta-vulytsia', 'karta-vulytsia-ramka', 'karta-za-mezhamy']
      .forEach(function (n) { k[n] = zminna(n); });
    return k;
  }

  // «Світ мінус Київ» — щоб тихо притінити все поза містом.
  function maska(mezha) {
    var zovni = [[RAMKA[0][0] - 2, RAMKA[0][1] - 2], [RAMKA[1][0] + 2, RAMKA[0][1] - 2],
      [RAMKA[1][0] + 2, RAMKA[1][1] + 2], [RAMKA[0][0] - 2, RAMKA[1][1] + 2], [RAMKA[0][0] - 2, RAMKA[0][1] - 2]];
    var g = mezha && mezha.geometry;
    var poly = !g ? [] : g.type === 'MultiPolygon' ? g.coordinates : [g.coordinates];
    var dirky = poly.map(function (p) { return p[0]; });
    return { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [zovni].concat(dirky) } };
  }

  function porozhnio() { return { type: 'FeatureCollection', features: [] }; }

  function styl(k, mezha, dani) {
    var nazva = ['coalesce', ['get', 'name:uk'], ['get', 'name']];
    var dorohy = function (klasy) { return ['all', ['==', ['geometry-type'], 'LineString'], ['in', ['get', 'class'], ['literal', klasy]]]; };
    var shyryna = function (z10, z14, z18) { return ['interpolate', ['exponential', 1.6], ['zoom'], 10, z10, 14, z14, 18, z18]; };
    return {
      version: 8,
      glyphs: SHRYFTY,
      sources: {
        osnova: { type: 'vector', url: PIDKLADKA },
        mezha: { type: 'geojson', data: mezha || porozhnio(), attribution: OSM },
        maska: { type: 'geojson', data: mezha ? maska(mezha) : porozhnio() },
        liniya: { type: 'geojson', data: dani.liniya },
        spravzhnie: { type: 'geojson', data: dani.spravzhnie },
        vasha: { type: 'geojson', data: dani.vasha }
      },
      layers: [
        { id: 'tlo', type: 'background', paint: { 'background-color': k.ground } },
        // ---- підкладка OpenFreeMap (схема OpenMapTiles) ----
        { id: 'zelen', type: 'fill', source: 'osnova', 'source-layer': 'park', paint: { 'fill-color': k['karta-zelen'] } },
        { id: 'lis', type: 'fill', source: 'osnova', 'source-layer': 'landcover', filter: ['in', ['get', 'class'], ['literal', ['wood', 'grass', 'farmland']]], paint: { 'fill-color': k['karta-zelen'], 'fill-opacity': 0.8 } },
        { id: 'voda', type: 'fill', source: 'osnova', 'source-layer': 'water', paint: { 'fill-color': k['karta-voda'] } },
        { id: 'richky', type: 'line', source: 'osnova', 'source-layer': 'waterway', minzoom: 11, paint: { 'line-color': k['karta-voda'], 'line-width': 1.5 } },
        { id: 'budynky', type: 'fill', source: 'osnova', 'source-layer': 'building', minzoom: 14, paint: { 'fill-color': k['karta-zabudova'], 'fill-outline-color': k.line } },
        { id: 'vulytsi-ramka', type: 'line', source: 'osnova', 'source-layer': 'transportation', minzoom: 12, filter: dorohy(['minor', 'service', 'tertiary', 'secondary']), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': k['karta-vulytsia-ramka'], 'line-width': shyryna(0.5, 4, 18) } },
        { id: 'vulytsi', type: 'line', source: 'osnova', 'source-layer': 'transportation', minzoom: 12, filter: dorohy(['minor', 'service', 'tertiary', 'secondary']), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': k['karta-vulytsia'], 'line-width': shyryna(0.3, 2.6, 15) } },
        { id: 'magistrali-ramka', type: 'line', source: 'osnova', 'source-layer': 'transportation', filter: dorohy(['motorway', 'trunk', 'primary']), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': k['line-strong'], 'line-width': shyryna(1.6, 6, 24) } },
        { id: 'magistrali', type: 'line', source: 'osnova', 'source-layer': 'transportation', filter: dorohy(['motorway', 'trunk', 'primary']), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': k['karta-vulytsia'], 'line-width': shyryna(0.8, 4.4, 20) } },
        { id: 'zaliznytsia', type: 'line', source: 'osnova', 'source-layer': 'transportation', minzoom: 11, filter: dorohy(['rail']), paint: { 'line-color': k['line-strong'], 'line-width': 1, 'line-dasharray': [3, 3] } },
        // ---- межа Києва (власний файл; видно і без підкладки) ----
        { id: 'za-mezhamy', type: 'fill', source: 'maska', paint: { 'fill-color': k['karta-za-mezhamy'], 'fill-opacity': 0.72 } },
        { id: 'mezha', type: 'line', source: 'mezha', layout: { 'line-join': 'round' }, paint: { 'line-color': k['line-strong'], 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 1.25, 14, 2.5] } },
        // ---- підписи: сірі й дрібні, щоб не підказувати відповідь занадто голосно ----
        { id: 'pidpysy-vulyts', type: 'symbol', source: 'osnova', 'source-layer': 'transportation_name', minzoom: 14, layout: { 'symbol-placement': 'line', 'text-field': nazva, 'text-font': ['Noto Sans Regular'], 'text-size': 11, 'text-max-angle': 30 }, paint: { 'text-color': k.muted, 'text-halo-color': k.ground, 'text-halo-width': 1.5 } },
        { id: 'pidpysy-raioniv', type: 'symbol', source: 'osnova', 'source-layer': 'place', minzoom: 11, filter: ['in', ['get', 'class'], ['literal', ['suburb', 'quarter', 'neighbourhood']]], layout: { 'text-field': nazva, 'text-font': ['Noto Sans Regular'], 'text-size': ['interpolate', ['linear'], ['zoom'], 11, 11, 15, 13], 'text-max-width': 8, 'text-letter-spacing': 0.04 }, paint: { 'text-color': k.muted, 'text-halo-color': k.ground, 'text-halo-width': 1.5 } },
        // ---- гра: лінія, справжнє місце (коло accent), відповідь (точка ink) ----
        { id: 'liniya', type: 'line', source: 'liniya', layout: { 'line-cap': 'butt' }, paint: { 'line-color': k.ink, 'line-width': 2, 'line-dasharray': [2, 2], 'line-opacity': 0.85 } },
        { id: 'spravzhnie-oreol', type: 'circle', source: 'spravzhnie', paint: { 'circle-radius': 22, 'circle-color': k.accent, 'circle-opacity': 0.16 } },
        { id: 'spravzhnie', type: 'circle', source: 'spravzhnie', paint: { 'circle-radius': 10, 'circle-color': k.accent, 'circle-stroke-color': k.surface, 'circle-stroke-width': 3 } },
        { id: 'vasha', type: 'circle', source: 'vasha', paint: { 'circle-radius': 7, 'circle-color': k.ink, 'circle-stroke-color': k.surface, 'circle-stroke-width': 2.5 } }
      ]
    };
  }

  function tochka(lngLat) {
    return { type: 'FeatureCollection', features: lngLat ? [{ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [lngLat.lng, lngLat.lat] } }] : [] };
  }

  function stvoryty(konteiner, opts) {
    opts = opts || {};
    maplibregl.setWorkerUrl('biblioteka/maplibre-gl-csp-worker.js');
    var mezha = null;
    var dani = { vasha: porozhnio(), spravzhnie: porozhnio(), liniya: porozhnio() };
    var mozhnaTorkatysia = true;
    var pidkladkaZbii = false;
    var telefon = window.matchMedia('(max-width: 600px)').matches;

    var karta = new maplibregl.Map({
      container: konteiner,
      style: styl(kolory(), null, dani),
      bounds: KYIV,
      fitBoundsOptions: { padding: 16 },
      maxBounds: RAMKA,
      minZoom: 8.5,
      maxZoom: 18,
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
      attributionControl: false,
      renderWorldCopies: false,
      fadeDuration: 0
    });
    karta.touchZoomRotate.disableRotation();
    karta.keyboard.disableRotation();
    karta.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    karta.addControl(new maplibregl.AttributionControl({ compact: telefon }), 'bottom-right');

    function onovyty(nazva) {
      var dzherelo = karta.getSource(nazva);
      if (dzherelo) dzherelo.setData(dani[nazva]);
    }

    // Дані гри могли змінитися ще до завантаження стилю — накладаємо їх після.
    karta.on('load', function () { ['vasha', 'spravzhnie', 'liniya'].forEach(onovyty); });

    fetch('mezha-kyieva.geojson', { credentials: 'omit' })
      .then(function (v) { return v.ok ? v.json() : null; })
      .then(function (g) {
        if (!g) return;
        mezha = g;
        var z = function () {
          var m = karta.getSource('mezha'); if (m) m.setData(g);
          var s = karta.getSource('maska'); if (s) s.setData(maska(g));
        };
        if (karta.isStyleLoaded()) z(); else karta.once('load', z);
      })
      .catch(function () { /* без межі гра теж працює */ });

    karta.on('error', function (e) {
      var dz = e && (e.sourceId || (e.source && e.source.id));
      var tekst = String(e && e.error && e.error.message || '');
      if (dz === 'osnova' || tekst.indexOf('openfreemap') !== -1 || tekst.indexOf('Failed to fetch') !== -1) {
        if (!pidkladkaZbii && opts.pryZboiPidkladky) opts.pryZboiPidkladky();
        pidkladkaZbii = true;
      }
    });

    karta.on('click', function (e) {
      if (!mozhnaTorkatysia) return;
      dani.vasha = tochka(e.lngLat);
      onovyty('vasha');
      if (opts.pryTorkanni) opts.pryTorkanni({ lat: e.lngLat.lat, lng: e.lngLat.lng });
    });

    // Темна тема ввімкнулась / вимкнулась — перемальовуємо підкладку в нових кольорах.
    var tema = window.matchMedia('(prefers-color-scheme: dark)');
    var pryZmini = function () { karta.setStyle(styl(kolory(), mezha, dani)); };
    if (tema.addEventListener) tema.addEventListener('change', pryZmini); else if (tema.addListener) tema.addListener(pryZmini);

    var api = {
      karta: karta,
      skynuty: function () {
        mozhnaTorkatysia = true;
        dani = { vasha: porozhnio(), spravzhnie: porozhnio(), liniya: porozhnio() };
        ['vasha', 'spravzhnie', 'liniya'].forEach(onovyty);
        karta.resize();
        karta.fitBounds(KYIV, { padding: 16, duration: 0 });
      },
      pokazatyRezultat: function (vasha, spravzhnie, bezAnimatsii) {
        mozhnaTorkatysia = false;
        var s = { lng: spravzhnie.lon, lat: spravzhnie.lat };
        dani.spravzhnie = tochka(s);
        dani.vasha = vasha ? tochka(vasha) : porozhnio();
        dani.liniya = vasha ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [[vasha.lng, vasha.lat], [s.lng, s.lat]] } } : porozhnio();
        ['vasha', 'spravzhnie', 'liniya'].forEach(onovyty);
        karta.resize();
        var mezhi = new maplibregl.LngLatBounds([s.lng, s.lat], [s.lng, s.lat]);
        if (vasha) mezhi.extend([vasha.lng, vasha.lat]);
        // Відступи з урахуванням легенди (угорі зліва), кнопок (угорі справа) і підписів (унизу).
        var shyroka = window.matchMedia('(min-width: 900px)').matches;
        var v = shyroka ? { top: 120, bottom: 120, left: 120, right: 120 } : { top: 76, bottom: 84, left: 40, right: 64 };
        karta.fitBounds(mezhi, { padding: v, maxZoom: 15.5, duration: bezAnimatsii ? 0 : 700 });
      },
      rozmir: function () { karta.resize(); },
      zboiPidkladky: function () { return pidkladkaZbii; }
    };
    window.MvHraKarta.ostannia = api;
    return api;
  }

  window.MvHraKarta = { stvoryty: stvoryty, styl: styl, KYIV: KYIV };
})();

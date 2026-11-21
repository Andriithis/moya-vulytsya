// Карта для макетів ZAVDANNYA-193: підкладка OpenFreeMap (OpenStreetMap) у кольорах стилю, соти H3 з випуску,
// проблеми, межі районів. Підписи — HTML поверх карти шрифтом стилю. Налаштування — window.K (зі сторінки).
(function () {
  var K = window.K, DN = window.DANI;
  var tel = document.documentElement.dataset.prystrii === 'tel';
  var soty = tel ? DN.soty7 : DN.soty8;
  var vybrana = tel ? DN.sota7 : DN.sota.h;

  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967296; }

  // недосконалі соти («Тепла»): зсув вершин на кілька метрів, детерміновано
  if (K.sotaVyd === 'jitter') {
    soty = JSON.parse(JSON.stringify(soty));
    soty.features.forEach(function (f) {
      var r = f.geometry.coordinates[0], h = f.properties.h;
      for (var i = 0; i < r.length - 1; i++) {
        r[i][0] += (hash(h + i) - .5) * (tel ? .0035 : .0016);
        r[i][1] += (hash(h + 'y' + i) - .5) * (tel ? .0022 : .001);
      }
      r[r.length - 1] = r[0].slice();
    });
  }
  // мозаїка («Свій Київ»): у кожного класу два відтінки смальти
  soty.features.forEach(function (f) { f.properties.v = hash(f.properties.h) < .5 ? 0 : 1; });

  var rayony = { type: 'FeatureCollection', features: Object.keys(DN.rayony).map(function (r) {
    var m = DN.rayony[r].mezha.slice(); m.push(m[0]);
    return { type: 'Feature', properties: { r: r }, geometry: { type: 'LineString', coordinates: m } };
  }) };
  var problemy = { type: 'FeatureCollection', features: DN.problemy.map(function (p) {
    return { type: 'Feature', properties: { n: p.n }, geometry: { type: 'Point', coordinates: [p.lon, p.lat] } };
  }) };

  var P = K.pidkladka;
  var shary = [
    { id: 'tlo', type: 'background', paint: { 'background-color': P.tlo } },
    { id: 'park', type: 'fill', source: 'omt', 'source-layer': 'park', paint: { 'fill-color': P.park, 'fill-opacity': P.parkOp == null ? 1 : P.parkOp } },
    { id: 'lis', type: 'fill', source: 'omt', 'source-layer': 'landcover', filter: ['in', ['get', 'class'], ['literal', ['wood', 'grass']]], paint: { 'fill-color': P.park, 'fill-opacity': P.parkOp == null ? .8 : P.parkOp * .8 } },
    { id: 'voda', type: 'fill', source: 'omt', 'source-layer': 'water', paint: { 'fill-color': P.voda } },
    { id: 'richky', type: 'line', source: 'omt', 'source-layer': 'waterway', paint: { 'line-color': P.voda, 'line-width': 1 } },
    { id: 'dorohy2', type: 'line', source: 'omt', 'source-layer': 'transportation', filter: ['in', ['get', 'class'], ['literal', ['secondary', 'tertiary']]], paint: { 'line-color': P.doroha2 || P.doroha, 'line-width': tel ? .4 : .6 } },
    { id: 'dorohy', type: 'line', source: 'omt', 'source-layer': 'transportation', filter: ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary']]], paint: { 'line-color': P.doroha, 'line-width': tel ? .8 : 1.3 } },
    { id: 'zaliznytsia', type: 'line', source: 'omt', 'source-layer': 'transportation', filter: ['==', ['get', 'class'], 'rail'], paint: { 'line-color': P.zaliznytsia || P.doroha2 || P.doroha, 'line-width': .6, 'line-dasharray': [3, 2] } },
  ];
  var R = K.ramp; // 5 кольорів (або 10 для мозаїки)
  var kolir = K.sotaVyd === 'mosaic'
    ? ['match', ['+', ['*', ['get', 'c'], 2], ['get', 'v']], 2, R[0], 3, R[1], 4, R[2], 5, R[3], 6, R[4], 7, R[5], 8, R[6], 9, R[7], 10, R[8], R[9]]
    : ['match', ['get', 'c'], 1, R[0], 2, R[1], 3, R[2], 4, R[3], R[4]];
  if (K.sotaVyd === 'hatch') {
    shary.push({ id: 'soty-tlo', type: 'fill', source: 'soty', paint: { 'fill-color': K.hatchTlo, 'fill-opacity': ['match', ['get', 'c'], 1, .25, 2, .35, 3, .45, 4, .6, .8] } });
    shary.push({ id: 'soty', type: 'fill', source: 'soty', paint: { 'fill-pattern': ['concat', 'h', ['to-string', ['get', 'c']]] } });
  } else if (K.sotaVyd !== 'vector') {
    shary.push({ id: 'soty', type: 'fill', source: 'soty', paint: { 'fill-color': kolir, 'fill-opacity': K.sotaOp == null ? 1 : K.sotaOp, 'fill-antialias': true } });
  } else {
    shary.push({ id: 'soty', type: 'fill', source: 'soty', paint: { 'fill-color': kolir, 'fill-opacity': K.sotaOp == null ? 1 : K.sotaOp } });
  }
  if (K.mezhaSoty) shary.push({ id: 'soty-mezha', type: 'line', source: 'soty', paint: { 'line-color': K.mezhaSoty, 'line-width': K.mezhaSotyW || .6 } });
  if (K.mezhaSoty2) shary.push({ id: 'soty-mezha2', type: 'line', source: 'soty', filter: ['>=', ['get', 'c'], 3], paint: { 'line-color': K.mezhaSoty2, 'line-width': .6, 'line-offset': 1.2 } });
  if (K.vershyna) shary.push({ id: 'vershyny', type: 'line', source: 'soty', filter: ['==', ['get', 'c'], 5], paint: { 'line-color': K.vershyna, 'line-width': K.vershynaW || 1.2 } });
  if (K.sotaVyd === 'vector') {
    shary.push({ id: 'vektory', type: 'line', source: 'vektory', paint: { 'line-color': K.vektor, 'line-width': ['match', ['get', 'c'], 1, .8, 2, 1, 3, 1.3, 4, 1.7, 2.3], 'line-opacity': ['match', ['get', 'c'], 1, .55, 2, .7, 3, .85, 1] }, layout: { 'line-cap': 'butt' } });
    shary.push({ id: 'vektory-krai', type: 'circle', source: 'vektory-krai', paint: { 'circle-radius': ['match', ['get', 'c'], 1, 1.2, 2, 1.4, 3, 1.6, 4, 2, 2.4], 'circle-color': K.vektor } });
  }
  shary.push({ id: 'rayony', type: 'line', source: 'rayony', paint: { 'line-color': K.mezhaRayonu, 'line-width': K.mezhaRayonuW || .8, 'line-dasharray': K.mezhaRayonuDash || [1, 0] } });
  shary.push({ id: 'vybrana', type: 'line', source: 'soty', filter: ['==', ['get', 'h'], vybrana], paint: { 'line-color': K.vybrana, 'line-width': K.vybranaW || 2 } });
  shary.push({ id: 'problemy', type: 'symbol', source: 'problemy', layout: { 'icon-image': 'problema', 'icon-allow-overlap': true, 'icon-size': tel ? .55 : .72 } });

  var dzherela = { omt: { type: 'vector', url: 'https://tiles.openfreemap.org/planet' }, soty: { type: 'geojson', data: soty },
    rayony: { type: 'geojson', data: rayony }, problemy: { type: 'geojson', data: problemy } };
  if (K.sotaVyd === 'vector') {
    var v = tel ? DN.vektory7 : DN.vektory8, lin = [], krai = [];
    var dl = tel ? .028 : .011;
    v.forEach(function (x) {
      if (x.a + x.b < (tel ? 10 : 18)) return;
      var k = Math.log2((x.b + 1) / (x.a + 1)), ang = Math.max(-55, Math.min(55, k * 50)) * Math.PI / 180;
      var dx = dl * Math.cos(ang), dy = dl * Math.sin(ang) * .64;
      var a = [x.lon - dx * .5, x.lat - dy * .5], b = [x.lon + dx * .5, x.lat + dy * .5];
      lin.push({ type: 'Feature', properties: { c: x.c }, geometry: { type: 'LineString', coordinates: [a, b] } });
      krai.push({ type: 'Feature', properties: { c: x.c }, geometry: { type: 'Point', coordinates: b } });
    });
    dzherela.vektory = { type: 'geojson', data: { type: 'FeatureCollection', features: lin } };
    dzherela['vektory-krai'] = { type: 'geojson', data: { type: 'FeatureCollection', features: krai } };
  }

  var c = K.kamera[tel ? 'tel' : 'pk'];
  var map = new maplibregl.Map({ container: 'map', style: { version: 8, sources: dzherela, layers: shary }, center: c.center, zoom: c.zoom,
    attributionControl: false, interactive: false, fadeDuration: 0, pixelRatio: window.devicePixelRatio });

  map.setPadding(tel ? { top: 60, bottom: 400, left: 0, right: 0 } : { top: 40, right: 400, left: 0, bottom: 0 });
  map.jumpTo({ center: c.center, zoom: c.zoom });

  function ikonka(vyd, kol, tlo) {
    var s = 22, cv = document.createElement('canvas'); cv.width = cv.height = s * 2;
    var x = cv.getContext('2d'); x.scale(2, 2); x.strokeStyle = kol; x.fillStyle = kol; x.lineWidth = 1.8;
    var m = s / 2;
    if (vyd === 'kilce') { x.beginPath(); x.arc(m, m, 5.5, 0, 7); x.fillStyle = tlo; x.fill(); x.stroke(); x.beginPath(); x.arc(m, m, 1.8, 0, 7); x.fillStyle = kol; x.fill(); }
    if (vyd === 'kvadrat') { x.fillStyle = tlo; x.fillRect(m - 5, m - 5, 10, 10); x.strokeRect(m - 5, m - 5, 10, 10); }
    if (vyd === 'kvadrat-povnyi') { x.fillRect(m - 5, m - 5, 10, 10); x.strokeStyle = tlo; x.lineWidth = 1.5; x.strokeRect(m - 5.5, m - 5.5, 11, 11); }
    if (vyd === 'romb') { x.beginPath(); x.moveTo(m, m - 6.5); x.lineTo(m + 6.5, m); x.lineTo(m, m + 6.5); x.lineTo(m - 6.5, m); x.closePath(); x.fillStyle = tlo; x.fill(); x.stroke(); }
    if (vyd === 'ruka') { x.lineWidth = 1.6; x.beginPath(); x.ellipse(m, m, 7, 5.6, -.3, 0.2, 6.1); x.stroke(); x.beginPath(); x.moveTo(m + 5, m - 5); x.lineTo(m + 8, m - 6.5); x.stroke(); }
    if (vyd === 'khrest') { x.lineWidth = 2.2; x.beginPath(); x.moveTo(m - 5, m - 5); x.lineTo(m + 5, m + 5); x.moveTo(m + 5, m - 5); x.lineTo(m - 5, m + 5); x.stroke(); }
    if (vyd === 'shevron') { x.lineWidth = 2; x.beginPath(); x.moveTo(m - 4, m - 6); x.lineTo(m + 3, m); x.lineTo(m - 4, m + 6); x.stroke(); }
    if (vyd === 'kolo') { x.beginPath(); x.arc(m, m, 4.6, 0, 7); x.fill(); x.lineWidth = 2; x.strokeStyle = tlo; x.stroke(); }
    return x.getImageData(0, 0, s * 2, s * 2);
  }
  function shtrykh(c, kol) {   // візерунок штриховки для класу c: чим більше подій, тим щільніше й товще
    var s = 8 * 2, cv = document.createElement('canvas'); cv.width = cv.height = s;
    var x = cv.getContext('2d'); x.strokeStyle = kol; x.lineWidth = [0, 1, 1.5, 2.1, 2.8, 3.2][c]; x.lineCap = 'square';
    x.beginPath(); for (var i = -s; i < s * 2; i += s / 2) { x.moveTo(i, s); x.lineTo(i + s, 0); } x.stroke();
    return x.getImageData(0, 0, s, s);
  }
  map.on('load', function () {
    var p = K.problema;
    map.addImage('problema', ikonka(p.vyd, p.kolir, p.tlo), { pixelRatio: 2 });
    if (K.sotaVyd === 'hatch') for (var i = 1; i <= 5; i++) map.addImage('h' + i, shtrykh(i, i === 5 ? K.hatchPik : K.hatch), { pixelRatio: 2 });
    var shar = document.getElementById('pidpysy');
    (K.pidpysy || []).forEach(function (pp) {
      if (tel && pp.pk) return;
      var t = pp.t, ll = pp.ll || (DN.rayony[t] ? DN.rayony[t].tsentr : null);
      if (!ll) return;
      var xy = map.project(ll), d = document.createElement('span');
      d.className = 'pidpys ' + (pp.kl || 'pidpys--rayon'); d.textContent = pp.n || t;
      d.style.left = xy.x + 'px'; d.style.top = xy.y + 'px';
      shar.appendChild(d);
    });
  });
  map.on('idle', function () { window.GOTOVO = true; });
})();

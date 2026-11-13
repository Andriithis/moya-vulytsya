// Карти сайту «Моя вулиця»: карта Києва сотами (головна і /karta/) і карта вулиці.
//
// Вигляд і поведінка — макет М7 (ZAVDANNYA-42, MV-58), перенесено в ZAVDANNYA-45:
//  * напрям «Індиго й м'ята»: кольори — CSS-змінні (site/sait/kolory.json), світла й темна тема (sait/tema.js);
//  * підкладка OpenFreeMap підфарбована в тон напряму (тло, вода, парки, будинки; у темній — ще й дороги й підписи);
//  * шкала частками (MV-55): клас кольору, прозорість і висота рахуються за місцем соти серед сот рівня, тож вигляд
//    однаковий за будь-якого обсягу даних; стовпчиком — лише вершини (верхні 12 % сот);
//  * три рівні сот H3 (7 ≈ 5 км², 8 ≈ 0,7 км², 9 ≈ 0,1 км²) і плавний перехід між ними, як у карті Києва;
//  * зблизька соти прозорішають і не закривають вулиць; назви вулиць не лягають на стовпчики;
//  * виділення «приціл» (свій колір, кутики), відгук на дотик (сота пружинить, вершина осідає);
//  * рух — для всіх (MV-58): якщо в системі вимкнено анімації, переліт м'якший (≈ 0,6 с, без нахилу й повороту).
// Безкоштовно — лише числа по сотах, без адрес і описів (AGENTS.md, розд. 8). Колір — кількість подій, не небезпека.
(function () {
  'use strict';

  var STYLI = { svitla: 'https://tiles.openfreemap.org/styles/positron', temna: 'https://tiles.openfreemap.org/styles/dark' };
  var SHRYFTY = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf';
  var KYIV = [[30.2361, 50.2132], [30.8264, 50.5908]];
  var MEZHI_RUKHU = [[29.6, 49.9], [31.5, 50.9]];
  var KOREN = document.documentElement.getAttribute('data-koren') || '/';
  var TYKHO = window.matchMedia('(prefers-reduced-motion: reduce)').matches;   // рух лишається, лише м'якший
  var OSM = '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap</a> · ' +
    '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a>';

  function zminna(n) { return getComputedStyle(document.documentElement).getPropertyValue('--' + n).trim(); }
  function tema() { return document.documentElement.getAttribute('data-t') === 'temna' ? 'temna' : 'svitla'; }
  function porozhnio() { return { type: 'FeatureCollection', features: [] }; }
  function chyslo(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function slovo(n, f) {
    var m10 = n % 10, m100 = n % 100;
    if (m100 >= 11 && m100 <= 14) return f[2];
    return m10 === 1 ? f[0] : m10 >= 2 && m10 <= 4 ? f[1] : f[2];
  }
  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function rgb(c) { var v = parseInt(c.slice(1), 16); return [v >> 16, (v >> 8) & 255, v & 255]; }
  function hexK(a) { return '#' + a.map(function (x) { return Math.round(clamp(x, 0, 255)).toString(16).padStart(2, '0'); }).join(''); }
  function zmishaty(c, tsil, k) { var a = rgb(c), b = rgb(tsil); return hexK(a.map(function (x, i) { return x + (b[i] - x) * k; })); }
  function telefon() { return window.innerWidth <= 700; }
  // Політика безпеки сторінок (style-src 'self') не пускає атрибути style з розмітки — розміри й кольори з даних
  // ставимо через data-атрибути (data-vys — висота в px, data-shyr — ширина у %, data-tlo — колір тла).
  function zastosuvatyStyli(korin) {
    korin.querySelectorAll('[data-vys],[data-shyr],[data-tlo]').forEach(function (e) {
      if (e.hasAttribute('data-vys')) e.style.height = e.getAttribute('data-vys') + 'px';
      if (e.hasAttribute('data-shyr')) e.style.width = e.getAttribute('data-shyr') + '%';
      if (e.hasAttribute('data-tlo')) e.style.background = e.getAttribute('data-tlo');
    });
  }

  // Кольори поточної теми — з CSS-змінних (їх пише збирач з kolory.json).
  function paleta() {
    var d = zminna('karta-doroha');
    return {
      t: tema(), ground: zminna('ground'), surface: zminna('surface'), ink: zminna('ink'), ink2: zminna('ink-2'),
      muted: zminna('muted'), mezha: zminna('mezha'), accent: zminna('accent'), tlo: zminna('karta-tlo'),
      park: zminna('karta-park'), voda: zminna('karta-voda'), budynky: zminna('karta-budynky'), doroha: d === 'none' ? null : d,
      pidpys: zminna('karta-pidpys'), oreol: zminna('karta-oreol'), vyd: zminna('vyd'),
      sc: [1, 2, 3, 4, 5].map(function (i) { return zminna('sc-' + i); }), pk: [zminna('pk-1'), zminna('pk-2')]
    };
  }

  // ---------- Підкладка: стиль OpenFreeMap, підфарбований у тон напряму (як у М7) ----------
  var UK_NAME = ['coalesce', ['get', 'name:uk'], ['get', 'name']];
  var PK_ID = { background: 'tlo', water: 'voda', landuse_park: 'park', landcover_wood: 'park', park: 'park', building: 'budynky' };
  function nazvaMistsia(l) { return l.type === 'symbol' && (['place', 'water_name', 'mountain_peak'].indexOf(l['source-layer']) !== -1 || /^base-/.test(l.id)); }
  function patchStyle(s, K) {
    var layers = s.layers.filter(function (l) { return !(l.type === 'symbol' && (/shield/.test(l.id) || l['source-layer'] === 'poi')); });
    var font = null;
    layers.forEach(function (l) {
      if (l.type !== 'symbol' || !l.layout) return;
      var tf = l.layout['text-field'];
      if (tf && JSON.stringify(tf).indexOf('name') !== -1) l.layout['text-field'] = UK_NAME;
      if (!font && l['source-layer'] === 'transportation_name' && l.layout['text-font']) font = l.layout['text-font'];
    });
    var src = Object.keys(s.sources).filter(function (k) { return s.sources[k].type === 'vector'; })[0];
    if (src && font) {
      var txt = function (id, minzoom, filter, extra) {
        var layout = { 'text-field': UK_NAME, 'text-font': font, 'text-size': 11, 'text-max-width': 8 };
        Object.keys(extra || {}).forEach(function (k) { layout[k] = extra[k]; });
        return { id: 'base-' + id, type: 'symbol', source: src, 'source-layer': 'poi', minzoom: minzoom, filter: filter, layout: layout,
          paint: { 'text-color': K.pidpys, 'text-halo-color': K.oreol, 'text-halo-width': 1.2 } };
      };
      layers.push(txt('park', 14, ['==', ['get', 'class'], 'park']),
        txt('metro', 13, ['all', ['==', ['get', 'class'], 'railway'], ['in', ['get', 'subclass'], ['literal', ['station', 'subway']]]], { 'text-offset': [0, 0.2] }));
    }
    var temna = K.t === 'temna';
    layers.forEach(function (l) {
      var c = PK_ID[l.id] && K[PK_ID[l.id]];
      if (c) {
        var k = l.type === 'background' ? 'background-color' : l.type === 'fill' ? 'fill-color' : null;
        if (k) { l.paint = Object.assign({}, l.paint || {}); l.paint[k] = c; }
      }
      if (l.id === 'building') l.paint = Object.assign({}, l.paint || {}, { 'fill-outline-color': K.budynky, 'fill-opacity': temna ? 0.7 : 0.6 });
      if (temna && K.doroha && l.type === 'line' && l['source-layer'] === 'transportation') {
        var holovna = /motorway|trunk|primary/.test(l.id);
        l.paint = Object.assign({}, l.paint || {}, { 'line-color': holovna ? zmishaty(K.doroha, K.pidpys, 0.18) : K.doroha, 'line-opacity': 1 });
      }
      if (temna && l.type === 'line' && l['source-layer'] === 'waterway') l.paint = Object.assign({}, l.paint || {}, { 'line-color': K.voda });
      if (l.type === 'symbol' && l.paint) l.paint = Object.assign({}, l.paint, { 'text-color': K.pidpys, 'text-halo-color': K.oreol, 'text-opacity': 1 });
    });
    return Object.assign({}, s, { layers: layers });
  }
  // Без мережі — лише тло в тон напряму; межу Києва домальовуємо з власного файлу.
  function zapasnyiStyl(K) {
    return { version: 8, glyphs: SHRYFTY, sources: {}, layers: [{ id: 'background', type: 'background', paint: { 'background-color': K.tlo } }] };
  }
  function styl(K) {
    return fetch(STYLI[K.t], { credentials: 'omit' })
      .then(function (v) { if (!v.ok) throw new Error(String(v.status)); return v.json(); })
      .then(function (s) { return { s: patchStyle(s, K), ok: true }; })
      .catch(function () { return { s: zapasnyiStyl(K), ok: false }; });
  }
  function mezhaKyieva(karta, K) {
    fetch(KOREN + 'sait/mezha-kyieva.geojson', { credentials: 'omit' })
      .then(function (v) { return v.ok ? v.json() : null; })
      .then(function (g) {
        if (!g || karta.getSource('mezha')) return;
        karta.addSource('mezha', { type: 'geojson', data: g });
        karta.addLayer({ id: 'mezha', type: 'line', source: 'mezha', paint: { 'line-color': K.mezha, 'line-width': 1.5 } });
      }).catch(function () {});
  }
  function pokazatyZbii(konteiner, ok) {
    var zboi = konteiner.parentNode.querySelector('.karta__zboi');
    if (zboi) zboi.hidden = ok;
  }
  function slukhatyZbii(karta, konteiner) {
    karta.on('error', function (e) {
      var t = String((e && e.error && e.error.message) || '');
      if ((e && e.sourceId === 'openmaptiles') || t.indexOf('openfreemap') !== -1 || t.indexOf('Failed to fetch') !== -1) pokazatyZbii(konteiner, false);
    });
    // Значків з підкладки, яких немає (вимкнені шари), не малюємо — порожній піксель замість попередження.
    karta.on('styleimagemissing', function (e) {
      if (!karta.hasImage(e.id)) karta.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) });
    });
  }

  // =====================================================================================================
  // Карта Києва сотами
  // =====================================================================================================
  var HRUPY = [['dtp', 'ДТП'], ['dor', 'Дороги'], ['hp', 'Громадський порядок'], ['mai', 'Майно'],
    ['nar', 'Наркотики'], ['alk', 'Алкоголь'], ['nas', 'Насильство']];
  var NAZVA_HRUPY = {}; HRUPY.forEach(function (h) { NAZVA_HRUPY[h[0]] = h[1]; });
  // R — радіус соти H3 у метрах; k — частка ширини соти під стовпчик; H — висота найвищої вершини в радіусах (як у М7).
  var RIVNI = [{ r: 7, id: 'XL', R: 1406, k: 0.55, H: 0.9, pl: '≈5 км²' }, { r: 8, id: 'L', R: 531, k: 0.64, H: 1.1, pl: '≈0,7 км²' },
    { r: 9, id: 'S', R: 201, k: 0.8, H: 1.6, pl: '≈0,1 км²' }];
  var GI = {}; RIVNI.forEach(function (G) { GI[G.id] = G; });
  var ZUM_BUDYNKIV = 14.5, PITCH = 40;
  // Пласкі соти: старий рівень згасає, новий проростає, смуги перекриваються — без провалу (механіка карти Києва).
  var FADE = { XL: [[0, 1], [9.6, 1], [10.0, 0]], L: [[9.45, 0], [9.85, 1], [12.3, 1], [12.8, 0]], S: [[12.0, 0], [12.4, 1], [14.0, 1], [15.2, 0.42], [17, 0.3]] };
  // Світла: зблизька пласкі соти прозорішають менше — бліда сота на парку не стає «парком»; вершини лишаються щільними.
  var FADE_SV = { S: [[12.0, 0], [12.4, 1], [14.0, 1], [15.2, 0.7], [17, 0.55]] };
  var OPS_SV = { S: [[12.4, 0], [12.55, 1], [15.2, 0.9], [17, 0.8]] };
  // Зблизька межа соти проступає лінією її кольору.
  var OBVID = { S: [[13.6, 0], [14.4, 0.85]] };
  // Стовпчики без «привидів»: старий рівень осідає й гасне, лише потім виростає новий.
  var ZMINA = [9.75, 12.4];
  // З зуму 14 стовпчики нижчають — на кварталі видно вулиці й назви.
  var MN = { XL: [[0, 1], [9.45, 1], [9.75, 0]], L: [[9.75, 0], [10.1, 1], [12.0, 1], [12.4, 0]], S: [[12.4, 0], [12.8, 1], [13.6, 1], [14, 0.6], [14.6, 0.32], [15.5, 0.15], [17, 0.05]] };
  var OPS = { XL: [[0, 1], [9.6, 1], [9.75, 0]], L: [[9.75, 0], [9.9, 1], [12.25, 1], [12.4, 0]], S: [[12.4, 0], [12.55, 1], [14.2, 1], [15.2, 0.5], [17, 0.4]] };
  var MEZHI = { XL: [0, 10.05], L: [9.4, 12.85], S: [11.95, 24] };
  var MEZHI_ST = { XL: [0, ZMINA[0]], L: [ZMINA[0], ZMINA[1]], S: [ZMINA[1], 24] };
  // Прозорість пласкої соти: lo + (hi − lo) · частка².
  var PROZ = { svitla: [0.2, 0.62], temna: [0.24, 0.5] };
  // Межі класів кольору — частками сот рівня: 20 / 20 / 20 / 28 / 12 %; стовпчиком — верхні 12 %.
  var KVANT = [0.2, 0.4, 0.6, 0.88], VERSHYNA = 0.88;
  var SEL_K = 1.25;   // виділена вершина — на 25 % вища («приціл»)

  function interp(st, z) {
    if (z <= st[0][0]) return st[0][1];
    for (var i = 1; i < st.length; i++) {
      var z1 = st[i][0], v1 = st[i][1], z0 = st[i - 1][0], v0 = st[i - 1][1];
      if (z <= z1) return v0 + (v1 - v0) * (z - z0) / (z1 - z0);
    }
    return st[st.length - 1][1];
  }
  function zaZumom(tochky, f) {
    var t = tochky.filter(function (z, i) { return tochky.indexOf(z) === i; }).sort(function (a, b) { return a - b; });
    var e = ['interpolate', ['linear'], ['zoom']];
    t.forEach(function (z) { e.push(z, f(z)); });
    return e;
  }
  var TOCHKY = {};
  RIVNI.forEach(function (G) {
    var id = G.id;
    TOCHKY[id] = FADE[id].concat(MN[id], OPS[id], FADE_SV[id] || [], OPS_SV[id] || []).map(function (x) { return x[0]; })
      .concat(MEZHI[id], MEZHI_ST[id]).filter(function (z) { return z < 24; });
  });

  function tsentr(kontur) {
    var cx = 0, cy = 0, m = kontur.length - 1;
    for (var i = 0; i < m; i++) { cx += kontur[i][0]; cy += kontur[i][1]; }
    return [cx / m, cy / m];
  }
  function zmenshyty(b, k) { return b.kontur.map(function (p) { return [b.cx + (p[0] - b.cx) * k, b.cy + (p[1] - b.cy) * k]; }); }
  // Кутики «прицілу»: біля кожної вершини шестикутника — два короткі відрізки до сусідніх вершин.
  function prytsil(b, k) {
    var v = zmenshyty(b, k).slice(0, -1), n = v.length;
    var mid = function (a, c, t) { return [a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t]; };
    return { type: 'Feature', properties: {}, geometry: { type: 'MultiLineString', coordinates: v.map(function (p, i) { return [mid(p, v[(i + n - 1) % n], 0.22), p, mid(p, v[(i + 1) % n], 0.22)]; }) } };
  }

  function kartaMista(konteiner) {
    var ekran = konteiner.parentNode;
    var $ = function (s) { return ekran.querySelector(s); };
    var K = paleta(), TEMA = K.t;
    var AKTYVNI = {}; HRUPY.forEach(function (h) { AKTYVNI[h[0]] = true; });
    var PERIOD = '3';   // MV-32: безкоштовно лише останні 3 роки; «Усі роки» — у підписці (чисел за них у файлах немає)
    var ROKY = [], VERSIIA = konteiner.getAttribute('data-versiia') || '';
    var HEXB = { XL: new Map(), L: new Map(), S: new Map() };
    var POR = { XL: [], L: [], S: [] }, POR_V = { XL: 0, L: 0, S: 0 }, MEDIANA = { XL: 0, L: 0, S: 0 };
    var ZARAZ = null, map = null, PIDKLADKA_OK = true;
    var MV = window.MvKarta = { karta: null, gotovo: false, stan: { pidkladka: false, pomylky: [], zaslony: 0 } };

    function vsiAktyvni() { return HRUPY.every(function (h) { return AKTYVNI[h[0]]; }); }
    function chysloG(p, g) { return Number(p[g + PERIOD] || 0); }
    function chysloSoty(p) {
      if (vsiAktyvni()) return Number(p['all' + PERIOD] || 0);
      var n = 0; HRUPY.forEach(function (h) { if (AKTYVNI[h[0]]) n += chysloG(p, h[0]); }); return n;
    }
    function nazvaPeriodu() { return ROKY[ROKY.length - 3] + '–' + ROKY[ROKY.length - 1]; }

    // Шкала частками: частка соти q — її місце серед непорожніх сот рівня (скільки менші + половина рівних) / усіх.
    function pererakhuvaty() {
      RIVNI.forEach(function (G) {
        var bs = Array.from(HEXB[G.id].values());
        bs.forEach(function (b) { b.nf = chysloSoty(b.p); b.kr = 0; b.q = 0; });
        var zi = bs.filter(function (b) { return b.nf > 0; }).sort(function (a, b) { return a.nf - b.nf; }), L = zi.length;
        for (var i = 0; i < L;) {
          var j = i; while (j < L && zi[j].nf === zi[i].nf) j++;
          var q = (i + (j - i) / 2) / L;
          for (var t = i; t < j; t++) { zi[t].q = q; zi[t].kr = KVANT.filter(function (x) { return q >= x; }).length; }
          i = j;
        }
        POR[G.id] = [0, 1, 2, 3, 4].map(function (k) { var b = zi.filter(function (x) { return x.kr === k; })[0]; return b ? b.nf : null; });
        var v = zi.filter(function (b) { return b.q >= VERSHYNA; })[0]; POR_V[G.id] = v ? v.nf : 0;
        MEDIANA[G.id] = L ? (L % 2 ? zi[(L - 1) / 2].nf : (zi[L / 2 - 1].nf + zi[L / 2].nf) / 2) : 0;
      });
    }
    function vershyna(b) { return b.nf > 0 && b.q >= VERSHYNA; }
    function chastkaVysoty(b) { return 0.2 + 0.8 * Math.sqrt(clamp((b.q - VERSHYNA) / (1 - VERSHYNA), 0, 1)); }
    function prozPlaskoi(b) { var lh = PROZ[TEMA]; return lh[0] + (lh[1] - lh[0]) * b.q * b.q; }
    function hexData(G) {
      return { type: 'FeatureCollection', features: Array.from(HEXB[G.id].values()).filter(function (b) { return b.nf > 0; }).map(function (b) {
        return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [b.kontur] },
          properties: { k: b.k, c: K.sc[b.kr], cv: K.vyd, o: K.sc[Math.min(4, b.kr + 1)], a: prozPlaskoi(b), n: b.nf } };
      }) };
    }
    // Стовпчик = тіло + тонка світла кромка зверху (сусідні вершини не зливаються). «Світло» — лише в темній темі.
    function koloryVershyny(b) {
      var t = Math.sqrt(clamp((b.q - VERSHYNA) / (1 - VERSHYNA), 0, 1)), c = zmishaty(K.pk[0], K.pk[1], t);
      if (TEMA === 'temna') return { tilo: zmishaty(c, '#000000', 0.45), kant: zmishaty(c, '#FFFFFF', 0.08) };
      return { tilo: zmishaty(c, '#000000', 0.06), kant: zmishaty(c, '#FFFFFF', 0.28) };
    }
    function colData(G) {
      var VYSOTA = G.R * G.H, KANT = G.R / 10, f = [];
      Array.from(HEXB[G.id].values()).filter(vershyna).forEach(function (b) {
        var h = VYSOTA * chastkaVysoty(b), k = koloryVershyny(b), poly = { type: 'Polygon', coordinates: [zmenshyty(b, G.k)] };
        var ch = function (c, bh, eb, eh, kant) {
          return { type: 'Feature', geometry: poly, properties: { k: b.k, c: c, cl: zmishaty(c, '#FFFFFF', 0.45),
            cv: kant ? zmishaty(K.vyd, '#FFFFFF', 0.18) : K.vyd, n: b.nf, h: h, bh: bh, eb: eb, eh: eh } };
        };
        f.push(ch(k.tilo, 0, 0, -KANT, false), ch(k.kant, h, -KANT, 0, true));
      });
      return { type: 'FeatureCollection', features: f };
    }

    // ---------- вирази за зумом ----------
    var NAVED = ['boolean', ['feature-state', 'naved'], false];
    var SEL = ['boolean', ['feature-state', 'sel'], false];
    var TYSK = ['-', 1, ['*', 0.16, ['coalesce', ['feature-state', 'tysk'], 0]]];
    var TYSK_SEL = ['*', TYSK, ['case', SEL, SEL_K, 1]];
    function proz2d(id) {
      var F = TEMA === 'svitla' ? FADE_SV[id] || FADE[id] : FADE[id];
      return zaZumom(TOCHKY[id], function (z) { return ['*', ['case', SEL, 0.92, NAVED, ['min', 0.95, ['+', ['get', 'a'], 0.2]], ['get', 'a']], interp(F, z)]; });
    }
    function vysota(id, H, E) {
      return zaZumom(TOCHKY[id], function (z) { return ['max', 0, ['*', interp(MN[id], z), TYSK_SEL, ['+', ['get', H], ['get', E]]]]; });
    }
    function opStovp(id) {
      var op = TEMA === 'temna' ? 0.95 : 0.88;
      return zaZumom(TOCHKY[id], function (z) { return +(op * interp((TEMA === 'svitla' && OPS_SV[id]) || OPS[id], z)).toFixed(3); });
    }
    function colG(z) { z = z == null ? map.getZoom() : z; return z < ZMINA[0] ? 'XL' : z < ZMINA[1] ? 'L' : 'S'; }

    // ---------- камера: місто цілим; адреса камери — своя (#зум/шир/довг/поворот/нахил) ----------
    function chytatyKameru() {
      var m = location.hash.match(/^#([\d.]+)\/([-\d.]+)\/([-\d.]+)(?:\/([-\d.]+))?(?:\/([-\d.]+))?/);
      return m ? { zoom: +m[1], center: [+m[3], +m[2]], bearing: +(m[4] || 0), pitch: +(m[5] || 0) } : null;
    }
    function kameraMista() {
      var W = konteiner.clientWidth || window.innerWidth, H = konteiner.clientHeight || window.innerHeight;
      var pad = telefon() ? { t: 120, b: 70, l: 0, r: 0 } : { t: 130, b: 60, l: 48, r: 48 };
      var my = function (la) { return Math.log(Math.tan(Math.PI / 4 + la * Math.PI / 360)); };
      var w = KYIV[0][0], s = KYIV[0][1], e = KYIV[1][0], n = KYIV[1][1];
      var dx = (e - w) / 360 * 512, dy = (my(n) - my(s)) / (2 * Math.PI) * 512;
      var z = Math.log2(Math.min((W - pad.l - pad.r) / dx, (H - pad.t - pad.b) / dy));
      var cy = (my(n) + my(s)) / 2, la = (2 * Math.atan(Math.exp(cy)) - Math.PI / 2) * 180 / Math.PI;
      return { zoom: z + (telefon() ? 0.3 : 0.35), center: [(w + e) / 2, la], bearing: 0, pitch: PITCH };
    }
    var KAM = chytatyKameru() || kameraMista();
    var D3 = KAM.pitch > 8;

    // ---------- шари даних ----------
    function dodatyShary() {
      if (map.getSource('k-hex-L')) return;   // уже додано (style.load міг настати до підписки)
      var layers = map.getStyle().layers;
      var ostLiniya = layers.map(function (l) { return l.type !== 'symbol'; }).lastIndexOf(true), nadSymbol = (layers[ostLiniya + 1] || {}).id;
      var tem = TEMA === 'temna';
      RIVNI.forEach(function (G) {
        var id = G.id, mz = MEZHI[id], ms = MEZHI_ST[id];
        map.addSource('k-hex-' + id, { type: 'geojson', promoteId: 'k', data: hexData(G) });
        map.addSource('k-col-' + id, { type: 'geojson', promoteId: 'k', data: colData(G) });
        map.addLayer({ id: 'k-hex-' + id, type: 'fill', source: 'k-hex-' + id, minzoom: mz[0], maxzoom: mz[1],
          paint: { 'fill-color': ['case', SEL, ['get', 'cv'], ['get', 'c']], 'fill-opacity': proz2d(id) } }, nadSymbol);
        map.addLayer({ id: 'k-hexl-' + id, type: 'line', source: 'k-hex-' + id, minzoom: mz[0], maxzoom: mz[1],
          paint: { 'line-color': tem ? 'rgba(0,0,0,.5)' : 'rgba(255,255,255,.45)', 'line-width': 0.6, 'line-opacity': zaZumom(TOCHKY[id], function (z) { return interp(FADE[id], z); }) } }, nadSymbol);
        if (OBVID[id]) map.addLayer({ id: 'k-hexo-' + id, type: 'line', source: 'k-hex-' + id, minzoom: 13.5, maxzoom: mz[1],
          paint: { 'line-color': ['get', 'o'], 'line-width': ['interpolate', ['linear'], ['zoom'], 14, 1, 17, 2],
            'line-opacity': ['interpolate', ['linear'], ['zoom']].concat([].concat.apply([], OBVID[id])) } }, nadSymbol);
        map.addLayer({ id: 'k-col-' + id, type: 'fill-extrusion', source: 'k-col-' + id, minzoom: ms[0], maxzoom: ms[1], paint: {
          'fill-extrusion-color': ['case', SEL, ['get', 'cv'], NAVED, ['get', 'cl'], ['get', 'c']],
          'fill-extrusion-base': vysota(id, 'bh', 'eb'), 'fill-extrusion-height': vysota(id, 'h', 'eh'),
          'fill-extrusion-opacity': opStovp(id), 'fill-extrusion-vertical-gradient': tem } }, nadSymbol);
      });
      // «Світло» (тінь на гранях) — лише в темній темі; у світлій — м'яке розсіяне.
      map.setLight(tem ? { anchor: 'viewport', position: [1.15, 200, 32], intensity: 0.6, color: '#ffffff' }
        : { anchor: 'viewport', position: [1.3, 200, 30], intensity: 0.18, color: '#ffffff' });
      // Виділена сота: тонка обвідка + кутики «прицілу» свого кольору.
      map.addSource('k-hexsel', { type: 'geojson', data: porozhnio() });
      map.addSource('k-hexsel2', { type: 'geojson', data: porozhnio() });
      map.addLayer({ id: 'k-hexselh', type: 'line', source: 'k-hexsel', layout: { 'line-join': 'round' }, paint: { 'line-color': tem ? K.ground : '#FFFFFF', 'line-width': 3.5 } });
      map.addLayer({ id: 'k-hexsel', type: 'line', source: 'k-hexsel', layout: { 'line-join': 'round' }, paint: { 'line-color': K.ink, 'line-width': 1.5 } });
      map.addLayer({ id: 'k-hexsel2', type: 'line', source: 'k-hexsel2', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': K.vyd, 'line-width': 3 } });
      // Невидимі «заслони» над стовпчиками: назви вулиць на них не лягають.
      dodatyZaslony();
      map.addSource('k-zasl', { type: 'geojson', data: porozhnio() });
      map.addLayer({ id: 'k-zasl', type: 'symbol', source: 'k-zasl', layout: { 'icon-image': ['get', 'im'], 'icon-anchor': 'bottom',
        'icon-allow-overlap': true, 'icon-ignore-placement': false, 'icon-pitch-alignment': 'viewport', 'icon-rotation-alignment': 'viewport',
        'icon-size': ['interpolate', ['exponential', 2], ['zoom'], 6, ['*', ['get', 's0'], Math.pow(2, 6)], 17, ['*', ['get', 's0'], Math.pow(2, 17)]] },
        paint: { 'icon-opacity': 0 } });
      // Назви місць — над стовпчиками, з власним контрастом.
      map.getStyle().layers.forEach(function (l) {
        if (!nazvaMistsia(l)) return;
        map.moveLayer(l.id);
        map.setPaintProperty(l.id, 'text-color', tem ? K.ink : K.ink2); map.setPaintProperty(l.id, 'text-halo-color', K.oreol);
        map.setPaintProperty(l.id, 'text-halo-width', 1.6); map.setPaintProperty(l.id, 'text-opacity', 1);
      });
      // «Щит» над виділеною сотою — назви районів і місць на неї не лягають.
      if (!map.hasImage('k-selzasl')) map.addImage('k-selzasl', { width: 32, height: 44, data: new Uint8Array(32 * 44 * 4) });
      map.addSource('k-selzasl', { type: 'geojson', data: porozhnio() });
      map.addLayer({ id: 'k-selzasl', type: 'symbol', source: 'k-selzasl', layout: { 'icon-image': 'k-selzasl', 'icon-anchor': 'bottom', 'icon-offset': [0, 16],
        'icon-allow-overlap': true, 'icon-ignore-placement': false, 'icon-pitch-alignment': 'viewport', 'icon-rotation-alignment': 'viewport', 'icon-size': 1 },
        paint: { 'icon-opacity': 0 } });
      if (!PIDKLADKA_OK) mezhaKyieva(map, K);
    }
    function zafarbuvaty() {
      if (!map || !map.getSource('k-hex-L')) return;
      RIVNI.forEach(function (G) { map.getSource('k-hex-' + G.id).setData(hexData(G)); map.getSource('k-col-' + G.id).setData(colData(G)); });
      zaslony();
    }

    // ---------- назви вулиць не лягають на стовпчики ----------
    var ZASL_W = 32, ZASL_R = [];
    for (var zr = 1; zr <= 14; zr += 0.5) ZASL_R.push(zr);
    function pikselivNaMetr(z) { return 512 * Math.pow(2, z) / (40075016 * Math.cos(50.45 * Math.PI / 180)); }
    function dodatyZaslony() {
      ZASL_R.forEach(function (r) {
        var id = 'k-zasl-' + r, h = Math.round(ZASL_W * r);
        if (!map.hasImage(id)) map.addImage(id, { width: ZASL_W, height: h, data: new Uint8Array(ZASL_W * h * 4) });
      });
    }
    function zaslony() {
      var src = map && map.getSource('k-zasl'); if (!src) return;
      var p = map.getPitch() * Math.PI / 180, id = colG(), G = GI[id], z = map.getZoom();
      if (p < 0.14) { src.setData(porozhnio()); MV.stan.zaslony = 0; return; }
      var mn = interp(MN[id], z), s0 = Math.sqrt(3) * G.R * G.k * pikselivNaMetr(0) / ZASL_W * 1.12;
      var f = Array.from(HEXB[id].values()).filter(vershyna).map(function (b) {
        var hm = G.R * G.H * chastkaVysoty(b) * mn; if (hm < G.R * 0.6) return null;
        var r = (2 * G.k * Math.cos(p) + hm / G.R * Math.sin(p)) / (Math.sqrt(3) * G.k);
        var im = ZASL_R.filter(function (x) { return x >= r; })[0] || ZASL_R[ZASL_R.length - 1];
        return { type: 'Feature', geometry: { type: 'Point', coordinates: [b.cx, b.cy] }, properties: { im: 'k-zasl-' + im, s0: s0 } };
      }).filter(Boolean);
      src.setData({ type: 'FeatureCollection', features: f });
      map.setLayoutProperty('k-zasl', 'icon-offset', [0, ZASL_W * Math.cos(p) / Math.sqrt(3)]);
      MV.stan.zaslony = f.length;
    }

    // ---------- дані ----------
    function zavantazhyty(G) {
      return fetch(konteiner.getAttribute('data-soty-' + G.r), { credentials: 'omit' }).then(function (v) { return v.json(); }).then(function (d) {
        ROKY = d.roky || ROKY;
        var m = new Map();
        d.soty.features.forEach(function (f) {
          var kontur = f.geometry.coordinates[0], c = tsentr(kontur);
          m.set(f.properties.id, { k: f.properties.id, p: f.properties, kontur: kontur, cx: c[0], cy: c[1], nf: 0, kr: 0, q: 0 });
        });
        HEXB[G.id] = m;
      });
    }
    var dani = Promise.all(RIVNI.map(zavantazhyty)).then(function () { pererakhuvaty(); });
    dani.catch(function () { pidkazka('Дані карти не завантажилися. Оновіть сторінку.'); });

    // ---------- карта ----------
    styl(K).then(function (r) {
      PIDKLADKA_OK = r.ok; pokazatyZbii(konteiner, r.ok);
      maplibregl.setWorkerUrl(KOREN + 'sait/biblioteka/maplibre-gl-csp-worker.js');
      map = new maplibregl.Map({ container: konteiner, style: r.s, center: KAM.center, zoom: KAM.zoom, bearing: KAM.bearing, pitch: KAM.pitch,
        minZoom: 8.5, maxZoom: 19, maxPitch: 60, maxBounds: MEZHI_RUKHU, attributionControl: false, renderWorldCopies: false, fadeDuration: 300 });
      MV.karta = map;
      map.touchPitch.enable();
      if (window.ResizeObserver) new ResizeObserver(function () { map.resize(); }).observe(konteiner);
      slukhatyZbii(map, konteiner);
      map.on('error', function (e) { MV.stan.pomylky.push(String(e && e.error && e.error.message)); });
      map.on('sourcedata', function (e) { if (e.tile && e.sourceId === 'openmaptiles') MV.stan.pidkladka = true; });
      var naStyl = function () {
        dodatyShary();
        dani.then(function () {
          zafarbuvaty(); namalyuvatyInfo(); pidpysZumu();
          if (ZARAZ) vydilyty(ZARAZ.G, ZARAZ.b, false);
          MV.gotovo = true;
        });
      };
      map.on('style.load', naStyl);
      if (map.isStyleLoaded()) naStyl();
      map.on('moveend', zapysatyKameru);
      map.on('zoomend', zaslony); map.on('pitchend', zaslony);
      map.on('zoomend', rozmirZaslony); map.on('pitchend', rozmirZaslony);
      map.on('zoomend', function () { if (ZARAZ && ZARAZ.G.id !== colG()) zakryty(); navesty(null); if (!$('#info').hidden) namalyuvatyInfo(); });
      map.on('pitchend', function () { var d = map.getPitch() > 8; if (d !== D3) { D3 = d; d3Tekst(); } });
      map.on('zoom', pidpysZumu);
      map.on('click', function (e) {
        var h = vluchannya(e.point, telefon());
        if (h) { TIP.remove(); natysnuty(h.G, h.b); vidkryty(h.G, h.b); } else { zakryty(); pidkazka('Тут немає подій у даних'); }
      });
      map.on('mousemove', function (e) {
        if (telefon()) return;
        var h = vluchannya(e.point, false);
        map.getCanvas().style.cursor = h ? 'pointer' : ''; navesty(h);
        if (!h) { TIP.remove(); return; }
        var t = h.b.nf < 5 ? 'Мало даних' : chyslo(h.b.nf) + ' ' + slovo(h.b.nf, ['подія', 'події', 'подій']);
        TIP.setLngLat(e.lngLat).setHTML('<b>' + t + '</b>' + (vershyna(h.b) ? ' · вершина' : '')).addTo(map);
      });
      map.on('mouseout', function () { TIP.remove(); navesty(null); });
      TIP = new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: 'k-tip', offset: 14, maxWidth: '320px' });
    });
    var TIP = null;

    function zapysatyKameru() {
      var c = map.getCenter();
      history.replaceState(history.state, '', location.pathname + location.search + '#' + map.getZoom().toFixed(2) + '/' + c.lat.toFixed(4) + '/' +
        c.lng.toFixed(4) + '/' + Math.round(map.getBearing()) + '/' + Math.round(map.getPitch()));
    }
    function pidpysZumu() { $('#tykha').hidden = !map || map.getZoom() < ZUM_BUDYNKIV; }

    // День/ніч — без перезавантаження: нові кольори, нова підкладка, ті самі соти й камера.
    document.addEventListener('mv-tema', function () {
      K = paleta(); TEMA = K.t;
      if (!map) return;
      styl(K).then(function (r) { PIDKLADKA_OK = r.ok; pokazatyZbii(konteiner, r.ok); map.setStyle(r.s, { diff: false }); });
    });

    // ---------- 2D/3D: лише нахил камери; кнопка показує, що ввімкнено зараз ----------
    var KUB = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 20 7.5V16.5L12 21 4 16.5V7.5Z"></path><path d="M4 7.5 12 12 20 7.5M12 12V21"></path></svg>';
    var PLASKO = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2"></rect><path d="M4 12h16M12 4v16"></path></svg>';
    function d3Tekst() {
      var b = $('#f3d'), t = D3 ? 'Зараз 3D (об’ємно). Натисніть — пласка карта 2D' : 'Зараз 2D (пласко). Натисніть — об’ємна карта 3D';
      b.innerHTML = '<span class="zn-v">' + (D3 ? KUB : PLASKO) + '<small>' + (D3 ? '3D' : '2D') + '</small></span>';
      b.title = t; b.setAttribute('aria-label', t); b.setAttribute('aria-pressed', String(D3));
    }
    $('#f3d').addEventListener('click', function () {
      D3 = !D3; prybraty(); d3Tekst();
      if (map) map.easeTo({ pitch: D3 ? PITCH : 0, duration: TYKHO ? 300 : 600, essential: true });
    });
    d3Tekst();

    // ---------- фільтр «Усі події ▾» ----------
    var fKnopka = $('.f-knopka'), fSpysok = $('#f-spysok');
    function pidpysFiltra() {
      var a = HRUPY.filter(function (h) { return AKTYVNI[h[0]]; });
      return a.length === HRUPY.length ? 'Усі події' : a.length === 1 ? a[0][1] : a.length + ' з ' + HRUPY.length + ' видів подій';
    }
    function spysokFiltra(v) { fSpysok.hidden = !v; fKnopka.setAttribute('aria-expanded', String(v)); }
    fKnopka.addEventListener('click', function () { var v = fSpysok.hidden; vidkrytyInfo(false); spysokFiltra(v); });
    fSpysok.addEventListener('change', function (e) {
      var x = e.target;
      if (x.hasAttribute('data-usi')) {
        HRUPY.forEach(function (h, i) { AKTYVNI[h[0]] = x.checked || i === 0; });
      } else if (x.hasAttribute('data-hrupa')) {
        var g = x.getAttribute('data-hrupa'), skilky = HRUPY.filter(function (h) { return AKTYVNI[h[0]]; }).length;
        if (x.checked) AKTYVNI[g] = true; else if (skilky > 1) AKTYVNI[g] = false;   // хоч один вид
      }
      fSpysok.querySelectorAll('[data-hrupa]').forEach(function (c) { c.checked = AKTYVNI[c.getAttribute('data-hrupa')]; });
      fSpysok.querySelector('[data-usi]').checked = vsiAktyvni();
      pislyaFiltra();
    });
    fSpysok.querySelectorAll('[data-period]').forEach(function (b) {
      b.addEventListener('click', function () {
        PERIOD = b.getAttribute('data-period');
        fSpysok.querySelectorAll('[data-period]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        pislyaFiltra();
      });
    });
    function pislyaFiltra() {
      $('#f-pidpys').textContent = pidpysFiltra();
      pererakhuvaty(); zafarbuvaty(); if (!$('#info').hidden) namalyuvatyInfo();
      if (ZARAZ) { if (ZARAZ.b.nf > 0) namalyuvatyKartku(); else zakryty(); }
    }
    document.addEventListener('pointerdown', function (e) { if (!fSpysok.hidden && !e.target.closest('#filtr')) spysokFiltra(false); });

    // ---------- ⓘ як читати карту: шкала з числами поточного масштабу ----------
    function ikonaVershyny(c) {
      return '<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M6 8 11 5.5 16 8V17L11 19.5 6 17Z" fill="' + c + '"></path><path d="M6 8 11 5.5 16 8 11 10.5Z" fill="' + zmishaty(c, '#FFFFFF', 0.4) + '"></path></svg>';
    }
    function namalyuvatyInfo() {
      var id = map ? colG() : 'L', p = POR[id], vidsotok = Math.round((1 - VERSHYNA) * 100);
      $('#shkala').innerHTML = '<div class="ryad"><span>менше</span><span class="zr">' + K.sc.map(function (c, i) {
        return '<span class="kl"><i data-tlo="' + c + '"></i><small>' + (p[i] == null ? '—' : chyslo(p[i]) + '+') + '</small></span>';
      }).join('') + '</span><span>більше</span></div><div class="vershyna">' + ikonaVershyny(K.pk[1]) + '<span>Стовпчиком — найгустіші ' + vidsotok +
        ' % сот (від ' + chyslo(POR_V[id]) + ' подій). Вище — більше. Числа — за ' + (ROKY.length ? nazvaPeriodu() : 'обраний період') + '.</span></div>';
      zastosuvatyStyli($('#shkala'));
    }
    function vidkrytyInfo(v) {
      $('#info').hidden = !v; $('#finfo').setAttribute('aria-expanded', String(v)); $('#filtr').hidden = v;
      if (v) { spysokFiltra(false); namalyuvatyInfo(); }
    }
    $('#finfo').addEventListener('click', function () { vidkrytyInfo($('#info').hidden); });
    $('#info').addEventListener('click', function (e) { if (e.target.closest('.i-x')) vidkrytyInfo(false); });

    // ---------- пошук: вулиці й райони з даних сайту (без геокодера) ----------
    var pole = $('#poshuk-karty'), ul = $('#pidkazky'), MISTSIA = null, PIDK = [], VYBR = -1;
    function norm(s) { return (s || '').toLowerCase().replace(/[’'ʼ`]/g, '').replace(/ґ/g, 'г').replace(/ё/g, 'е').replace(/[-.,«»"]/g, ' ').replace(/\s+/g, ' ').trim(); }
    function zavantazhytyPoshuk() {
      if (MISTSIA) return Promise.resolve(MISTSIA);
      return fetch(konteiner.getAttribute('data-poshuk'), { credentials: 'omit' }).then(function (v) { return v.json(); }).then(function (d) {
        MISTSIA = d.vulytsi.map(function (v) {
          return { nazva: v[0], dod: v[1] ? v[1] + ' район' : 'вулиця', slug: v[2], tochka: [v[3], v[4]], n: v[5], p: norm(v[0]), alt: norm(v[6]) };
        }).concat(d.rayony.map(function (r) {
          return { nazva: r[0] + ' район', dod: 'район', mezhi: [[r[1], r[2]], [r[3], r[4]]], n: 1e9, p: norm(r[0] + ' район'), alt: '' };
        }));
        return MISTSIA;
      });
    }
    function znaity(q) {
      var slova = q.split(' ');
      return MISTSIA.map(function (m) {
        var i = m.p.indexOf(q), vsi = slova.every(function (s) { return m.p.indexOf(s) !== -1 || m.alt.indexOf(s) !== -1; });
        if (i < 0 && !vsi) return null;
        return { m: m, i: i, poch: i === 0 || (i > 0 && m.p[i - 1] === ' ') ? 0 : i >= 0 ? 1 : 2 };
      }).filter(Boolean).sort(function (a, b) { return a.poch - b.poch || b.m.n - a.m.n || a.m.nazva.length - b.m.nazva.length; })
        .slice(0, telefon() ? 6 : 8);
    }
    function pokazatyPidkazky() {
      var q = norm(pole.value);
      if (q.length < 2) { ul.hidden = true; PIDK = []; pole.setAttribute('aria-expanded', 'false'); return; }
      zavantazhytyPoshuk().then(function () {
        if (norm(pole.value) !== q) return;
        PIDK = znaity(q); VYBR = -1;
        ul.innerHTML = PIDK.length ? PIDK.map(function (x, j) {
          var t = x.m.nazva, nt = norm(t), i = nt === x.m.p ? x.i : -1;
          // Підсвічуємо знайдене: решта назви — жирніша (як у М7). Назву з апострофом показуємо цілою.
          var html = i >= 0 && nt.length === t.length ? '<b>' + esc(t.slice(0, i)) + '</b>' + esc(t.slice(i, i + q.length)) + '<b>' + esc(t.slice(i + q.length)) + '</b>' : '<b>' + esc(t) + '</b>';
          return '<li role="option" id="pk' + j + '" data-j="' + j + '" aria-selected="false"><span>' + html + '</span><small>' + esc(x.m.dod) + '</small></li>';
        }).join('') : '<li class="porozh">Такої назви немає в даних</li>';
        ul.hidden = false; pole.setAttribute('aria-expanded', 'true');
      });
    }
    function vybraty(j) {
      var x = PIDK[j]; if (!x || !map) return;
      var m = x.m; ul.hidden = true; pole.value = m.nazva; pole.blur(); ekran.classList.remove('shukayu'); zakryty();
      var pt = D3 ? PITCH : 0;
      if (m.mezhi) {
        map.fitBounds(m.mezhi, { padding: telefon() ? { top: 130, bottom: 100, left: 20, right: 20 } : { top: 150, bottom: 60, left: 80, right: 420 },
          pitch: TYKHO ? map.getPitch() : pt, bearing: TYKHO ? map.getBearing() : 0, duration: TYKHO ? 600 : 1200, essential: true });
        return;
      }
      // Переліт ≈ 1,2 с до соти вулиці (≈ 0,1 км²) з найбільшою кількістю подій — і її картка.
      var lo = m.tochka[0], la = m.tochka[1], b = null, bd = Infinity;
      HEXB.S.forEach(function (c) { if (!c.nf) return; var d = Math.pow((c.cx - lo) * 0.64, 2) + Math.pow(c.cy - la, 2); if (d < bd) { bd = d; b = c; } });
      if (b && Math.sqrt(bd) * 111320 > GI.S.R * 2.2) b = null;   // найближча сота з подіями — не далі ніж через одну
      // Місце стає лівіше картки (ПК) чи вище шторки (телефон) — щоб картка його не закрила.
      var zsuv = telefon() ? [0, -Math.round(konteiner.clientHeight * 0.2)] : [-200, 0];
      map.once('moveend', function () { if (b && b.nf > 0) vidkryty(GI.S, b, m.nazva, m.slug); else pidkazka('Тут немає подій у даних'); });
      if (TYKHO) map.easeTo({ center: [lo, la], zoom: 14.2, offset: zsuv, duration: 600, essential: true });   // без нахилу й повороту
      else map.flyTo({ center: [lo, la], zoom: 14.2, pitch: pt, offset: zsuv, duration: 1200, essential: true });
    }
    pole.addEventListener('input', pokazatyPidkazky);
    pole.addEventListener('focus', function () { ekran.classList.add('shukayu'); vidkrytyInfo(false); spysokFiltra(false); pokazatyPidkazky(); });
    pole.addEventListener('blur', function () { setTimeout(function () { ekran.classList.remove('shukayu'); ul.hidden = true; pole.setAttribute('aria-expanded', 'false'); }, 150); });
    pole.addEventListener('keydown', function (e) {
      var n = PIDK.length;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (!n) return; e.preventDefault(); VYBR = (VYBR + (e.key === 'ArrowDown' ? 1 : -1) + n) % n;
        ul.querySelectorAll('li').forEach(function (li, j) { li.setAttribute('aria-selected', String(j === VYBR)); });
        pole.setAttribute('aria-activedescendant', 'pk' + VYBR);
      } else if (e.key === 'Escape') { ul.hidden = true; }
    });
    pole.form.addEventListener('submit', function (e) {
      e.preventDefault();
      zavantazhytyPoshuk().then(function () {
        if (!PIDK.length && norm(pole.value).length >= 2) PIDK = znaity(norm(pole.value));
        if (PIDK.length) vybraty(VYBR >= 0 ? VYBR : 0); else pidkazka('Такої назви немає в даних');
      });
    });
    ul.addEventListener('pointerdown', function (e) { var li = e.target.closest('[data-j]'); if (li) { e.preventDefault(); vybraty(+li.getAttribute('data-j')); } });
    if (telefon()) pole.placeholder = 'Вулиця або район';

    // ---------- картка соти: коротко, як у М7; лише числа, без адрес і описів ----------
    var ZAMOK = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"></path></svg>';
    function porivnyannya(n, G) {
      var baza = MEDIANA[G.id]; if (!baza) return '';
      var r = n / baza;
      if (r >= 0.9 && r <= 1.1) return 'як у типовій соті';
      var bilshe = r > 1, x = bilshe ? r : 1 / r, ok = x < 10 ? Math.round(x * 10) / 10 : Math.round(x), cile = ok === Math.round(ok);
      var sl = !cile ? 'раза' : slovo(ok, ['раз', 'рази', 'разів']);
      return 'у ' + String(ok).replace('.', ',') + ' ' + sl + ' ' + (bilshe ? 'більше' : 'менше') + ' за типову соту';
    }
    function masyv(x) { return typeof x === 'string' ? JSON.parse(x) : (x || []); }
    // Останні 3 роки — з числами; старші (MV-32, макет М7) — сірі стовпчики з замком без чисел, лише якщо в соті є старші події (o).
    function stovpchyky(p) {
      var y = masyv(p.y), mx = Math.max.apply(null, y.concat([1])), H = 36, ost = ROKY[ROKY.length - 1];
      var vidkr = ROKY.slice(-y.length), stari = p.o ? ROKY.slice(0, ROKY.length - y.length) : [];
      var zam = stari.map(function (r) {
        return '<div class="r zamk" title="' + r + ': у підписці"><em>' + ZAMOK + '</em><u data-vys="' + Math.round(H * 0.6) + '"></u><span>’' + String(r).slice(2) + '</span></div>';
      }).join('');
      return '<div class="k-roky">' + zam + y.map(function (v, i) {
        var h = v ? Math.max(4, Math.round(H * v / mx)) : 2, r = vidkr[i];
        return '<div class="r' + (r === ost ? ' nepovnyi' : '') + '" title="' + r + ': ' + v + '"><em>' + (v ? chyslo(v) : '') + '</em><u data-vys="' + h + '"' +
          (v ? '' : ' class="nul"') + '></u><span>’' + String(r).slice(2) + '</span></div>';
      }).join('') + '</div><p class="pidpys-sir">' + (stari.length ? stari[0] + '–' + stari[stari.length - 1] + ' — у підписці · ' : '') + ost + ' — неповний рік</p>';
    }
    function namalyuvatyKartku() {
      var G = ZARAZ.G, b = ZARAZ.b, p = b.p, n = b.nf, el = $('#kartka'), filtr = !vsiAktyvni();
      var vul = masyv(p.u), rn = p.r ? p.r + ' район' : '';
      var nazva = ZARAZ.nazva || (G.id === 'S' && vul.length ? vul[0][1] : '') || rn || 'Київ';
      var pidnazva = [nazva !== rn ? rn : '', 'сота ' + G.pl].filter(Boolean).join(' · ');
      var tilo;
      if (n < 5) {
        tilo = '<div class="malo"><b>Мало даних</b><span>Менше 5 подій за ' + nazvaPeriodu() + (filtr ? ' (обрані види)' : '') + '</span></div>';
      } else {
        var top = HRUPY.filter(function (h) { return h[0] !== 'nas' && AKTYVNI[h[0]] && chysloG(p, h[0]) > 0; })
          .map(function (h) { return [chysloG(p, h[0]), h[1]]; }).sort(function (x, y) { return y[0] - x[0]; }).slice(0, 3);
        var nas = AKTYVNI.nas && chysloG(p, 'nas') > 0 ? '<div class="nas"><span>Насильство</span><b>' + chyslo(chysloG(p, 'nas')) + '</b></div>' : '';
        var pik = p.h ? '<div class="pik"><b>Пік: ' + esc(p.h.replace(/ (\d)/, ', $1')) + ' год</b><span>за ' + nazvaPeriodu() + ', де відомий час</span></div>'
          : '<div class="pik"><span>Мало даних про час</span></div>';
        var povt = masyv(p.p);
        tilo = '<div class="k-chyslo"><div class="velyke">' + chyslo(n) + '</div><div class="pid">' + slovo(n, ['подія', 'події', 'подій']) + ' за ' + nazvaPeriodu() +
          (filtr ? ' · обрані види' : '') + '<br><span class="por">' + porivnyannya(n, G) + '</span></div></div>' +
          '<section class="blok"><h3>Найбільше тут</h3>' + top.map(function (x) { return '<div class="hr"><span>' + esc(x[1]) + '</span><b>' + chyslo(x[0]) + '</b></div>'; }).join('') + nas + '</section>' +
          '<section class="blok"><h3>За роками · усі види</h3>' + stovpchyky(p) + pik + '</section>' +
          (povt.length ? '<section class="blok"><h3>Повторюється тут</h3><ul class="povt">' + povt.slice(0, 4).map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul></section>' : '');
      }
      if (vul.length) {
        tilo += '<section class="blok"><h3>Вулиці в соті</h3><p class="k-vulytsi">' + vul.map(function (v) {
          return '<a href="' + KOREN + 'vulytsia/' + encodeURIComponent(v[0]) + '/">' + esc(v[1]) + '</a>';
        }).join(' · ') + '</p></section>';
      } else if (ZARAZ.slug) {
        tilo += '<section class="blok"><p class="k-vulytsi"><a href="' + KOREN + 'vulytsia/' + encodeURIComponent(ZARAZ.slug) + '/">Сторінка вулиці</a></p></section>';
      }
      if (Number(p.a) > 0) {
        tilo += '<p class="zamok" aria-disabled="true"><span>' + ZAMOK + ' ' + chyslo(Number(p.a)) + ' ' + slovo(Number(p.a), ['подія', 'події', 'подій']) +
          ' з адресами й описами — у підписці</span></p>';
      }
      // MV-60: тихий шлях до платного — на сторінки заглушки, що вже є
      tilo += '<nav class="k-dali" aria-label="Більше про це місце">' +
        '<a class="klav" href="' + KOREN + 'zahlushka/?dzherelo=sota-pidpyska#tsiny">Що саме тут було → підписка</a>' +
        '<a class="klav" href="' + KOREN + 'zahlushka/?dzherelo=sota-analiz#tsiny">Аналіз адреси</a></nav>';
      var mezha = 'Лише те, що дійшло до суду' + (G.id === 'S' ? ' · справи про домашнє насильство й щодо дітей — лише у великих сотах' : '') +
        (VERSIIA ? ' · дані станом на ' + esc(VERSIIA) : '');
      el.innerHTML = '<div class="k-ruchka"></div><div class="k-shap"><div><h2>' + esc(nazva) + '</h2><p>' + esc(pidnazva) + '</p></div>' +
        '<button class="k-x" type="button" aria-label="Закрити">×</button></div>' + tilo + '<p class="mezha">' + mezha + '</p>';
      zastosuvatyStyli(el);
    }

    // «Назад» телефона чи браузера закриває картку: відкриття додає крок в історію.
    var KROK = false, ANIM_SEL = 0, ZASL_SEL = null;
    function prybraty() {
      if (!ZARAZ) return; cancelAnimationFrame(ANIM_SEL);
      ['k-col-', 'k-hex-'].forEach(function (s) { if (map && map.getSource(s + ZARAZ.G.id)) map.setFeatureState({ source: s + ZARAZ.G.id, id: ZARAZ.b.k }, { sel: false }); });
      ['k-hexsel', 'k-hexsel2'].forEach(function (s) { if (map && map.getSource(s)) map.getSource(s).setData(porozhnio()); });
      zaslonaVydilennya(null);
      ZARAZ = null; var el = $('#kartka'); el.hidden = true; el.classList.remove('vysoka');
    }
    function zakryty() { var bulo = !!ZARAZ; prybraty(); if (bulo && KROK) { KROK = false; history.back(); } }
    window.addEventListener('popstate', function () { if (KROK) { KROK = false; prybraty(); } });
    function zaslonaVydilennya(G, b) {
      ZASL_SEL = G ? { G: G, b: b } : null; var src = map && map.getSource('k-selzasl'); if (!src) return;
      if (!G) { src.setData(porozhnio()); return; }
      src.setData({ type: 'Feature', geometry: { type: 'Point', coordinates: [b.cx, b.cy] }, properties: {} }); rozmirZaslony();
    }
    function rozmirZaslony() {
      if (!ZASL_SEL || !map.getLayer('k-selzasl')) return;
      var v = zmenshyty(ZASL_SEL.b, 1.25).map(function (q) { return map.project(q).x; });
      map.setLayoutProperty('k-selzasl', 'icon-size', Math.max(0.5, (Math.max.apply(null, v) - Math.min.apply(null, v)) / 32));
    }
    // Виділена сота: обвідка спершу «вдавлюється» (0,86) і пружинить до повного розміру (0,26 с), далі спокійно «дихає».
    function vydilyty(G, b, zRukhom) {
      if (!map || !map.getSource('k-hexsel')) return;
      ['k-col-', 'k-hex-'].forEach(function (s) { if (map.getSource(s + G.id)) map.setFeatureState({ source: s + G.id, id: b.k }, { sel: true }); });
      zaslonaVydilennya(G, b);
      var obr = function (k) {
        map.getSource('k-hexsel').setData({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: zmenshyty(b, k) } });
        map.getSource('k-hexsel2').setData(prytsil(b, 1.2 * k));
      };
      cancelAnimationFrame(ANIM_SEL); obr(1);
      map.setPaintProperty('k-hexsel', 'line-opacity', 1); map.setPaintProperty('k-hexsel2', 'line-opacity', 1);
      if (!zRukhom) return;
      var t0 = performance.now();
      var krok = function (t) {
        var x = (t - t0) / 1000;
        if (x < 0.26) { var u = x / 0.26; obr(0.86 + 0.14 * (1 - Math.pow(1 - u, 3)) + 0.035 * Math.sin(Math.PI * u)); } else if (x < 0.3) obr(1);
        if (!TYKHO) {   // «дихання» — лише коли система не просить менше руху
          var dykh = 0.85 + 0.15 * Math.cos(2 * Math.PI * x / 2.8);
          map.setPaintProperty('k-hexsel', 'line-opacity', dykh); map.setPaintProperty('k-hexsel2', 'line-opacity', dykh);
        }
        if (ZARAZ && ZARAZ.b === b && (!TYKHO || x < 0.3)) ANIM_SEL = requestAnimationFrame(krok);
      };
      ANIM_SEL = requestAnimationFrame(krok);
    }
    // Натиск вершини: осідає на 16 % за 0,08 с і повертається за 0,2 с.
    function natysnuty(G, b) {
      if (!map.getSource('k-col-' + G.id) || !vershyna(b)) return; var t0 = performance.now();
      var krok = function (t) {
        var x = (t - t0) / 1000, v = x < 0.08 ? x / 0.08 : Math.max(0, 1 - (x - 0.08) / 0.2);
        map.setFeatureState({ source: 'k-col-' + G.id, id: b.k }, { tysk: v }); if (x < 0.28) requestAnimationFrame(krok);
      };
      requestAnimationFrame(krok);
    }
    function vidkryty(G, b, nazva, slug) {
      prybraty(); ZARAZ = { G: G, b: b, nazva: nazva || null, slug: slug || null };
      var el = $('#kartka'); el.hidden = false; el.scrollTop = 0; namalyuvatyKartku();
      el.classList.remove('z'); void el.offsetWidth; el.classList.add('z');
      if (!KROK) { history.pushState({ kartka: 1 }, '', location.href); KROK = true; }
      vydilyty(G, b, true);   // ні плашки, ні карта не рухаються, коли відкривається картка
    }
    (function () {   // шторка на телефоні: потягнути за ручку чи шапку — вище або нижче
      var el = $('#kartka'), st = null;
      el.addEventListener('pointerdown', function (e) {
        if (!telefon() || e.target.closest('.k-x') || !e.target.closest('.k-ruchka,.k-shap')) return;
        st = { y: e.clientY, h: el.offsetHeight, rukh: false }; el.setPointerCapture(e.pointerId); el.classList.add('tyagnu');
      });
      el.addEventListener('pointermove', function (e) {
        if (!st) return; var dy = st.y - e.clientY; if (Math.abs(dy) > 4) st.rukh = true;
        var H = ekran.clientHeight;
        if (st.rukh) el.style.height = Math.min(H - 8, Math.max(H * 0.45, st.h + dy)) + 'px';
      });
      var kin = function () {
        if (!st) return; var vys = st.rukh ? el.offsetHeight > ekran.clientHeight * 0.72 : !el.classList.contains('vysoka');
        st = null; el.classList.remove('tyagnu'); el.style.height = ''; el.classList.toggle('vysoka', vys);
      };
      el.addEventListener('pointerup', kin); el.addEventListener('pointercancel', kin);
      el.addEventListener('click', function (e) { if (e.target.closest('.k-x')) zakryty(); });
    })();
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { zakryty(); vidkrytyInfo(false); spysokFiltra(false); } });

    // ---------- влучання: у 3D — стовпчик під пальцем; повз стовпчики — сота на землі ----------
    function zOznaky(f) {
      var id = f.layer.id.split('-').pop(), b = HEXB[id] && HEXB[id].get(f.properties.k);
      return b && b.nf ? { G: GI[id], b: b } : null;
    }
    function vluchannya(p, dotyk) {
      var id = colG(), kol = ['k-col-' + id].filter(function (x) { return map.getLayer(x); });
      if (kol.length && map.getPitch() > 8) {
        var f = map.queryRenderedFeatures([p.x, p.y], { layers: kol }).map(zOznaky).filter(Boolean);
        if (f.length) return f[0];
        if (dotyk) {
          var r = 16, best = null, bd = Infinity;
          map.queryRenderedFeatures([[p.x - r, p.y - r], [p.x + r, p.y + r]], { layers: kol }).map(zOznaky).filter(Boolean).forEach(function (h) {
            var q = map.project([h.b.cx, h.b.cy]), d = Math.pow(q.x - p.x, 2) + Math.pow(q.y - p.y, 2); if (d < bd) { bd = d; best = h; }
          });
          if (best) return best;
        }
      }
      var pl = ['k-hex-' + id].filter(function (x) { return map.getLayer(x); });
      var g = pl.length ? map.queryRenderedFeatures([p.x, p.y], { layers: pl }).map(zOznaky).filter(Boolean) : [];
      return g[0] || null;
    }
    var tPidk = 0;
    function pidkazka(t) { var el = $('#pidkazka'); el.textContent = t; el.classList.add('vyd'); clearTimeout(tPidk); tPidk = setTimeout(function () { el.classList.remove('vyd'); }, 1400); }
    var NAV = null;
    function navesty(h) {
      var kl = function (x) { return x && x.G.id + ':' + x.b.k; };
      if (kl(h) === kl(NAV)) return;
      [[NAV, false], [h, true]].forEach(function (xv) {
        var x = xv[0]; if (!x) return;
        ['k-hex-', 'k-col-'].forEach(function (s) { if (map.getSource(s + x.G.id)) map.setFeatureState({ source: s + x.G.id, id: x.b.k }, { naved: xv[1] }); });
      });
      NAV = h;
    }

    // Для перевірок і знімків.
    MV.vidkryty = function (id, k) { var b = HEXB[id].get(k); if (b) vidkryty(GI[id], b); };
    MV.zakryty = zakryty;
    MV.zaraz = function () { return ZARAZ && { id: ZARAZ.G.id, k: ZARAZ.b.k, nazva: ZARAZ.nazva }; };
    MV.poshuk = function (t) { pole.value = t; return zavantazhytyPoshuk().then(function () { PIDK = znaity(norm(t)); return PIDK.map(function (x) { return x.m.nazva; }); }); };
    MV.vybraty = function (j) { vybraty(j); };
    MV.colG = function () { return colG(); };
    MV.vershyny = function (id) { return Array.from(HEXB[id].values()).filter(vershyna).map(function (b) { return b.k; }); };
    MV.tsentr = function (id, k) { var b = HEXB[id].get(k); return b && [b.cx, b.cy]; };
    MV.tykho = TYKHO;
  }

  // =====================================================================================================
  // Карта вулиці: соти рівня 9 з числом подій (5 кроків тієї самої шкали), без будинків
  // =====================================================================================================
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
    var map = null, zaraz = { K: null, ok: true };
    function shary() {
      var K = zaraz.K, ok = zaraz.ok;
      if (map.getSource('soty')) return;
      var layers = map.getStyle().layers;
      var ostLiniya = layers.map(function (l) { return l.type !== 'symbol'; }).lastIndexOf(true), nadSymbol = (layers[ostLiniya + 1] || {}).id;
      map.addSource('soty', { type: 'geojson', data: soty });
      map.addLayer({ id: 'soty', type: 'fill', source: 'soty', paint: { 'fill-color': ['match', ['get', 'k'], 1, K.sc[0], 2, K.sc[1], 3, K.sc[2], 4, K.sc[3], K.sc[4]],
        'fill-opacity': ['interpolate', ['linear'], ['zoom'], 13, 0.72, 16, 0.5] } }, nadSymbol);
      map.addLayer({ id: 'soty-mezha', type: 'line', source: 'soty', paint: { 'line-color': K.sc[4], 'line-width': 1, 'line-opacity': 0.6 } }, nadSymbol);
      if (!ok) mezhaKyieva(map, K);
    }
    function pobuduvaty(K) {
      return styl(K).then(function (r) {
        pokazatyZbii(konteiner, r.ok);
        zaraz = { K: K, ok: r.ok };
        if (map) { map.setStyle(r.s, { diff: false }); return; }
        maplibregl.setWorkerUrl(KOREN + 'sait/biblioteka/maplibre-gl-csp-worker.js');
        map = new maplibregl.Map({ container: konteiner, style: r.s, bounds: ramka || KYIV, fitBoundsOptions: { padding: 24, maxZoom: 15.5 },
          maxBounds: MEZHI_RUKHU, minZoom: 8.5, maxZoom: 18, dragRotate: false, pitchWithRotate: false, touchPitch: false,
          attributionControl: false, renderWorldCopies: false, fadeDuration: 0 });
        map.touchZoomRotate.disableRotation();
        map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: OSM }), 'bottom-right');
        if (window.ResizeObserver) new ResizeObserver(function () { map.resize(); }).observe(konteiner);
        slukhatyZbii(map, konteiner);
        map.on('style.load', shary);
        if (map.isStyleLoaded()) shary();
        window.MvKarta = { karta: map };
      });
    }
    pobuduvaty(paleta());
    document.addEventListener('mv-tema', function () { pobuduvaty(paleta()); });
  }

  zastosuvatyStyli(document);
  var m = document.getElementById('karta-mista');
  if (m) kartaMista(m);
  var v = document.getElementById('karta-vulytsi');
  if (v) kartaVulytsi(v);
})();

// Сцена рушія «Вау» (ZAVDANNYA-127). Кадр 1080×1920; кожен кадр малює window.kadr(t) — без годинника браузера.
//
// Сценарій (JSON, пише video/vau/stsenarii.py) — доріжки, що інтерполюються за часом:
//   kamera  [{t, c:[lon,lat], z, p, b, e, luk}]   — ключі камери; e — пом'якшення, luk — «стрибок» зуму в польоті
//   tochky  [{dani:{x,y,g,t,ox?,oy?,te?}, rozmir:[[t,px]], yaskravist:[[t,a]], tryv}] — тисячі подій (WebGL-шар)
//   soty    [{dani:GeoJSON, vysota:[[t,k]], prozorist:[[t,a]], rozpad:[{id,t}]}] — соти H3, 3D як на сайті
//   lini    [{coords, t0, t1, t2, kolir, shyr}]   — підсвітка вулиці, що малюється
//   kiltsia [{t, c, kolir}]                       — хвиля від точки
//   mitky   [{t0, t1, c, tekst, kolir, styl, n}]  — підписи на карті (вид події, назва місця, число)
//   tekst   [{t0, t1, styl, tekst, ...}]          — кінетичний текст (hook, velykyi, pidpys, lich, kartka, fin…)
//   ui      [{t0, t1, typ, ...}]                  — намальовані макети сайту: пошук, сповіщення, панель, довідка, канал
//   spalakh [{t, sila}], trus [{t, sila}]         — спалах і поштовх камери на ударах звуку
(function () {
  'use strict';
  var W = 1080, H = 1920;
  var S = null, map = null, T = 0, K = null, DRUHA = null;
  // Реєстр виглядів (ZAVDANNYA-138): теми, стилі сот і стилі адрес — рівноправні, вибір у сценарії. Окремі модулі
  // (S.moduli, напр. вигляди ZAVDANNYA-139) лише дописують сюди свої записи — рушій не переписується.
  var VAU = window.VAU = window.VAU || {};
  VAU.temy = VAU.temy || {}; VAU.styliSot = VAU.styliSot || {}; VAU.styliAdres = VAU.styliAdres || {};
  var STYLI = { svitla: 'https://tiles.openfreemap.org/styles/positron', temna: 'https://tiles.openfreemap.org/styles/dark' };
  var KOL = {
    // дороги — темні й нейтральні, соти — яскраві з чіткою межею: інакше соти зливаються з вулицями («мурашник», MV-151)
    temna: { tlo: '#11142A', voda: '#122343', park: '#0B2A2E', budynky: '#1C2035', doroha: '#262A40', pidpys: '#D3D6EC', oreol: '#11142A',
      sc: ['#4B4FA8', '#5C61C4', '#7075DA', '#8A8FEA', '#A5A9F5'], sl: '#C3C6FF', pk: ['#33BB92', '#4DCB9E'], b3d: '#262B4A', mezha: '#7D83AB' },
    svitla: { tlo: '#EFF0F6', voda: '#CADDF6', park: '#E4F2DE', budynky: '#E3E4EB', doroha: null, pidpys: '#444658', oreol: '#FFFFFF',
      sc: ['#9CA1E3', '#7E84CE', '#6066C1', '#464AA9', '#303482'], sl: '#303482', pk: ['#5DD0A9', '#31B88D'], b3d: '#D9DBE6', mezha: '#76798C' }
  };
  // тема = основа (темна / світла підкладка) + свої кольори; 'temna' і 'svitla' — вбудовані
  VAU.temy.temna = VAU.temy.temna || { baza: 'temna' };
  VAU.temy.svitla = VAU.temy.svitla || { baza: 'svitla' };
  function tema(imia) {
    var t = VAU.temy[imia];
    if (!t) throw new Error('невідома тема: ' + imia);
    var baza = t.baza || 'temna';
    return { t: baza, imia: imia, kol: Object.assign({}, KOL[baza], t.kol || {}), styl: t.styl || STYLI[baza] };
  }

  // ---------------------------------------------------------------- час і пом'якшення
  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function lerp(a, b, k) { return a + (b - a) * k; }
  var E = {
    l: function (k) { return k; },
    io: function (k) { return k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2; },
    o: function (k) { return 1 - Math.pow(1 - k, 3); },
    i: function (k) { return k * k * k; },
    oo: function (k) { return 1 - Math.pow(1 - k, 5); },
    back: function (k) { var c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2); },
    sin: function (k) { return -(Math.cos(Math.PI * k) - 1) / 2; }
  };
  function trek(arr, t, def) {           // [[t, v], …] → v у момент t (пом'якшено між ключами)
    if (!arr || !arr.length) return def;
    if (t <= arr[0][0]) return arr[0][1];
    for (var i = 1; i < arr.length; i++) {
      if (t <= arr[i][0]) {
        var a = arr[i - 1], b = arr[i], k = (t - a[0]) / Math.max(1e-6, b[0] - a[0]);
        return lerp(a[1], b[1], E[b[2] || 'io'](k));
      }
    }
    return arr[arr.length - 1][1];
  }
  function merc(lon, lat) {
    var y = Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360));
    return [(lon + 180) / 360, 0.5 - y / (2 * Math.PI)];
  }
  function lonlat(x, y) {
    var lat = Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180 / Math.PI;
    return [x * 360 - 180, lat];
  }

  function kamera(t) {
    var K_ = S.kamera;
    if (t <= K_[0].t) return K_[0];
    for (var i = 1; i < K_.length; i++) {
      if (t <= K_[i].t) {
        var a = K_[i - 1], b = K_[i];
        var k = E[b.e || 'io']((t - a.t) / Math.max(1e-6, b.t - a.t));
        var ma = merc(a.c[0], a.c[1]), mb = merc(b.c[0], b.c[1]);
        // переліт «дугою»: якщо luk — зум спершу відступає (як flyTo), центр рухається в просторі світу, а не градусів
        var z = lerp(a.z, b.z, k);
        if (b.luk) z -= b.luk * Math.sin(Math.PI * k);
        var c = lonlat(lerp(ma[0], mb[0], k), lerp(ma[1], mb[1], k));
        if (b.luk) {   // коли зум відступає, центр має рухатися швидше на початку зуму — так погляд не «пливе»
          var kz = E.sin(clamp((t - a.t) / Math.max(1e-6, b.t - a.t), 0, 1));
          c = lonlat(lerp(ma[0], mb[0], kz), lerp(ma[1], mb[1], kz));
        }
        return { c: c, z: z, p: lerp(a.p || 0, b.p || 0, k), b: lerp(a.b || 0, b.b || 0, k) };
      }
    }
    return K_[K_.length - 1];
  }

  // ---------------------------------------------------------------- підкладка в тон сайту (як site/sait/karta.js)
  var UK = ['coalesce', ['get', 'name:uk'], ['get', 'name']];
  function zmishaty(c, d, k) {
    var a = parseInt(c.slice(1), 16), b = parseInt(d.slice(1), 16);
    var r = [16, 8, 0].map(function (s) { return Math.round(((a >> s) & 255) + ((((b >> s) & 255) - ((a >> s) & 255)) * k)); });
    return '#' + r.map(function (x) { return x.toString(16).padStart(2, '0'); }).join('');
  }
  function patchStyle(s, tema) {
    var Kc = K.kol, temna = tema === 'temna';
    var layers = s.layers.filter(function (l) { return !(l.type === 'symbol' && (/shield|oneway|place_state|place_country/.test(l.id) || l['source-layer'] === 'poi' || l['source-layer'] === 'housenumber')); });
    // bez_pidpysiv: гра «Вгадай район» — жодних назв на карті (інакше відповідь написано на ній)
    if (S.bez_pidpysiv) layers = layers.filter(function (l) { return l.type !== 'symbol'; });
    // номерів будинків на карті не буває взагалі (MV-25): шар housenumber прибрано вище
    if (S.bez_3d) layers = layers.filter(function (l) { return l.type !== 'fill-extrusion'; });
    // менше підписів: села й містечка навколо Києва — лише зблизька, щоб кадр не був «газетою»
    var MINZ = { place_village: 12.5, place_other: 12, place_town: 10.8, place_suburb: 10.2 };
    layers.forEach(function (l) { if (MINZ[l.id]) l.minzoom = Math.max(l.minzoom || 0, MINZ[l.id]); });
    var font = null;
    layers.forEach(function (l) {
      if (l.type === 'symbol' && l.layout) {
        var tf = l.layout['text-field'];
        if (tf && JSON.stringify(tf).indexOf('name') !== -1) l.layout['text-field'] = UK;
        if (!font && l['source-layer'] === 'transportation_name' && l.layout['text-font']) font = l.layout['text-font'];
        if (l['source-layer'] === 'transportation_name') {     // назви вулиць — більші: кадр дивляться з телефона
          l.layout['text-size'] = ['interpolate', ['linear'], ['zoom'], 13, 20, 16, 30, 18, 36];
        }
        if (l['source-layer'] === 'place') {
          l.layout['text-size'] = ['interpolate', ['linear'], ['zoom'], 9, 26, 13, 34, 16, 40];
        }
      }
      var id = l.id;
      var c = id === 'background' ? Kc.tlo : id === 'water' ? Kc.voda : /park|wood/.test(id) && l.type === 'fill' ? Kc.park : id === 'building' ? Kc.budynky : null;
      if (c) {
        var k = l.type === 'background' ? 'background-color' : l.type === 'fill' ? 'fill-color' : null;
        if (k) { l.paint = Object.assign({}, l.paint || {}); l.paint[k] = c; }
      }
      if (temna && Kc.doroha && l.type === 'line' && l['source-layer'] === 'transportation') {
        var holovna = /motorway|trunk|primary/.test(id);
        l.paint = Object.assign({}, l.paint || {}, { 'line-color': holovna ? zmishaty(Kc.doroha, Kc.pidpys, 0.14) : Kc.doroha, 'line-opacity': 1 });
      }
      if (temna && l.type === 'line' && l['source-layer'] === 'waterway') l.paint = Object.assign({}, l.paint || {}, { 'line-color': Kc.voda });
      if (l.type === 'symbol' && l.paint) l.paint = Object.assign({}, l.paint, { 'text-color': Kc.pidpys, 'text-halo-color': Kc.oreol, 'text-halo-width': 2, 'text-opacity': 1 });
    });
    var src = Object.keys(s.sources).filter(function (k) { return s.sources[k].type === 'vector'; })[0];
    K.shryft = font;
    if (src && font && !S.bez_pidpysiv) {
      layers.push({ id: 'base-metro', type: 'symbol', source: src, 'source-layer': 'poi', minzoom: 12.5,
        filter: ['all', ['==', ['get', 'class'], 'railway'], ['in', ['get', 'subclass'], ['literal', ['station', 'subway']]]],
        layout: { 'text-field': UK, 'text-font': font, 'text-size': 26, 'text-max-width': 8 },
        paint: { 'text-color': Kc.pidpys, 'text-halo-color': Kc.oreol, 'text-halo-width': 2 } });
    }
    if (src && !S.bez_3d) {   // 3D-будинки зблизька — «кіно», а не схема
      var pershyiSymvol = layers.findIndex(function (l) { return l.type === 'symbol'; });
      layers.splice(pershyiSymvol, 0, { id: 'budynky-3d', type: 'fill-extrusion', source: src, 'source-layer': 'building', minzoom: 14,
        paint: { 'fill-extrusion-color': Kc.b3d, 'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 8],
          'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
          'fill-extrusion-opacity': ['interpolate', ['linear'], ['zoom'], 14, 0, 15, temna ? 0.85 : 0.75] } });
    }
    s.layers = layers;
    return s;
  }

  // ---------------------------------------------------------------- точки подій: власний WebGL-шар
  var VS = [
    'attribute vec2 a_pos; attribute vec2 a_org; attribute float a_t; attribute float a_g; attribute float a_te;',
    'uniform mat4 u_m; uniform float u_t; uniform float u_px; uniform float u_tryv; uniform float u_ring;',
    'varying float v_g; varying float v_s; varying float v_ring; varying float v_a; varying float v_flash;',
    'void main(){',
    '  float age = u_t - a_t;',
    '  if (age < 0.0 || (a_te > 0.0 && u_t > a_te + 0.4)) { gl_Position = vec4(2.0,2.0,2.0,1.0); gl_PointSize = 0.0; return; }',
    '  float k = clamp(age / u_tryv, 0.0, 1.0); k = 1.0 - pow(1.0 - k, 3.0);',
    '  vec2 p = mix(a_org, a_pos, k);',
    '  gl_Position = u_m * vec4(p, 0.0, 1.0);',
    '  float pop = age < 0.45 ? (1.0 + 1.6 * exp(-age * 9.0) * sin(min(age * 14.0, 3.1416))) : 1.0;',
    '  float ringK = clamp(age / 0.55, 0.0, 1.0);',
    '  float sz = u_px * pop;',
    '  float outer = u_ring > 0.0 && age < 0.55 ? sz * (1.0 + 5.0 * ringK) * 1.25 : sz * 2.6;',
    '  gl_PointSize = max(outer, sz * 2.6);',
    '  v_s = gl_PointSize / sz; v_g = a_g; v_ring = u_ring > 0.0 && age < 0.55 ? ringK : -1.0;',
    '  v_a = a_te > 0.0 ? clamp(1.0 - (u_t - a_te) / 0.4, 0.0, 1.0) : 1.0;',
    '  v_flash = exp(-age * 6.0);',
    '}'].join('\n');
  var FS = [
    'precision mediump float;',
    'uniform vec3 u_kol[8]; uniform float u_alfa; uniform float u_glow;',
    'varying float v_g; varying float v_s; varying float v_ring; varying float v_a; varying float v_flash;',
    'void main(){',
    '  float d = length(gl_PointCoord - 0.5) * 2.0 * v_s;',          // d в одиницях радіуса ядра (ядро — 1.0)
    '  vec3 c = u_kol[0]; int g = int(v_g + 0.5);',
    '  if (g == 1) c = u_kol[1]; else if (g == 2) c = u_kol[2]; else if (g == 3) c = u_kol[3]; else if (g == 4) c = u_kol[4]; else if (g == 5) c = u_kol[5]; else if (g == 6) c = u_kol[6]; else if (g == 7) c = u_kol[7];',
    '  float core = 1.0 - smoothstep(0.55, 0.85, d);',
    '  float glow = exp(-d * d * 0.55) * u_glow;',
    '  float ring = 0.0;',
    '  if (v_ring >= 0.0) { float rr = 1.0 + 5.0 * v_ring; ring = (1.0 - smoothstep(0.0, 0.35, abs(d - rr))) * (1.0 - v_ring) * 0.9; }',
    '  vec3 col = mix(c, vec3(1.0), 0.55 * v_flash * core);',
    '  float a = clamp(core + glow + ring, 0.0, 1.0) * u_alfa * v_a;',
    '  if (a < 0.003) discard;',
    '  gl_FragColor = vec4(col * a, a);',
    '}'].join('\n');

  function hexRgb(h) { var v = parseInt(h.slice(1), 16); return [(v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255]; }

  function sharTochok(id, sh) {
    var prog, buf, n, loc = {};
    return {
      id: id, type: 'custom', renderingMode: '2d',
      onAdd: function (m, gl) {
        function shader(type, src) { var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
          if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; }
        prog = gl.createProgram();
        gl.attachShader(prog, shader(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FS));
        gl.linkProgram(prog);
        ['a_pos', 'a_org', 'a_t', 'a_g', 'a_te'].forEach(function (a) { loc[a] = gl.getAttribLocation(prog, a); });
        ['u_m', 'u_t', 'u_px', 'u_tryv', 'u_ring', 'u_kol', 'u_alfa', 'u_glow'].forEach(function (u) { loc[u] = gl.getUniformLocation(prog, u); });
        var d = sh.dani; n = d.x.length;
        var arr = new Float32Array(n * 7);
        for (var i = 0; i < n; i++) {
          var p = merc(d.x[i] / 1e5, d.y[i] / 1e5);
          var o = d.ox ? merc(d.ox[i] / 1e5, d.oy[i] / 1e5) : p;
          arr.set([p[0], p[1], o[0], o[1], d.t[i], d.g[i], d.te ? d.te[i] : 0], i * 7);
        }
        buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, arr, gl.STATIC_DRAW);
      },
      render: function (gl, args) {
        if (T < (sh.t0 || 0) - 0.01 || T > (sh.t1 || 1e9)) return;
        var alfa = trek(sh.yaskravist, T, 1);
        if (alfa <= 0.001) return;
        gl.useProgram(prog);
        gl.uniformMatrix4fv(loc.u_m, false, args.defaultProjectionData.mainMatrix);
        gl.uniform1f(loc.u_t, T);
        gl.uniform1f(loc.u_px, trek(sh.rozmir, T, 7));
        gl.uniform1f(loc.u_tryv, sh.tryv || 0.6);
        gl.uniform1f(loc.u_ring, sh.kiltse === false ? 0 : 1);
        gl.uniform1f(loc.u_alfa, alfa);
        gl.uniform1f(loc.u_glow, sh.glow === undefined ? (K.t === 'temna' ? 0.55 : 0.25) : sh.glow);
        var kol = []; (S.kolory || []).forEach(function (h) { kol.push.apply(kol, hexRgb(h)); });
        while (kol.length < 24) kol.push(1);
        gl.uniform3fv(loc.u_kol, new Float32Array(kol));
        gl.bindBuffer(gl.ARRAY_BUFFER, buf);
        var st = 28;
        gl.enableVertexAttribArray(loc.a_pos); gl.vertexAttribPointer(loc.a_pos, 2, gl.FLOAT, false, st, 0);
        gl.enableVertexAttribArray(loc.a_org); gl.vertexAttribPointer(loc.a_org, 2, gl.FLOAT, false, st, 8);
        gl.enableVertexAttribArray(loc.a_t); gl.vertexAttribPointer(loc.a_t, 1, gl.FLOAT, false, st, 16);
        gl.enableVertexAttribArray(loc.a_g); gl.vertexAttribPointer(loc.a_g, 1, gl.FLOAT, false, st, 20);
        gl.enableVertexAttribArray(loc.a_te); gl.vertexAttribPointer(loc.a_te, 1, gl.FLOAT, false, st, 24);
        gl.disable(gl.DEPTH_TEST);
        gl.enable(gl.BLEND);
        if (sh.aditiv) gl.blendFunc(gl.ONE, gl.ONE); else gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
        gl.drawArrays(gl.POINTS, 0, n);
        [loc.a_pos, loc.a_org, loc.a_t, loc.a_g, loc.a_te].forEach(function (a) { gl.disableVertexAttribArray(a); });
      }
    };
  }

  // ---------------------------------------------------------------- соти H3 (3D, шкала сайту)
  // Стилі сот (ZAVDANNYA-138) — рівноправні, вибір у сценарії (sh.styl_sot). Опис стилю:
  //   zalyvka   — непрозорість заливки (null — як на сайті: яскравіше зблизька, до 0,8)
  //   mezha     — колір меж: 'sl' (світла лінія), 'tlo' (шов кольору тла) або #колір; shyr — товщина на z 9 / 12 / 15
  //   znyk      — наскільки приглушити дороги й будинки під сотами (0…1); znyk_nazvy — ще й назви вулиць
  //   vysota    — 'verkh' (стовпчики лише верхнім 12 %, як на сайті) або 'vsi' (кожна сота — стовпчик за числом)
  //   op3d      — непрозорість стовпчиків (менше — вулиці видно крізь них)
  //   dodaty(ctx) / onovyty(ctx) — власний вигляд (модулі ZAVDANNYA-139): замість звичайного
  VAU.styliSot.sait = VAU.styliSot.sait || { zalyvka: null, mezha: 'sl', shyr: [1.4, 2.6, 4], mezha_a: 0.85, znyk: 0, vysota: 'verkh' };
  VAU.styliSot.sklo = VAU.styliSot.sklo || { zalyvka: 0.5, mezha: 'sl', shyr: [1.4, 2.6, 4], mezha_a: 0.85, znyk: 0.6, vysota: 'verkh' };
  VAU.styliSot.plytka = VAU.styliSot.plytka || { zalyvka: 0.94, mezha: 'tlo', shyr: [2.4, 4, 6], mezha_a: 1, znyk: 1, znyk_nazvy: true, vysota: 'verkh' };
  VAU.styliSot.stovpchyky = VAU.styliSot.stovpchyky || { zalyvka: 0.18, mezha: 'sl', shyr: [1, 1.6, 2.4], mezha_a: 0.45, znyk: 0, vysota: 'vsi', op3d: 0.66 };
  VAU.styliSot.stovpchyky_shchilno = VAU.styliSot.stovpchyky_shchilno || { zalyvka: 0.0, mezha: 'tlo', shyr: [1, 1.6, 2.4], mezha_a: 0.0, znyk: 0.5, vysota: 'vsi', op3d: 0.93 };
  var STAROVYI = { zalyvka: null, mezha: 'sl', shyr: [1.4, 2.6, 4], mezha_a: 0.85, znyk: 0, vysota: 'verkh' };   // без styl_sot — як було до 134
  function stylSot(sh) {
    if (!sh.styl_sot) return STAROVYI;
    var d = VAU.styliSot[sh.styl_sot];
    if (!d) throw new Error('невідомий стиль сот: ' + sh.styl_sot);
    return d;
  }
  function dodatySoty(i, sh, pered) {
    var id = 'soty-' + i, Kc = K.kol, d = stylSot(sh);
    map.addSource(id, { type: 'geojson', data: sh.dani, promoteId: 'id' });
    var kolir = ['match', ['get', 'k'], 1, Kc.sc[0], 2, Kc.sc[1], 3, Kc.sc[2], 4, Kc.sc[3], Kc.sc[4]];
    var vershyna = ['case', ['>', ['get', 'v'], 0], ['interpolate', ['linear'], ['get', 'v'], 0, Kc.pk[0], 1, Kc.pk[1]], kolir];
    var rozpadIds = (sh.rozpad || []).map(function (r) { return r.id; });
    sh._ids = rozpadIds;
    if (d.dodaty) { d.dodaty({ map: map, id: id, sh: sh, Kc: Kc, pered: pered, kolir: kolir }); return; }
    map.addLayer({ id: id + '-f', type: 'fill', source: id, paint: { 'fill-color': kolir, 'fill-opacity': 0 } }, pered);
    var lk = d.mezha === 'tlo' ? Kc.tlo : d.mezha === 'sl' ? Kc.sl : d.mezha;
    map.addLayer({ id: id + '-l', type: 'line', source: id, paint: { 'line-color': lk,
      'line-width': ['interpolate', ['linear'], ['zoom'], 9, d.shyr[0], 12, d.shyr[1], 15, d.shyr[2]], 'line-opacity': 0 } }, pered);
    if (d.znyk) zibratyZnyk(d);
    var filtr = d.vysota === 'vsi' ? ['>', ['get', 'n'], 0] :
      sh.lyshe_rozpad ? ['in', ['get', 'id'], ['literal', rozpadIds]] : ['any', ['>', ['get', 'v'], 0], ['in', ['get', 'id'], ['literal', rozpadIds]]];
    map.addLayer({ id: id + '-3d', type: 'fill-extrusion', source: id,
      // lyshe_rozpad: у 3D — лише соти, що розпадаються; решта пласкі з чіткою межею (інакше стовпи затуляють «вибух»)
      filter: filtr, paint: {
      'fill-extrusion-color': d.vysota === 'vsi' ? kolir : sh.vershyny === false ? kolir : vershyna,
      'fill-extrusion-height': 0, 'fill-extrusion-base': 0, 'fill-extrusion-opacity': 0.9,
      'fill-extrusion-vertical-gradient': true } }, pered);
  }
  // під сотами дороги й будинки приглушені (рівна заливка замість доріжок); znyk_nazvy — ще й назви вулиць
  var ZNYK = [];
  function zibratyZnyk(d) {
    if (ZNYK.length) return;
    map.getStyle().layers.forEach(function (l) {
      var sl = l['source-layer'];
      if (l.type === 'line' && (sl === 'transportation' || sl === 'aeroway')) ZNYK.push([l.id, 'line-opacity', map.getPaintProperty(l.id, 'line-opacity') === undefined ? 1 : +map.getPaintProperty(l.id, 'line-opacity') || 1]);
      else if (l.id === 'building') ZNYK.push([l.id, 'fill-opacity', 1]);
      else if (d.znyk_nazvy && l.type === 'symbol' && sl === 'transportation_name') ZNYK.push([l.id, 'text-opacity', 1]);
    });
  }
  function onovytySoty(i, sh) {
    var id = 'soty-' + i, d = stylSot(sh);
    var a = trek(sh.prozorist, T, 1) * (T < (sh.t0 || 0) || T > (sh.t1 || 1e9) ? 0 : 1);
    var v = trek(sh.vysota, T, 0);
    var zum = map.getZoom();
    if (d.onovyty) { d.onovyty({ map: map, id: id, sh: sh, a: a, v: v, zum: zum, T: T, Kc: K.kol }); return; }
    // зблизька заливка яскравіша (MV-151): на z 12+ сота читається плямою, а не сіткою поверх вулиць
    var zal = (sh.zalyvka === undefined ? 0.55 : sh.zalyvka) * (sh.yaskravo_zblyzka === false ? 1 : lerp(1, 1.8, clamp((zum - 11) / 2, 0, 1)));
    // В1 («мурашник»): стиль зі styl_sot лежить над дорогами (як на сайті); без нього — як було (під дорогами)
    var fz = d.zalyvka === null ? Math.min(0.8, zal) : (sh.zalyvka !== undefined && sh.styl_sot === 'sklo' ? sh.zalyvka : d.zalyvka);
    map.setPaintProperty(id + '-f', 'fill-opacity', a * fz);
    map.setPaintProperty(id + '-l', 'line-opacity', a * (sh.mezha_prozorist === undefined ? d.mezha_a : sh.mezha_prozorist));
    if (d.znyk) ZNYK.forEach(function (l) { map.setPaintProperty(l[0], l[1], l[2] * (1 - a * d.znyk)); });
    // висота відносно наближення: зблизька стовпчики нижчі, інакше закривають вулиці (як на сайті)
    var maks = (sh.maks_vysota || 2500) * clamp(Math.pow(2, (sh.z_ref || 10.5) - zum), 0.06, 1.4);
    var rozpad = ['coalesce', ['feature-state', 'r'], 1];
    var vv = d.vysota === 'vsi' ? ['get', 'h'] :
      sh._ids.length ? ['case', ['in', ['get', 'id'], ['literal', sh._ids]], ['max', ['get', 'v'], 0.45], ['get', 'v']] : ['get', 'v'];
    map.setPaintProperty(id + '-3d', 'fill-extrusion-height', ['*', vv, maks, v, rozpad]);
    var op3 = d.op3d !== undefined ? d.op3d : zum > 13 ? 0.62 : zum > 12 ? 0.8 : 0.92;
    map.setPaintProperty(id + '-3d', 'fill-extrusion-opacity', Math.max(0.0, Math.min(1, a * (v > 0.001 ? op3 : 0))));
    (sh.rozpad || []).forEach(function (r) {
      var k = clamp((T - r.t) / 0.35, 0, 1);
      map.setFeatureState({ source: id, id: r.id }, { r: 1 - E.i(k) });
    });
  }

  // ---------------------------------------------------------------- адреси (В3): місця з числом подій, як карта підписника
  // sh: {dani: GeoJSON точок {n, t}, styl_adres, t0, t1, prozorist, rozmir}. Підпис — лише число подій, ніколи не номер
  // будинку (MV-25, MV-60). Стилі — рівноправні: 'kola' (коло з числом), 'svitni' (світні точки без числа),
  // 'kiltsia' (кільце з числом). Модулі можуть дописати свої: VAU.styliAdres[імʼя] = {dodaty(ctx), onovyty(ctx)}.
  function radiusAdres(baza) {   // радіус ∝ √n і росте з наближенням
    return ['*', ['interpolate', ['linear'], ['zoom'], 11, 0.45, 13, 0.75, 15, 1.1, 17, 1.5], ['+', baza, ['*', 6.5, ['sqrt', ['get', 'n']]]]];
  }
  function shryftZhyrnyi() {
    var f = (K.shryft || ['Noto Sans Regular']).map(function (x) { return String(x).replace('Regular', 'Bold'); });
    return f;
  }
  VAU.styliAdres.kola = VAU.styliAdres.kola || {
    dodaty: function (c) {
      var Kc = c.Kc;
      c.map.addLayer({ id: c.id + '-k', type: 'circle', source: c.id, paint: { 'circle-color': Kc.pk[1], 'circle-opacity': 0,
        'circle-radius': radiusAdres(12), 'circle-stroke-color': Kc.oreol, 'circle-stroke-width': 3, 'circle-stroke-opacity': 0 } }, c.pered);
      c.map.addLayer({ id: c.id + '-n', type: 'symbol', source: c.id, filter: ['>=', ['get', 'n'], c.sh.min_chyslo || 2],
        layout: { 'text-field': ['to-string', ['get', 'n']], 'text-font': shryftZhyrnyi(), 'text-size': ['interpolate', ['linear'], ['zoom'], 11, 18, 15, 30],
          'text-allow-overlap': true, 'symbol-sort-key': ['-', 0, ['get', 'n']] },
        paint: { 'text-color': K.t === 'temna' ? '#0B0D1C' : '#FFFFFF', 'text-opacity': 0 } });
    },
    onovyty: function (c) {
      c.map.setPaintProperty(c.id + '-k', 'circle-opacity', c.a * 0.92);
      c.map.setPaintProperty(c.id + '-k', 'circle-stroke-opacity', c.a);
      c.map.setPaintProperty(c.id + '-n', 'text-opacity', c.a);
    }
  };
  VAU.styliAdres.kiltsia = VAU.styliAdres.kiltsia || {
    dodaty: function (c) {
      var Kc = c.Kc;
      c.map.addLayer({ id: c.id + '-k', type: 'circle', source: c.id, paint: { 'circle-color': Kc.tlo, 'circle-opacity': 0,
        'circle-radius': radiusAdres(12), 'circle-stroke-color': Kc.pk[0], 'circle-stroke-width': 5, 'circle-stroke-opacity': 0 } }, c.pered);
      c.map.addLayer({ id: c.id + '-n', type: 'symbol', source: c.id, filter: ['>=', ['get', 'n'], c.sh.min_chyslo || 2],
        layout: { 'text-field': ['to-string', ['get', 'n']], 'text-font': shryftZhyrnyi(), 'text-size': ['interpolate', ['linear'], ['zoom'], 11, 18, 15, 30],
          'text-allow-overlap': true }, paint: { 'text-color': Kc.pidpys, 'text-opacity': 0 } });
    },
    onovyty: function (c) {
      c.map.setPaintProperty(c.id + '-k', 'circle-opacity', c.a * 0.85);
      c.map.setPaintProperty(c.id + '-k', 'circle-stroke-opacity', c.a);
      c.map.setPaintProperty(c.id + '-n', 'text-opacity', c.a);
    }
  };
  VAU.styliAdres.svitni = VAU.styliAdres.svitni || {
    dodaty: function (c) {
      var Kc = c.Kc;
      c.map.addLayer({ id: c.id + '-g', type: 'circle', source: c.id, paint: { 'circle-color': Kc.pk[1], 'circle-opacity': 0,
        'circle-radius': radiusAdres(18), 'circle-blur': 1 } }, c.pered);
      c.map.addLayer({ id: c.id + '-k', type: 'circle', source: c.id, paint: { 'circle-color': K.t === 'temna' ? '#E9FFF6' : Kc.pk[1], 'circle-opacity': 0,
        'circle-radius': ['*', 0.35, radiusAdres(8)] } }, c.pered);
    },
    onovyty: function (c) {
      c.map.setPaintProperty(c.id + '-g', 'circle-opacity', c.a * 0.75);
      c.map.setPaintProperty(c.id + '-k', 'circle-opacity', c.a);
    }
  };
  function dodatyAdresy(i, sh, pered) {
    var id = 'adresy-' + i, d = VAU.styliAdres[sh.styl_adres || 'kola'];
    if (!d) throw new Error('невідомий стиль адрес: ' + sh.styl_adres);
    map.addSource(id, { type: 'geojson', data: sh.dani });
    d.dodaty({ map: map, id: id, sh: sh, Kc: K.kol, pered: pered });
    sh._shary = map.getStyle().layers.filter(function (l) { return l.source === id; }).map(function (l) { return l.id; });
  }
  function onovytyAdresy(i, sh) {
    var id = 'adresy-' + i, d = VAU.styliAdres[sh.styl_adres || 'kola'];
    var a = trek(sh.prozorist, T, 1) * (T < (sh.t0 || 0) || T > (sh.t1 || 1e9) ? 0 : 1);
    // місця з'являються за власним часом t (хвиля, хронологія): фільтр за часом кадру
    var f = ['<=', ['get', 't'], T];
    sh._shary.forEach(function (l) {
      var bazovyi = l.slice(-2) === '-n' ? ['>=', ['get', 'n'], sh.min_chyslo || 2] : null;
      map.setFilter(l, bazovyi ? ['all', f, bazovyi] : f);
    });
    d.onovyty({ map: map, id: id, sh: sh, a: a, T: T, Kc: K.kol });
  }

  // ---------------------------------------------------------------- кінетичний текст
  // верх — під логотипом і рядком джерела (С5); низ — вище підпису TikTok (≈ 1500)
  var Y = { verkh: 400, vyshche: 580, tsentr: 800, nyzhche: 1020, niz: 1200 };
  function rozbyty(tekst) {   // *слово* — акцент
    var out = [], a = false;
    String(tekst).split(/(\*[^*]+\*|\n)/).forEach(function (ch) {
      if (!ch) return;
      if (ch === '\n') { out.push({ br: true }); return; }
      var akc = /^\*[\s\S]*\*$/.test(ch); if (akc) ch = ch.slice(1, -1);
      ch.split(/(\n|[ \t]+)/).forEach(function (w) {
        if (w === '\n') out.push({ br: true }); else if (w && !/^\s+$/.test(w)) out.push({ w: w, a: akc }); else if (w) out.push({ sp: true });
      });
    });
    return out;
  }
  function chyslo(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
  // узгодження з числом у кожному кадрі, поки лічильник біжить (С10): 1 подія, 3 події, 73 події, 49 подій
  function vidm(n, f) { n = Math.abs(Math.round(n)); var o = n % 10, d = n % 100;
    return o === 1 && d !== 11 ? f[0] : (o >= 2 && o <= 4 && !(d >= 12 && d <= 14)) ? f[1] : f[2]; }
  var LOGO = '<svg class="logo" viewBox="0 0 48 48"><path class="z1" d="M24 2 43 13v22L24 46 5 35V13z"/><path class="z2" d="M24 15 32 19.5v9L24 33l-8-4.5v-9z"/></svg>';

  function zbuduvatyTekst(it) {
    var el = document.createElement('div');
    el.className = 't ' + it.styl + (it.c ? ' c' : '') + (it.klas ? ' ' + it.klas : '');
    var y = typeof it.y === 'number' ? it.y : Y[it.y || 'tsentr'];
    el.style.top = y + 'px';
    if (it.styl === 'fin') {
      el.innerHTML = LOGO + '<h2>' + (it.zag || '') + '</h2>' + (it.tekst ? '<p>' + it.tekst + '</p>' : '') + (it.knopka ? '<span class="knopka">' + it.knopka + '</span>' : '');
    } else if (it.styl === 'kartka') {
      el.innerHTML = (it.zag ? '<b class="zag">' + it.zag + '</b>' : '') + '<span class="tilo"></span>' + (it.dz ? '<i class="dz">' + it.dz + '</i>' : '');
    } else if (it.styl === 'lich') {
      el.innerHTML = '<span class="n"></span>' + (it.pidpys ? '<small>' + it.pidpys + '</small>' : '');
    } else if (it.styl === 'godynnyk') {
      el.innerHTML = '<span class="n"></span>' + (it.pidpys ? '<small>' + it.pidpys + '</small>' : '');
    } else if (it.styl === 'variant') {
      el.innerHTML = '<b>' + it.bukva + '</b>' + it.tekst;
    } else if (it.styl === 'stovpchyky') {
      el.innerHTML = it.riady.map(function (r) { return '<div class="r"><span class="s" style="background:' + r.kolir + '"></span><span class="n">0</span><span class="nz">' + r.tekst + '</span></div>'; }).join('');
    } else if (it.styl === 'vidlik') {
      el.innerHTML = '<span class="n"></span>';
    } else if (it.styl === 'baner') {        // С1: кінцівка ≤ 1 с поверх руху, не окремий нерухомий кадр
      el.innerHTML = LOGO + '<div><b>' + (it.zag || '') + '</b><span>' + (it.knopka || '') + '</span></div>';
    } else if (it.styl === 'split') {        // С6: поділений екран — дві половини, по числу
      el.innerHTML = it.riady.map(function (r) { return '<div class="pol"' + (r.kolir ? ' style="background:' + r.kolir + '"' : '') + '>' +
        (r.zag ? '<span class="zag">' + r.zag + '</span>' : '') + '<span class="n">' + (r.n === undefined ? '' : '0') + '</span><span class="nz">' + r.tekst + '</span></div>'; }).join('');
    } else if (it.styl === 'komentar') {     // наклейка-коментар (ролик-відповідь)
      el.innerHTML = '<div class="khto"><span class="av"></span>' + (it.khto || '') + '</div><div class="tx">' + it.tekst + '</div>';
    } else if (it.styl === 'kolony') {       // вертикальні стовпчики (місяці)
      el.innerHTML = it.riady.map(function (r) { return '<div class="k' + (r.akc ? ' akc' : '') + '"><span class="n">' + (r.pokaz ? '0' : '') +
        '</span><span class="s"></span><span class="nz">' + r.tekst + '</span></div>'; }).join('');
    } else if (it.styl === 'shtamp') {       // печатка «МІФ» / «ФАКТ»
      el.innerHTML = '<span>' + it.tekst + '</span>';
    } else if (it.styl === 'kalendar') {     // «Календар року»: місяці → клітинки-дні, рівень 0–4 (ZAVDANNYA-138)
      var gi = 0;
      el.innerHTML = it.misiatsi.map(function (m) {
        var h = '<div class="mis"><b>' + m.nazva + '</b><div class="sitka">';
        for (var p = 0; p < m.pochatok; p++) h += '<span class="d pust"></span>';
        m.dni.forEach(function (k) { h += '<span class="d k' + k + '" data-i="' + (gi++) + '"></span>'; });
        return h + '</div></div>';
      }).join('');
    } else if (it.styl === 'taimer') {       // смуга часу «3 секунди»
      el.innerHTML = '<span class="s"></span><span class="n"></span>';
    } else {
      var html = '';
      if (it.styl === 'pidpys') html += '<span class="ramka">';
      rozbyty(it.tekst).forEach(function (s) {
        if (s.br) html += '<br>'; else if (s.sp) html += ' '; else html += '<span class="w' + (s.a ? ' a' : '') + '">' + s.w + '</span>';
      });
      if (it.styl === 'pidpys') html += '</span>';
      if (it.pid) html += '<small>' + it.pid + '</small>';   // slovo: другий рядок дрібніше
      if (it.styl === 'slovo') html = '<div class="vn">' + html + '</div>';   // у flex-контейнері пробіли між словами зникали
      el.innerHTML = html;
    }
    document.getElementById('tekst').appendChild(el);
    it.el = el; it.slova = Array.prototype.slice.call(el.querySelectorAll('.w'));
  }

  function odrazu(it) { return it.odrazu || it.t0 <= 0.0001; }   // С2: що стоїть з кадру 0 — видно повністю вже в кадрі 0
  function zaslona(it, t) {   // спільна поява й зникнення елемента
    var vh = it.vkhid === undefined ? 0.25 : it.vkhid, vyh = it.vykhid === undefined ? 0.22 : it.vykhid;
    var a = odrazu(it) ? 1 : clamp((t - it.t0) / Math.max(1e-3, vh), 0, 1), z = clamp((it.t1 - t) / Math.max(1e-3, vyh), 0, 1);
    return { a: a, z: z, v: t >= it.t0 && t <= it.t1 };
  }

  function onovytyTekst(it, t) {
    var el = it.el, s = zaslona(it, t);
    if (!s.v) { el.style.opacity = 0; return; }
    var vykhidK = E.i(1 - s.z);
    var anim = it.anim || 'slam';
    el.style.opacity = 1;
    el.style.transform = 'translateY(' + (-40 * vykhidK) + 'px)';
    if (vykhidK > 0) el.style.opacity = 1 - vykhidK;
    if (it.slova.length && it.styl !== 'pidpys') {
      var krok = it.krok === undefined ? (anim === 'slam' ? 0.09 : 0.06) : it.krok;
      it.slova.forEach(function (w, i) {
        var k = odrazu(it) ? 1 : clamp((t - it.t0 - i * krok) / (anim === 'slam' ? 0.2 : 0.3), 0, 1);
        if (anim === 'slam') {
          var sc = lerp(1.9, 1, E.oo(k));
          w.style.transform = 'scale(' + sc + ')'; w.style.opacity = clamp(k * 2, 0, 1); w.style.filter = 'blur(' + ((1 - k) * 10) + 'px)';
        } else if (anim === 'pop') {
          w.style.transform = 'scale(' + lerp(0.3, 1, E.back(k)) + ')'; w.style.opacity = clamp(k * 3, 0, 1);
        } else if (anim === 'vgoru') {
          w.style.transform = 'translateY(' + lerp(70, 0, E.oo(k)) + 'px)'; w.style.opacity = k;
        } else if (anim === 'drukarka') {
          w.style.opacity = k > 0 ? 1 : 0;
        } else { w.style.opacity = k; }
      });
    }
    if (it.styl === 'pidpys') {   // субтитр: усе видно, поточне слово — кольором (karaoke)
      var ramka = el.querySelector('.ramka');
      ramka.style.opacity = E.o(s.a);
      el.style.transform = 'translateY(' + (lerp(30, 0, E.o(s.a)) - 30 * vykhidK) + 'px)';
      var tryv = (it.t1 - it.t0 - 0.3), n = it.slova.length;
      var kur = Math.floor(clamp((t - it.t0 - 0.1) / tryv, 0, 0.999) * n);
      it.slova.forEach(function (w, i) { w.classList.toggle('zaraz', i === kur); });
    }
    if (it.styl === 'lich') {
      var k = clamp((t - it.t0 - (it.zatrymka || 0)) / (it.tryv || 1.6), 0, 1);
      var v = it.kluchi ? trek(it.kluchi, t, it.do) : lerp(it.vid || 0, it.do, E[it.e || 'oo'](k));
      el.querySelector('.n').textContent = (it.pered || '') + chyslo(v) + (it.pislia || '');
      if (it.formy && it.pidpys) el.querySelector('small').textContent = it.pidpys.replace('{f}', vidm(v, it.formy));
      var sc = 1 + 0.08 * Math.exp(-Math.max(0, t - it.t0 - (it.tryv || 1.6)) * 10) * (k >= 1 ? 1 : 0);
      el.style.transform = 'scale(' + lerp(0.6, 1, E.back(s.a)) * sc + ') translateY(' + (-40 * vykhidK) + 'px)';
      el.style.transformOrigin = it.c ? 'center' : 'left center';
    }
    if (it.styl === 'godynnyk') {
      var h = trek(it.hodyny, t, 0);
      var hh = Math.floor(h) % 24, mm = Math.floor((h - Math.floor(h)) * 60);
      el.querySelector('.n').textContent = String(hh).padStart(2, '0') + ':' + String(mm).padStart(2, '0');
    }
    if (it.styl === 'vidlik') {
      var ost = Math.ceil(it.t1 - t - 1e-6);
      var fr = (it.t1 - t) - Math.floor(it.t1 - t);
      el.querySelector('.n').textContent = Math.max(1, ost);
      el.style.transform = 'scale(' + lerp(1.0, 1.5, E.o(clamp((fr - 0.75) / 0.25, 0, 1))) + ')';
      el.style.opacity = clamp(fr * 2.5, 0, 1);
    }
    if (it.styl === 'kartka') {
      var tilo = el.querySelector('.tilo');
      // С4: переказ — цілим реченням (друкарка — лише якщо сценарій явно просить)
      var tekst = it.tekst, sym = it.drukarka !== true ? tekst.length : Math.floor(clamp(t - it.t0 - 0.25, 0, 99) * (it.shvydkist || 38));
      tilo.textContent = tekst.slice(0, sym);
      el.style.transform = 'translateY(' + (lerp(80, 0, E.oo(s.a)) - 40 * vykhidK) + 'px) scale(' + lerp(0.94, 1, E.oo(s.a)) + ')';
      el.style.opacity = Math.min(s.a * 2, 1 - vykhidK);
    }
    if (it.styl === 'variant') {
      var kv = odrazu(it) ? 1 : E.back(clamp((t - it.t0) / 0.3, 0, 1));
      el.style.transform = 'translateX(' + lerp(-700, 0, kv) + 'px)';
      el.classList.toggle('pravylno', it.vidpovid !== undefined && t >= it.vidpovid && it.pravylno);
      el.classList.toggle('ni', it.vidpovid !== undefined && t >= it.vidpovid && !it.pravylno);
    }
    if (it.styl === 'stovpchyky') {
      var rows = el.querySelectorAll('.r'), maks = Math.max.apply(null, it.riady.map(function (r) { return r.n; }));
      it.riady.forEach(function (r, i) {
        var k = E.oo(clamp((t - it.t0 - 0.15 * i) / 0.9, 0, 1));
        rows[i].querySelector('.s').style.width = Math.max(8, 520 * (r.n / maks) * k) + 'px';
        rows[i].querySelector('.n').textContent = chyslo(r.n * k);
        rows[i].style.opacity = clamp(k * 3, 0, 1);
      });
    }
    if (it.styl === 'fin') {
      el.style.transform = 'scale(' + lerp(0.85, 1, E.back(clamp(s.a, 0, 1))) + ')';
      el.style.opacity = s.a;
    }
    if (it.styl === 'baner') {
      var kb = E.back(clamp((t - it.t0) / 0.22, 0, 1));
      el.style.transform = 'translateY(' + lerp(260, 0, kb) + 'px) scale(' + lerp(0.9, 1, kb) + ')';
      el.style.opacity = Math.min(clamp(s.a * 3, 0, 1), s.z);
    }
    if (it.styl === 'slovo') {   // удар: панель на весь кадр «вбивається», слова — разом
      var ks = odrazu(it) ? 1 : E.oo(clamp((t - it.t0) / 0.16, 0, 1));
      el.style.transform = 'scale(' + lerp(1.25, 1, ks) + ')';
      el.style.opacity = Math.min(ks, s.z);
    }
    if (it.styl === 'split') {
      var pol = el.querySelectorAll('.pol');
      it.riady.forEach(function (r, i) {
        var kp = odrazu(it) ? 1 : E.oo(clamp((t - it.t0 - 0.12 * i) / 0.35, 0, 1));
        pol[i].style.transform = 'translateX(' + lerp(i ? 560 : -560, 0, kp) + 'px)';
        if (r.n !== undefined) pol[i].querySelector('.n').textContent = (r.pered || '') +
          chyslo(r.n * (odrazu(it) ? 1 : E.oo(clamp((t - it.t0 - 0.2 - 0.12 * i) / 0.8, 0, 1)))) + (r.pislia || '');
      });
    }
    if (it.styl === 'komentar') {
      var kk = odrazu(it) ? 1 : E.back(clamp((t - it.t0) / 0.3, 0, 1));
      el.style.transform = 'scale(' + lerp(0.5, 1, kk) + ') rotate(' + lerp(-6, -2, kk) + 'deg)';
      el.style.transformOrigin = 'left top';
    }
    if (it.styl === 'kolony') {
      var ks2 = el.querySelectorAll('.k'), mk = Math.max.apply(null, it.riady.map(function (r) { return r.n; }));
      it.riady.forEach(function (r, i) {
        var kc = E.oo(clamp((t - it.t0 - (it.krok || 0.12) * i) / 0.6, 0, 1));
        ks2[i].querySelector('.s').style.height = Math.max(6, (it.vysota || 520) * (r.n / mk) * kc) + 'px';
        if (r.pokaz) ks2[i].querySelector('.n').textContent = chyslo(r.n * kc);
      });
    }
    if (it.styl === 'shtamp') {
      var kt = odrazu(it) ? 1 : clamp((t - it.t0) / 0.18, 0, 1);
      el.querySelector('span').style.transform = 'rotate(-8deg) scale(' + lerp(2.4, 1, E.oo(kt)) + ')';
      el.style.opacity = Math.min(kt * 1.5, s.z);
    }
    if (it.styl === 'kalendar') {
      if (!it._dni) it._dni = Array.prototype.slice.call(el.querySelectorAll('.d[data-i]'));
      var cur = odrazu(it) && !it.kluchi ? 1e9 : trek(it.kluchi, t, 1e9);
      it._dni.forEach(function (d, i) {
        d.classList.toggle('on', i <= cur);
        d.classList.toggle('akc', (it.akc || []).indexOf(i) !== -1 && t >= (it.akc_t || 0));
      });
    }
    if (it.styl === 'taimer') {
      var zl = clamp((it.t1 - t) / Math.max(0.1, it.t1 - it.t0), 0, 1);
      el.querySelector('.s').style.width = (zl * 100) + '%';
      el.querySelector('.n').textContent = Math.max(0, Math.ceil(it.t1 - t - 1e-6)) + ' с';
    }
  }

  // ---------------------------------------------------------------- макети сайту
  function zbuduvatyUi(u) {
    var el = document.createElement('div');
    el.className = 'ui ' + u.typ;
    var ZN = '<svg viewBox="0 0 48 48"><path class="z1" d="M24 2 43 13v22L24 46 5 35V13z"/><path class="z2" d="M24 15 32 19.5v9L24 33l-8-4.5v-9z"/></svg>';
    if (u.typ === 'zavisa') { el.style.cssText = 'position:absolute;inset:0;background:' + (u.kolir || (K.t === 'svitla' ? '#F4F5FB' : '#05060F')); }
    if (u.typ === 'sota') el.innerHTML = ZN;   // персонаж «Сота» — лише знак, без обличчя (MV-148)
    if (u.typ === 'poshuk') el.innerHTML = '<span class="lupa"></span><span class="txt"></span><span class="kursor"></span>';
    if (u.typ === 'spov') el.innerHTML = ZN + '<div><b>' + u.zag + '</b><span>' + u.tekst + '</span></div><small>' + (u.koly || 'зараз') + '</small>';
    if (u.typ === 'panel') el.innerHTML = '<h3>' + u.zag + '</h3><div class="pid">' + (u.pid || '') + '</div>' +
      '<div class="ryad">' + u.chysla.map(function (c) { return '<div class="kl"><b data-n="' + c[0] + '">0</b><span>' + c[1] + '</span></div>'; }).join('') + '</div>' +
      (u.knopka ? '<span class="knopka">' + u.knopka + '</span>' : '');
    if (u.typ === 'dokument') el.innerHTML = '<span class="tsina">' + (u.tsina || '') + '</span><h4>' + u.zag + '</h4><div class="pid">' + (u.pid || '') + '</div>' +
      u.sektsii.map(function (s) {
        var bars = (s.bary || []).map(function (b) { return '<span class="bar" style="width:' + b[0] + 'px;background:' + b[1] + '"></span>'; }).join('');
        return '<div class="sek"><b>' + s.zag + '</b>' + (bars ? '<div>' + bars + '</div>' : '') + '<div class="smuha" style="width:92%"></div><div class="smuha" style="width:70%"></div></div>';
      }).join('');
    if (u.typ === 'kanal') el.innerHTML = '<div class="shapka">' + ZN + '<div>' + u.zag + '<small>' + (u.pid || '') + '</small></div></div>' +
      u.dopysy.map(function (d) { return '<div class="dopys">' + d[0] + '<i>' + (d[1] || '') + '</i></div>'; }).join('');
    document.getElementById('ui').appendChild(el);
    u.el = el;
  }
  function onovytyUi(u, t) {
    var el = u.el, s = zaslona(u, t);
    if (!s.v) { el.style.opacity = 0; return; }
    var vyh = E.i(1 - s.z);
    el.style.opacity = 1 - vyh;
    if (u.typ === 'zavisa') { el.style.opacity = 1; return; }
    if (u.typ === 'sota') { sota(u, t); return; }
    if (u.typ === 'poshuk') {
      var k = clamp((t - u.t0 - 0.35) / (u.druk || 1.2), 0, 1);
      var txt = u.tekst.slice(0, Math.round(u.tekst.length * k));
      el.querySelector('.txt').textContent = txt || '';
      if (!txt) el.querySelector('.txt').innerHTML = '<span class="pidkazka">' + (u.pidkazka || 'Адреса або вулиця') + '</span>';
      el.querySelector('.kursor').style.opacity = (Math.floor(t * 2.5) % 2 === 0 || k < 1) ? 1 : 0;
      el.style.transform = 'translateY(' + lerp(-260, 0, E.back(s.a)) + 'px)';
    } else if (u.typ === 'spov') {
      el.style.transform = 'translateY(' + (lerp(-420, 0, E.back(clamp((t - u.t0) / 0.45, 0, 1))) - 300 * vyh) + 'px)';
    } else if (u.typ === 'panel') {
      el.style.transform = 'translateY(' + lerp(900, 0, E.oo(clamp((t - u.t0) / 0.6, 0, 1))) + 'px)';
      el.querySelectorAll('b[data-n]').forEach(function (b, i) {
        var k = E.oo(clamp((t - u.t0 - 0.4 - i * 0.15) / 1.0, 0, 1));
        b.textContent = chyslo(+b.getAttribute('data-n') * k);
      });
    } else if (u.typ === 'dokument') {
      var sk = trek(u.prokrutka || [[u.t0, 0], [u.t1, 0]], t, 0);
      el.style.transform = 'translateY(' + lerp(1400, 0, E.oo(clamp((t - u.t0) / 0.6, 0, 1))) + 'px) rotate(' + lerp(4, 0, E.oo(s.a)) + 'deg)';
      el.querySelectorAll('.sek').forEach(function (sek, i) {
        var k = clamp((t - u.t0 - 0.6 - i * (u.krok || 0.5)) / 0.35, 0, 1);
        sek.style.opacity = k; sek.style.transform = 'translateY(' + lerp(30, 0, E.o(k)) + 'px)';
      });
      el.scrollTop = sk;
    } else if (u.typ === 'kanal') {
      el.style.transform = 'translateY(' + lerp(300, 0, E.oo(clamp((t - u.t0) / 0.5, 0, 1))) + 'px)';
      el.querySelectorAll('.dopys').forEach(function (d, i) {
        var k = clamp((t - u.t0 - 0.5 - i * (u.krok || 0.9)) / 0.3, 0, 1);
        d.style.opacity = k; d.style.transform = 'scale(' + lerp(0.8, 1, E.back(k)) + ')'; d.style.transformOrigin = 'left bottom';
        d.style.display = k > 0 ? 'block' : 'none';
      });
    }
  }

  // «Сота» стрибає між точками карти: дуга, стиск при приземленні, легке погойдування в спокої (MV-148)
  function sota(u, t) {
    var K_ = u.kroky, el = u.el, i = 0;
    while (i < K_.length - 1 && t >= K_[i + 1][0]) i++;
    var a = K_[i], b = K_[Math.min(i + 1, K_.length - 1)], strybok = u.strybok || 0.55;
    var pa = map.project([a[1], a[2]]), x = pa.x, y = pa.y, vys = 0, sx = 1, sy = 1;
    var kin = b[0], poch = kin - strybok;
    if (b !== a && t > poch) {
      var k = clamp((t - poch) / strybok, 0, 1), pb = map.project([b[1], b[2]]);
      x = lerp(pa.x, pb.x, E.io(k)); y = lerp(pa.y, pb.y, E.io(k));
      vys = Math.sin(Math.PI * k) * (u.vysota || 220);
      sx = 1 - 0.12 * Math.sin(Math.PI * k); sy = 1 + 0.18 * Math.sin(Math.PI * k);
    } else {
      var pislia = t - a[0];
      if (pislia >= 0 && pislia < 0.3) { var q = Math.sin(Math.PI * pislia / 0.3) * Math.exp(-pislia * 6); sx = 1 + 0.25 * q; sy = 1 - 0.25 * q; }
      vys = 6 * Math.sin(t * 4.2);
    }
    var r = u.rozmir || 130;
    el.style.left = (x - r / 2) + 'px'; el.style.top = (y - r - vys) + 'px';
    el.style.width = r + 'px'; el.style.height = r + 'px';
    el.style.transformOrigin = '50% 100%';
    el.style.transform = 'scale(' + sx + ',' + sy + ') rotate(' + (6 * Math.sin(t * 2.1)) + 'deg)';
    var s = zaslona(u, t);
    el.style.opacity = s.v ? Math.min(E.o(s.a), s.z) : 0;
  }

  // ---------------------------------------------------------------- мітки на карті й накладка
  function zbuduvatyMitku(m) {
    var el = document.createElement('div');
    el.className = 'm' + (m.styl ? ' ' + m.styl : '');
    el.innerHTML = (m.kolir ? '<i style="background:' + m.kolir + '"></i>' : '') + m.tekst + (m.n !== undefined ? '<b>' + m.n + '</b>' : '');
    document.getElementById('mitky').appendChild(el);
    m.el = el;
  }
  function onovytyMitku(m, t) {
    var s = zaslona(m, t);
    if (!s.v) { m.el.style.display = 'none'; return; }
    var p = map.project(m.c);
    if (p.x < -200 || p.x > W + 200 || p.y < -100 || p.y > H + 100) { m.el.style.display = 'none'; return; }
    m.el.style.display = 'block';
    var k = E.back(clamp((t - m.t0) / 0.28, 0, 1)), z = E.i(1 - s.z);
    m.el.style.left = (p.x + (m.dx || 0)) + 'px'; m.el.style.top = (p.y - 18 - (m.dy || 0)) + 'px';
    m.el.style.transform = 'translate(-50%, -100%) scale(' + lerp(0.2, 1, k) * (1 - 0.3 * z) + ')';
    m.el.style.transformOrigin = '50% 100%';
    m.el.style.opacity = clamp(k * 2, 0, 1) * (1 - z);
  }

  var ctx = null;
  function nakladka(t) {
    ctx.clearRect(0, 0, W, H);
    (S.lini || []).forEach(function (l) {
      if (t < l.t0 || t > (l.t2 || 1e9) + 0.5) return;
      var k = E.io(clamp((t - l.t0) / Math.max(0.01, l.t1 - l.t0), 0, 1));
      var a = l.t2 ? clamp(1 - (t - l.t2) / 0.5, 0, 1) : 1;
      var pts = l.coords.map(function (c) { return map.project(c); });
      var dov = 0, seg = [];
      for (var i = 1; i < pts.length; i++) { var d = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y); seg.push(d); dov += d; }
      var tsil = dov * k;
      ctx.save(); ctx.globalAlpha = a; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      [[l.shyr * 3.2, 0.18], [l.shyr * 1.8, 0.35], [l.shyr, 1]].forEach(function (sh) {
        ctx.strokeStyle = l.kolir; ctx.globalAlpha = a * sh[1]; ctx.lineWidth = sh[0];
        ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
        var ido = 0;
        for (var i = 1; i < pts.length; i++) {
          if (ido + seg[i - 1] <= tsil) { ctx.lineTo(pts[i].x, pts[i].y); ido += seg[i - 1]; }
          else { var r = (tsil - ido) / seg[i - 1]; ctx.lineTo(lerp(pts[i - 1].x, pts[i].x, r), lerp(pts[i - 1].y, pts[i].y, r)); break; }
        }
        ctx.stroke();
      });
      ctx.restore();
    });
    (S.kiltsia || []).forEach(function (r) {
      var age = t - r.t; if (age < 0 || age > (r.tryv || 1.2)) return;
      var k = age / (r.tryv || 1.2), p = map.project(r.c);
      ctx.save(); ctx.strokeStyle = r.kolir || '#66E6BA'; ctx.globalAlpha = (1 - k) * 0.9; ctx.lineWidth = 6 * (1 - k) + 1;
      ctx.beginPath(); ctx.arc(p.x, p.y, 20 + (r.radius || 260) * E.o(k), 0, Math.PI * 2); ctx.stroke(); ctx.restore();
    });
  }

  // ---------------------------------------------------------------- завантаження й кадр
  function zachekaty() {
    return new Promise(function (ok) {
      var gotovo = false;
      function perevir() {
        if (gotovo) return;
        if (map.loaded() && map.areTilesLoaded()) { gotovo = true; ok(); return; }
        map.once('idle', perevir);
        setTimeout(perevir, 250);
      }
      map.once('render', function () { setTimeout(perevir, 0); });
      map.triggerRepaint();
    });
  }

  window.kadr = function (t) {
    T = t;
    var k = kamera(t);
    map.jumpTo({ center: k.c, zoom: k.z, pitch: k.p || 0, bearing: k.b || 0 });
    (S.soty || []).forEach(function (sh, i) { onovytySoty(i, sh); });
    (S.adresy || []).forEach(function (sh, i) { onovytyAdresy(i, sh); });
    var druha = null;
    if (S.druha && DRUHA) {   // поділений екран (День і ніч): друга сцена в рамці, межа рухається за доріжкою kordon
      var yk = trek(S.druha.kordon, t, 0.5) * H;
      DRUHA.el.style.clipPath = 'inset(' + yk + 'px 0 0 0)';
      DRUHA.liniia.style.top = (yk - 3) + 'px';
      DRUHA.liniia.style.opacity = yk > 2 && yk < H - 2 ? 1 : 0;
      druha = DRUHA.el.contentWindow.kadr(t);
    }
    (S.tekst || []).forEach(function (it) { onovytyTekst(it, t); });
    (S.ui || []).forEach(function (u) { onovytyUi(u, t); });
    var spalakh = 0; (S.spalakh || []).forEach(function (f) { var a = t - f.t; if (a >= 0 && a < 0.35) spalakh = Math.max(spalakh, (f.sila || 0.6) * Math.exp(-a * 12)); });
    // спалах — лише підсвітка удару: повний білий шар засвічував весь кадр сірим (аркуші ZAVDANNYA-129)
    document.getElementById('spalakh').style.opacity = spalakh * 0.35;
    var dx = 0, dy = 0; (S.trus || []).forEach(function (f) { var a = t - f.t; if (a >= 0 && a < 0.5) { var s = (f.sila || 14) * Math.exp(-a * 9); dx += s * Math.sin(a * 83); dy += s * Math.cos(a * 71); } });
    document.getElementById('karta').style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(' + (dx || dy ? 1.03 : 1) + ')';
    var zv = 0, zn = 0, zf = 0;
    (S.tekst || []).forEach(function (it) {
      var s_ = zaslona(it, t); if (!s_.v || it.styl === 'vidlik' || it.styl === 'slovo' || it.styl === 'split' || it.styl === 'shtamp') return;
      var k = Math.min(E.o(s_.a), s_.z);
      var y = typeof it.y === 'number' ? it.y : Y[it.y || 'tsentr'];
      if (it.styl === 'fin') zf = Math.max(zf, k); else if (y < 820) zv = Math.max(zv, k); else zn = Math.max(zn, k);
    });
    (S.ui || []).forEach(function (u) { var s_ = zaslona(u, t); if (s_.v && (u.typ === 'dokument' || u.typ === 'kanal')) zf = Math.max(zf, Math.min(E.o(s_.a), s_.z) * 0.8); });
    document.getElementById('zat-v').style.opacity = zv * (S.zatemnennia === undefined ? 1 : S.zatemnennia);
    document.getElementById('zat-n').style.opacity = zn * (S.zatemnennia === undefined ? 1 : S.zatemnennia);
    document.getElementById('zat-f').style.opacity = zf * 0.82;
    var z = document.getElementById('znak'); z.style.opacity = S.znak === false ? 0 : trek(S.znak_prozorist, t, 0.92);
    var dz = document.getElementById('dzherelo'); dz.style.opacity = trek(S.dzherelo_prozorist, t, 1);
    return Promise.all([zachekaty(), druha]).then(function () {
      (S.mitky || []).forEach(function (m) { onovytyMitku(m, t); });
      nakladka(t);
      return true;
    });
  };

  function start() {
    var q = new URLSearchParams(location.search);
    return fetch(q.get('s')).then(function (v) { return v.json(); }).then(function (s) {
      S = s;
      return Promise.all((S.moduli || []).map(function (m) {   // власні вигляди (ZAVDANNYA-139) — до вибору теми
        return new Promise(function (ok, ne) { var e = document.createElement('script'); e.src = m; e.onload = ok; e.onerror = function () { ne(new Error('модуль ' + m)); }; document.head.appendChild(e); });
      }));
    }).then(function () {
      K = tema(S.tema || 'temna');
      document.documentElement.setAttribute('data-t', K.t);
      document.documentElement.setAttribute('data-tema', K.imia);
      if (S.bez_nakladok) document.documentElement.classList.add('bez-nakladok');
      // С5: джерело й «Голос згенеровано» — великі, вгорі під логотипом (зона, вільна від інтерфейсу TikTok); MV-150
      document.getElementById('dzherelo').innerHTML = '<span>' + (S.dzherelo === undefined ? 'Рішення судів (ЄДРСР) · лише те, що дійшло до суду' : S.dzherelo) +
        '</span>' + (S.holos_poznaka ? '<span class="hp">' + S.holos_poznaka + '</span>' : '');
      ctx = document.getElementById('nakladka').getContext('2d');
      (S.tekst || []).forEach(zbuduvatyTekst);
      (S.ui || []).forEach(zbuduvatyUi);
      (S.mitky || []).forEach(zbuduvatyMitku);
      if (S.druha) {
        var fr = document.createElement('iframe');
        fr.id = 'druha'; fr.src = 'stsena.html?s=' + encodeURIComponent(S.druha.s);
        var li = document.createElement('div'); li.id = 'druha-liniia';
        var kadrEl = document.getElementById('kadr');
        kadrEl.insertBefore(fr, document.getElementById('nakladka'));
        kadrEl.insertBefore(li, document.getElementById('nakladka'));
        DRUHA = { el: fr, liniia: li, gotovo: new Promise(function (ok) { fr.onload = function () { fr.contentWindow.gotovo.then(ok); }; }) };
      }
      return fetch(K.styl).then(function (v) { return v.json(); });
    }).then(function (styl) {
      var k0 = kamera(0);
      maplibregl.setWorkerUrl('../../site/hra/biblioteka/maplibre-gl-csp-worker.js');
      map = new maplibregl.Map({ container: 'karta', style: patchStyle(styl, K.t), center: k0.c, zoom: k0.z, pitch: k0.p || 0, bearing: k0.b || 0,
        interactive: false, attributionControl: { compact: false }, fadeDuration: 0, maxPitch: 85, preserveDrawingBuffer: true,
        pixelRatio: 1, canvasContextAttributes: { antialias: true, preserveDrawingBuffer: true } });
      window._map = map;
      return new Promise(function (ok) { map.on('load', ok); });
    }).then(function () {
      var pershyiSymvol = (map.getStyle().layers.find(function (l) { return l.type === 'symbol'; }) || {}).id;
      if (S.mezha) {
        map.addSource('mezha', { type: 'geojson', data: S.mezha });
        map.addLayer({ id: 'mezha', type: 'line', source: 'mezha', paint: { 'line-color': K.kol.mezha, 'line-width': 2, 'line-opacity': 0.7 } }, pershyiSymvol);
      }
      // pershyiSymvol у стилях OpenFreeMap — назва води, вона йде ДО будинків і доріг: усе, що вставлено перед нею, лежить
      // під дорогами (причина «мурашника», В1). nadLiniiamy — над останнім шаром ліній, під підписами (як на сайті).
      var shary = map.getStyle().layers, ost = shary.map(function (l) { return l.type !== 'symbol'; }).lastIndexOf(true);
      var nadLiniiamy = (shary[ost + 1] || {}).id;
      if (S.mezha && S.nad_dorohamy) map.moveLayer('mezha', nadLiniiamy);   // MV-161: межа міста — над дорогами
      (S.soty || []).forEach(function (sh, i) { dodatySoty(i, sh, sh.styl_sot ? nadLiniiamy : pershyiSymvol); });
      (S.adresy || []).forEach(function (sh, i) { dodatyAdresy(i, sh, nadLiniiamy); });
      // MV-161: точки подій — над дорогами (nad_dorohamy); інакше — як було (під дорогами)
      (S.tochky || []).forEach(function (sh, i) { map.addLayer(sharTochok('tochky-' + i, sh), S.tochky_nad_pidpysamy ? undefined : S.nad_dorohamy ? nadLiniiamy : pershyiSymvol); });
      return Promise.all([document.fonts.ready, DRUHA ? DRUHA.gotovo : null]);
    }).then(function () { return window.kadr(0); }).then(function () {
      return { tryvalist: S.tryvalist };
    });
  }
  window.gotovo = start();
})();

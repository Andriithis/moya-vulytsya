// Візуальна лабораторія роликів (ZAVDANNYA-139): додаткові теми й вигляди для сцени рушія «Вау».
//
// Окремий модуль, щоб не переписувати stsena.js навпіл з іншими завданнями. Сцена вантажить його перед stsena.js і
// викликає лише три гачки: теми (window.VAU_VYHLIADY.temy → KOL), dodaty(api) після шарів карти, kadr(t) у кожному кадрі.
// Вмикається полями сценарію:
//   tema — 'temna' | 'svitla' (як було) або нова тема: 'nich', 'papir', 'vechir', 'sontse', 'monokhrom'
//   styl — об'єкт або список об'єктів {typ, ...}; typ:
//     соти:     'sklo_kraia' (скло з підсвіткою країв), 'neon' (контурні неонові), 'dykhannia' (пульс за числом),
//               'stovpy' (3D-стовпчики: vsi / skliani / rist — параметрами)
//     адреси:   'svitni' (світні точки), 'teplo' (теплова пляма), 'shpyli' (тонкі 3D-шпилі), 'sonyashnyk' (події
//               довкола місця), 'khvyli' (кільця-хвилі), 'bulbashky' (бульбашки з числом)
//     не карта: 'infografika', 'hodynnyk', 'kalendar', 'kartka_zvit' — на весь кадр поверх карти
// Колір = кількість даних або вид події, не «небезпека»: жодного червоного (MV-58, AGENTS.md розд. 4). Номерів будинків
// тут немає взагалі — місця приходять лише координатою й числом подій (MV-25, MV-60).
(function () {
  'use strict';
  // ------------------------------------------------------------------ теми (поля як KOL у stsena.js + osnova)
  var TEMY = {
    // нічне місто: майже чорне тло, неоновий індиго, вершини — яскрава м'ята
    nich: { osnova: 'temna', tlo: '#05060D', voda: '#0A1130', park: '#05110F', budynky: '#0C0E1C', doroha: '#1A1D3C', pidpys: '#C9CCF5', oreol: '#05060D',
      sc: ['#2A2D8C', '#3B3DC8', '#5658F2', '#7E74FF', '#A98CFF'], sl: '#8E93FF', pk: ['#2FF5C0', '#8BFFE2'], b3d: '#141734', mezha: '#6A70C8', akc: '#2FF5C0' },
    // папір і чорнило: кремове тло, соти — чорнильно-сині відтінки
    papir: { osnova: 'svitla', tlo: '#F4EFE3', voda: '#D9D9D2', park: '#E9E5D3', budynky: '#E6DFCF', doroha: '#D3CAB6', pidpys: '#2B2A3A', oreol: '#F4EFE3',
      sc: ['#C8C6DA', '#9C99C2', '#6C68A5', '#45418A', '#24205E'], sl: '#24205E', pk: ['#1F8F6D', '#11704F'], b3d: '#E2DACA', mezha: '#6F6A63', akc: '#24205E' },
    // тепла вечірня: сливове тло, шкала до бурштину; вершини — м'ята бренду
    vechir: { osnova: 'temna', tlo: '#1B1326', voda: '#21193A', park: '#1A1A22', budynky: '#281C33', doroha: '#33263F', pidpys: '#F3DECB', oreol: '#1B1326',
      sc: ['#4D3266', '#6E4180', '#97588A', '#C78577', '#ECB461'], sl: '#F3C88E', pk: ['#66E6BA', '#A6F3D8'], b3d: '#2D2140', mezha: '#A88BA8', akc: '#F5B759' },
    // контрастна для телефона на сонці: біле тло, темні дороги, насичений індиго
    sontse: { osnova: 'svitla', tlo: '#FFFFFF', voda: '#B8D3FF', park: '#E2F4DA', budynky: '#E9E9EF', doroha: '#A3A5B4', pidpys: '#05060D', oreol: '#FFFFFF',
      sc: ['#AEB2F7', '#7E84F0', '#5057E0', '#2A30BE', '#12148A'], sl: '#05060D', pk: ['#00B07C', '#008A61'], b3d: '#DADBE5', mezha: '#30323F', akc: '#12148A' },
    // монохром з одним акцентом: сірі соти, лише найбільші — м'ятні
    monokhrom: { osnova: 'temna', tlo: '#0E0E11', voda: '#18181D', park: '#121215', budynky: '#1D1D22', doroha: '#28282E', pidpys: '#D2D2D8', oreol: '#0E0E11',
      sc: ['#2E2E35', '#45454E', '#60606A', '#80808B', '#A6A6B1'], sl: '#B6B6C0', pk: ['#66E6BA', '#8CECCB'], b3d: '#202026', mezha: '#77777F', akc: '#66E6BA' }
  };

  var A = null, SP = [], ctx = null, POVNYI = null;
  function spysok(S) { return !S.styl ? [] : Array.isArray(S.styl) ? S.styl : [S.styl]; }
  function cl(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function lr(a, b, k) { return a + (b - a) * k; }
  function eo(k) { return 1 - Math.pow(1 - k, 3); }
  function eback(k) { var c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2); }
  function rgba(h, a) { var v = parseInt(h.slice(1), 16); return 'rgba(' + (v >> 16 & 255) + ',' + (v >> 8 & 255) + ',' + (v & 255) + ',' + a + ')'; }
  function chyslo(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
  function alfa(st, t) { return A.trek(st.prozorist, t, 1) * (t < (st.t0 || 0) - 1e-6 || t > (st.t1 || 1e9) ? 0 : 1); }
  function kolirKlasu(Kc) { return ['match', ['get', 'k'], 1, Kc.sc[0], 2, Kc.sc[1], 3, Kc.sc[2], 4, Kc.sc[3], Kc.sc[4]]; }
  function kolirVershyny(Kc) { return ['case', ['>', ['get', 'v'], 0], ['interpolate', ['linear'], ['get', 'v'], 0, Kc.pk[0], 1, Kc.pk[1]], kolirKlasu(Kc)]; }
  // «з'являється хвилею від центру»: 0…1 за часом і полем d (0 — центр, 1 — край)
  function khvylia(tt, rozkyd, tryv) {
    var x = ['min', 1, ['max', 0, ['/', ['-', tt, ['*', ['get', 'd'], rozkyd]], tryv]]];
    return ['*', ['*', x, x], ['-', 3, ['*', 2, x]]];
  }
  function zumK(zref, st) { return cl(Math.pow(2, (zref - A.map.getZoom())), 0.06, 1.6); }

  // ------------------------------------------------------------------ місця (адреси): {x, y, n, g, t} → GeoJSON точок
  function mistsiaGeo(m, kolory) {
    var f = [];
    for (var i = 0; i < m.x.length; i++) {
      f.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [m.x[i] / 1e5, m.y[i] / 1e5] },
        properties: { n: m.n[i], t: m.t ? m.t[i] : 0, kol: kolory[m.g[i]] || kolory[0], i: i } });
    }
    return { type: 'FeatureCollection', features: f };
  }
  function shestykutnyk(lon, lat, r) {   // тонкий шпиль — шестикутник радіуса r метрів
    var k = [], dlat = r / 111320, dlon = r / (111320 * Math.cos(lat * Math.PI / 180));
    for (var j = 0; j <= 6; j++) { var a = (j % 6) * Math.PI / 3; k.push([lon + dlon * Math.cos(a), lat + dlat * Math.sin(a)]); }
    return [k];
  }

  // ------------------------------------------------------------------ вигляди
  var V = {};

  // Скло з підсвіткою країв: прозора заливка над дорогами, світна розмита межа й тонка чітка лінія
  V.sklo_kraia = {
    dodaty: function (st, id) {
      var m = A.map, Kc = A.Kc;
      m.addSource(id, { type: 'geojson', data: st.dani });
      m.addLayer({ id: id + '-f', type: 'fill', source: id, paint: { 'fill-color': kolirKlasu(Kc), 'fill-opacity': 0 } }, A.nad);
      m.addLayer({ id: id + '-vf', type: 'fill', source: id, filter: ['>', ['get', 'v'], 0], paint: { 'fill-color': Kc.pk[1], 'fill-opacity': 0 } }, A.nad);
      m.addLayer({ id: id + '-g', type: 'line', source: id, paint: { 'line-color': A.temna ? Kc.sl : Kc.sc[3], 'line-width': 14, 'line-blur': 12, 'line-opacity': 0 } }, A.nad);
      m.addLayer({ id: id + '-vg', type: 'line', source: id, filter: ['>', ['get', 'v'], 0], paint: { 'line-color': Kc.pk[1], 'line-width': 16, 'line-blur': 12, 'line-opacity': 0 } }, A.nad);
      m.addLayer({ id: id + '-l', type: 'line', source: id, paint: { 'line-color': A.temna ? '#F0F1FA' : Kc.sl, 'line-width': 1.6, 'line-opacity': 0 } }, A.nad);
    },
    kadr: function (st, id, t) {
      var m = A.map, a = alfa(st, t), tt = t - (st.t0 || 0);
      var z = khvylia(tt, st.rozkyd || 1.2, 0.5);
      m.setPaintProperty(id + '-f', 'fill-opacity', ['*', a * (st.zalyvka || (A.temna ? 0.3 : 0.38)), z]);
      m.setPaintProperty(id + '-vf', 'fill-opacity', ['*', a * 0.3, z]);
      m.setPaintProperty(id + '-g', 'line-opacity', ['*', a * (A.temna ? 0.55 : 0.45), z]);
      m.setPaintProperty(id + '-vg', 'line-opacity', ['*', a * 0.8, z]);
      m.setPaintProperty(id + '-l', 'line-opacity', ['*', a * 0.85, z]);
    }
  };

  // Контурні неонові: майже без заливки, межа світиться кольором класу; соти «вмикаються» хвилею від центру
  V.neon = {
    dodaty: function (st, id) {
      var m = A.map, Kc = A.Kc, kol = kolirVershyny(Kc);
      m.addSource(id, { type: 'geojson', data: st.dani });
      m.addLayer({ id: id + '-f', type: 'fill', source: id, paint: { 'fill-color': kol, 'fill-opacity': 0 } }, A.nad);
      [[22, 16, 0.3], [8, 5, 0.65], [2.4, 0, 1]].forEach(function (s, j) {
        m.addLayer({ id: id + '-l' + j, type: 'line', source: id, layout: { 'line-join': 'round' },
          paint: { 'line-color': j === 2 ? (A.temna ? ['case', ['>', ['get', 'v'], 0], '#E6FFF6', '#E4E2FF'] : kol) : kol, 'line-width': s[0], 'line-blur': s[1], 'line-opacity': 0 } }, A.nad);
      });
    },
    kadr: function (st, id, t) {
      var m = A.map, a = alfa(st, t), tt = t - (st.t0 || 0);
      var z = khvylia(tt, st.rozkyd || 1.5, 0.25);
      // легке мерехтіння «неонової трубки» при вмиканні — лише в перші 0,25 с кожної соти
      m.setPaintProperty(id + '-f', 'fill-opacity', ['*', a * (st.zalyvka || 0.08), z]);
      [0.3, 0.65, 1].forEach(function (k, j) { m.setPaintProperty(id + '-l' + j, 'line-opacity', ['*', a * k, z]); });
    }
  };

  // «Дихаючі»: заливка й низький 3D пульсують; амплітуда — за класом (більше подій — сильніше дихає), фаза — хвилею
  V.dykhannia = {
    dodaty: function (st, id) {
      var m = A.map, Kc = A.Kc;
      m.addSource(id, { type: 'geojson', data: st.dani });
      m.addLayer({ id: id + '-f', type: 'fill', source: id, paint: { 'fill-color': kolirVershyny(Kc), 'fill-opacity': 0 } }, A.nad);
      m.addLayer({ id: id + '-l', type: 'line', source: id, paint: { 'line-color': A.temna ? Kc.sl : Kc.tlo, 'line-width': 1.4, 'line-opacity': 0 } }, A.nad);
      if (st.vysota !== false) m.addLayer({ id: id + '-3d', type: 'fill-extrusion', source: id, filter: ['>=', ['get', 'k'], 4],
        paint: { 'fill-extrusion-color': kolirVershyny(Kc), 'fill-extrusion-height': 0, 'fill-extrusion-opacity': 0.85, 'fill-extrusion-vertical-gradient': true } }, A.nad);
    },
    kadr: function (st, id, t) {
      var m = A.map, a = alfa(st, t), w = 2 * Math.PI / (st.period || 1.6);
      var hvylia = ['+', 0.5, ['*', 0.5, ['sin', ['-', t * w, ['*', ['get', 'd'], 9]]]]];
      var amp = ['/', ['get', 'k'], 5];
      m.setPaintProperty(id + '-f', 'fill-opacity', ['*', a, ['+', 0.16, ['*', 0.62, amp, hvylia]]]);
      m.setPaintProperty(id + '-l', 'line-opacity', a * 0.5);
      if (st.vysota !== false) m.setPaintProperty(id + '-3d', 'fill-extrusion-height',
        ['*', a * (st.maks_vysota || 900) * zumK(st.z_ref || 11), ['+', 0.15, ['get', 'h']], ['+', 0.35, ['*', 0.65, hvylia]]]);
    }
  };

  // 3D-стовпчики: vsi — усі соти; skliani — напівпрозорі над вулицями з контуром на землі; rist — ростуть хвилею
  V.stovpy = {
    dodaty: function (st, id) {
      var m = A.map, Kc = A.Kc;
      m.addSource(id, { type: 'geojson', data: st.dani });
      if (st.kontur !== false) {
        m.addLayer({ id: id + '-f', type: 'fill', source: id, paint: { 'fill-color': kolirKlasu(Kc), 'fill-opacity': 0 } }, A.nad);
        m.addLayer({ id: id + '-l', type: 'line', source: id, paint: { 'line-color': A.temna ? Kc.sl : Kc.sc[4], 'line-width': 1.6, 'line-opacity': 0 } }, A.nad);
      }
      m.addLayer({ id: id + '-3d', type: 'fill-extrusion', source: id, filter: st.lyshe_vershyny ? ['>', ['get', 'v'], 0] : ['>=', ['get', 'n'], st.min_n || 1],
        paint: { 'fill-extrusion-color': kolirVershyny(Kc), 'fill-extrusion-height': 0, 'fill-extrusion-opacity': st.skliani ? 0.42 : 0.92,
          'fill-extrusion-vertical-gradient': !st.skliani } }, A.nad);
    },
    kadr: function (st, id, t) {
      var m = A.map, a = alfa(st, t), tt = t - (st.t0 || 0);
      var rist = st.rist ? khvylia(tt, st.rozkyd || 2.2, st.tryv_rostu || 0.9) : 1;
      var maks = (st.maks_vysota || 2600) * zumK(st.z_ref || 10.8) * A.trek(st.vysota, t, 1);
      m.setPaintProperty(id + '-3d', 'fill-extrusion-height', ['*', maks, ['+', 0.04, ['get', 'h']], rist]);
      m.setPaintProperty(id + '-3d', 'fill-extrusion-opacity', cl(a, 0, 1) * (st.skliani ? 0.42 : 0.92));
      if (st.kontur !== false) {
        m.setPaintProperty(id + '-f', 'fill-opacity', a * (st.skliani ? 0.2 : 0.35));
        m.setPaintProperty(id + '-l', 'line-opacity', a * 0.7);
      }
    }
  };

  // Світні точки: кожне місце — точка з ореолом; розмір — за числом подій, колір — вид; вискакують за часом t
  V.svitni = {
    dodaty: function (st, id) {
      var m = A.map;
      m.addSource(id, { type: 'geojson', data: mistsiaGeo(st.mistsia, A.S.kolory) });
      m.addLayer({ id: id + '-o', type: 'circle', source: id, paint: { 'circle-color': ['get', 'kol'], 'circle-radius': 0, 'circle-blur': 1, 'circle-opacity': 0 } }, A.nad);
      m.addLayer({ id: id + '-y', type: 'circle', source: id, paint: { 'circle-color': ['get', 'kol'], 'circle-radius': 0, 'circle-blur': 0.25, 'circle-opacity': 0 } }, A.nad);
      m.addLayer({ id: id + '-b', type: 'circle', source: id, paint: { 'circle-color': '#FFFFFF', 'circle-radius': 0, 'circle-blur': 0.5, 'circle-opacity': 0 } }, A.nad);
    },
    kadr: function (st, id, t) {
      var m = A.map, a = alfa(st, t), zf = Math.pow(2, (m.getZoom() - (st.z_ref || 14.5)) * 0.6);
      var vik = ['-', t, ['get', 't']];
      var pop = ['case', ['<', vik, 0], 0, ['<', vik, 0.18], ['*', 1.6, ['/', vik, 0.18]], ['<', vik, 0.45], ['-', 1.6, ['*', 0.6, ['/', ['-', vik, 0.18], 0.27]]], 1];
      var r = ['*', zf * (st.rozmir || 1), pop, ['+', 4, ['*', 3.2, ['sqrt', ['get', 'n']]]]];
      var pulse = 1 + 0.12 * Math.sin(t * 3.2);
      m.setPaintProperty(id + '-o', 'circle-radius', ['*', r, 3.2 * pulse]);
      m.setPaintProperty(id + '-o', 'circle-opacity', a * (A.temna ? 0.42 : 0.3));
      m.setPaintProperty(id + '-y', 'circle-radius', r);
      m.setPaintProperty(id + '-y', 'circle-opacity', a * 0.95);
      m.setPaintProperty(id + '-b', 'circle-radius', ['*', r, 0.38]);
      m.setPaintProperty(id + '-b', 'circle-opacity', a * (A.temna ? 0.85 : 0.6));
    }
  };

  // Теплова пляма: щільність подій розмитою плямою (індиго → м'ята → майже біле), без червоного
  V.teplo = {
    dodaty: function (st, id) {
      var m = A.map, Kc = A.Kc;
      m.addSource(id, { type: 'geojson', data: mistsiaGeo(st.mistsia, A.S.kolory) });
      var kinets = A.temna ? '#F2FFF9' : Kc.pk[1];
      m.addLayer({ id: id, type: 'heatmap', source: id, paint: {
        'heatmap-weight': ['min', 1, ['/', ['ln', ['+', 1, ['get', 'n']]], st.ln_maks || 4]],
        'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(0,0,0,0)', 0.12, rgba(Kc.sc[0], 0.55), 0.35, rgba(Kc.sc[2], 0.8),
          0.6, rgba(Kc.sc[4], 0.9), 0.82, Kc.pk[0], 1, kinets],
        'heatmap-radius': 30, 'heatmap-intensity': 0, 'heatmap-opacity': 0 } }, A.nad);
    },
    kadr: function (st, id, t) {
      var m = A.map, a = alfa(st, t), k = eo(cl((t - (st.t0 || 0)) / (st.tryv || 1.6), 0, 1));
      m.setPaintProperty(id, 'heatmap-radius', (st.radius || 34) * Math.pow(2, (m.getZoom() - (st.z_ref || 13)) * 0.75));
      m.setPaintProperty(id, 'heatmap-intensity', lr(0.15, st.intensyvnist || 1.1, k));
      m.setPaintProperty(id, 'heatmap-opacity', a * 0.92);
    }
  };

  // Тонкі 3D-шпилі: на кожному місці — вузький шестикутний стовпчик, висота — за числом, ростуть за часом t
  V.shpyli = {
    dodaty: function (st, id) {
      var m = A.map, d = st.mistsia, f = [];
      for (var i = 0; i < d.x.length; i++) {
        f.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: shestykutnyk(d.x[i] / 1e5, d.y[i] / 1e5, st.r || 9) },
          properties: { n: d.n[i], t: d.t ? d.t[i] : 0, kol: A.S.kolory[d.g[i]] || A.S.kolory[0] } });
      }
      m.addSource(id, { type: 'geojson', data: { type: 'FeatureCollection', features: f } });
      m.addSource(id + '-p', { type: 'geojson', data: mistsiaGeo(d, A.S.kolory) });
      m.addLayer({ id: id + '-o', type: 'circle', source: id + '-p', paint: { 'circle-color': ['get', 'kol'], 'circle-radius': 0, 'circle-blur': 1, 'circle-opacity': 0 } }, A.nad);
      m.addLayer({ id: id, type: 'fill-extrusion', source: id, paint: { 'fill-extrusion-color': ['get', 'kol'], 'fill-extrusion-height': 0,
        'fill-extrusion-opacity': 0.95, 'fill-extrusion-vertical-gradient': true } }, A.nad);
    },
    kadr: function (st, id, t) {
      var m = A.map, a = alfa(st, t);
      var x = ['min', 1, ['max', 0, ['/', ['-', t, ['get', 't']], st.tryv_rostu || 0.7]]];
      var rist = ['-', 1, ['*', ['-', 1, x], ['-', 1, x], ['-', 1, x]]];
      m.setPaintProperty(id, 'fill-extrusion-height', ['*', st.m_na_podiu || 14, ['min', st.maks_n || 120, ['get', 'n']], rist]);
      m.setPaintProperty(id, 'fill-extrusion-opacity', a * 0.95);
      m.setPaintProperty(id + '-o', 'circle-radius', ['*', 14 * Math.pow(2, (m.getZoom() - 14.5) * 0.6), ['sqrt', ['min', 60, ['get', 'n']]], x]);
      m.setPaintProperty(id + '-o', 'circle-opacity', a * 0.35);
    }
  };

  // Соняшник: події одного публічного місця розкладаються спіраллю довкола нього (кут золотого перетину), число в центрі
  V.sonyashnyk = {
    kadr: function (st, id, t) {
      var a = alfa(st, t); if (a <= 0) return;
      var p = A.map.project(st.c), d = st.podii, krok = (st.krok || 17) * Math.pow(2, (A.map.getZoom() - (st.z_ref || 15)) * 0.7);
      var rozm = (st.rozmir || 9) * Math.pow(2, (A.map.getZoom() - (st.z_ref || 15)) * 0.5), vidkryto = 0;
      ctx.save(); ctx.globalAlpha = a;
      for (var i = 0; i < d.g.length; i++) {
        var vik = t - d.t[i]; if (vik < 0) continue;
        vidkryto++;
        var k = cl(vik / 0.4, 0, 1), r = krok * Math.sqrt(i + 1.5), ug = (i + 1) * 2.39996 + (st.oberty || 0.12) * t;
        var x = p.x + r * Math.cos(ug) * eo(k), y = p.y + r * Math.sin(ug) * eo(k) * (st.splushchennia || 1);
        var kol = A.S.kolory[d.g[i]] || '#66E6BA', rr = rozm * (k < 1 ? lr(1.8, 1, eo(k)) : 1);
        ctx.fillStyle = rgba(kol, 0.22); ctx.beginPath(); ctx.arc(x, y, rr * 2.4, 0, 7); ctx.fill();
        ctx.fillStyle = kol; ctx.beginPath(); ctx.arc(x, y, rr, 0, 7); ctx.fill();
      }
      // центр — кружок із числом (тільки число подій, без адреси)
      var R = 62 + 6 * Math.sin(t * 4);
      ctx.fillStyle = A.temna ? 'rgba(17,20,42,.92)' : 'rgba(255,255,255,.95)';
      ctx.strokeStyle = A.Kc.pk[1]; ctx.lineWidth = 6;
      ctx.beginPath(); ctx.arc(p.x, p.y, R, 0, 7); ctx.fill(); ctx.stroke();
      ctx.fillStyle = A.temna ? '#F0F1FA' : '#1C1E2D'; ctx.font = '800 54px Plex'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(chyslo(vidkryto), p.x, p.y + 3);
      ctx.restore();
    }
  };

  // Кільця-хвилі: кожне місце час від часу «пульсує» кільцем; більше подій — більше кільце й частіше
  V.khvyli = {
    kadr: function (st, id, t) {
      var a = alfa(st, t); if (a <= 0) return;
      var d = st.mistsia, zf = Math.pow(2, (A.map.getZoom() - (st.z_ref || 14)) * 0.6);
      ctx.save();
      for (var i = 0; i < d.x.length; i++) {
        if (t < (d.t ? d.t[i] : 0)) continue;
        var p = A.map.project([d.x[i] / 1e5, d.y[i] / 1e5]);
        if (p.x < -200 || p.x > A.W + 200 || p.y < -200 || p.y > A.H + 200) continue;
        var n = d.n[i], kol = A.S.kolory[d.g[i]] || '#66E6BA';
        var Rm = (26 + 22 * Math.sqrt(n)) * zf, per = lr(2.4, 1.1, cl(Math.log(n) / 4.5, 0, 1)), faza = (i * 0.618) % 1;
        for (var j = 0; j < 2; j++) {
          var k = ((t - (d.t ? d.t[i] : 0)) / per + faza + j * 0.5) % 1;
          ctx.strokeStyle = kol; ctx.globalAlpha = a * (1 - k) * 0.85; ctx.lineWidth = lr(5, 1, k);
          ctx.beginPath(); ctx.arc(p.x, p.y, 4 + Rm * eo(k), 0, 7); ctx.stroke();
        }
        ctx.globalAlpha = a; ctx.fillStyle = kol; ctx.beginPath(); ctx.arc(p.x, p.y, 4 + 1.6 * Math.sqrt(n) * zf, 0, 7); ctx.fill();
      }
      ctx.restore();
    }
  };

  // Бульбашки з числом: найбільші місця — кружки з кількістю подій; спливають по черзі й ледь погойдуються
  V.bulbashky = {
    kadr: function (st, id, t) {
      var a = alfa(st, t); if (a <= 0) return;
      var d = st.mistsia, zf = Math.pow(2, (A.map.getZoom() - (st.z_ref || 14)) * 0.5);
      ctx.save(); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      for (var i = d.x.length - 1; i >= 0; i--) {
        var t0 = d.t ? d.t[i] : 0; if (t < t0) continue;
        var p = A.map.project([d.x[i] / 1e5, d.y[i] / 1e5]);
        var k = cl((t - t0) / 0.45, 0, 1), n = d.n[i], kol = A.S.kolory[d.g[i]] || '#66E6BA';
        var r = Math.max(30, (16 + 5.8 * Math.sqrt(n)) * zf) * eback(k), y = p.y - 8 * Math.sin(t * 2.2 + i);
        ctx.globalAlpha = a * cl(k * 2, 0, 1);
        ctx.fillStyle = rgba(kol, A.temna ? 0.88 : 0.92); ctx.strokeStyle = A.temna ? 'rgba(255,255,255,.75)' : 'rgba(17,20,42,.55)'; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.arc(p.x, y, r, 0, 7); ctx.fill(); ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.beginPath(); ctx.arc(p.x - r * 0.35, y - r * 0.38, r * 0.22, 0, 7); ctx.fill();
        if (r > 26) { ctx.fillStyle = '#11142A'; ctx.font = '800 ' + Math.round(Math.min(64, r * 0.78)) + 'px Plex'; ctx.fillText(chyslo(n), p.x, y + 2); }
      }
      ctx.restore();
    }
  };

  // ------------------------------------------------------------------ не карта: на весь кадр (DOM поверх карти)
  function panel(st, klas, html) {
    var el = document.createElement('div');
    el.className = 'p139 ' + klas;
    el.innerHTML = html;
    POVNYI.appendChild(el);
    st._el = el;
    return el;
  }
  function vkhid(st, t) {   // спільна поява панелі
    var el = st._el, a = alfa(st, t);
    el.style.opacity = a;
    el.style.display = a > 0 ? 'block' : 'none';
    return a;
  }

  // Інфографіка: велике число, 100 кружків-частин за видами, рядки видів
  V.infografika = {
    dodaty: function (st) {
      var tochky = '';
      st.chastky.forEach(function (g, j) { for (var i = 0; i < g.n; i++) tochky += '<i data-g="' + j + '" style="--k:' + g.kolir + '"></i>'; });
      panel(st, 'infografika', '<div class="zag">' + st.zag + '</div><div class="n"></div><div class="pid">' + st.pid + '</div>' +
        '<div class="sitka">' + tochky + '</div><div class="lehenda">' + st.chastky.map(function (g) {
          return '<div><i style="background:' + g.kolir + '"></i><b>' + g.n + ' зі 100</b> ' + g.tekst + '</div>'; }).join('') + '</div>');
    },
    kadr: function (st, id, t) {
      if (vkhid(st, t) <= 0) return;
      var tt = t - (st.t0 || 0), el = st._el;
      el.querySelector('.n').textContent = chyslo(st.n * eo(cl(tt / 1.4, 0, 1)));
      el.querySelectorAll('.sitka i').forEach(function (i, j) {
        var k = cl((tt - 0.6 - j * 0.022) / 0.25, 0, 1);
        i.style.transform = 'scale(' + eback(k) + ')'; i.style.opacity = k;
      });
      el.querySelectorAll('.lehenda div').forEach(function (r, j) { var k = cl((tt - 1.2 - j * 0.35) / 0.3, 0, 1); r.style.opacity = k; r.style.transform = 'translateX(' + lr(-60, 0, eo(k)) + 'px)'; });
    }
  };

  // Годинник: 24 промені — скільки подій о кожній годині; стрілка обходить добу, у центрі — година й число
  V.hodynnyk = {
    dodaty: function (st) {
      var maks = Math.max.apply(null, st.hodyny), svg = '<svg viewBox="-500 -500 1000 1000">';
      svg += '<circle r="205" class="osn"/>';
      for (var h = 0; h < 24; h++) {
        var ug = (h / 24) * 2 * Math.PI - Math.PI / 2, dov = 225 + 255 * st.hodyny[h] / maks;
        svg += '<path data-h="' + h + '" data-d="' + dov.toFixed(1) + '" class="pr" d=""/>';
        if (h % 3 === 0) svg += '<text x="' + (Math.cos(ug) * 175).toFixed(1) + '" y="' + (Math.sin(ug) * 175 + 11).toFixed(1) + '">' + h + '</text>';
      }
      svg += '<line class="strilka" x1="0" y1="0" x2="0" y2="-490"/></svg>';
      panel(st, 'hodynnyk', '<div class="zag">' + st.zag + '</div>' + svg + '<div class="tsentr"><b></b><span></span></div>' + (st.pid ? '<div class="pid">' + st.pid + '</div>' : ''));
    },
    kadr: function (st, id, t) {
      if (vkhid(st, t) <= 0) return;
      var tt = t - (st.t0 || 0), el = st._el, Kc = A.Kc, maks = Math.max.apply(null, st.hodyny);
      var hz = cl((tt - 0.4) / ((st.t1 || 6) - (st.t0 || 0) - 0.6), 0, 1) * 24, hh = Math.min(23, Math.floor(hz));
      el.querySelectorAll('.pr').forEach(function (p) {
        var h = +p.getAttribute('data-h'), k = eo(cl((tt - h * 0.03) / 0.6, 0, 1)), dov = 215 + (+p.getAttribute('data-d') - 215) * k;
        var u0 = (h / 24) * 2 * Math.PI - Math.PI / 2 + 0.03, u1 = ((h + 1) / 24) * 2 * Math.PI - Math.PI / 2 - 0.03;
        p.setAttribute('d', 'M' + (Math.cos(u0) * 215).toFixed(1) + ' ' + (Math.sin(u0) * 215).toFixed(1) + ' L' + (Math.cos(u0) * dov).toFixed(1) + ' ' + (Math.sin(u0) * dov).toFixed(1) +
          ' A' + dov.toFixed(1) + ' ' + dov.toFixed(1) + ' 0 0 1 ' + (Math.cos(u1) * dov).toFixed(1) + ' ' + (Math.sin(u1) * dov).toFixed(1) +
          ' L' + (Math.cos(u1) * 215).toFixed(1) + ' ' + (Math.sin(u1) * 215).toFixed(1) + ' Z');
        var kl = Math.min(4, Math.floor(5 * st.hodyny[h] / (maks + 1)));
        p.style.fill = h === hh ? Kc.pk[1] : Kc.sc[kl];
        p.style.opacity = h <= hh ? 1 : 0.55;
      });
      el.querySelector('.strilka').setAttribute('transform', 'rotate(' + (hz / 24 * 360) + ')');
      el.querySelector('.tsentr b').textContent = String(hh).padStart(2, '0') + ':00';
      el.querySelector('.tsentr span').textContent = chyslo(st.hodyny[hh]);
    }
  };

  // Календар року: 12 місяців × дні; клітинки світяться день за днем, колір — скільки подій того дня (частками)
  V.kalendar = {
    dodaty: function (st) {
      var MIS = ['Січ', 'Лют', 'Бер', 'Кві', 'Тра', 'Чер', 'Лип', 'Сер', 'Вер', 'Жов', 'Лис', 'Гру'], html = '<div class="mis">', den = 0;
      var poch = new Date(Date.UTC(st.rik, 0, 1)).getUTCDay(); poch = (poch + 6) % 7;     // понеділок — 0
      for (var m = 0; m < 12; m++) {
        var dniv = new Date(Date.UTC(st.rik, m + 1, 0)).getUTCDate();
        html += '<div class="kal-m"><b>' + MIS[m] + '</b><div class="dni">';
        for (var p = 0; p < poch; p++) html += '<span class="pus"></span>';
        for (var d = 0; d < dniv; d++, den++) html += '<span data-d="' + den + '"></span>';
        poch = (poch + dniv) % 7;
        html += '</div></div>';
      }
      panel(st, 'kalendar', '<div class="zag">' + st.zag + '</div>' + html + '</div><div class="pid"></div>');
    },
    kadr: function (st, id, t) {
      if (vkhid(st, t) <= 0) return;
      var tt = t - (st.t0 || 0), el = st._el, Kc = A.Kc, dni = st.dni, n = dni.length, por = st.porohy;
      var ido = Math.floor(cl((tt - 0.3) / (st.tryv || 3.6), 0, 1) * n), suma = 0;
      el.querySelectorAll('.dni span[data-d]').forEach(function (s) {
        var d = +s.getAttribute('data-d'), v = dni[d] || 0;
        if (d < ido) {
          suma += v;
          var kl = v >= por[3] ? 4 : v >= por[2] ? 3 : v >= por[1] ? 2 : v >= por[0] ? 1 : 0;
          s.style.background = d === st.maks_den && tt > (st.tryv || 3.6) + 0.3 ? Kc.pk[1] : Kc.sc[kl];
          s.style.transform = d > ido - 6 ? 'scale(1.35)' : 'scale(1)';
        } else { s.style.background = ''; s.style.transform = 'scale(1)'; }
      });
      el.querySelector('.pid').innerHTML = '<b>' + chyslo(suma) + '</b> ' + st.pid;
    }
  };

  // Картка-звіт, що гортається: шапка, числа, роки, види — як довідка, але лише відкриті числа без адреси будинку
  V.kartka_zvit = {
    dodaty: function (st) {
      var mr = Math.max.apply(null, st.roky.map(function (r) { return r[1]; })), mh = Math.max.apply(null, st.hrupy.map(function (r) { return r[1]; }));
      var mm = Math.max.apply(null, st.misiatsi);
      var MIS = ['С', 'Л', 'Б', 'К', 'Т', 'Ч', 'Л', 'С', 'В', 'Ж', 'Л', 'Г'];
      panel(st, 'kartka-zvit', '<div class="arkush">' +
        '<div class="shapka"><svg viewBox="0 0 48 48"><path class="z1" d="M24 2 43 13v22L24 46 5 35V13z"/><path class="z2" d="M24 15 32 19.5v9L24 33l-8-4.5v-9z"/></svg><span>Моя вулиця</span></div>' +
        '<h2>' + st.zag + '</h2><div class="pid">' + st.pid + '</div>' +
        '<div class="chysla">' + st.chysla.map(function (c) { return '<div><b data-n="' + c[0] + '">0</b><span>' + c[1] + '</span></div>'; }).join('') + '</div>' +
        '<h3>За роками</h3><div class="roky">' + st.roky.map(function (r) { return '<div><i data-w="' + (r[1] / mr) + '"></i><b>' + r[0] + '</b><span>' + chyslo(r[1]) + '</span></div>'; }).join('') + '</div>' +
        '<h3>Які події</h3><div class="hrupy">' + st.hrupy.map(function (r) { return '<div><i data-w="' + (r[1] / mh) + '" style="background:' + r[2] + '"></i><span>' + r[0] + ' · ' + chyslo(r[1]) + '</span></div>'; }).join('') + '</div>' +
        '<h3>За місяцями</h3><div class="misiatsi">' + st.misiatsi.map(function (v, j) { return '<div><i data-h="' + (v / mm) + '"></i><span>' + MIS[j] + '</span></div>'; }).join('') + '</div>' +
        '<div class="dz">' + st.dz + '</div></div>');
    },
    kadr: function (st, id, t) {
      if (vkhid(st, t) <= 0) return;
      var tt = t - (st.t0 || 0), el = st._el, ark = el.querySelector('.arkush');
      var vys = ark.offsetHeight, prokr = Math.max(0, vys - 1500);
      var k = cl((tt - 1.0) / ((st.t1 || 6) - (st.t0 || 0) - 1.4), 0, 1);
      ark.style.transform = 'translateY(' + (lr(160, 0, eo(cl(tt / 0.5, 0, 1))) - prokr * (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2)) + 'px)';
      el.querySelectorAll('b[data-n]').forEach(function (b, j) { b.textContent = chyslo(+b.getAttribute('data-n') * eo(cl((tt - 0.3 - j * 0.15) / 0.9, 0, 1))); });
      el.querySelectorAll('i[data-w]').forEach(function (i, j) { i.style.width = (100 * +i.getAttribute('data-w') * eo(cl((tt - 0.8 - j * 0.08) / 0.7, 0, 1))) + '%'; });
      el.querySelectorAll('i[data-h]').forEach(function (i, j) { i.style.height = (100 * +i.getAttribute('data-h') * eo(cl((tt - 2.0 - j * 0.05) / 0.6, 0, 1))) + '%'; });
    }
  };

  // ------------------------------------------------------------------ гачки для stsena.js
  window.VAU_VYHLIADY = {
    temy: TEMY,
    vyhliady: V,
    dodaty: function (api) {
      A = api;
      var kadr = document.getElementById('kadr'), pislia = document.getElementById('vinietka');
      var cv = document.createElement('canvas'); cv.id = 'nakladka139'; cv.width = api.W; cv.height = api.H;
      kadr.insertBefore(cv, pislia); ctx = cv.getContext('2d');
      POVNYI = document.createElement('div'); POVNYI.id = 'povnyi139'; kadr.insertBefore(POVNYI, pislia);
      SP = spysok(api.S);
      SP.forEach(function (st, i) {
        if (!V[st.typ]) throw new Error('невідомий вигляд: ' + st.typ);
        if (V[st.typ].dodaty) V[st.typ].dodaty(st, 'v139-' + i);
      });
    },
    kadr: function (t) {
      if (!A) return;
      ctx.clearRect(0, 0, A.W, A.H);
      SP.forEach(function (st, i) { V[st.typ].kadr(st, 'v139-' + i, t); });
    }
  };
})();

/* Звіт адреси — поведінка сторінок ZAVDANNYA-69: карта-супутник (SVG з OSM), розділи «Аркуша» на телефоні,
   картки подій, «Місця довкола» ↔ карта. Без атрибутів style у розмітці: розміри — з data-*. */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var ZNIMOK = /[?&]znimok=1/.test(location.search);
  var TELEFON = window.matchMedia('(max-width: 760px)');
  var MALO_RUKHU = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ——— знімки для публічного показу: номери будинків і рішень сховані ——— */
  if (ZNIMOK) {
    document.documentElement.classList.add('znimok');
    document.querySelectorAll('.nb').forEach(function (el) { el.textContent = '••'; });
    document.querySelectorAll('.nr').forEach(function (el) { el.textContent = '•••••••••'; });
  }
  document.querySelectorAll('[data-shyr]').forEach(function (u) { u.style.width = u.getAttribute('data-shyr') + '%'; });
  document.querySelectorAll('[data-vys]').forEach(function (u) { u.style.height = u.getAttribute('data-vys') + '%'; });

  document.addEventListener('click', function (ev) {
    var sh = ev.target.closest('.podiya__shap');
    if (sh) {
      var v = sh.parentElement.classList.toggle('vidkryta');
      sh.setAttribute('aria-expanded', v ? 'true' : 'false');
      return;
    }
    var shche = ev.target.closest('.shche');
    if (shche) shche.parentElement.classList.toggle('vidkryta');
  });

  /* ——— «Аркуш» на телефоні: розділи згорнуті, висновок — у заголовку ——— */
  var rozdily = document.querySelectorAll('.rozdil');
  function zgornuty() { rozdily.forEach(function (d) { d.open = !TELEFON.matches; }); }
  zgornuty();
  if (TELEFON.addEventListener) TELEFON.addEventListener('change', zgornuty);

  /* ——— карта ——— */
  var M = window.MAPA;
  var svg = document.querySelector('.suputnyk__karta svg.mapa');
  if (!M || !svg) return;

  function el(tag, attrs, batko) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (batko) batko.appendChild(e);
    return e;
  }
  function shliakh(p, zakr) {
    var s = 'M' + p[0][0] + ' ' + p[0][1];
    for (var i = 1; i < p.length; i++) s += 'L' + p[i][0] + ' ' + p[i][1];
    return zakr ? s + 'Z' : s;
  }
  function ramka(tochky, zapas) {
    var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    tochky.forEach(function (p) { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); });
    if (x0 > x1) return [-400, -400, 800, 800];
    return [x0 - zapas, y0 - zapas, x1 - x0 + 2 * zapas, y1 - y0 + 2 * zapas];
  }
  var kont = [];
  M.kontur.forEach(function (p) { kont = kont.concat(p); });
  var vul = [];
  M.vul.forEach(function (p) { p.forEach(function (t) { if (Math.abs(t[0]) < 1050 && Math.abs(t[1]) < 1050) vul.push(t); }); });
  var VYDY = {
    dovkola: ramka(kont, 70), budynok: [-170, -170, 340, 340], vulytsia: ramka(vul.length ? vul : [[-300, -300], [300, 300]], 120),
    podii: [-340, -340, 680, 680]
  };
  var PIDPYSY = {
    dovkola: ['10 хв пішки від будинку', 'Контур — ≈ 800 м по вулицях; номери — «Місця довкола».'],
    budynok: ['Будинок і двір', 'Темний — ваш будинок; крапки — події, до 300 м.'],
    vulytsia: ['Ваша вулиця', 'Кружок — скільки подій на адресі; темні — скупчення, 5+.'],
    podii: ['Усі події до 300 м', 'Крапка — подія; світлі — дорожні.']
  };

  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  var baza = el('g', {}, svg);
  el('rect', { x: -4000, y: -4000, width: 8000, height: 8000, 'class': 'm-tlo' }, baza);
  M.zel.forEach(function (p) { el('path', { d: shliakh(p, true), 'class': 'm-zel' }, baza); });
  ['pish', 'proizd', 'vulytsia', 'holovna'].forEach(function (k) {
    M.dor.forEach(function (r) { if (r.k === k) el('path', { d: shliakh(r.p), 'class': 'm-d m-d-' + k }, baza); });
  });
  M.bud.forEach(function (b) { if (!b.ty) el('path', { d: shliakh(b.p, true), 'class': 'm-bud' }, baza); });
  var gVul = el('g', {}, svg);
  M.vul.forEach(function (p) { el('path', { d: shliakh(p), 'class': 'm-vul' }, gVul); });
  M.kontur.forEach(function (p) { el('path', { d: shliakh(p, true), 'class': 'm-kontur' }, svg); });
  M.bud.forEach(function (b) { if (b.ty) el('path', { d: shliakh(b.p, true), 'class': 'm-dim' }, svg); });

  // позначки сталого розміру на екрані: кожна в <g>, масштаб = метрів на піксель
  var zn = [];
  function znak(batko, x, y, klas) {
    var g = el('g', { 'class': klas || '' }, batko); g._x = x; g._y = y; zn.push(g); return g;
  }
  var gPidp = el('g', {}, svg);
  M.pidpysy.forEach(function (p) {
    var g = znak(gPidp, p.x, p.y); g._a = p.a;
    el('text', { 'class': 'm-pidpys', 'text-anchor': 'middle', 'dominant-baseline': 'central' }, g).textContent = p.t;
  });
  var gT = el('g', { 'class': 'shar-tochky' }, svg);
  M.podii.forEach(function (p) {
    var g = znak(gT, p.x, p.y);
    el('circle', { r: 2.6, 'class': 'm-tochka' + (p.v === 'ДТП' || p.v === 'ДОР' ? ' dor' : '') }, g);
  });
  var gA = el('g', { 'class': 'shar-adr' }, svg);
  M.vul_adr.forEach(function (a) {
    var g = znak(gA, a.x, a.y, 'm-adr' + (a.s ? ' skup' : ''));
    el('circle', { r: 6 + 2.2 * Math.sqrt(a.k) }, g);
    el('text', {}, g).textContent = a.k;
  });
  var gM = el('g', { 'class': 'shar-mistsia' }, svg);
  var mitky = {};
  M.mistsia.forEach(function (m) {
    var g = znak(gM, m.x, m.y, 'm-mistse'); g.setAttribute('data-typ', m.t); g.setAttribute('data-mistse', m.i);
    el('circle', { r: 11 }, g);
    el('text', {}, g).textContent = m.i;
    mitky[m.i] = g;
  });
  var gDim = znak(svg, 0, -22);
  el('text', { 'class': 'm-dim-pidpys', 'text-anchor': 'middle' }, gDim).textContent = 'ваш будинок';

  var vb = null;
  function masshtab() {
    var w = svg.clientWidth || 400, h = svg.clientHeight || 400;
    var s = Math.max(vb[2] / w, vb[3] / h);
    zn.forEach(function (g) {
      g.setAttribute('transform', 'translate(' + g._x + ' ' + g._y + ') scale(' + s.toFixed(4) + ')' + (g._a ? ' rotate(' + g._a + ')' : ''));
    });
  }
  var anim = null;
  function pokazaty(rezhym) {
    var tsil = VYDY[rezhym] || VYDY.dovkola;
    svg.setAttribute('class', 'mapa rezhym-' + rezhym);
    var pp = PIDPYSY[rezhym] || PIDPYSY.dovkola;
    var pid = document.querySelector('.suputnyk__pidpys');
    if (pid) { pid.querySelector('b').textContent = pp[0]; pid.querySelector('span').textContent = pp[1]; }
    if (!vb || MALO_RUKHU) { vb = tsil.slice(); svg.setAttribute('viewBox', vb.join(' ')); masshtab(); return; }
    var start = vb.slice(), t0 = null;
    if (anim) cancelAnimationFrame(anim);
    function krok(t) {
      if (!t0) t0 = t;
      var k = Math.min(1, (t - t0) / 550); k = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      vb = start.map(function (v, i) { return v + (tsil[i] - v) * k; });
      svg.setAttribute('viewBox', vb.join(' ')); masshtab();
      if (k < 1) anim = requestAnimationFrame(krok);
    }
    anim = requestAnimationFrame(krok);
  }
  pokazaty('dovkola');
  window.addEventListener('resize', function () { if (vb) masshtab(); });

  // розділ, який читають, керує картою
  var sekts = document.querySelectorAll('.suputnyk__vmist [data-rezhym]');
  var potochnyi = null;
  var spost = new IntersectionObserver(function (zapysy) {
    zapysy.forEach(function (z) {
      if (!z.isIntersecting) return;
      var r = z.target.getAttribute('data-rezhym');
      document.querySelectorAll('.aktyvnyi').forEach(function (a) { a.classList.remove('aktyvnyi'); });
      z.target.classList.add('aktyvnyi');
      if (r !== potochnyi) { potochnyi = r; pokazaty(r); }
    });
  }, { rootMargin: '-35% 0px -60% 0px' });
  sekts.forEach(function (s) { spost.observe(s); });

  // «Місця довкола» ↔ позначки
  function vydilyty(i, tak) {
    var g = mitky[i]; if (g) g.classList.toggle('tut', tak);
    var li = document.querySelector('.mistse[data-mistse="' + i + '"]'); if (li) li.classList.toggle('tut', tak);
  }
  document.querySelectorAll('.mistse').forEach(function (li) {
    var i = li.getAttribute('data-mistse');
    li.addEventListener('mouseenter', function () { vydilyty(i, true); });
    li.addEventListener('mouseleave', function () { vydilyty(i, false); });
  });
  Object.keys(mitky).forEach(function (i) {
    mitky[i].addEventListener('click', function () {
      var li = document.querySelector('.mistse[data-mistse="' + i + '"]');
      if (li) { li.scrollIntoView({ behavior: MALO_RUKHU ? 'auto' : 'smooth', block: 'center' }); vydilyty(i, true); setTimeout(function () { vydilyty(i, false); }, 1600); }
    });
  });
})();

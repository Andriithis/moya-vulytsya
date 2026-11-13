/* Спільні помічники шаблонів «Моєї вулиці» для соцмереж (ZAVDANNYA-12).
   Кожен шаблон оголошує window.pokazaty(dani); скрипт brend/zrobyty.py викликає її,
   чекає шрифти й знімає PNG. Тексти вставляються лише як текст (textContent), не як розмітка. */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';

  /* Знак — та сама фігура, що в шапці заглушки (viewBox 0 0 26 28). */
  function znak(vysota, zovni, vseredyni) {
    var s = document.createElementNS(NS, 'svg');
    s.setAttribute('viewBox', '0 0 26 28');
    s.setAttribute('height', vysota);
    s.setAttribute('width', Math.round(vysota * 26 / 28));
    s.setAttribute('aria-hidden', 'true');
    s.innerHTML = '<path d="M13 1 L25 8 L25 20 L13 27 L1 20 L1 8 Z" style="fill:' + (zovni || 'var(--accent)') + '"/>' +
      '<path d="M13 9 L18 12 L18 17 L13 20 L8 17 L8 12 Z" style="fill:' + (vseredyni || '#FFFFFF') + '"/>';
    return s;
  }

  /* Шестикутник із гострим верхом: центр (cx, cy), «радіус» r. */
  function hex(cx, cy, r) {
    var w = r * Math.sqrt(3) / 2;
    return 'M' + cx + ' ' + (cy - r) + ' L' + (cx + w) + ' ' + (cy - r / 2) + ' L' + (cx + w) + ' ' + (cy + r / 2) +
      ' L' + cx + ' ' + (cy + r) + ' L' + (cx - w) + ' ' + (cy + r / 2) + ' L' + (cx - w) + ' ' + (cy - r / 2) + ' Z';
  }

  /* Поле сот у шкалі даних (мотив карти). Колір — лише кількість даних, не небезпека.
     Вибір кольору детермінований (за номером соти), щоб картинка не мінялася між запусками. */
  function sotyPole(svg, x0, y0, stovptsi, ryadky, r, kolory, propusk) {
    var w = r * Math.sqrt(3), h = r * 1.5, i = 0;
    for (var y = 0; y < ryadky; y++) {
      for (var x = 0; x < stovptsi; x++, i++) {
        var k = kolory[(i * 7 + y * 3 + (x * x) % 5) % kolory.length];
        if (propusk && propusk(x, y)) continue;
        var p = document.createElementNS(NS, 'path');
        p.setAttribute('d', hex(x0 + x * w + (y % 2 ? w / 2 : 0), y0 + y * h, r * 0.94));
        p.style.fill = k;
        svg.appendChild(p);
      }
    }
  }

  /* Скупчення сот навколо однієї виділеної (accent) — «місце на карті».
     Це прикраса-мотив, а не справжня карта: координат тут немає. znak — '?' або 'tochka'. */
  function klaster(svg, w, h, r, znak) {
    var dx = r * Math.sqrt(3), dy = r * 1.5, cx = w / 2, cy = h / 2, i = 0;
    var kol = ['var(--data-1)', 'var(--data-2)', 'var(--data-1)', 'var(--data-3)', 'var(--data-2)'];
    var ryad = Math.ceil(h / dy / 2) + 1, stov = Math.ceil(w / dx / 2) + 1;
    for (var y = -ryad; y <= ryad; y++) {
      for (var x = -stov; x <= stov; x++, i++) {
        var px = cx + x * dx + (Math.abs(y) % 2 ? dx / 2 : 0), py = cy + y * dy;
        var vid = Math.hypot((px - cx) / w, (py - cy) / h);
        if (vid > 0.48 || px < r || px > w - r || py < r || py > h - r) continue;
        var p = document.createElementNS(NS, 'path');
        p.setAttribute('d', hex(px, py, r * 0.93));
        var golovna = x === 0 && y === 0;
        p.style.fill = golovna ? 'var(--accent)' : kol[(i * 7 + y * y) % kol.length];
        p.style.opacity = golovna ? 1 : Math.max(0.25, 1 - vid * 1.6);
        svg.appendChild(p);
      }
    }
    if (znak === '?') {
      var t = document.createElementNS(NS, 'text');
      t.setAttribute('x', cx); t.setAttribute('y', cy + r * 0.36); t.setAttribute('text-anchor', 'middle');
      t.style.font = '800 ' + Math.round(r) + 'px Plex, system-ui, sans-serif'; t.style.fill = '#FFFFFF';
      t.textContent = '?'; svg.appendChild(t);
    } else {
      var c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', cx); c.setAttribute('cy', cy); c.setAttribute('r', r * 0.3); c.style.fill = '#FFFFFF';
      svg.appendChild(c);
    }
  }

  function tekst(id, znachennya) {
    var el = document.getElementById(id);
    if (!el) return;
    if (znachennya === undefined || znachennya === null || znachennya === '') { el.hidden = true; return; }
    el.hidden = false;
    /* Число не відривається від одиниці: «15 кг», «1 199 грн» — нерозривний пробіл. */
    el.textContent = String(znachennya).replace(/(\d) (?=[\dA-Za-zА-Яа-яЄєІіЇїҐґ%×])/g, '$1\u00A0');
  }

  /* Числа: пробіл у тисячах, кома в дробах (голос системи дизайну). */
  function chyslo(n) {
    if (typeof n !== 'number') return String(n);
    var s = String(n).split('.');
    s[0] = s[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    return s.join(',');
  }

  function maket(dani) {
    if (!dani.maket) return;
    var m = document.createElement('div');
    m.className = 'maket'; m.textContent = 'МАКЕТ';
    document.querySelector('.polotno').appendChild(m);
  }

  window.Brend = { znak: znak, hex: hex, klaster: klaster, sotyPole: sotyPole, tekst: tekst, chyslo: chyslo, maket: maket,
    SHKALA: ['var(--data-1)', 'var(--data-2)', 'var(--data-3)', 'var(--data-4)', 'var(--data-5)'] };
})();

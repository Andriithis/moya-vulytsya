// Картинка «Поділитися» для гри (ZAVDANNYA-07): 1080 × 1350, у стилі системи дизайну.
// На картинці — назва гри, очки, «Моя вулиця», адреса сайту. БЕЗ адрес і описів подій.
// Малюємо на полотні в браузері; нічого не надсилаємо на сервер.
(function () {
  'use strict';

  var W = 1080, H = 1350;
  // Картинка завжди у світлих кольорах системи — однаково виглядає в будь-якій стрічці.
  var K = {
    ground: '#F4F5FB', surface: '#FFFFFF', ink: '#1C1E2D', ink2: '#3E4155', muted: '#5F6275',
    line: '#DFE1E9', accent: '#4447A6', accentSoft: '#DFE3FC', attention: '#3C3CA1', attentionSoft: '#E8E8F4'
  };
  var MISIATSI = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'];

  function dataTekstom(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
    return m ? (+m[3]) + ' ' + MISIATSI[+m[2] - 1] + ' ' + m[1] : '';
  }

  function sota(c, x, y, r) {          // шестикутник «вершиною вгору», центр (x, y)
    c.beginPath();
    for (var i = 0; i < 6; i++) {
      var a = Math.PI / 180 * (60 * i - 90);
      var px = x + r * Math.cos(a), py = y + r * Math.sin(a);
      if (i === 0) c.moveTo(px, py); else c.lineTo(px, py);
    }
    c.closePath();
  }

  function zaokruhlenyi(c, x, y, w, h, r) {
    c.beginPath();
    c.moveTo(x + r, y); c.lineTo(x + w - r, y); c.arcTo(x + w, y, x + w, y + r, r);
    c.lineTo(x + w, y + h - r); c.arcTo(x + w, y + h, x + w - r, y + h, r);
    c.lineTo(x + r, y + h); c.arcTo(x, y + h, x, y + h - r, r);
    c.lineTo(x, y + r); c.arcTo(x, y, x + r, y, r); c.closePath();
  }

  function rozstav(c, tekst, x, y, krok) {   // текст із розрядкою (для «мікро»-написів)
    for (var i = 0; i < tekst.length; i++) { c.fillText(tekst[i], x, y); x += c.measureText(tekst[i]).width + krok; }
    return x;
  }

  function sotaRezultatu(c, x, y, r, ochky) {
    sota(c, x, y, r);
    if (ochky >= 500) { c.fillStyle = K.accent; c.fill(); }
    else if (ochky > 0) { c.fillStyle = K.accentSoft; c.fill(); c.lineWidth = 4; c.strokeStyle = K.accent; c.stroke(); }
    else { c.fillStyle = K.surface; c.fill(); c.lineWidth = 4; c.strokeStyle = K.attention; c.stroke(); }
  }

  // dani: {rezhym: 'raund'|'den', suma, maks, rezultaty: [очки…], vidstanTekst, data, demo, sait}
  function namaluvaty(dani) {
    var Y = window.MvHraYadro;
    var polotno = document.createElement('canvas');
    polotno.width = W; polotno.height = H;
    var c = polotno.getContext('2d');
    var P = 96;

    c.fillStyle = K.ground; c.fillRect(0, 0, W, H);

    // Знак і назва
    c.save(); c.translate(P, 92); c.scale(2.4, 2.4);
    c.beginPath(); c.moveTo(13, 1); c.lineTo(25, 8); c.lineTo(25, 20); c.lineTo(13, 27); c.lineTo(1, 20); c.lineTo(1, 8); c.closePath();
    c.fillStyle = K.accent; c.fill();
    c.beginPath(); c.moveTo(13, 9); c.lineTo(18, 12); c.lineTo(18, 17); c.lineTo(13, 20); c.lineTo(8, 17); c.lineTo(8, 12); c.closePath();
    c.fillStyle = K.surface; c.fill();
    c.restore();
    c.fillStyle = K.ink; c.textBaseline = 'middle';
    c.font = '800 46px Plex, system-ui, sans-serif';
    c.fillText('Моя вулиця', P + 84, 126);

    if (dani.demo) {
      c.font = '600 26px Plex, system-ui, sans-serif';
      var t = 'ДЕМО-КОЛОДА', tw = c.measureText(t).width + 11 * 2 + 48;
      zaokruhlenyi(c, W - P - tw, 100, tw, 54, 27); c.fillStyle = K.attentionSoft; c.fill();
      c.fillStyle = K.attention; rozstav(c, t, W - P - tw + 24, 128, 2);
    }

    // Назва гри і режим
    c.textBaseline = 'alphabetic';
    c.fillStyle = K.muted; c.font = '600 30px Plex, system-ui, sans-serif';
    rozstav(c, 'ВГАДАЙ, ДЕ ЦЕ БУЛО', P, 360, 3);
    c.fillStyle = K.ink; c.font = '800 60px Plex, system-ui, sans-serif';
    c.fillText(dani.rezhym === 'den' ? 'Подія дня' : 'Раунд з 10 подій', P, 440);
    if (dani.rezhym === 'den' && dani.data) {
      c.fillStyle = K.muted; c.font = '400 36px Plex, system-ui, sans-serif';
      c.fillText(dataTekstom(dani.data), P, 496);
    }

    // Очки
    c.fillStyle = K.ink; c.font = '800 260px Plex, system-ui, sans-serif';
    c.fillText(Y.chyslo(dani.suma), P - 8, 790);
    c.fillStyle = K.muted; c.font = '400 42px Plex, system-ui, sans-serif';
    c.fillText(Y.slovoOchky(dani.suma) + ' із ' + Y.chyslo(dani.maks), P, 862);

    // Соти результатів: одна сота — одна подія
    var r = dani.rezultaty || [];
    if (dani.rezhym === 'den') {
      sotaRezultatu(c, P + 44, 990, 44, r[0] || 0);
      c.fillStyle = K.ink; c.font = '800 54px Plex, system-ui, sans-serif';
      c.fillText(dani.vidstanTekst ? 'за ' + dani.vidstanTekst.replace(/ /g, ' ') : '', P + 120, 1010);
    } else {
      var krok = (W - 2 * P) / 10, rr = Math.min(40, krok / 2 - 6);
      for (var i = 0; i < 10; i++) sotaRezultatu(c, P + krok * i + krok / 2, 990, rr, i < r.length ? r[i] : 0);
    }

    // Низ: адреса сайту
    c.strokeStyle = K.line; c.lineWidth = 2;
    c.beginPath(); c.moveTo(P, 1128); c.lineTo(W - P, 1128); c.stroke();
    c.fillStyle = K.muted; c.font = '400 34px Plex, system-ui, sans-serif';
    c.fillText('Зіграйте й ви — події з судових рішень Києва', P, 1196);
    c.fillStyle = K.accent; c.font = '800 52px Plex, system-ui, sans-serif';
    c.fillText(dani.sait || '[САЙТ]', P, 1264);
    return polotno;
  }

  function doBlob(polotno) {
    return new Promise(function (ok, ni) {
      polotno.toBlob(function (b) { if (b) ok(b); else ni(new Error('Не вдалося створити картинку')); }, 'image/png');
    });
  }

  // Системне «поділитися» телефона з картинкою; на комп'ютері — завантаження файлу.
  // Повертає 'podilylysia' | 'zavantazheno' | 'skasovano'.
  function podilytysia(dani) {
    var shryfty = document.fonts && document.fonts.load ? Promise.all([
      document.fonts.load('800 60px Plex'), document.fonts.load('600 30px Plex'), document.fonts.load('400 30px Plex')
    ]).catch(function () {}) : Promise.resolve();
    return shryfty.then(function () { return doBlob(namaluvaty(dani)); }).then(function (blob) {
      var imya = dani.rezhym === 'den' ? 'moya-vulytsya-podiya-dnya.png' : 'moya-vulytsya-vhadai.png';
      var fail = null;
      try { fail = new File([blob], imya, { type: 'image/png' }); } catch (e) { fail = null; }
      var dotyk = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
      if (fail && dotyk && navigator.canShare && navigator.canShare({ files: [fail] })) {
        return navigator.share({ files: [fail], title: 'Вгадай, де це було', text: 'Мій результат у грі «Вгадай, де це було»' })
          .then(function () { return 'podilylysia'; }, function (e) {
            if (e && e.name === 'AbortError') return 'skasovano';
            return zavantazhyty(blob, imya);
          });
      }
      return zavantazhyty(blob, imya);
    });
  }

  function zavantazhyty(blob, imya) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = imya; a.rel = 'noopener';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
    return 'zavantazheno';
  }

  window.MvHraKartka = { namaluvaty: namaluvaty, podilytysia: podilytysia, dataTekstom: dataTekstom, W: W, H: H };
})();

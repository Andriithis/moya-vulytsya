// «Для бізнесу» (ZAVDANNYA-157): запит на доступ до бази → POST /api/forma/biznes (сервер продажу, таблиця biznes_zapyty;
// перевірки — ті самі, що в site/worker/prodazh/biznes.js). Що надсилаємо: лише поля форми й канал зі сторінки. Кукі не
// надсилаємо, у пам'ять браузера нічого не пишемо.
(function () {
  'use strict';
  var f = document.getElementById('biznes-forma');
  if (!f) return;
  var stan = f.querySelector('.biznes-forma__stan');
  var knopka = f.querySelector('button[type="submit"]');
  var META = ['nerukhomist', 'strakhuvannia', 'doslidzhennia', 'mista', 'inshe'];
  var STROKY = ['misiats', 'rik', 'ne_znaiu'];

  function kanal() {
    var d = (new URLSearchParams(window.location.search).get('dzherelo') || '').toLowerCase();
    return /^[a-z0-9-]{1,40}$/.test(d) ? d : 'biznes';
  }
  function skazaty(t, pomylka) {
    stan.textContent = t;
    stan.classList.toggle('biznes-forma__stan--pomylka', !!pomylka);
  }

  f.addEventListener('submit', function (podiia) {
    podiia.preventDefault();
    var d = {
      kompaniia: f.kompaniia.value.trim(), kontakt: f.kontakt.value.trim(), meta: f.meta.value,
      terytoriia: f.terytoriia.value.trim(), strok: (f.querySelector('input[name="strok"]:checked') || {}).value || 'ne_znaiu',
      komentar: f.komentar.value.trim(), zghoda: f.zghoda.checked, kanal: kanal()
    };
    if (!d.kompaniia) { skazaty('Вкажіть компанію.', true); f.kompaniia.focus(); return; }
    if (!d.kontakt) { skazaty('Вкажіть пошту чи телефон для відповіді.', true); f.kontakt.focus(); return; }
    if (META.indexOf(d.meta) === -1) { skazaty('Оберіть, для чого потрібні дані.', true); f.meta.focus(); return; }
    if (STROKY.indexOf(d.strok) === -1) d.strok = 'ne_znaiu';
    if (!d.zghoda) { skazaty('Потрібна згода з політикою конфіденційності.', true); f.zghoda.focus(); return; }
    knopka.disabled = true;
    skazaty('Надсилаємо…');
    fetch('/api/forma/biznes', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d),
      // same-origin, а не no-referrer сторінки: інакше браузер шле «Origin: null», і сервер відхиляє форму як чужу
      credentials: 'omit', referrerPolicy: 'same-origin', cache: 'no-store'
    }).then(function (v) {
      if (!v.ok) throw new Error(String(v.status));
      f.reset();
      skazaty('Дякуємо! Запит отримано — партнер проєкту відповість протягом 2 робочих днів.');
    }).catch(function () {
      skazaty('Не вдалося надіслати. Спробуйте за хвилину або скористайтеся запасною формою нижче.', true);
    }).then(function () { knopka.disabled = false; });
  });
})();

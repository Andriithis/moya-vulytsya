// Поведінка форми звернення (ZAVDANNYA-06, п. 2). Відправка — лише через nadsylannya.js.
// Без мережі: зрозуміле повідомлення, а введене лишається у формі (форму лише ховаємо).
(function () {
  'use strict';
  var N = window.MvNadsylannya;
  function $(id) { return document.getElementById(id); }

  var forma = $('zvernennya');
  var vdacha = $('vdacha');
  var zboi = $('zboi');
  var stan = $('zvernennya-stan');
  var knopka = $('zvernennya-knopka');
  var NAPYS = knopka.textContent;
  var TEKST_ZBOYU = $('zboi-tekst').textContent;
  var TEKST_BEZ_MEREZHI = 'Немає зв\'язку з інтернетом. Ваше звернення не загубилося — воно лишилося у формі. ' +
    'Натисніть «Спробувати ще», коли з\'явиться зв\'язок.';

  function pokazatyPomylku(tekst, pole) {
    stan.textContent = tekst;
    stan.hidden = false;
    forma.classList.add('forma--pomylka');
    if (pole) { pole.setAttribute('aria-invalid', 'true'); pole.focus(); }
  }
  function skynutyPomylky() {
    stan.hidden = true;
    stan.textContent = '';
    forma.classList.remove('forma--pomylka');
    forma.querySelectorAll('[aria-invalid]').forEach(function (el) { el.removeAttribute('aria-invalid'); });
  }
  function kontaktDobryi(k) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(k) ||
      /^@[A-Za-z0-9_]{4,32}$/.test(k) ||
      /^(https?:\/\/)?t\.me\/[A-Za-z0-9_]{4,32}$/i.test(k);
  }
  function pokazatyZbii() {
    $('zboi-tekst').textContent = navigator.onLine === false ? TEKST_BEZ_MEREZHI : TEKST_ZBOYU;
    forma.hidden = true;
    zboi.hidden = false;
    zboi.focus();
  }
  function pokazatyVdachu() {
    forma.hidden = true;
    zboi.hidden = true;
    vdacha.hidden = false;
    vdacha.focus();
  }

  function vidpravyty() {
    skynutyPomylky();
    var vybrano = forma.querySelector('input[name="shcho_ne_tak"]:checked');
    var dani = {
      posylannya: $('posylannya').value.trim(),
      shchoNeTak: vybrano ? vybrano.value : '',
      poyasnennya: $('poyasnennya').value.trim(),
      kontakt: $('kontakt').value.trim(),
      zghoda: $('zghoda').checked
    };
    if (!dani.posylannya) return pokazatyPomylku('Вкажіть посилання на подію або номер рішення.', $('posylannya'));
    if (!dani.shchoNeTak) return pokazatyPomylku('Виберіть, що не так.', forma.querySelector('input[name="shcho_ne_tak"]'));
    if (dani.shchoNeTak === 'inshe' && !dani.poyasnennya) return pokazatyPomylku('Напишіть коротко, що саме не так.', $('poyasnennya'));
    if (!dani.kontakt) return pokazatyPomylku('Вкажіть пошту або нік у Телеграмі — куди відповісти.', $('kontakt'));
    if (!kontaktDobryi(dani.kontakt)) return pokazatyPomylku('Перевірте контакт: потрібна пошта (name@poshta.ua) або нік у Телеграмі (@nik).', $('kontakt'));
    if (!dani.zghoda) return pokazatyPomylku('Без згоди ми не можемо прийняти звернення. Поставте позначку, якщо згодні.', $('zghoda'));

    if ($('sait').value) { pokazatyVdachu(); return; }   // пастка для ботів
    if (navigator.onLine === false) { pokazatyZbii(); return; }

    knopka.disabled = true;
    knopka.textContent = 'Надсилаємо…';
    N.nadislatyZvernennya(dani).then(pokazatyVdachu, pokazatyZbii).then(function () {
      knopka.disabled = false;
      knopka.textContent = NAPYS;
    });
  }

  forma.addEventListener('submit', function (e) { e.preventDefault(); vidpravyty(); });
  $('sprobuvaty-shche').addEventListener('click', function () {
    zboi.hidden = true;
    forma.hidden = false;
    vidpravyty();
  });
})();

// Поведінка заглушки: форма, кнопки, чотири числа (MV-5).
// Рахуємо натискання, а не людей: жодних ідентифікаторів, кукі й записів у пам'ять браузера.
(function () {
  'use strict';
  var N = window.MvNadsylannya;
  var dzherelo = new URLSearchParams(window.location.search).get('dzherelo');

  function $(id) { return document.getElementById(id); }

  // 1. Сторінку відкрито.
  N.nadislatyPodiyu('pryishly', dzherelo);

  // Короткі написи з макета телефона.
  var telefon = window.matchMedia('(max-width: 600px)');
  var dovgi = new Map();
  function napysy() {
    document.querySelectorAll('[data-korotko]').forEach(function (el) {
      var vlast = el.tagName === 'OPTION' ? 'textContent' : 'placeholder';
      if (!dovgi.has(el)) dovgi.set(el, el[vlast]);
      el[vlast] = telefon.matches ? el.getAttribute('data-korotko') : dovgi.get(el);
    });
  }
  napysy();
  if (telefon.addEventListener) telefon.addEventListener('change', napysy);

  var forma = $('forma');
  var vdacha = $('vdacha');
  var zboi = $('zboi');
  var stan = $('forma-stan');
  var knopka = $('forma-knopka');

  function doFormy(fokus) {
    $('peredzamovlennya').scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (fokus) setTimeout(function () { fokus.focus({ preventScroll: true }); }, 300);
  }

  // 2. «Перевірити адресу».
  $('poshuk').addEventListener('submit', function (e) {
    e.preventDefault();
    var adresa = $('adresa').value.trim();
    if (!adresa) { $('adresa').focus(); return; }
    N.nadislatyPodiyu('adresa', dzherelo);
    $('adresa2').value = adresa;
    var misto = $('misto');
    if (!telefon.matches && misto.value === '') {
      $('misto2').value = '';
      doFormy($('misto2'));
    } else {
      doFormy($('kontakt'));
    }
  });

  // 3. Будь-яка кнопка «Передзамовити».
  document.querySelectorAll('[data-peredzamovyty]').forEach(function (el) {
    el.addEventListener('click', function () {
      N.nadislatyPodiyu('peredzamovyty', dzherelo);
      var v = el.getAttribute('data-peredzamovyty');
      if (v === 'analiz' || v === 'pidpyska') $('shcho').value = v;
    });
  });
  document.querySelectorAll('[data-vybir]').forEach(function (el) {
    el.addEventListener('click', function () { $('shcho').value = el.getAttribute('data-vybir'); });
  });

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
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(k) ||          // пошта
      /^@[A-Za-z0-9_]{4,32}$/.test(k) ||                   // @нік у Телеграмі
      /^(https?:\/\/)?t\.me\/[A-Za-z0-9_]{4,32}$/i.test(k); // посилання t.me
  }

  function vidpravyty() {
    skynutyPomylky();
    var dani = {
      shcho: $('shcho').value,
      misto: $('misto2').value.trim(),
      adresa: $('adresa2').value.trim(),
      kontakt: $('kontakt').value.trim(),
      zghoda: $('zghoda').checked,
      dzherelo: dzherelo
    };
    if (!dani.misto) return pokazatyPomylku('Вкажіть місто.', $('misto2'));
    if (!dani.kontakt) return pokazatyPomylku('Вкажіть пошту або нік у Телеграмі.', $('kontakt'));
    if (!kontaktDobryi(dani.kontakt)) return pokazatyPomylku('Перевірте контакт: потрібна пошта (name@poshta.ua) або нік у Телеграмі (@nik).', $('kontakt'));
    if (!dani.zghoda) return pokazatyPomylku('Без згоди ми не можемо зберегти контакт. Поставте позначку, якщо згодні.', $('zghoda'));

    // Пастка для ботів: заповнене приховане поле — вдаємо успіх і нічого не надсилаємо.
    if ($('sait').value) { pokazatyVdachu(); return; }

    knopka.disabled = true;
    knopka.textContent = 'Надсилаємо…';
    N.nadislatyZayavku(dani).then(function () {
      N.nadislatyPodiyu('kontakt', dzherelo);
      pokazatyVdachu();
    }, function () {
      forma.hidden = true;
      zboi.hidden = false;
      zboi.focus();
    }).then(function () {
      knopka.disabled = false;
      knopka.textContent = 'Передзамовити';
    });
  }

  function pokazatyVdachu() {
    forma.hidden = true;
    zboi.hidden = true;
    vdacha.hidden = false;
    vdacha.focus();
  }

  forma.addEventListener('submit', function (e) { e.preventDefault(); vidpravyty(); });
  $('sprobuvaty-shche').addEventListener('click', function () {
    zboi.hidden = true;
    forma.hidden = false;
    vidpravyty();
  });
})();

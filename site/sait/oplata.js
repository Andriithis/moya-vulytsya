// Оплата-заглушка (ZAVDANNYA-110, Т-3): пам'ятає, що й для якого будинку хотіли купити.
// ?tovar=dovidka&budynok=/budynok/…/&adresa=… → «Ви обрали: …» і посилання на форму з тими самими даними:
// канал заявки «oplata-<товар>[-<звідки>]» (рахуємо в MV-5), адреса — у поле «Адреса», «Що цікавить» — наперед.
(function () {
  'use strict';
  var q = new URLSearchParams(window.location.search);
  var vybir = document.getElementById('vybir');
  var knopka = document.getElementById('oplata-poshta');
  if (!vybir || !knopka) return;
  var tovary = JSON.parse(vybir.getAttribute('data-tovary') || '{}');
  var tovar = (q.get('tovar') || '').replace(/[^a-z]/g, '');
  var budynok = q.get('budynok') || '';
  var adresa = (q.get('adresa') || '').slice(0, 200);
  if (!/^\/budynok\/[a-z0-9-]+\/[a-z0-9-]+\/$/.test(budynok)) { budynok = ''; }
  if (!budynok) adresa = '';
  var dzherelo = (q.get('dzherelo') || '').toLowerCase().replace(/[^a-z0-9-]/g, '');
  if (!tovary[tovar] && !adresa) return;

  var kanal = ('oplata' + (tovary[tovar] ? '-' + tovar : '') + (dzherelo ? '-' + dzherelo : '')).slice(0, 40);
  var shcho = { dovidka: 'analiz', try: 'analiz', zvit: 'analiz', dodatkova: 'analiz', pidpyska: 'pidpyska',
    rieltor: 'pidpyska', osbb: 'kompaniya', biznes: 'kompaniya' }[tovar] || 'povidomyty';
  var p = new URLSearchParams({ dzherelo: kanal, shcho: shcho });
  if (adresa) p.set('adresa', adresa);
  knopka.href = '/zahlushka/?' + p.toString() + '#peredzamovlennya';

  vybir.textContent = '';
  var b = document.createElement('b');
  b.textContent = tovary[tovar] || 'Довідка';
  vybir.appendChild(document.createTextNode('Ви обрали: '));
  vybir.appendChild(b);
  if (adresa) {
    vybir.appendChild(document.createTextNode(' · '));
    var a = document.createElement('a');
    a.href = budynok;
    a.textContent = adresa;
    vybir.appendChild(a);
  }
  vybir.appendChild(document.createTextNode('. Залиште пошту — напишемо, щойно це можна буде замовити.'));
  vybir.hidden = false;
})();

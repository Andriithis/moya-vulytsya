// Робочий файл кешу (service worker) заглушки «Моя вулиця» (ZAVDANNYA-06, п. 4).
//
// Що робить:
//   * під час встановлення кладе в кеш браузера ВЛАСНІ файли сайту: сторінки,
//     стилі, скрипти, шрифти, іконки. Жодних даних про відвідувача — лише файли сайту;
//   * сторінки й файли сайту віддає з кешу — тому сайт відкривається без мережі;
//   * НЕ чіпає відправку форм і лічильників (POST) і будь-які запити на інші адреси:
//     вони йдуть у мережу як звичайно; без мережі сторінка сама показує повідомлення,
//     а введене лишається у формі.
//
// VERSIYA і FAILY підставляє zibraty.py під час збирання (версія — відбиток усіх файлів,
// тож після кожного оновлення сайту браузер бере нові файли і стирає старий кеш).
'use strict';

var VERSIYA = 'mv-zahlushka-' + /*VERSIYA*/'rozrobka';
var FAILY = /*FAILY*/['./', 'index.html'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(VERSIYA).then(function (kesh) {
    return kesh.addAll(FAILY.map(function (f) { return new Request(f, { cache: 'reload' }); }));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (nazvy) {
    return Promise.all(nazvy.filter(function (n) {
      return n.indexOf('mv-zahlushka-') === 0 && n !== VERSIYA;
    }).map(function (n) { return caches.delete(n); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var z = e.request;
  if (z.method !== 'GET') return;                              // форми й лічильники — у мережу
  var adresa = new URL(z.url);
  if (adresa.origin !== self.location.origin) return;           // інші адреси — у мережу
  if (adresa.pathname.indexOf('/rest/') !== -1) return;          // сховище — ніколи з кешу
  var storinka = z.mode === 'navigate';
  e.respondWith(caches.open(VERSIYA).then(function (kesh) {
    // ?dzherelo=… не впливає на файл сторінки, тому для сторінок його не враховуємо.
    return kesh.match(z, { ignoreSearch: storinka }).then(function (zbereheno) {
      if (zbereheno) return zbereheno;
      return fetch(z).catch(function () {
        // Без мережі і без файлу в кеші: для сторінки — головна з кешу.
        if (storinka) return kesh.match('index.html');
        throw new Error('Немає мережі');
      });
    });
  }));
});

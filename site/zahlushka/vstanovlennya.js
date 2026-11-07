// Встановлення на телефон (ZAVDANNYA-06, п. 4): реєструє робочий файл кешу sw.js,
// щоб сторінки відкривалися без мережі і Chrome міг запропонувати «Встановити».
// Нічого не знає про відвідувача і нічого про нього не зберігає.
(function () {
  'use strict';
  if (!('serviceWorker' in navigator)) return;
  if (location.protocol !== 'https:' && location.hostname !== '127.0.0.1' && location.hostname !== 'localhost') return;
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('sw.js', { scope: './' }).catch(function () { /* без кешу сайт теж працює */ });
  });
})();

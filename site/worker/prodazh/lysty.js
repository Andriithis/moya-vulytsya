// Шаблони листів, які сервер надсилає сам за розкладом (ZAVDANNYA-132). Ціни — лише з таблиці (tsiny.js).
import TS from './tsiny.js';

const NBSP = ' ';
const suma = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
const data = (t) => { const d = new Date(t * 1000); return `${String(d.getUTCDate()).padStart(2, '0')}.${String(d.getUTCMonth() + 1).padStart(2, '0')}.${d.getUTCFullYear()}`; };

/** MV-155, П7: лист ОСББ за 3 дні до річного списання. */
export function nahaduvanniaOsbb({ adresa, diie_do, adresaSaitu }) {
  return {
    tema: `Через 3 дні — річна оплата «${TS.nazvy.osbb}»`,
    tekst: `Добрий день!\n\n` +
      `${data(diie_do)} закінчується оплачений рік «${TS.nazvy.osbb}»${adresa ? ` (${adresa})` : ''}. ` +
      `Того ж дня платіжний сервіс автоматично спише ${suma(TS.tsiny.osbb)} грн за наступний рік — з тієї самої картки.\n\n` +
      `Якщо продовжувати не треба — скасуйте підписку в кабінеті до цієї дати: ${adresaSaitu}/kabinet/ ` +
      `(кнопка «Скасувати підписку»). Після скасування нових списань не буде, а оплачений рік діє до кінця.\n\n` +
      `Якщо все гаразд — нічого робити не треба.\n\nМоя вулиця`,
  };
}

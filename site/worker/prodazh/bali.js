// Бали ігор ↔ кабінет (ZAVDANNYA-123; MV-130, MV-138, MV-140). Стик готовий, але ВИМКНЕНИЙ: працює лише з
// OBMIN_BALIV = 'tak' (вмикає партнер після висновку юриста й запуску кабінету). Без змінної — жодної адреси, жодного запису.
//
// Правила:
//  - бали лише серверні, за акаунтом (таблиця bali_rukh); з пристрою не переносяться;
//  - чужі бали не обміняти: користувач — лише з сесії кабінету, будь-які id з форми ігноруються;
//  - двічі не обміняти: (1) той самий запит (поле `zapyt`) — один запис (UNIQUE kliuch); (2) списання — одним SQL-рядком
//    з умовою «баланс ≥ ціна і за 30 днів обмінів не було», тож два одночасні запити не спишуть двічі;
//  - нарахування — лише функцією narakhuvaty (сервер сам рахує очки гри); адреси, що нараховує бали з телефона, НЕМАЄ.
// Курс — той самий, що в site/ihry/nalashtuvannia.json (звіряє tests/test_ihry.py).
import TS from './tsiny.js';
import { vypadkovyi } from './bezpeka.js';
import { teper, odyn, vsi, zrobyty, postavytyDovidku, dodatyMisiatsi } from './logika.js';

export const KURS = {
  ochok_za_bal: 100,
  stelia_baliv_na_den: 300,
  obminiv_na_30_dniv: 1,
  obmin: { dovidka: { baliv: 1500, tovar: 'dovidka' }, 'pidpyska-misiats': { baliv: 3000, tovar: 'pidpyska' } },
};
const DEN_S = 86400;

export const uvimkneno = (env) => env.PRODAZH === 'tak' && env.OBMIN_BALIV === 'tak';

export async function balans(env, korystuvach_id) {
  return (await odyn(env, 'SELECT COALESCE(SUM(zmina), 0) AS b FROM bali_rukh WHERE korystuvach_id = ?', korystuvach_id)).b;
}

/** Нарахувати бали за гру (сервер сам порахував очки). Стеля на добу — як у грі; той самий kliuch удруге — нічого. */
export async function narakhuvaty(env, korystuvach_id, ochky, kliuch, prychyna) {
  const t = teper(env);
  const dobaVid = t - (t % DEN_S);
  const vzhe = (await odyn(env, `SELECT COALESCE(SUM(zmina), 0) AS b FROM bali_rukh WHERE korystuvach_id = ? AND zmina > 0 AND stvoreno >= ?`,
    korystuvach_id, dobaVid)).b;
  const baliv = Math.max(0, Math.min(Math.floor(Math.max(0, ochky) / KURS.ochok_za_bal), KURS.stelia_baliv_na_den - vzhe));
  if (!baliv) return 0;
  const r = await zrobyty(env, 'INSERT OR IGNORE INTO bali_rukh (korystuvach_id, zmina, prychyna, kliuch, stvoreno) VALUES (?, ?, ?, ?, ?)',
    korystuvach_id, baliv, String(prychyna), 'n:' + String(kliuch), t);
  return r.meta?.changes ? baliv : 0;
}

/**
 * Обміняти бали на товар. korystuvach_id — ЛИШЕ з сесії. zapyt — разовий номер форми (захист від повторного надсилання).
 * Повертає { ok, dovidka?, pidpyska?, chomu? }.
 */
export async function obminiaty(env, korystuvach_id, { tovar, budynok = null, adresa = null, zapyt }) {
  if (!uvimkneno(env)) return { ok: false, chomu: 'Обмін балів ще не ввімкнено.' };
  const o = KURS.obmin[tovar];
  if (!o) return { ok: false, chomu: 'Такого обміну немає.' };
  if (o.tovar === 'dovidka' && !budynok) return { ok: false, chomu: 'Оберіть будинок для довідки.' };
  if (!/^[a-z0-9]{8,40}$/.test(String(zapyt || ''))) return { ok: false, chomu: 'Оновіть сторінку кабінету й спробуйте ще раз.' };
  const t = teper(env);
  const zam = 'z' + vypadkovyi(15);
  const kliuch = `o:${korystuvach_id}:${zapyt}`;
  // Одне речення SQL — атомарно: баланс і «раз на 30 днів» перевіряються там само, де пишеться списання.
  const r = await zrobyty(env, `INSERT OR IGNORE INTO bali_rukh (korystuvach_id, zmina, prychyna, kliuch, zamovlennia_id, stvoreno)
    SELECT ?, ?, ?, ?, ?, ?
    WHERE (SELECT COALESCE(SUM(zmina), 0) FROM bali_rukh WHERE korystuvach_id = ?) >= ?
      AND NOT EXISTS (SELECT 1 FROM bali_rukh WHERE korystuvach_id = ? AND zmina < 0 AND stvoreno > ?)`,
  korystuvach_id, -o.baliv, 'obmin:' + tovar, kliuch, zam, t,
  korystuvach_id, o.baliv, korystuvach_id, t - Math.floor(30 / KURS.obminiv_na_30_dniv) * DEN_S);
  if (!r.meta?.changes) {
    const vzhe = await odyn(env, 'SELECT zamovlennia_id FROM bali_rukh WHERE kliuch = ?', kliuch);
    if (vzhe) return { ok: true, povtor: true, zamovlennia_id: vzhe.zamovlennia_id };
    if ((await balans(env, korystuvach_id)) < o.baliv) return { ok: false, chomu: `Потрібно ${o.baliv} балів.` };
    return { ok: false, chomu: 'Обмін — раз на 30 днів.' };
  }
  // Замовлення з сумою 0 (servis = 'bali') — для обліку партнера; далі — як після оплати.
  await zrobyty(env, `INSERT INTO zamovlennia (id, korystuvach_id, tovar, budynok, adresa, suma, status, servis, stvoreno, oplacheno)
                      VALUES (?, ?, ?, ?, ?, 0, 'oplacheno', 'bali', ?, ?)`, zam, korystuvach_id, o.tovar, budynok, adresa, t, t);
  if (o.tovar === 'dovidka') {
    return { ok: true, zamovlennia_id: zam,
      dovidka: await postavytyDovidku(env, { korystuvach_id, zamovlennia_id: zam, budynok, adresa, rezhym: 'dovidka' }) };
  }
  // Місяць підписки: без автосписань (status 'skasovana' від початку — далі не продовжується), 1 довідка в місяці.
  const p = 'p' + vypadkovyi(15);
  await zrobyty(env, `INSERT INTO pidpysky (id, korystuvach_id, tovar, status, pochatok, diie_do, zamovlennia_id, stvoreno, skasovano)
                      VALUES (?, ?, 'pidpyska', 'skasovana', ?, ?, ?, ?, ?)`, p, korystuvach_id, t, dodatyMisiatsi(t, TS.period_misiatsiv.pidpyska), zam, t, t);
  return { ok: true, zamovlennia_id: zam, pidpyska: p };
}

export async function zhurnal(env, korystuvach_id, n = 10) {
  return vsi(env, 'SELECT zmina, prychyna, stvoreno FROM bali_rukh WHERE korystuvach_id = ? ORDER BY id DESC LIMIT ?', korystuvach_id, n);
}

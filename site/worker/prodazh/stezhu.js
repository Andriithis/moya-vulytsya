// «Стежу» — щомісячний лист «Нове біля дому» підписникам (ZAVDANNYA-150, п. 4; MV-14, ZAVDANNYA-119).
// Як у видавача довідок: сервер віддає чергу, а лист складає скрипт там, де лежать дані (site/prodazh/lyst_stezhu.py:
// стрічка місяця з dani-edrsr/src/nove_tyzhnia.py --dniv 30 і модуль lyst/). Скрипт не бачить пошти — лише непрозорий номер
// і адреси «Стежу»; пошту підставляє й лист надсилає сервер (ключ пошти — лише секрет Workers).
//
//   GET  /api/vnutr/stezhu?period=РРРР-ММ      хто чекає листа за цей місяць: [{ id, adresy: [{ budynok, adresa }] }]
//   POST /api/vnutr/lyst-stezhu/<id>          { period, tema, tekst } → лист людині; повтор за той самий місяць — 409
import * as L from './logika.js';
import { nadislaty } from './poshta.js';

export const VYMKNENO = 'vymkneno';             // рядок lysty_stezhu: людина попросила не надсилати лист
const PERIOD = /^\d{4}-\d{2}$/;
const TOVARY = ['pidpyska', 'rieltor'];         // ОСББ має свою щомісячну довідку; юрист — не про будинки

async function diiePidpyska(env, korystuvach_id) {
  return (await L.stanPidpysok(env, korystuvach_id)).some((p) => p.diie && TOVARY.includes(p.tovar));
}

export async function vymknenyi(env, korystuvach_id) {
  return !!(await L.odyn(env, 'SELECT 1 AS t FROM lysty_stezhu WHERE korystuvach_id = ? AND period = ?', korystuvach_id, VYMKNENO));
}

export async function cherha(env, period) {
  if (!PERIOD.test(period)) return null;
  const ks = await L.vsi(env, `SELECT DISTINCT s.korystuvach_id AS k FROM stezhu s
    WHERE NOT EXISTS (SELECT 1 FROM lysty_stezhu l WHERE l.korystuvach_id = s.korystuvach_id AND l.period IN (?, ?))
    ORDER BY s.korystuvach_id`, period, VYMKNENO);
  const vyhid = [];
  for (const { k } of ks) {
    if (!(await diiePidpyska(env, k))) continue;
    const adresy = await L.vsi(env, 'SELECT budynok, adresa FROM stezhu WHERE korystuvach_id = ? ORDER BY stvoreno', k);
    vyhid.push({ id: `k${k}`, adresy });
  }
  return vyhid;
}

export async function nadislatyLyst(env, id, { period, tema, tekst } = {}) {
  const m = String(id).match(/^k(\d{1,12})$/);
  if (!m || !PERIOD.test(String(period)) || typeof tema !== 'string' || typeof tekst !== 'string'
      || !tema || tema.length > 200 || !tekst || tekst.length > 100_000) return { status: 400 };
  const k = Number(m[1]);
  const ja = await L.odyn(env, 'SELECT * FROM korystuvachi WHERE id = ?', k);
  if (!ja || !(await diiePidpyska(env, k)) || (await vymknenyi(env, k))) return { status: 404 };
  const r = await L.zrobyty(env, 'INSERT OR IGNORE INTO lysty_stezhu (korystuvach_id, period, nadislano) VALUES (?, ?, ?)', k, period, L.teper(env));
  if (!r.meta?.changes) return { status: 409 };
  await nadislaty(env, { komu: ja.poshta, tema, tekst });
  return { status: 204 };
}

/** Кабінет: увімкнути чи вимкнути лист. */
export async function peremknuty(env, korystuvach_id, uvimknuty) {
  if (uvimknuty) await L.zrobyty(env, 'DELETE FROM lysty_stezhu WHERE korystuvach_id = ? AND period = ?', korystuvach_id, VYMKNENO);
  else await L.zrobyty(env, 'INSERT OR IGNORE INTO lysty_stezhu (korystuvach_id, period, nadislano) VALUES (?, ?, ?)', korystuvach_id, VYMKNENO, L.teper(env));
}

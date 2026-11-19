// Поштовх видавачу довідок у GitHub Actions (ZAVDANNYA-133, п. 2; docs/PLATNA-CHASTYNA.md, розд. 3).
//
// Видавач (site/prodazh/vydavach.py + генератор dani-edrsr/src/zvit) працює не на своєму сервері, а запуском GitHub Actions
// у приватному dani-edrsr (.github/workflows/vydavach.yml). Сервер продажу, поставивши оплачену довідку в чергу, просить
// GitHub почати запуск (workflow_dispatch) — і запуск забирає всю чергу тим самим шляхом, що й раніше (/api/vnutr/…).
// Якщо поштовх не дійшов (GitHub недоступний), кожні 10 хв розклад Workers дивиться в чергу й штовхає знову (index.js).
//
//   змінна  VYDAVACH_GITHUB         'власник/репозиторій/файл.yml@гілка', напр. 'Andriithis/dani-edrsr/vydavach.yml@main'
//   секрет  VYDAVACH_GITHUB_TOKEN   токен GitHub лише на цей репозиторій, право «Actions: read and write» (і нічого більше)
// Без них — нічого не робить (як і було: видавач можна запускати й самому, будь-де).
import { odyn, teper } from './logika.js';

export function nalashtovano(env) {
  return /^[\w.-]+\/[\w.-]+\/[\w.-]+\.ya?ml@[\w./-]+$/.test(env.VYDAVACH_GITHUB || '') && !!env.VYDAVACH_GITHUB_TOKEN;
}

/** Попросити GitHub почати запуск видавача. true — GitHub прийняв (200 або 204). Помилки не кидає: оплата від цього не залежить. */
export async function shturhnuty(env, prychyna = '') {
  if (!nalashtovano(env)) return false;
  const [shliakh, gilka] = env.VYDAVACH_GITHUB.split('@');
  const [vlasnyk, repo, fail] = shliakh.split('/');
  try {
    const r = await fetch(`https://api.github.com/repos/${vlasnyk}/${repo}/actions/workflows/${fail}/dispatches`, {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.VYDAVACH_GITHUB_TOKEN}`, accept: 'application/vnd.github+json',
        'x-github-api-version': '2022-11-28', 'user-agent': 'moya-vulytsya-prodazh', 'content-type': 'application/json',
      },
      body: JSON.stringify({ ref: gilka, inputs: { prychyna: String(prychyna).slice(0, 60) } }),
      signal: AbortSignal.timeout(8000),
    });
    // Документація GitHub (19.11.2026): успіх — 200 з номером запуску; раніше — 204 без тіла. Приймаємо обидва.
    const ok = r.status === 200 || r.status === 204;
    if (!ok) console.log(`видавач: GitHub відповів ${r.status} — спробує розклад`);
    return ok;
  } catch (err) {
    console.log(`видавач: поштовх не дійшов (${err.message}) — спробує розклад`);
    return false;
  }
}

/** Розклад (кожні 10 хв): є оплачені довідки, що чекають довше за 5 хв, — штовхнути ще раз. */
export async function pidhaniaty(env) {
  if (!nalashtovano(env)) return false;
  const t = teper(env);
  const r = await odyn(env, `SELECT COUNT(*) AS n FROM dovidky d JOIN zamovlennia z ON z.id = d.zamovlennia_id
    WHERE z.status = 'oplacheno' AND d.sprob < 3 AND ((d.status = 'v_cherzi' AND d.stvoreno < ?) OR (d.status = 'hotuietsia' AND d.vziato < ?))`,
  t - 300, t - 30 * 60);
  return r.n > 0 ? shturhnuty(env, 'rozklad') : false;
}

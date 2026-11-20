// Cloudflare Workers: сторінки будинків «Моєї вулиці» з пачок (ZAVDANNYA-88; формат — site/khostynh.py)
// і сервер продажу (ZAVDANNYA-99, prodazh/; змінна PRODAZH: 'tak' — продаж, 'skoro' — «залиште пошту» й форми
// (ZAVDANNYA-132), інакше його адреси — звичайний сайт).
// Скрипт запускається лише для адрес із run_worker_first у wrangler.jsonc; решту сайту Cloudflare віддає сам.
// Частина будинків нічого не пише й ключів не має; ключі продажу — лише секрети Workers (docs/PRODAZH-SERVER.md).
import { prodazh } from './prodazh/index.js';
import { prybraty, nahadatyOsbb, shchomisiachnaOsbb } from './prodazh/logika.js';
import { budynok } from './budynky.js';
import { pidhaniaty } from './prodazh/vydavach.js';
import { nahadaty as nahadatyBiznes } from './prodazh/biznes.js';

export const CHASTO = '*/10 * * * *';     // той самий рядок — у site/khostynh.py (triggers)

export default {
  async fetch(request, env) {
    const p = await prodazh(request, env);
    if (p) return p;
    return (await budynok(request, env)) || env.ASSETS.fetch(request);
  },
  // Щодня (Cron Trigger у wrangler.jsonc): прибирання (прострочені входи, старі файли довідок) і лист ОСББ
  // за 3 дні до річного списання (MV-155, П7); щомісячна довідка ОСББ — сама, раз на місяць підписки (ZAVDANNYA-143).
  // Кожні 10 хв (ZAVDANNYA-133): якщо оплачена довідка чекає довше за 5 хв — ще раз штовхнути видавача в GitHub Actions.
  async scheduled(event, env) {
    if (env.PRODAZH !== 'tak') return;
    if (event?.cron === CHASTO) { await pidhaniaty(env); return; }
    await prybraty(env);
    await nahadatyOsbb(env, (env.ADRESA_SAITU || '').replace(/\/$/, ''));
    await shchomisiachnaOsbb(env);
    await nahadatyBiznes(env);          // «Для бізнесу» (ZAVDANNYA-157): договір клієнта спливає за 14 днів — лист партнеру
  },
};

// Cloudflare Workers: сторінки будинків «Моєї вулиці» з пачок (ZAVDANNYA-88; формат — site/khostynh.py)
// і сервер продажу (ZAVDANNYA-99, prodazh/; вмикається змінною PRODAZH = 'tak', інакше його адреси — звичайний сайт).
// Скрипт запускається лише для адрес із run_worker_first у wrangler.jsonc; решту сайту Cloudflare віддає сам.
// Частина будинків нічого не пише й ключів не має; ключі продажу — лише секрети Workers (docs/PRODAZH-SERVER.md).
import { prodazh } from './prodazh/index.js';
import { prybraty } from './prodazh/logika.js';
import { budynok } from './budynky.js';

export default {
  async fetch(request, env) {
    const p = await prodazh(request, env);
    if (p) return p;
    return (await budynok(request, env)) || env.ASSETS.fetch(request);
  },
  // Щоденне прибирання (Cron Trigger у wrangler.jsonc): прострочені входи, старі файли довідок.
  async scheduled(event, env) {
    if (env.PRODAZH === 'tak') await prybraty(env);
  },
};

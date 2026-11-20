// Місцевий запуск сервера продажу без Cloudflare і без грошей (ZAVDANNYA-99): справжній site/worker/index.js,
// база — SQLite у пам'яті, файли — у пам'яті, оплата — тестова, листи — у журнал і на /__lysty (лише тут).
//   node site/worker/testy/mistsevyi.mjs [порт] [тека зібраного сайту]
// PRODAZH=skoro node … — режим «Скоро — залиште пошту» (ZAVDANNYA-132); ADMIN_KLIUCH — для вивантаження форм.
// Без теки сайту будинки — два вигадані (/budynok/zhylianska/5/, /budynok/obolonskyi/16/).
// Для справжньої перевірки на Cloudflare — `npx wrangler dev` у теці <сайт>-worker (docs/PRODAZH-SERVER.md).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import worker from '../index.js';
import { d1, r2 } from './pidminy.mjs';

const port = parseInt(process.argv[2] || '8799', 10);
const sait = process.argv[3];
const ADRESA = `http://127.0.0.1:${port}`;
const VYHADANI = { '/budynok/zhylianska/5/': 'вулиця Жилянська, 5', '/budynok/obolonskyi/16/': 'проспект Оболонський, 16' };

const env = {
  PRODAZH: process.env.PRODAZH || 'tak', ADMIN_KLIUCH: process.env.ADMIN_KLIUCH || 'mistsevyi-admin', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', ADRESA_SAITU: ADRESA,
  TEST_KLIUCH: process.env.TEST_KLIUCH || 'mistsevyi-test', VYDACHA_KLIUCH: process.env.VYDACHA_KLIUCH || 'mistsevyi-vydavach',
  BAZA: d1(), DOVIDKY: r2(), __LYSTY: [],
  PARTNERY: process.env.PARTNERY || 'partner@mistsevyi.test',   // кабінет звернень /kabinet/zvernennia/ (ZAVDANNYA-161)
  // Вхід через Google (ZAVDANNYA-142): з цими змінними видно кнопку; справжній вхід — лише з клієнтом Google на домені
  GOOGLE_KLIIENT_ID: process.env.GOOGLE_KLIIENT_ID || '', GOOGLE_SEKRET: process.env.GOOGLE_SEKRET || '',
  ASSETS: {
    async fetch(req) {
      const p = decodeURIComponent(new URL(req.url).pathname);
      if (!sait) {
        return VYHADANI[p] ? new Response(`<!doctype html><h1>${VYHADANI[p]}</h1>`) : new Response('немає', { status: 404 });
      }
      const f = path.join(sait, p.endsWith('/') ? p + 'index.html' : p);
      if (!f.startsWith(path.resolve(sait)) || !fs.existsSync(f)) return new Response('немає', { status: 404 });
      const typ = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
        '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json',
        '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8' }[path.extname(f)] || 'application/octet-stream';
      return new Response(fs.readFileSync(f), { headers: { 'content-type': typ } });   // як Cloudflare: тип за розширенням
    },
  },
};
if (sait && fs.existsSync(path.join(sait, '_budynky'))) {
  env.PACHOK = String(fs.readdirSync(path.join(sait, '_budynky')).filter((f) => f.startsWith('s')).length);
}

http.createServer(async (rq, rs) => {
  const chunks = [];
  for await (const c of rq) chunks.push(c);
  if (rq.url === '/__lysty') {
    rs.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
    rs.end(JSON.stringify(env.__LYSTY));
    return;
  }
  const h = new Headers();
  for (const [k, v] of Object.entries(rq.headers)) if (typeof v === 'string') h.set(k, v);
  const req = new Request(ADRESA + rq.url, { method: rq.method, headers: h, body: ['GET', 'HEAD'].includes(rq.method) ? undefined : Buffer.concat(chunks) });
  const r = await worker.fetch(req, env);
  const zag = {};
  r.headers.forEach((v, k) => { zag[k] = v; });
  rs.writeHead(r.status, zag);
  rs.end(Buffer.from(await r.arrayBuffer()));
}).listen(port, '127.0.0.1', () => console.log(`сервер продажу (місцевий, тестова оплата): ${ADRESA}`));

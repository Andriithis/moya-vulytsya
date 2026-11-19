// «Судова практика» місцево (ZAVDANNYA-135): справжній site/worker/index.js на зібраному сайті + таблиці юриста з теки
// (site/prodazh/praktyka_r2.py … --do-teky <тека>). Для знімків і перевірки очима; оплата тестова, грошей немає.
//   node site/worker/testy/sp_proba.mjs <порт> <тека сайту> <тека R2>
// GET /__yurist — увійти як юрист з оплаченою підпискою (кука ставиться у відповіді й переводить у /pidpysnyk/praktyka/).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import worker from '../index.js';
import TS from '../prodazh/tsiny.js';
import { d1, r2 } from './pidminy.mjs';

const [port, sait, tekaR2] = [parseInt(process.argv[2] || '8798', 10), process.argv[3], process.argv[4]];
const ADRESA = `http://127.0.0.1:${port}`;
for (const t of TS.sudova) if (!TS.prodaietsia.includes(t)) TS.prodaietsia.push(t);   // як після дописаної оферти

const DOVIDKY = r2();
(function zavantazhyty(d, kor = '') {
  for (const f of fs.readdirSync(d)) {
    const p = path.join(d, f);
    if (fs.statSync(p).isDirectory()) zavantazhyty(p, `${kor}${f}/`);
    else DOVIDKY.m.set(kor + f, fs.readFileSync(p, 'utf8'));
  }
})(tekaR2);

const env = {
  PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', TESTOVA_OPLATA: 'tak', ADRESA_SAITU: ADRESA, TEST_KLIUCH: 'proba', VYDACHA_KLIUCH: 'proba-v',
  BAZA: d1(), DOVIDKY, __LYSTY: [],
  ASSETS: { async fetch(req) {
    const p = decodeURIComponent(new URL(req.url).pathname);
    const f = path.join(sait, p.endsWith('/') ? p + 'index.html' : p);
    if (!f.startsWith(path.resolve(sait)) || !fs.existsSync(f)) return new Response('немає', { status: 404 });
    const typ = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
      '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' }[path.extname(f)] || 'application/octet-stream';
    return new Response(fs.readFileSync(f), { headers: { 'content-type': typ } });
  } },
};

async function w(metod, shliakh, { forma, kuka } = {}) {
  const h = { origin: ADRESA };
  if (kuka) h.cookie = kuka;
  return worker.fetch(new Request(ADRESA + shliakh, { method: metod, headers: h, body: forma ? new URLSearchParams(forma) : undefined, redirect: 'manual' }), env);
}

async function yurist() {
  const poshta = 'yurist@proba.ua';
  let r = await w('POST', '/api/zamovlennia', { forma: { tovar: 'spyurist', poshta, zghoda: 'tak', odrazu: 'tak' } });
  const id = r.headers.get('location').match(/(z[a-z2-7]+)/)[1];
  const t = await (await w('GET', `/oplata/test/${id}/`)).text();
  const f = [...t.matchAll(/<form method="post" action="\/api\/spovishchennia\/test">([\s\S]*?)<\/form>/g)]
    .map((x) => Object.fromEntries([...x[1].matchAll(/name="([^"]+)" value="([^"]*)"/g)].map((y) => [y[1], y[2]]))).find((x) => x.podiia === 'oplata');
  await worker.fetch(new Request(ADRESA + '/api/spovishchennia/test', { method: 'POST', body: new URLSearchParams(f) }), env);
  await w('POST', '/kabinet/vkhid', { forma: { poshta } });
  const k = env.__LYSTY.at(-1).tekst.match(/vkhid\/\?t=([a-z2-7]+)/)[1];
  r = await w('GET', `/kabinet/vkhid/?t=${k}`);
  return r.headers.get('set-cookie');
}

http.createServer(async (rq, rs) => {
  const chunks = [];
  for await (const c of rq) chunks.push(c);
  if (rq.url === '/__yurist') {
    rs.writeHead(303, { 'set-cookie': (await yurist()).replace('; Secure', ''), location: '/pidpysnyk/praktyka/?stattia=kupap-130' });
    rs.end();
    return;
  }
  const h = new Headers();
  for (const [k, v] of Object.entries(rq.headers)) if (typeof v === 'string') h.set(k, v);
  const req = new Request(ADRESA + rq.url, { method: rq.method, headers: h, body: ['GET', 'HEAD'].includes(rq.method) ? undefined : Buffer.concat(chunks) });
  let r = await worker.fetch(req, env);
  if (!r || r.status === 404) {                                   // звичайний сайт
    const a = await env.ASSETS.fetch(req);
    r = a;
  }
  const zag = {};
  r.headers.forEach((v, k) => { zag[k] = v; });
  rs.writeHead(r.status, zag);
  rs.end(Buffer.from(await r.arrayBuffer()));
}).listen(port, '127.0.0.1', () => console.log(`«Судова практика» місцево: ${ADRESA}`));

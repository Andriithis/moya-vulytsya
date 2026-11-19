// Перевірка карти підписника на СПРАВЖНІЙ зібраній карті (ZAVDANNYA-133, п. 1) — не тест, а замір; даних у репозиторії немає.
//   python site/prodazh/karta_r2.py <тека карти> --do-teky <сховище>
//   node site/worker/testy/karta_proba.mjs <сховище>
// Справжній скрипт Workers, база — схема D1 у SQLite з одним підписником, R2 — тека на диску. Друкує: скільки адрес
// перевірено, у скількох знайшлися події, час відповіді й обсяг прочитаного зі сховища на один запит «події адреси».
import fs from 'node:fs';
import worker from '../index.js';
import { sha256 } from '../prodazh/bezpeka.js';
import { d1, r2ZTeky } from './pidminy.mjs';

const teka = process.argv[2];
if (!teka) { console.error('вкажіть теку сховища'); process.exit(2); }
const T0 = Math.floor(Date.now() / 1000);
const R = r2ZTeky(teka);
let chytan = 0, bait = 0;
const KARTA = { async get(k) { const o = await R.get(k); if (o) { chytan++; bait += o.body.length; } return o; } };
const env = { PRODAZH: 'tak', PLATIZHNYI_SERVIS: 'test', ADRESA_SAITU: 'https://mv.test', BAZA: d1(), DOVIDKY: R, KARTA,
  ASSETS: { async fetch() { return new Response('', { status: 404 }); } } };
const db = env.BAZA.db;
db.prepare('INSERT INTO korystuvachi (id, poshta, stvoreno) VALUES (1, ?, ?)').run('proba@mv.test', T0);
db.prepare(`INSERT INTO pidpysky (id, korystuvach_id, tovar, status, pochatok, diie_do, zamovlennia_id, stvoreno)
            VALUES ('p', 1, 'pidpyska', 'aktyvna', ?, ?, 'z', ?)`).run(T0 - 10, T0 + 86400, T0);
db.prepare('INSERT INTO sesii (hash, korystuvach_id, do_) VALUES (?, 1, ?)').run(sha256('s'), T0 + 3600);
const kuka = 'mv_sesiia=s';
const get = (s) => worker.fetch(new Request('https://mv.test' + s, { headers: { cookie: kuka } }), env);

const versiia = JSON.parse(fs.readFileSync(`${teka}/karta/potochna.json`, 'utf8')).versiia;
const tochky = [];
for (const f of fs.readdirSync(`${teka}/karta/${versiia}/indeks`)) {
  for (const [la, lo, , adr] of JSON.parse(fs.readFileSync(`${teka}/karta/${versiia}/indeks/${f}`, 'utf8'))) tochky.push([la, lo, adr]);
}
const vybirka = tochky.filter((_, i) => i % Math.max(1, Math.floor(tochky.length / 1000)) === 0);
let z = 0, podii = 0, ms = [];
await get(`/pidpysnyk/api/podii?la=${vybirka[0][0]}&lo=${vybirka[0][1]}`);      // прогрів маніфесту
chytan = 0; bait = 0;
for (const [la, lo, adr] of vybirka) {
  const t = performance.now();
  const r = await get(`/pidpysnyk/api/podii?la=${la}&lo=${lo}`);
  const v = await r.json();
  ms.push(performance.now() - t);
  if (r.status === 200 && v.adresa === adr) { z++; podii += v.podii.length; }
}
ms.sort((a, b) => a - b);
const s = await get('/pidpysnyk/');
console.log(JSON.stringify({ versiia, tochok: tochky.length, perevireno: vybirka.length, znaideno_tiiezh_adresu: z, podii,
  ms_mediana: +ms[ms.length >> 1].toFixed(2), ms_95: +ms[Math.floor(ms.length * 0.95)].toFixed(2),
  chytan_R2_na_zapyt: +(chytan / vybirka.length).toFixed(2), KB_na_zapyt: +(bait / vybirka.length / 1024).toFixed(1),
  storinka: s.status }));

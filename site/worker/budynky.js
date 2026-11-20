// Сторінки будинків з пачок (ZAVDANNYA-88; формат — site/khostynh.py). Нічого не пише, ключів не має.

function fnv1a(tekst) {
  const b = new TextEncoder().encode(tekst);
  let h = 0x811c9dc5;
  for (let i = 0; i < b.length; i++) {
    h ^= b[i];
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

function esc(t) {
  return String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// «24-a» → «24-А»: риску лишаємо, латинську літеру показуємо кирилицею (slug_nomera, storinky_mv100.py).
const LITERY = { a: 'А', b: 'Б', v: 'В', h: 'Г', g: 'Ґ', d: 'Д', e: 'Е', ie: 'Є', zh: 'Ж', z: 'З', y: 'И', i: 'І', k: 'К', l: 'Л',
  m: 'М', n: 'Н', o: 'О', p: 'П', r: 'Р', s: 'С', t: 'Т', u: 'У', f: 'Ф' };
export function nomerZSlug(n) {
  return n.split('-').map((x, i) => (i && LITERY[x] ? LITERY[x] : x)).join('-');
}

/** ZAVDANNYA-177 (ZVIT-165, п. 2): «такого будинку немає» — назва вулиці, номер, посилання на вулицю й пошук.
 * Шаблон /_404-budynok.html пише збирач (zibraty_sait.storinka_nemaie_budynku); вулицю беремо з vulytsi/pokazhchyk.json. */
export async function nemaieBudynku(env, url, slug) {
  const t = await env.ASSETS.fetch(new Request(new URL('/_404-budynok.html', url)));
  if (!t.ok) {
    const r = await env.ASSETS.fetch(new Request(new URL('/404.html', url)));
    return new Response(r.body, { status: 404, headers: { 'content-type': 'text/html; charset=utf-8' } });
  }
  const [slugV, slugN] = (slug || '').split('/');
  const nomer = slugN ? nomerZSlug(slugN) : '';
  let vul = null;
  try {
    const p = await env.ASSETS.fetch(new Request(new URL('/vulytsi/pokazhchyk.json', url)));
    if (p.ok) vul = (await p.json()).find((v) => v[0] === slugV) || null;
  } catch (e) { vul = null; }
  const Nazva = vul ? vul[1].charAt(0).toUpperCase() + vul[1].slice(1) : '';
  const vmist = vul
    ? `<span class="mitka">будинок</span><h1>${esc(Nazva)}, ${esc(nomer)}: такого будинку в даних поки немає</h1>` +
      '<p>У цього будинку немає ні звернень до 1551 за 12 місяців, ні подій з рішень судів з його адресою — тому й окремої сторінки ' +
      'немає. Можливо, номер записано інакше: з літерою, корпусом чи дробом — пошукайте нижче або в списку будинків вулиці.</p>' +
      `<div class="diyi"><a class="knopka knopka--holovna" href="/vulytsia/${esc(vul[0])}/">${esc(Nazva)} — уся вулиця й будинки</a></div>`
    : '<span class="mitka">будинок</span><h1>Такої адреси в даних немає</h1>' +
      '<p>Сторінки будинку немає: у даних немає ні звернень до 1551, ні подій з рішень судів з цією адресою. Можливо, вулицю ' +
      'перейменовано або назву записано інакше — пошукайте нижче.</p>';
  const zapyt = vul ? `${vul[1].replace(/^(вулиця|проспект|бульвар|провулок|площа) /, '')} ${nomer}` : '';
  const html = (await t.text()).replace(/<!--NEMAIE-BUDYNKU-->[\s\S]*?<!--\/NEMAIE-BUDYNKU-->/, () => vmist).replace('%%ZAPYT%%', esc(zapyt));
  return new Response(html, { status: 404, headers: { 'content-type': 'text/html; charset=utf-8', 'x-content-type-options': 'nosniff' } });
}

/** Відповідь для /budynok/* або null, якщо адреса не будинку. */
export async function budynok(request, env) {
  const url = new URL(request.url);
  const m = url.pathname.match(/^\/budynok\/([a-z0-9-]+\/[a-z0-9-]+)(\/|\/kartynka\.png|\/index\.html)?$/);
  if (!m) return null;
  if (!m[2]) return Response.redirect(new URL(url.pathname + '/' + url.search, url).toString(), 301);
  // ZAVDANNYA-154: …/index.html — та сама сторінка; одна адреса для Google (без дубліката)
  if (m[2] === '/index.html') return Response.redirect(new URL(`/budynok/${m[1]}/${url.search}`, url).toString(), 301);
  const slug = m[1];
  const kartynka = m[2] === '/kartynka.png';
  const pachok = parseInt(env.PACHOK, 10) || 1;
  const nomer = String(fnv1a(slug) % pachok).padStart(5, '0');
  const r = await env.ASSETS.fetch(new Request(new URL(`/_budynky/${kartynka ? 'k' : 's'}${nomer}.bin`, url)));
  if (!r.ok) return nemaieBudynku(env, url, slug);
  const buf = await r.arrayBuffer();
  const L = new DataView(buf).getUint32(0);
  const z = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, L)))[slug];
  if (!z) return nemaieBudynku(env, url, slug);
  return new Response(new Uint8Array(buf, 4 + L + z[0], z[1]), {
    headers: {
      'content-type': kartynka ? 'image/png' : 'text/html; charset=utf-8',
      'cache-control': 'public, max-age=3600',
      'x-content-type-options': 'nosniff',
    },
  });
}

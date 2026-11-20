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

async function nemaie(env, url) {
  const r = await env.ASSETS.fetch(new Request(new URL('/404.html', url)));
  return new Response(r.body, { status: 404, headers: { 'content-type': 'text/html; charset=utf-8' } });
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
  if (!r.ok) return nemaie(env, url);
  const buf = await r.arrayBuffer();
  const L = new DataView(buf).getUint32(0);
  const z = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, L)))[slug];
  if (!z) return nemaie(env, url);
  return new Response(new Uint8Array(buf, 4 + L + z[0], z[1]), {
    headers: {
      'content-type': kartynka ? 'image/png' : 'text/html; charset=utf-8',
      'cache-control': 'public, max-age=3600',
      'x-content-type-options': 'nosniff',
    },
  });
}

"""Перевірка зібраного сайту «очима Google» (ZAVDANNYA-154).

    python site/perevirka_google.py <тека сайту> [--adresa-saitu https://…] [--zvit zvit.json]

Читає теку, яку зібрав `zibraty_sait.py` (обидва варіанти хостингу: сторінки будинків з пачок `_budynky/` теж),
і перевіряє те, що заважає пошуку Google:
  * у кожної сторінки — один <title>, опис, канонічна адреса на саму себе, один <h1>;
  * заголовок до 70 знаків, опис 50–170 (довші Google обрізає);
  * карта сайту: адреси існують, не закриті «noindex», не заборонені robots.txt, не повторюються;
  * сторінки з «noindex» — не в карті сайту; відкриті для пошуку — у карті;
  * однакові заголовки й описи серед відкритих для пошуку сторінок (дублікати);
  * внутрішні посилання: биті й сторінки-сироти (на них не веде жодне посилання);
  * розмітка schema.org (JSON-LD) читається, має @type; у Place — адреса; у BreadcrumbList — позиції по порядку;
  * у заголовках і описах немає оцінки безпечності (AGENTS.md, розд. 4).
Нічого не змінює. Код виходу 1, якщо є помилки.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

DZHERELO = Path(__file__).resolve().parent
sys.path.insert(0, str(DZHERELO))

MAKS_TITLE = 70
MIN_OPYS, MAKS_OPYS = 50, 170
# Оцінка безпечності в тому, що видно в пошуку (AGENTS.md, розд. 4): ні «безпечний», ні «небезпечний», ні рейтингів.
ZABORONENO = re.compile(r'безпечн|рейтинг|страшн|кримінальн(?:ий|ого) район', re.I)

TITLE = re.compile(r'<title>(.*?)</title>', re.S)
OPYS = re.compile(r'<meta name="description" content="([^"]*)"')
CANON = re.compile(r'<link rel="canonical" href="([^"]*)"')
H1 = re.compile(r'<h1[\s>]')
NOINDEX = re.compile(r'<meta name="robots" content="[^"]*noindex')
REFRESH = re.compile(r'<meta http-equiv="refresh"')
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
HREF = re.compile(r'<a\b[^>]*\bhref="([^"]+)"')


def storinky(teka: Path):
    """(адреса, html) усіх сторінок: файли index.html і сторінки будинків з пачок (варіант workers)."""
    for f in sorted(teka.rglob('*.html')):
        rel = f.relative_to(teka).as_posix()
        if rel.startswith(('_budynky/', 'sait/', 'zahlushka/hra/')):
            continue
        if f.name == 'index.html':
            a = '/' + rel[:-len('index.html')]
        else:
            a = '/' + rel
        yield a, f.read_text(encoding='utf-8')
    pachky = teka / '_budynky'
    if pachky.is_dir():
        import struct
        for p in sorted(pachky.glob('s*.bin')):
            d = p.read_bytes()
            L = struct.unpack('>I', d[:4])[0]
            for slug, (z, n) in json.loads(d[4:4 + L].decode('utf-8')).items():
                yield f'/budynok/{slug}/', d[4 + L + z:4 + L + z + n].decode('utf-8')


def zaboroneni_robots(teka: Path) -> list[str]:
    f = teka / 'robots.txt'
    if not f.is_file():
        return []
    return [r.split(':', 1)[1].strip() for r in f.read_text(encoding='utf-8').splitlines()
            if r.lower().startswith('disallow:') and r.split(':', 1)[1].strip()]


def adresy_sitemap(teka: Path, adresa_saitu: str) -> list[str]:
    ns = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    korin = ET.parse(teka / 'sitemap.xml').getroot()
    faily = [teka / 'sitemap.xml']
    if korin.tag == ns + 'sitemapindex':
        faily = [teka / urlsplit(l.text).path.lstrip('/') for l in korin.iter(ns + 'loc')]
    adresy = []
    for f in faily:
        for l in ET.parse(f).getroot().iter(ns + 'loc'):
            u = l.text.strip()
            adresy.append(u[len(adresa_saitu):] if u.startswith(adresa_saitu) else u)
    return adresy


def normuvaty(href: str, vid: str) -> str | None:
    """Внутрішнє посилання → адреса сторінки (без ?…, #…); зовнішні й файли — None."""
    if href.startswith(('http://', 'https://', 'mailto:', 'tel:', '#', 'javascript:')):
        return None
    shl = urlsplit(html.unescape(href)).path
    if not shl:
        return None
    if not shl.startswith('/'):
        shl = vid.rsplit('/', 1)[0] + '/' + shl
    ostannie = shl.rsplit('/', 1)[-1]
    if ostannie and '.' in ostannie and not ostannie.endswith('.html'):
        return None                       # картинки, json, pdf
    return shl


def perevirka_ld(t: str) -> list[str]:
    pomylky = []
    for blok in LD.findall(t):
        try:
            o = json.loads(blok)
        except ValueError as v:
            pomylky.append(f'JSON-LD не читається: {v}')
            continue
        typ = o.get('@type')
        if not typ or o.get('@context') != 'https://schema.org':
            pomylky.append('JSON-LD без @type або @context')
        if typ == 'Place' and not (o.get('address') or o.get('geo') or o.get('containedInPlace')):
            pomylky.append('Place без адреси, точки й місця')
        if typ == 'BreadcrumbList':
            el = o.get('itemListElement', [])
            if [x.get('position') for x in el] != list(range(1, len(el) + 1)):
                pomylky.append('BreadcrumbList: позиції не по порядку')
            if any('item' not in x for x in el[:-1]):
                pomylky.append('BreadcrumbList: проміжний пункт без адреси')
    return pomylky


def perevirka(teka: Path, adresa_saitu: str) -> dict:
    adresa_saitu = adresa_saitu.rstrip('/')
    pomylky: dict[str, list[str]] = defaultdict(list)
    vidkryti, zakryti, title_vsi, opys_vsi = set(), set(), defaultdict(list), defaultdict(list)
    vkhidni = Counter()
    vsi = set()
    posylannia: dict[str, set] = {}
    typy_ld = Counter()
    dovzhyny = {'title': [], 'opys': []}
    zaboroneni = zaboroneni_robots(teka)
    for a, t in storinky(teka):
        vsi.add(a)
        if a == '/404.html' or any(a.startswith(z) for z in zaboroneni):
            posylannia[a] = set()          # службові: Google їх не бачить
            continue
        if REFRESH.search(t):              # переадресації: лише канонічна адреса на ціль
            zakryti.add(a)
            posylannia[a] = set()
            continue
        titles, opysy, canon = TITLE.findall(t), OPYS.findall(t), CANON.findall(t)
        noindex = bool(NOINDEX.search(t))
        (zakryti if noindex else vidkryti).add(a)
        if len(titles) != 1:
            pomylky[a].append(f'заголовків <title>: {len(titles)}')
        if len(opysy) != 1:
            pomylky[a].append(f'описів: {len(opysy)}')
        if len(canon) != 1 or html.unescape(canon[0]) != adresa_saitu + a:
            if not a.endswith('.html') or len(canon) != 1:
                pomylky[a].append(f'канонічна адреса не на себе: {canon}')
        if a.startswith(('/vulytsia/', '/budynok/', '/rayon/', '/mistse/')) and len(H1.findall(t)) != 1:
            pomylky[a].append(f'<h1>: {len(H1.findall(t))}')
        if titles:
            ti = html.unescape(titles[0])
            dovzhyny['title'].append(len(ti))
            if not noindex:
                title_vsi[ti].append(a)
            if len(ti) > MAKS_TITLE:
                pomylky[a].append(f'заголовок {len(ti)} знаків (> {MAKS_TITLE})')
            if ZABORONENO.search(ti):
                pomylky[a].append(f'оцінка безпечності в заголовку: {ti}')
        if opysy:
            op = html.unescape(opysy[0])
            dovzhyny['opys'].append(len(op))
            if not noindex:
                opys_vsi[op].append(a)
            if not MIN_OPYS <= len(op) <= MAKS_OPYS:
                pomylky[a].append(f'опис {len(op)} знаків (норма {MIN_OPYS}–{MAKS_OPYS})')
            if ZABORONENO.search(op):
                pomylky[a].append(f'оцінка безпечності в описі: {op}')
        for p in perevirka_ld(t):
            pomylky[a].append(p)
        for blok in LD.findall(t):
            try:
                typy_ld[json.loads(blok).get('@type')] += 1
            except ValueError:
                pass
        # посилання — лише з тіла сторінки (без шапки й підвалу: вони однакові всюди і сиріт не рятують)
        tilo = t.split('<main', 1)[-1].split('</main>', 1)[0]
        vykhidni = {n for n in (normuvaty(h, a) for h in HREF.findall(tilo)) if n}
        posylannia[a] = vykhidni
        for n in vykhidni - {a}:
            vkhidni[n] += 1
    # шапка й підвал: вітрини, вулиці, карта — на кожній сторінці
    for a, t in storinky_shapky(teka):
        vkhidni[a] += 1

    smap = adresy_sitemap(teka, adresa_saitu)
    smap_set = set(smap)
    for a, n in Counter(smap).items():
        if n > 1:
            pomylky[a].append(f'у карті сайту {n} рази')
    for a in smap:
        if a not in vsi:
            pomylky[a].append('у карті сайту, але сторінки немає')
        elif a in zakryti:
            pomylky[a].append('у карті сайту, але закрита «noindex» або переадресація')
        if any(a.startswith(z) for z in zaboroneni):
            pomylky[a].append('у карті сайту, але заборонена robots.txt')
    ne_v_karti = sorted(a for a in vidkryti - smap_set if not a.endswith('.html') and a != '/404.html')
    for a in ne_v_karti:
        pomylky[a].append('відкрита для пошуку, але не в карті сайту')
    bity = Counter()
    for a, vykh in posylannia.items():
        for n in vykh:
            if n not in vsi and not (teka / n.lstrip('/')).exists():
                bity[n] += 1
                pomylky[a].append(f'бите посилання: {n}')
    syroty = sorted(a for a in vidkryti if a != '/' and not vkhidni[a] and not a.endswith('.html'))
    for a in syroty:
        pomylky[a].append('сирота: жодна сторінка сайту не веде сюди')
    dubli_title = {t: s for t, s in title_vsi.items() if len(s) > 1}
    dubli_opys = {o: s for o, s in opys_vsi.items() if len(s) > 1}
    for t, s in dubli_title.items():
        for a in s:
            pomylky[a].append(f'той самий заголовок ще на {len(s) - 1} сторінках')
    for o, s in dubli_opys.items():
        for a in s:
            pomylky[a].append(f'той самий опис ще на {len(s) - 1} сторінках')

    def rozpodil(xs):
        xs = sorted(xs)
        return {'min': xs[0], 'mediana': xs[len(xs) // 2], 'max': xs[-1]} if xs else {}
    vydy = Counter()
    for a, p in pomylky.items():
        for x in p:
            vydy[re.sub(r'\d+', 'N', x.split(':')[0])] += 1
    return {
        'storinok': len(vsi), 'vidkrytykh': len(vidkryti), 'zakrytykh': len(zakryti), 'u_karti_saitu': len(smap),
        'syrit': len(syroty), 'bytykh_posylan': sum(bity.values()), 'dubliv_title': len(dubli_title),
        'dubliv_opysu': len(dubli_opys), 'jsonld': dict(typy_ld), 'dovzhyny': {k: rozpodil(v) for k, v in dovzhyny.items()},
        'storinok_z_pomylkamy': len(pomylky), 'vydy_pomylok': dict(vydy.most_common()),
        'pomylky': {a: p for a, p in sorted(pomylky.items())},
    }


def storinky_shapky(teka: Path):
    """Адреси з шапки й підвалу головної — вони є на кожній сторінці."""
    f = teka / 'index.html'
    if not f.is_file():
        return
    t = f.read_text(encoding='utf-8')
    poza = t.split('<main', 1)[0] + t.split('</main>', 1)[-1]
    for h in HREF.findall(poza):
        n = normuvaty(h, '/')
        if n:
            yield n, ''


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('teka', type=Path)
    p.add_argument('--adresa-saitu', default='')
    p.add_argument('--zvit', type=Path)
    p.add_argument('--pokazaty', type=int, default=20, help='скільки сторінок з помилками показати')
    a = p.parse_args(argv)
    adresa = a.adresa_saitu
    if not adresa:      # з robots.txt
        m = re.search(r'Sitemap: (\S+)/sitemap\.xml', (a.teka / 'robots.txt').read_text(encoding='utf-8'))
        adresa = m.group(1) if m else ''
    z = perevirka(a.teka, adresa)
    if a.zvit:
        a.zvit.write_text(json.dumps(z, ensure_ascii=False, indent=1), encoding='utf-8')
    korotko = {k: v for k, v in z.items() if k != 'pomylky'}
    print(json.dumps(korotko, ensure_ascii=False, indent=1))
    for adr, p_ in list(z['pomylky'].items())[:a.pokazaty]:
        print(adr, '—', '; '.join(p_[:4]))
    return 1 if z['pomylky'] else 0


if __name__ == '__main__':
    sys.exit(main())

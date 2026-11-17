"""Покажчик для бота «Мій будинок» і районних каналів (ZAVDANNYA-97).

    python bot/indeks.py <events-<дата>.db> <budynky.json> <вихід.json>
                         [--pereimenuvannya CSV] [--mezhi-rayoniv JSON] [--koloda koloda-<дата>.json]

Бере той самий випуск і те саме зведення будинків, що й збирач сайту (`site/zibraty_sait.py --budynky`), і тим самим
кодом рахує адреси сторінок — тож посилання бота й каналів ведуть рівно на сторінки сайту.

У покажчику — **лише те, що й так є на відкритих сторінках** (MV-99, MV-100, MV-102): адреса будинку, адреса його сторінки,
числа скарг 1551 по темах і медіана сусідів, події з рішень числом за відкриті роки (статеві й щодо дітей не входять уже у
зведенні `dani-edrsr/src/budynky_sait.py`). Описів подій, посилань на рішення, імен тут немає.
Виняток — `koloda`: події гри (MV-12) для районних каналів; вони й так публічні в грі, номер будинку з них прибирає
генератор дописів (`bot/kanaly.py`, MV-25, MV-60).

Потрібно те саме, що для збирача сайту (бібліотека h3). Сам бот і генератор дописів працюють лише з цим файлом.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
sys.path.insert(0, str(KORIN / 'brend'))


def _rayon_vulytsi(v) -> str | None:
    return v.rayony.most_common(1)[0][0] if v.rayony else None


def zibraty(baza: Path, budynky: Path, pereimenuvannya: Path | None = None, mezhi_rayoniv: Path | None = None,
            koloda: Path | None = None) -> dict:
    import dani as D
    import storinky_mv100 as M
    import zibraty_sait as Z
    from adresa_pokazu import bez_nomera

    dn = D.zibraty_dani(baza, pereimenuvannya, mezhi_rayoniv or KORIN / 'data' / 'borders.json')
    vulytsi = sorted((v for v in dn.vulytsi.values() if v.podii), key=lambda v: v.slug)
    bud = M.Budynky(budynky, dn, vulytsi)
    syri = json.loads(Path(budynky).read_text(encoding='utf-8'))
    # Сирий запис зведення → будинок сайту: за точкою й номером (Budynky не зберігає ключ зведення).
    za_tochkoyu = {}
    for x in syri['budynky']:
        za_tochkoyu.setdefault((x['lat'], x['lon'], x['nomer']), x)

    vykhid_b = []
    for b in bud.spysok:
        x = za_tochkoyu.get((b['lat'], b['lon'], b['nomer']), {})
        hrupy = Counter()
        for g in b['vidkryti'].values():
            hrupy.update(g)
        vsi_podii = sum(sum(g.values()) for g in x.get('podii', {}).values())
        zap = {'a': b['adresa'], 'u': b['url'], 'n': b['nomer'], 'v': b['vulytsia'], 'la': b['lat'], 'lo': b['lon']}
        if b['vulytsia_slug']:
            zap['vs'] = b['vulytsia_slug']
        if b['rayon']:
            zap['r'] = b['rayon']
        if b['skarh']:
            zap['sk'] = b['skarhy']
            if b['susidy']:
                zap['su'] = b['susidy']
            if x.get('ostannii'):
                zap['o'] = x['ostannii']
        if b['podii_vidkr']:
            zap['ph'] = dict(sorted(hrupy.items()))
        if vsi_podii:
            zap['pv'] = vsi_podii          # усі роки — лише для «нове з минулого тижня» (різниця двох покажчиків)
        vykhid_b.append(zap)

    vykhid_v = [{'s': v.slug, 'n': v.nazva, 't': v.typ, 'k': v.korotka, 'r': _rayon_vulytsi(v), 'p': len(v.nedavni)}
                for v in vulytsi]

    podii_r = M.podii_rayoniv(dn)
    skarhy_r = {}
    for r, bs in bud.za_rayonom.items():
        c = Counter()
        for b in bs:
            c.update(b['skarhy'])
        skarhy_r[r] = c
    rayony = sorted(set(podii_r) | set(skarhy_r))
    vykhid_r = [{'n': r, 's': Z.slug_rayonu(r), 'ph': dict(sorted(podii_r.get(r, Counter()).items())),
                 'sk': dict(skarhy_r.get(r, Counter()).most_common()), 'b': len(bud.za_rayonom.get(r, []))}
                for r in rayony]

    vykhid_k = []
    if koloda:
        kol = json.loads(Path(koloda).read_text(encoding='utf-8'))
        za_kliuchem = {(v.typ, D.kliuch(v.korotka)): v for v in vulytsi}
        for p in kol.get('podii', []):
            vul = bez_nomera(p.get('adresa', ''))
            r_ = D.rozibraty_vulytsiu(vul)
            slug = dn.zvedennia.varianty.get(r_) if r_ else None
            if isinstance(slug, (list, tuple)):
                slug = slug[0] if slug else None
            v = dn.vulytsi.get(slug) if isinstance(slug, str) else None
            if v is None and r_:
                v = za_kliuchem.get((r_[0], D.kliuch(r_[1])))
            rayon = dn.rayony.rayon(p['lat'], p['lon']) if dn.rayony else None
            # Лише потрібне для допису: без повного опису (там імена й номер будинку) і без номера будинку в адресі.
            vykhid_k.append({'id': p['id'], 'vyd': p.get('vyd'), 'kategoriia': p.get('kategoriia'), 'rik': p.get('rik'),
                             'opys_korotkyi': p.get('opys_korotkyi', ''), 'vulytsia': vul, 'typ_mistsia': p.get('typ_mistsia'),
                             'rishennya_nomer': p.get('rishennya_nomer', ''), 'rishennya_url': p.get('rishennya_url', ''),
                             'vulytsia_slug': v.slug if v and v.podii else None,
                             'vulytsia_nazva': v.nazva if v else None, 'rayon': rayon})

    return {'versiia': bud.versiia, 'misiatsi_1551': bud.misiatsi, 'r_susidy_m': bud.r_susidy,
            'roky_podii': [D.VIDKRYTI_ROKY[0], D.VIDKRYTI_ROKY[-1]], 'hrupy': dict(D.HRUPY),
            'budynky': vykhid_b, 'vulytsi': vykhid_v, 'rayony': vykhid_r, 'koloda': vykhid_k}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Покажчик для бота «Мій будинок» і районних каналів.')
    p.add_argument('baza', type=Path)
    p.add_argument('budynky', type=Path)
    p.add_argument('vykhid', type=Path)
    p.add_argument('--pereimenuvannya', type=Path)
    p.add_argument('--mezhi-rayoniv', type=Path)
    p.add_argument('--koloda', type=Path)
    a = p.parse_args(argv)
    z = zibraty(a.baza, a.budynky, a.pereimenuvannya, a.mezhi_rayoniv, a.koloda)
    a.vykhid.write_text(json.dumps(z, ensure_ascii=False, separators=(',', ':'), sort_keys=True), encoding='utf-8')
    print(f"будинків: {len(z['budynky'])}; вулиць: {len(z['vulytsi'])}; районів: {len(z['rayony'])}; "
          f"подій колоди: {len(z['koloda'])} (з вулицею сайту: {sum(1 for k in z['koloda'] if k['vulytsia_slug'])})")
    return 0


if __name__ == '__main__':
    sys.exit(main())

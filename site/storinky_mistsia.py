# -*- coding: utf-8 -*-
"""Сторінки публічних місць (ZAVDANNYA-124; MV-54, MV-60, MV-98, MV-116, MV-135): станції метро, ТЦ, ринки, вокзали,
парки й сквери, пляжі, мости, острови — /mistse/<slug>/ і покажчик /mistsia/.

Лише числа (MV-3): події за групами й роками, порівняння «тут · у типовому місці того самого типу» (MV-98), скарги 1551
будинків у колі 200 м — підсумком, без адрес. «Що поруч» не робимо. Житлового тут нічого: жодного номера будинку чи
посилання на сторінку будинку (тест tests/test_mistsia.py). Посилання місце ↔ вулиця ↔ район. Блок «Для медіа» —
візуал з dani-edrsr/src/vizual_mistsia.py (MV-135), коли його файли лежать у теці --media.
Тонкі місця (1–2 події) — сторінка є, але не в пошуку Google (як вулиці).
"""
from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import dani as D
import mistsia as MS
import zibraty_sait as Z
import storinky_mv100 as M

e, chyslo, vidminok, NBSP = Z.e, Z.chyslo, Z.vidminok, Z.NBSP
HASLO = 'Моя вулиця — що відбувається під боком'
SKARHY_M = 200                    # скарги 1551 будинків у колі навколо місця
# schema.org: тип місця для пошуку
SCHEMA = {'метро': 'SubwayStation', 'вокзал': 'TrainStation', 'ТЦ': 'ShoppingCenter', 'парк': 'Park', 'пляж': 'Beach',
          'міст': 'Bridge', 'ринок': 'Place', 'острів': 'Place'}
TYPOVA = {'метро': 'типова станція метро', 'ТЦ': 'типовий ТЦ', 'ринок': 'типовий ринок', 'вокзал': 'типовий вокзал',
          'парк': 'типовий парк чи сквер', 'пляж': 'типовий пляж', 'міст': 'типовий міст', 'острів': 'типовий острів'}
TYPOVE = {'метро': 'типової станції метро', 'ТЦ': 'типового ТЦ', 'ринок': 'типового ринку', 'вокзал': 'типового вокзалу',
          'парк': 'типового парку чи скверу', 'пляж': 'типового пляжу', 'міст': 'типового мосту', 'острів': 'типового острова'}
MITKY = {'більше': 'більше, ніж у {t}', 'як зазвичай': 'як у {t}', 'менше': 'менше, ніж у {t}',
         'мало даних': 'мало даних, щоб порівнювати'}


def malymy(t: str) -> str:
    """Перша літера мала, але абревіатури («ДТП») — як є."""
    return t if t[:2].isupper() else t[:1].lower() + t[1:]


def media_mistsia(media: Path | None, m: MS.Mistse) -> dict | None:
    """MV-135: візуал — лише для публічного місця, чия сторінка — ця; усі файли на місці; інакше None."""
    if not media:
        return None
    f = media / m.slug / 'vizual.json'
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding='utf-8'))
    if d.get('typ') not in Z.MEDIA_PUBLICHNI or d.get('storinka') != f'/mistse/{m.slug}/':
        return None
    if any(not (media / m.slug / n).exists() for n, _, _ in Z.MEDIA_FAILY):
        return None
    return d


def skarhy_poruch(bud, m: MS.Mistse) -> Counter:
    """Скарги 1551 будинків у колі 200 м — лише підсумок тем (без адрес будинків)."""
    s = Counter()
    if not bud:
        return s
    for b in bud.spysok:
        if b.get('lat') is not None and MS.vidstan_m(m.lat, m.lon, b['lat'], b['lon']) <= SKARHY_M:
            s.update(b['skarhy'])
    return s


def storinka_mistsia(dn: D.Dani, m: MS.Mistse, pr: dict, adresa_saitu: str, bud=None, media: dict | None = None,
                     kolory: dict | None = None, vykhid: Path | None = None) -> str:
    roky_t = Z.PERIOD_VIDKRYTYI
    nazva = MS.z_velykoi(m.nazva)
    typ_t = MS.TYPY[m.typ][0]
    vsogo = pr['vsogo']
    v = dn.vulytsi.get(m.vulytsia) if m.vulytsia else None
    kryhty = [('/', 'Головна'), ('/mistsia/', 'Місця')]
    if m.rayon:
        kryhty.append((f'/rayon/{Z.slug_rayonu(m.rayon)}/', f'{m.rayon} район'))
    kryhty.append(('', nazva))
    ch = [M.kryhty_html(kryhty)]
    hrupy = [(k, n) for k, n in pr['hrupy'] if k in M.HRUPY_PODII]
    naichastishe = ', '.join(f'{malymy(M.HRUPY_PODII[k])} — {chyslo(n)}' for k, n in hrupy[:2])
    rech = f'{e(nazva)}: за {roky_t} у даних судів — {Z.podii_slovo(vsogo)}, де місцем названо саме це місце' + (
        f'; найчастіше — {e(naichastishe)}' if naichastishe else '') + '.'
    mitka = 'Київ' + (f' · {m.rayon} район' if m.rayon else '') + f' · {typ_t}'
    ch.append(f'''<section class="zaholovok"><span class="mitka">{e(mitka)}</span><h1>{e(nazva)}</h1>
<p>{rech}</p>{Z.onovleno(dn.versiia)}</section>''')

    # Коротко
    ost = D.VIDKRYTI_ROKY[-1]
    chysla = [(chyslo(vsogo), f'{vidminok(vsogo, ("подія", "події", "подій"))} за {roky_t}'),
              (chyslo(pr['roky'].get(ost, 0)), f'у {ost} році (рік ще триває)')]
    ch.append('<section class="chysla" aria-label="Коротко">' + ''.join(
        f'<div class="kartka chyslo-blok"><b class="chyslo">{a}</b><span>{b}</span></div>' for a, b in chysla) + '</section>')

    # Порівняння (MV-98): обидва числа поруч, кроки однакової ваги; «подія» — помітно над таблицею.
    t = TYPOVE[m.typ]
    if pr['typove'] is not None:
        typove = pr['typove']
        typove_t = chyslo(round(typove)) if typove == int(typove) else f'{typove:.1f}'.replace('.', ',')
        ch.append(f'''<section class="rozdil"><h2>Порівняння з тим самим типом місць</h2>
<p class="rozdil__pidpys"><b>Подія — один випадок із рішення суду.</b> Порівнюємо з серединою серед {chyslo(pr["mists_typu"])} місць того самого типу в даних.</p>
<div class="kartka por"><div class="por__ryad por__ryad--1"><span class="por__nazva">Тут</span><span class="por__smuha"><i class="sh-{M.shyryna(vsogo, max(vsogo, typove))} por--tut"></i></span><b>{chyslo(vsogo)}</b></div>
<div class="por__ryad por__ryad--1"><span class="por__nazva">{e(MS.z_velykoi(TYPOVA[m.typ]))}</span><span class="por__smuha"><i class="sh-{M.shyryna(typove, max(vsogo, typove))} por--tut"></i></span><b>{typove_t}</b></div>
<p class="por__mitka">{e(MITKY[pr["mitka"]].format(t=t))}</p></div>
<p class="prymitka">Це кількість у даних, а не оцінка місця: людне місце дає більше подій.</p></section>''')
    else:
        ch.append('<section class="rozdil"><h2>Порівняння з тим самим типом місць</h2><p class="rozdil__pidpys">Місць цього типу в даних '
                  'замало, щоб порівнювати.</p></section>')

    # Групи (MV-116)
    if hrupy:
        maks = max(n for _, n in hrupy)
        ch.append('<section class="rozdil"><h2>Події за групами</h2>'
                  f'<p class="rozdil__pidpys">{roky_t}; статеві злочини й справи щодо дітей на відкритих сторінках не рахуємо.</p>'
                  '<div class="kartka por">' + ''.join(
                      f'<div class="por__ryad por__ryad--1"><span class="por__nazva">{e(M.HRUPY_PODII[k])}</span>'
                      f'<span class="por__smuha"><i class="sh-{M.shyryna(n, maks)} por--tut"></i></span><b>{chyslo(n)}</b></div>'
                      for k, n in hrupy) + '</div></section>')

    # Роки
    maks = max(pr['roky'].values(), default=0) or 1
    ch.append('<section class="rozdil"><h2>Події за роками</h2>'
              f'<p class="rozdil__pidpys">{ost} — неповний рік.</p><div class="kartka por">' + ''.join(
                  f'<div class="por__ryad por__ryad--1"><span class="por__nazva">{r}</span>'
                  f'<span class="por__smuha"><i class="sh-{M.shyryna(n, maks)} por--tut"></i></span><b>{chyslo(n)}</b></div>'
                  for r, n in pr['roky'].items()) + '</div></section>')

    # Скарги 1551 поруч — лише підсумок тем
    sk = skarhy_poruch(bud, m)
    if sk:
        maks = max(sk.values())
        ch.append(f'<section class="rozdil"><h2>Скарги 1551 поруч</h2><p class="rozdil__pidpys">Звернення мешканців будинків '
                  f'у колі {SKARHY_M} м за {e(M.period_1551(bud.misiatsi))} — {M.skarhy_slovo(sum(sk.values()))}. Це скарги людей, '
                  'не перевірені факти, і вони про будинки, а не про саме місце.</p><div class="kartka por">' + ''.join(
                      f'<div class="por__ryad por__ryad--1"><span class="por__nazva">{e(M.z_velykoi(h))}</span>'
                      f'<span class="por__smuha"><i class="sh-{M.shyryna(n, maks)} por--tut"></i></span><b>{chyslo(n)}</b></div>'
                      for h, n in sk.most_common(6)) + '</div></section>')

    if media:
        ch.append(Z.blok_media(media, m.slug, f'/mistse/{m.slug}/media'))
        ch.append(f'<p class="prymitka">Візуал рахує всі події в колі {media["radius"]} м довкола — і на сусідніх вулицях, тому '
                  'там число більше, ніж угорі сторінки, де лише події з назвою самого місця.</p>')

    # Місце ↔ вулиця ↔ район
    posylannia = []
    if v:
        posylannia.append(f'<a class="knopka" href="/vulytsia/{v.slug}/">{e(v.nazva)}</a>')
    if m.rayon:
        posylannia.append(f'<a class="knopka" href="/rayon/{Z.slug_rayonu(m.rayon)}/">{e(m.rayon)} район</a>')
    posylannia.append(f'<a class="knopka" href="/mistsia/#{e(m.typ)}">{e(MS.TYPY[m.typ][1])}</a>')
    ch.append(f'<section class="rozdil"><h2>Довкола</h2><div class="diyi">{"".join(posylannia)}</div></section>')
    knopka_pidpysky = M.T.knopka_oplaty('/oplata/?tovar=pidpyska&amp;dzherelo=mistse', f'Підписка — події з адресами, {M.tsina("pidpyska")}', True)
    ch.append(f'''<section class="rozdil"><h2>Що далі</h2><p class="haslo">{e(HASLO)}</p>
<div class="diyi">{knopka_pidpysky}
<a class="knopka" href="/karta/">Карта Києва</a></div></section>''')
    ch.append('<p class="prymitka">Дані — з рішень судів, які дійшли до реєстру; це не всі події тут. Рахуємо лише події, де '
              f'суд назвав саме це місце; домашнє насильство — нарівні, статеві й щодо дітей — ні. Дані станом на {e(dn.versiia)}.</p>')

    title = f'{nazva}, Київ: {Z.podii_slovo(vsogo)} з рішень судів {roky_t} | Моя вулиця'
    opys = (f'{nazva} ({m.rayon + " район" if m.rayon else "Київ"}): {Z.podii_slovo(vsogo)} з судових рішень за {roky_t}'
            + (f', найчастіше — {naichastishe}' if naichastishe else '') + '. Лише числа, без адрес і описів.')
    place = {'@context': 'https://schema.org', '@type': SCHEMA[m.typ], 'name': f'{nazva}, Київ',
             'url': f'{adresa_saitu}/mistse/{m.slug}/', 'geo': {'@type': 'GeoCoordinates', 'latitude': m.lat, 'longitude': m.lon},
             'dateModified': dn.versiia}
    if m.rayon:
        place['containedInPlace'] = {'@type': 'Place', 'name': f'{m.rayon} район, Київ'}
    kartynka = None
    if kolory is not None and vykhid is not None:
        import kartynky as K
        Z.zapysaty_bajty(vykhid / 'mistse' / m.slug / 'kartynka.png',
                         K.kartynka(mitka, nazva, [chysla[0]], kolory))
        kartynka = (f'/mistse/{m.slug}/kartynka.png', f'{nazva}: {chysla[0][0]} {chysla[0][1]}')
    return Z.storinka(shlyakh=f'/mistse/{m.slug}/', title=title, opys=opys, tilo='\n'.join(ch), adresa_saitu=adresa_saitu,
                      aktyvne='vulytsi/', dodatkovo_head=M.ld_skrypt(place, M.kryhty_ld(kryhty, adresa_saitu)),
                      kartynka=kartynka, indeksuvaty=vsogo >= Z.MIN_PODII_DLYA_POSHUKU)


def storinka_pokazhchyka(mistsia: dict, adresa_saitu: str) -> str:
    za_typom = defaultdict(list)
    for m in mistsia.values():
        za_typom[m.typ].append(m)
    ch = [M.kryhty_html([('/', 'Головна'), ('', 'Місця')]),
          '<section class="zaholovok"><span class="mitka">Київ</span><h1>Публічні місця</h1>'
          '<p>Станції метро, торгові центри, ринки, вокзали, парки, пляжі й мости, які суди називають місцем події. '
          'На сторінці кожного — лише числа: скільки подій, з яких груп, за роками, і порівняння з типовим місцем того самого типу.</p></section>']
    for typ in MS.TYPY:
        if not za_typom.get(typ):
            continue
        vs = sorted(za_typom[typ], key=lambda x: (Z.kliuch_abetky(x.vlasna), x.slug))
        ch.append(f'<section class="rozdil" id="{e(typ)}"><h2>{e(MS.TYPY[typ][1])}</h2><ul class="spysok-vulyts">' + ''.join(
            f'<li><a href="/mistse/{x.slug}/">{e(MS.z_velykoi(x.nazva))}</a><small>{chyslo(len(x.podii))}</small></li>' for x in vs)
            + '</ul></section>')
    return Z.storinka(shlyakh='/mistsia/', title='Публічні місця Києва: метро, ТЦ, ринки, вокзали, парки | Моя вулиця',
                      opys='Станції метро, ТЦ, ринки, вокзали, парки, пляжі й мости Києва — скільки подій з рішень судів, лише числа.',
                      tilo='\n'.join(ch), adresa_saitu=adresa_saitu, aktyvne='vulytsi/')


def blok_mists(mistsia: list, zaholovok: str) -> str:
    """Список посилань на сторінки місць (для сторінок вулиці й району)."""
    if not mistsia:
        return ''
    return (f'<section class="rozdil"><h2>{e(zaholovok)}</h2><ul class="spysok-vulyts">' + ''.join(
        f'<li><a href="/mistse/{m.slug}/">{e(MS.z_velykoi(m.nazva))}</a><small>{chyslo(len(m.podii))}</small></li>'
        for m in sorted(mistsia, key=lambda x: (-len(x.podii), x.slug))) + '</ul></section>')


def zibraty(dn: D.Dani, vykhid: Path, adresa_saitu: str, bud=None, media: Path | None = None,
            vsi: dict | None = None) -> tuple[list, int, dict]:
    """Пише /mistse/<slug>/ і /mistsia/; повертає (адреси для sitemap, скільки з «Для медіа», slug → Mistse)."""
    vsi = MS.zibraty(dn) if vsi is None else vsi
    if not vsi:
        return [], 0, vsi
    kolory = Z.kolory_tem()['svitla']
    adresy, z_media = ['/mistsia/'], 0
    for m in vsi.values():
        pr = MS.profil(dn, m, vsi)
        md = media_mistsia(media, m)
        if md:
            shutil.copytree(media / m.slug, vykhid / 'mistse' / m.slug / 'media', dirs_exist_ok=True)
            z_media += 1
        Z.zapysaty(vykhid / 'mistse' / m.slug / 'index.html', storinka_mistsia(dn, m, pr, adresa_saitu, bud, md, kolory, vykhid))
        if pr['vsogo'] >= Z.MIN_PODII_DLYA_POSHUKU:
            adresy.append(f'/mistse/{m.slug}/')
    Z.zapysaty(vykhid / 'mistsia' / 'index.html', storinka_pokazhchyka(vsi, adresa_saitu))
    return adresy, z_media, vsi

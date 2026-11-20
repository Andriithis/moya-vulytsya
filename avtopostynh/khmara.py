"""Автопостинг без сервера — один запуск за розкладом GitHub Actions (ZAVDANNYA-131, MV-153).

    python avtopostynh/khmara.py --stan <тека стану> [--vkhid <тека входу>] hodyna
    python avtopostynh/khmara.py --stan … prybraty ID --prychyna "…" [--mistse] [--usi-merezhi]
    python avtopostynh/khmara.py --stan … vidnovyty MEREZHA
    python avtopostynh/khmara.py --stan … zhurnal
    python avtopostynh/khmara.py --stan … tiktok 129-t5 --posylannia https://www.tiktok.com/@…/video/…

Те саме, що `servis.py` на сервері, але для хмари, де між запусками нічого не живе:
- стан (`cherha.db`, пачки) лежить у теці `--stan`; робочий процес бере її з гілки `avtopostynh-stan` і повертає назад;
- вхід — тека `--vkhid` з приватного Release: `indeks.json` (покажчик для дописів Telegram), `media/` (ролики й картки з
  `manifest.json`), необов'язково `kanaly.json`; або `kanaly` — у змінній `MV_KANALY_JSON` (не секрет);
- **типово пробний режим**: справжня публікація — лише коли `MV_PROBNYI=0` явно (на сервері навпаки, `servis.py`);
- **TikTok у хмарі вимкнено**: ключ оновлення TikTok змінюється при кожному оновленні й мусить десь зберігатися між запусками
  (`docs/AVTOPOSTYNH.md`, розд. 6, п. 1), а записати секрет GitHub з робочого процесу без додаткового ключа не можна;
  до аудиту TikTok однаково публікує лише «бачу тільки я» — ролики туди партнер ставить сам;
- сторінки-перегляду з сервером немає: замість неї `PEREHLIAD.md` у гілці стану й підсумок запуску в GitHub (що вийшло, з ID);
  «Прибрати» — ручний запуск того самого робочого процесу з командою `prybraty` (`docs/AVTOPOSTYNH.md`, розд. 9).
Ключі — лише змінні середовища з секретів GitHub; у теку стану не пишуться (`cherha.py` токенів не зберігає).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TUT = Path(__file__).resolve().parent
sys.path.insert(0, str(TUT))

import cherha as C  # noqa: E402
import cherha_rolykiv as CR  # noqa: E402
import pravyla as P  # noqa: E402
import rozklad as R  # noqa: E402
import servis as SV  # noqa: E402

NE_V_KHMARI = {'tiktok'}
PEREHLIAD = 'PEREHLIAD.md'
TIKTOK = 'TikTok.md'          # чекліст Микити: що поставити в TikTok вручну (ZAVDANNYA-159)
# що зберігати між запусками (решта — тимчасове: «опубліковане» пробного режиму з копіями роликів тощо)
ZBERIHATY = ('cherha.db', PEREHLIAD, TIKTOK, 'pachky')
NAZVY = {'telegram': 'Telegram', 'youtube': 'YouTube', 'facebook': 'Facebook', 'instagram': 'Instagram', 'tiktok': 'TikTok'}
STANY = {'chekaie': 'у черзі', 'opublikovano': 'вийшло', 'vidkhyleno': 'не пройшло перевірку', 'pomylka': 'помилка',
         'propushcheno': 'пропущено', 'prybrano': 'прибрано', 'prybraty_vruchnu': 'прибрати вручну (партнер)',
         CR.STAN_VRUCHNU: 'поставити вручну (TikTok.md)'}


def probnyi() -> bool:
    return os.environ.get('MV_PROBNYI', '1').strip() != '0'


def merezhi_dlia_khmary() -> tuple[str, list[str]]:
    """MV_MEREZHI без мереж, які в хмарі не працюють. Повертає (нове значення, що прибрано)."""
    vsi = [m.strip() for m in os.environ.get('MV_MEREZHI', 'telegram').split(',') if m.strip()]
    return ','.join(m for m in vsi if m not in NE_V_KHMARI), [m for m in vsi if m in NE_V_KHMARI]


def kanaly(vkhid: Path | None) -> dict:
    t = os.environ.get('MV_KANALY_JSON', '').strip()
    if t:
        return json.loads(t)
    f = vkhid / 'kanaly.json' if vkhid else None
    return json.loads(f.read_text(encoding='utf-8')) if f and f.is_file() else {}


def _komirka(t) -> str:
    return str(t or '').replace('|', '/').replace('\n', ' ').strip()


def perehliad_md(sv: SV.Servis, zaraz: datetime, dniv: int = 7) -> str:
    """Що вийшло й що в черзі: останні `dniv` днів і наступна доба. Для телефона — таблиці Markdown."""
    vid, do = C.iso(zaraz - timedelta(days=dniv)), C.iso(zaraz + timedelta(days=1))
    vsi = [o for o in sv.q.vsi() if vid <= o['chas'] <= do]
    ch = ['# Автопостинг «Моєї вулиці» — що вийшло', '',
          f'Оновлено {R.po_kyievu(C.iso(zaraz))} за Києвом.'
          + (' **Пробний режим — у мережі нічого не пішло.**' if sv.probnyi else ''), '']
    for z in sv.q.stan_merezh():
        if z.get('zupyneno_do') and z['zupyneno_do'] > C.iso(zaraz):
            ch.append(f'> **{NAZVY.get(z["merezha"], z["merezha"])} зупинено**: {_komirka(z["prychyna"])}. '
                      'Партнер розбирається, потім — запуск з командою `vidnovyty`.')
            ch.append('')
    if not vsi:
        ch += ['Нічого за цей час.', '']
    for m in NAZVY:
        rr = [o for o in vsi if o['merezha'] == m]
        if not rr:
            continue
        ch += [f'## {NAZVY[m]}', '', '| Коли | Канал | Що | Стан | ID | Посилання |', '|---|---|---|---|---|---|']
        for o in rr:
            pochatok = (o.get('zaholovok') or o.get('tekst') or '').strip().split('\n')[0][:60]
            stan = STANY.get(o['stan'], o['stan'])
            if o['stan'] in ('vidkhyleno', 'pomylka') and o.get('zauvazhennia'):
                stan += ': ' + '; '.join(o['zauvazhennia'])[:120]
            ch.append(f'| {R.po_kyievu(o["chas"])} | {_komirka(o.get("kanal"))} | {_komirka(pochatok)} | {_komirka(stan)} '
                      f'| `{o["id"]}` | {_komirka(o.get("url_dopysu"))} |')
        ch.append('')
    ch += ['## Як прибрати допис', '',
           'GitHub → вкладка **Actions** → «Автопостинг» → **Run workflow** → команда `prybraty`, у поле «id» — ID з таблиці, '
           'у «prychyna» — чому (наприклад «видно номер будинку»). Галочка «mistse» — більше не писати про це місце, '
           '«usi_merezhi» — той самий ролик з усіх мереж. Telegram видаляє лише дописи, молодші за 48 год; старші — '
           'партнер вручну (стан «прибрати вручну»).', '']
    return '\n'.join(ch)


def zapustyty(stan: Path, vkhid: Path | None, komanda: str, a: argparse.Namespace, zaraz: datetime | None = None) -> list[str]:
    zaraz = zaraz or C.teper()
    zvit = []
    znachennia, prybrano = merezhi_dlia_khmary()
    os.environ['MV_MEREZHI'] = znachennia
    if prybrano:
        zvit.append(f'у хмарі не публікуємо: {", ".join(prybrano)} (ключ TikTok змінюється щоразу — ставить партнер)')
    media = vkhid / 'media' if vkhid and (vkhid / 'media').is_dir() else None
    sv = SV.Servis(stan, probnyi(), media, os.environ.get('MV_ADRESA_SAITU', SV.ADRESA_SAITU), kanaly(vkhid))
    if sv.probnyi:   # пробний режим показує рівно те, що піде з хмари
        sv.uvimkneni = lambda: [m for m in P.MEREZHI if m not in NE_V_KHMARI]
    try:
        if komanda == 'hodyna':
            indeks = vkhid / 'indeks.json' if vkhid and (vkhid / 'indeks.json').is_file() else None
            if not indeks:
                zvit.append('немає indeks.json у вході — дописів Telegram цього тижня не буде')
            zvit += sv.hodyna(indeks, None, zaraz)
        elif komanda == 'prybraty':
            if not a.id or not (a.prychyna or '').strip():
                raise SystemExit('prybraty: потрібні id і prychyna')
            zvit += sv.prybraty(a.id.strip(), a.prychyna, a.mistse, a.usi_merezhi)
        elif komanda == 'vidnovyty':
            if a.merezha not in P.MEREZHI:
                raise SystemExit(f'vidnovyty: мережа одна з {", ".join(P.MEREZHI)}')
            sv.q.vidnovyty(a.merezha)
            zvit.append(f'{a.merezha}: відновлено')
        elif komanda == 'tiktok':
            if not a.id or not (a.posylannia or '').strip():
                raise SystemExit('tiktok: потрібні id ролика й посилання на нього в TikTok')
            zvit.append(CR.tiktok_postavleno(sv.q, a.id.strip(), a.posylannia, zaraz))
        elif komanda == 'zhurnal':
            for z in reversed(sv.q.zhurnal(C.iso(zaraz - timedelta(days=7)))):
                zvit.append(f'{R.po_kyievu(z["chas"])} {z["merezha"]:9} {z["kanal"][:14]:14} {z["podiia"]:16} '
                            f'{z["povidomlennia"]}')
        md = perehliad_md(sv, zaraz)
        (Path(stan) / PEREHLIAD).write_text(md, encoding='utf-8')
        (Path(stan) / TIKTOK).write_text(CR.tiktok_md(sv.q, zaraz, sv.sait), encoding='utf-8')
        if getattr(a, 'tiktok_teka', None):
            n = len(CR.faily_tiktok(sv.q, zaraz, sv.media, Path(a.tiktok_teka)))
            if n:
                zvit.append(f'TikTok: {n} ролик(ів) поставити вручну — файли у вкладенні запуску, чекліст {TIKTOK}')
        pidsumok = os.environ.get('GITHUB_STEP_SUMMARY')
        if pidsumok:
            with open(pidsumok, 'a', encoding='utf-8') as f:
                f.write('```\n' + '\n'.join(zvit or ['нічого не сталося']) + '\n```\n\n' + md + '\n')
    finally:
        sv.q.zakryty()
    return zvit


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Автопостинг «Моєї вулиці» без сервера (GitHub Actions).')
    p.add_argument('--stan', type=Path, required=True, help='тека стану (з гілки avtopostynh-stan)')
    p.add_argument('--vkhid', type=Path, help='тека входу з приватного Release: indeks.json, media/, kanaly.json')
    p.add_argument('--zaraz', help='«зараз» для перевірки (ISO), типово справжній час')
    p.add_argument('--tiktok-teka', type=Path, help='куди покласти файли TikTok на найближчі дні (вкладення запуску)')
    p.add_argument('komanda', choices=['hodyna', 'prybraty', 'vidnovyty', 'zhurnal', 'tiktok'])
    p.add_argument('id', nargs='?', default='')
    p.add_argument('--prychyna', default='')
    p.add_argument('--mistse', action='store_true')
    p.add_argument('--usi-merezhi', action='store_true')
    p.add_argument('--merezha', default='')
    p.add_argument('--posylannia', default='', help='tiktok: посилання на ролик у TikTok')
    a = p.parse_args(argv)
    zaraz = datetime.fromisoformat(a.zaraz).astimezone(timezone.utc) if a.zaraz else None
    print('пробний режим — нічого не надсилаємо' if probnyi() else 'СПРАВЖНЯ ПУБЛІКАЦІЯ')
    for x in zapustyty(a.stan, a.vkhid, a.komanda, a, zaraz):
        print(x)
    return 0


if __name__ == '__main__':
    sys.exit(main())

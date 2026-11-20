"""Заміри роликів: щоденний збір чисел і тижневий підсумок для центрального чату (ZAVDANNYA-159;
`docs/ROLYKY-SYSTEMA.md`, розд. 4; MV-158, MV-161).

    python avtopostynh/zamiry.py --cherha <cherha.db з гілки avtopostynh-stan> --zamiry <тека zamiry/> [--data РРРР-ММ-ДД]
                                 [--pidsumok] [--bez-merezh]

Що робить (щодня о ≈ 06:00 за Києвом, робочий процес `avtopostynh/github/zamiry.yml` у приватному репозиторії):
1. **Реєстр** `zamiry/rolyky.csv` — один рядок на публікацію ролика з черги (`cherha_rolykiv.py`): `id, typ, varianty,
   dovzhyna_s, holos, merezha, url, zovnishnii_id, opublikovano, kudy, mitka, stan`. Колонка `typ` — дослівно з
   `docs/ROLYKY-TYPY.md`, розд. 1. Береться з черги автопостингу (TikTok — після команди `tiktok`).
2. **Знімки** `zamiry/znimky.csv` — для кожної публікації, молодшої за 30 днів, числа «за весь час» на сьогодні
   (денні — різницею знімків): YouTube (Data API + Analytics API), Instagram (insights), Facebook (video_insights);
   TikTok — з вивантаження TikTok Studio, покладеного в `zamiry/tiktok/` (CSV, раз на тиждень). Колонка `typ` — теж тут.
3. **Дії на сайті з міткою** (`perekhody`, `zaiavky`) — з вивантаження форм сайту (`/api/admin/vyvantazhennia/…`,
   ключ MV_ADMIN_KLIUCH): події сторінок і заявки «скоро», чий канал закінчується міткою ролика (`yt-129-t5`).
   Це не відвідування, а дії (натиснув, залишив пошту) — єдине число про продаж (розд. 4.3).
4. **Тижневий підсумок** `zamiry/tyzhden-<понеділок>.md` — у понеділок (або `--pidsumok`): таблиця по типах і
   позначка «посилити / тримати / прибрати» за правилами розд. 4.4.

Сирі числа — лише в приватному репозиторії (розд. 4.3). Текст коментарів не збираємо — лише кількість.
Ключі — лише змінні середовища (ті самі, що в автопостингу), у файли не пишуться.
**Не перевірено** на справжніх ключах: форма запитів і розбір — за документацією, на штучних відповідях у тестах.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sqlite3
import statistics
import sys
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TUT = Path(__file__).resolve().parent
sys.path.insert(0, str(TUT))

import cherha_rolykiv as CR  # noqa: E402
import merezhi as M  # noqa: E402
from pravyla import KOD_MEREZHI  # noqa: E402
from rozklad import KYIV  # noqa: E402

REIESTR = ['id', 'typ', 'varianty', 'dovzhyna_s', 'holos', 'merezha', 'url', 'zovnishnii_id', 'opublikovano', 'kudy',
           'mitka', 'stan']
ZNIMKY = ['data', 'id', 'typ', 'merezha', 'perehliady', 'perehliady_spravzhni', 'lajky', 'komentari', 'poshyrennia',
          'zberezhennia', 'serednii_chas_s', 'chastka_perehliadu', 'utrymannia_3s', 'dlia_tebe', 'perekhody', 'zaiavky']
DNIV_ZBIRATY = 30
MEREZHI_API = ('youtube', 'instagram', 'facebook')
DEN_PIDSUMKU = 0                      # понеділок
MIN_PUBLIKATSII = 5                   # розд. 4.4: тип судимо після 5 публікацій
POSYLYTY_MEDIANA, POSYLYTY_ODYN = 2.0, 3.0
PRYBRATY_Z, PRYBRATY_OSTANNI = 5, 6   # «прибрати»: нижче медіани акаунта в 5 з 6 останніх
HACHOK_VYPADKOVIST = 0.05             # різниця утримання на 3 с менше 5 пунктів — випадковість
DEN_PORIVNIANNIA = 7                  # перегляди порівнюємо на 7-й день (молодші — останні)
# Продуктові типи (розд. 4.4: судимо за діями на сайті). Реєстр типів не має окремої позначки — список тут.
PRODUKTOVI = {'Запис сайту: як користуватися', 'POV: застава завтра (К-25)', 'Хтось читає звіт — і вау',
              'Стежу за вулицею · Рієлтор · ОСББ'}
NAZVY = {'youtube': 'YouTube', 'instagram': 'Instagram', 'facebook': 'Facebook', 'tiktok': 'TikTok', 'telegram': 'Telegram'}


# ==================================================================== файли
def chytaty_csv(f: Path) -> list[dict]:
    if not f.is_file():
        return []
    with open(f, encoding='utf-8-sig', newline='') as h:
        return list(csv.DictReader(h))


def pysaty_csv(f: Path, polia: list[str], ryadky: list[dict]):
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, 'w', encoding='utf-8', newline='') as h:
        w = csv.DictWriter(h, fieldnames=polia, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        for r in ryadky:
            w.writerow({k: _komirka(r.get(k)) for k in polia})


def _komirka(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def chyslo(v) -> float | None:
    if v is None or v == '':
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ==================================================================== 1. реєстр
def reiestr(shliakh_cherhy: Path) -> list[dict]:
    """Опубліковані ролики з черги автопостингу → рядки реєстру (прибрані теж: їхні числа до прибирання — дані)."""
    if not Path(shliakh_cherhy).is_file():
        return []
    db = sqlite3.connect(f'file:{shliakh_cherhy}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        ryadky = db.execute("SELECT * FROM odynytsi WHERE stan IN ('opublikovano','prybrano','prybraty_vruchnu') "
                            'ORDER BY opublikovano, merezha').fetchall()
    finally:
        db.close()
    r = []
    for x in ryadky:
        o = json.loads(x['dani'])
        if o.get('dzherelo') != 'cherha':
            continue
        m = x['merezha']
        r.append({'id': o['rolyk_id'], 'typ': o.get('typ_rolyka', ''), 'varianty': o.get('varianty', ''),
                  'dovzhyna_s': o.get('dovzhyna_s', ''), 'holos': 'так' if o.get('holos') else 'ні', 'merezha': m,
                  'url': x['url_dopysu'] or '', 'zovnishnii_id': x['zovnishnii_id'] or '',
                  'opublikovano': x['opublikovano'] or x['chas'], 'kudy': o.get('kudy', ''),
                  'mitka': f'{KOD_MEREZHI.get(m, m)}-{o["rolyk_id"]}', 'stan': x['stan']})
    return r


# ==================================================================== 2. мережі
class Zbirach:
    """Числа однієї мережі за зовнішніми id. http_ — для тестів (штучна мережа)."""

    def __init__(self, http_=None):
        self.http = http_ or M.http


class YouTubeZamiry(Zbirach):
    """Data API v3 `videos.list` (перегляди, лайки, коментарі) + YouTube Analytics API (`engagedViews` — «справжні»
    перегляди Shorts, середній час і частка перегляду, поширення; крива утримання `audienceWatchRatio` → утримання на 3 с).
    Вхід — той самий, що для публікації (MV_YOUTUBE_*), але згода має містити ще `yt-analytics.readonly`."""

    def __init__(self, http_=None):
        super().__init__(http_)
        self.yt = M.YouTube(http_=self.http)

    def _get(self, url: str, t: str) -> dict:
        v = self.http('GET', url, {'Authorization': f'Bearer {t}'})
        if v.status != 200:
            raise RuntimeError(self.yt._pomylka(v).pomylka)
        return v.json()

    def zibraty(self, ryadky: list[dict], sohodni: date) -> dict[str, dict]:
        t = self.yt._token()
        if isinstance(t, M.Rezultat):
            raise RuntimeError(t.pomylka)
        ids = [r['zovnishnii_id'] for r in ryadky if r['zovnishnii_id']]
        r: dict[str, dict] = {}
        for i in range(0, len(ids), 50):
            q = urllib.parse.urlencode({'part': 'statistics', 'id': ','.join(ids[i:i + 50])})
            for it in self._get(f'https://www.googleapis.com/youtube/v3/videos?{q}', t).get('items', []):
                s = it.get('statistics', {})
                r[it['id']] = {'perehliady': s.get('viewCount'), 'lajky': s.get('likeCount'),
                               'komentari': s.get('commentCount')}
        if not ids:
            return r
        pochatok = min(r_['opublikovano'][:10] for r_ in ryadky if r_['zovnishnii_id'])
        q = urllib.parse.urlencode({'ids': 'channel==MINE', 'startDate': pochatok, 'endDate': sohodni.isoformat(),
                                    'metrics': 'engagedViews,averageViewDuration,averageViewPercentage,shares',
                                    'dimensions': 'video', 'filters': 'video==' + ','.join(ids)})
        a = self._get(f'https://youtubeanalytics.googleapis.com/v2/reports?{q}', t)
        stovptsi = [h['name'] for h in a.get('columnHeaders', [])]
        for ryad in a.get('rows', []):
            d = dict(zip(stovptsi, ryad))
            z = r.setdefault(d['video'], {})
            z.update({'perehliady_spravzhni': d.get('engagedViews'), 'serednii_chas_s': d.get('averageViewDuration'),
                      'chastka_perehliadu': round(d['averageViewPercentage'] / 100, 4)
                      if d.get('averageViewPercentage') is not None else None, 'poshyrennia': d.get('shares')})
        for r_ in ryadky:                                            # утримання на 3 с — крива по одному ролику
            dovzh = chyslo(r_.get('dovzhyna_s'))
            if not r_['zovnishnii_id'] or not dovzh or dovzh <= 3:
                continue
            q = urllib.parse.urlencode({'ids': 'channel==MINE', 'startDate': r_['opublikovano'][:10],
                                        'endDate': sohodni.isoformat(), 'metrics': 'audienceWatchRatio',
                                        'dimensions': 'elapsedVideoTimeRatio', 'filters': f'video=={r_["zovnishnii_id"]}'})
            kryva = self._get(f'https://youtubeanalytics.googleapis.com/v2/reports?{q}', t).get('rows', [])
            tochka = next((ryad for ryad in kryva if ryad[0] >= 3 / dovzh), None)
            if tochka:
                r.setdefault(r_['zovnishnii_id'], {})['utrymannia_3s'] = round(min(tochka[1], 1.0), 4)
        return r


def _meta_znachennia(dani: list[dict]) -> dict:
    """[{name, values: [{value}]} або {name, total_value: {value}}] → {name: value}."""
    r = {}
    for d in dani:
        if 'total_value' in d:
            r[d['name']] = (d['total_value'] or {}).get('value')
        elif d.get('values'):
            r[d['name']] = d['values'][-1].get('value')
    return r


class MetaZbirach(Zbirach):
    def __init__(self, http_=None):
        super().__init__(http_)
        self.token = M.zminna('MV_META_PAGE_TOKEN')
        self.baza = f'https://graph.facebook.com/{os.environ.get("MV_META_VERSIA", "v27.0")}'

    def _get(self, shliakh: str, polia: dict) -> dict:
        q = urllib.parse.urlencode({**polia, 'access_token': self.token})
        v = self.http('GET', f'{self.baza}/{shliakh}?{q}')
        if v.status != 200:
            raise RuntimeError(M._meta_pomylka(v, self.token).pomylka)
        return v.json()


class InstagramZamiry(MetaZbirach):
    """`GET /{ig-media-id}/insights`: перегляди, охоплення, лайки, коментарі, поширення, збереження, середній час Reels.
    Кривої утримання й джерел трафіку Instagram не дає (розд. 4.1)."""
    METRYKY = 'views,reach,likes,comments,shares,saved,ig_reels_avg_watch_time'
    PROSTI = 'views,likes,comments,shares,saved'        # якщо Instagram не знає якоїсь метрики (змінює їх часто)

    def zibraty(self, ryadky: list[dict], sohodni: date) -> dict[str, dict]:
        r = {}
        for x in ryadky:
            if not x['zovnishnii_id']:
                continue
            try:
                d = _meta_znachennia(self._get(f'{x["zovnishnii_id"]}/insights', {'metric': self.METRYKY}).get('data', []))
            except RuntimeError:
                d = _meta_znachennia(self._get(f'{x["zovnishnii_id"]}/insights', {'metric': self.PROSTI}).get('data', []))
            chas = chyslo(d.get('ig_reels_avg_watch_time'))
            r[x['zovnishnii_id']] = {'perehliady': d.get('views'), 'lajky': d.get('likes'), 'komentari': d.get('comments'),
                                     'poshyrennia': d.get('shares'), 'zberezhennia': d.get('saved'),
                                     'serednii_chas_s': round(chas / 1000, 2) if chas is not None else None}
        return r


class FacebookZamiry(MetaZbirach):
    """`GET /{video-id}/video_insights` для Reels сторінки: відтворення, середній час (мс), дії (коментарі, поширення),
    реакції. Право `read_insights` на сторінку. Назви метрик Reels — за документацією, на живій сторінці не перевірено."""
    METRYKY = 'blue_reels_play_count,post_video_avg_time_watched,post_video_social_actions,post_video_likes_by_reaction_type'

    def zibraty(self, ryadky: list[dict], sohodni: date) -> dict[str, dict]:
        r = {}
        for x in ryadky:
            if not x['zovnishnii_id']:
                continue
            d = _meta_znachennia(self._get(f'{x["zovnishnii_id"]}/video_insights', {'metric': self.METRYKY}).get('data', []))
            dii = d.get('post_video_social_actions') or {}
            reaktsii = d.get('post_video_likes_by_reaction_type') or {}
            chas = chyslo(d.get('post_video_avg_time_watched'))
            r[x['zovnishnii_id']] = {
                'perehliady': d.get('blue_reels_play_count'),
                'lajky': sum(v for v in reaktsii.values() if isinstance(v, (int, float))) if reaktsii else None,
                'komentari': dii.get('COMMENT') if isinstance(dii, dict) else None,
                'poshyrennia': dii.get('SHARE') if isinstance(dii, dict) else None,
                'serednii_chas_s': round(chas / 1000, 2) if chas is not None else None}
        return r


ZBIRACHI = {'youtube': YouTubeZamiry, 'instagram': InstagramZamiry, 'facebook': FacebookZamiry}


# ==================================================================== TikTok — вивантаження Studio
# Назви колонок вивантаження TikTok Studio не перевірено (розд. 4.1, 6) — розпізнаємо за кількома варіантами
# англійською й українською; ідентифікуємо ролик за посиланням (/video/<число>) або колонкою «id» (наш id, вписаний руками).
KOLONKY_TIKTOK = {
    'posylannia': ('video link', 'link', 'url', 'посилання', 'посилання на відео'),
    'video_id': ('video id', 'post id', 'id відео'),
    'id': ('id', 'наш id'),
    'perehliady': ('video views', 'views', 'total views', 'total play', 'plays', 'перегляди', 'перегляди відео'),
    'lajky': ('likes', 'total likes', 'вподобання', 'лайки'),
    'komentari': ('comments', 'total comments', 'коментарі'),
    'poshyrennia': ('shares', 'total shares', 'поширення'),
    'zberezhennia': ('saves', 'favorites', 'add to favorites', 'збереження', 'додано в обране'),
    'serednii_chas_s': ('average watch time', 'avg. watch time', 'average time watched', 'середній час перегляду'),
    'chastka_perehliadu': ('watched full video', 'full video watch rate', 'переглянули повністю', 'повний перегляд'),
    'dlia_tebe': ('for you', 'for you page', 'для тебе', 'для вас'),
}


def _chyslo_tiktok(v: str, chastka: bool = False) -> float | None:
    t = str(v or '').strip().replace(' ', '').replace(' ', '')
    if not t:
        return None
    vidsotok = t.endswith('%')
    t = t.rstrip('%sс').replace(',', '.')
    mnozh = 1
    if t[-1:].upper() in ('K', 'M'):
        mnozh, t = (1000 if t[-1].upper() == 'K' else 1_000_000), t[:-1]
    try:
        x = float(t) * mnozh
    except ValueError:
        return None
    if chastka and (vidsotok or x > 1):
        x /= 100
    return round(x, 4)


def tiktok_import(teka: Path, reiestr_: list[dict], sohodni: date) -> tuple[list[dict], list[str]]:
    """CSV з `zamiry/tiktok/` → знімки TikTok. Дата знімка — з назви файлу (РРРР-ММ-ДД), інакше сьогодні."""
    tt = [r for r in reiestr_ if r['merezha'] == 'tiktok']
    za_video = {CR.VIDEO_ID_TIKTOK.search(r['url'])[1]: r for r in tt if CR.VIDEO_ID_TIKTOK.search(r['url'] or '')}
    za_video.update({r['zovnishnii_id']: r for r in tt if r['zovnishnii_id']})
    za_id = {r['id']: r for r in tt}
    znimky, zauvazhennia = [], []
    for f in sorted(Path(teka).glob('*.csv')) if Path(teka).is_dir() else []:
        m = re.search(r'(\d{4}-\d{2}-\d{2})', f.name)
        data = m[1] if m else sohodni.isoformat()
        tekst = f.read_text(encoding='utf-8-sig', errors='replace')
        try:
            dialekt = csv.Sniffer().sniff(tekst.splitlines()[0] if tekst else ',', delimiters=',;\t')
        except csv.Error:
            dialekt = csv.excel
        ryadky = list(csv.DictReader(io.StringIO(tekst), dialect=dialekt))
        if not ryadky:
            zauvazhennia.append(f'{f.name}: порожній')
            continue
        nazvy = {k: (k or '').strip().lower() for k in ryadky[0]}
        kol = {nashe: next((k for k, n in nazvy.items() if n in varianty), None)
               for nashe, varianty in KOLONKY_TIKTOK.items()}
        if not kol['perehliady']:
            zauvazhennia.append(f'{f.name}: не знайшов колонки переглядів (є: {", ".join(nazvy.values())})')
            continue
        for ryad in ryadky:
            r = None
            if kol['id'] and (ryad.get(kol['id']) or '').strip() in za_id:
                r = za_id[ryad[kol['id']].strip()]
            for k in ('video_id', 'posylannia'):
                if not r and kol[k]:
                    mm = re.search(r'(\d{6,})', ryad.get(kol[k]) or '')
                    r = za_video.get(mm[1]) if mm else None
            if not r:
                zauvazhennia.append(f'{f.name}: рядок без відповідного ролика в реєстрі '
                                    f'({(ryad.get(kol["posylannia"]) if kol["posylannia"] else "") or "без посилання"})')
                continue
            z = {'data': data, 'id': r['id'], 'typ': r['typ'], 'merezha': 'tiktok'}
            for pole in ('perehliady', 'lajky', 'komentari', 'poshyrennia', 'zberezhennia', 'serednii_chas_s'):
                z[pole] = _chyslo_tiktok(ryad.get(kol[pole])) if kol[pole] else None
            for pole in ('chastka_perehliadu', 'dlia_tebe'):
                z[pole] = _chyslo_tiktok(ryad.get(kol[pole]), chastka=True) if kol[pole] else None
            znimky.append(z)
    return znimky, zauvazhennia


# ==================================================================== 3. дії на сайті з міткою
def dii_na_saiti(reiestr_: list[dict], http_=None) -> tuple[dict, str]:
    """{мітка: (події, заявки)} з вивантаження форм сайту. Без адреси сайту чи ключа — порожньо й пояснення."""
    sait, kluch = os.environ.get('MV_ADRESA_SAITU', '').rstrip('/'), os.environ.get('MV_ADMIN_KLIUCH', '')
    if not sait or not kluch:
        return {}, 'дії на сайті не зібрано: немає MV_ADRESA_SAITU або MV_ADMIN_KLIUCH'
    http_ = http_ or M.http
    mitky = {r['mitka'] for r in reiestr_}
    r = {m: [0, 0] for m in mitky}

    def tablytsia(imia):
        v = http_('GET', f'{sait}/api/admin/vyvantazhennia/{imia}', {'Authorization': f'Bearer {kluch}'})
        if v.status != 200:
            raise RuntimeError(f'вивантаження {imia}: {v.status}')
        return list(csv.DictReader(io.StringIO(v.tilo.decode('utf-8-sig'))))

    def chyia(kanal: str) -> str | None:
        k = (kanal or '').strip().lower()
        return next((m for m in mitky if k == m or k.endswith('-' + m)), None)

    try:
        for ryad in tablytsia('podiya'):
            m = chyia(ryad.get('kanal'))
            if m:
                r[m][0] += int(chyslo(ryad.get('n')) or 1)
        for ryad in tablytsia('skoro'):
            m = chyia(ryad.get('kanal'))
            if m:
                r[m][1] += 1
    except (RuntimeError, OSError) as e:
        return {}, f'дії на сайті не зібрано: {M.bez_sekretiv(str(e), kluch)}'
    return r, ''


# ==================================================================== щодня
def zibraty(cherha: Path, zamiry: Path, sohodni: date, z_merezh: bool = True, http_=None) -> list[str]:
    zvit = []
    reiestr_ = reiestr(cherha)
    pysaty_csv(zamiry / 'rolyky.csv', REIESTR, reiestr_)
    zvit.append(f'реєстр: {len(reiestr_)} публікацій')
    znimky = {(z['data'], z['id'], z['merezha']): z for z in chytaty_csv(zamiry / 'znimky.csv')}
    vid = (sohodni - timedelta(days=DNIV_ZBIRATY)).isoformat()
    svizhi = [r for r in reiestr_ if r['opublikovano'][:10] >= vid]
    dii, chomu = dii_na_saiti(svizhi, http_) if z_merezh else ({}, 'дії на сайті — без мережі')
    if chomu:
        zvit.append(chomu)
    for m in MEREZHI_API:
        rr = [r for r in svizhi if r['merezha'] == m]
        if not rr or not z_merezh:
            continue
        try:
            chysla = ZBIRACHI[m](http_).zibraty(rr, sohodni)
        except M.NeNalashtovano as e:
            zvit.append(f'{NAZVY[m]}: не налаштовано ({e})')
            continue
        except (RuntimeError, OSError, KeyError, ValueError) as e:
            zvit.append(f'{NAZVY[m]}: не зібрано — {e}')
            continue
        n = 0
        for r in rr:
            z = {'data': sohodni.isoformat(), 'id': r['id'], 'typ': r['typ'], 'merezha': m,
                 **chysla.get(r['zovnishnii_id'], {})}
            if r['mitka'] in dii:
                z['perekhody'], z['zaiavky'] = dii[r['mitka']]
            znimky[(z['data'], z['id'], m)] = z
            n += 1
        zvit.append(f'{NAZVY[m]}: знімків {n}')
    tt, zauv = tiktok_import(zamiry / 'tiktok', reiestr_, sohodni)
    for z in tt:
        r = next((x for x in reiestr_ if x['id'] == z['id'] and x['merezha'] == 'tiktok'), None)
        if r and r['mitka'] in dii and z['data'] == sohodni.isoformat():
            z['perekhody'], z['zaiavky'] = dii[r['mitka']]
        znimky[(z['data'], z['id'], 'tiktok')] = {**znimky.get((z['data'], z['id'], 'tiktok'), {}), **z}
    for r in reiestr_:          # TikTok і Telegram без вивантаження — хоч дії на сайті щодня
        if r['merezha'] in MEREZHI_API or r['mitka'] not in dii or r['opublikovano'][:10] < vid:
            continue
        k = (sohodni.isoformat(), r['id'], r['merezha'])
        z = znimky.setdefault(k, {'data': k[0], 'id': r['id'], 'typ': r['typ'], 'merezha': r['merezha']})
        z['perekhody'], z['zaiavky'] = dii[r['mitka']]
    if tt or zauv:
        zvit.append(f'TikTok: знімків з вивантаження {len(tt)}' + (f'; {len(zauv)} зауважень' if zauv else ''))
        zvit += [f'  {z}' for z in zauv[:20]]
    pysaty_csv(zamiry / 'znimky.csv', ZNIMKY, sorted(znimky.values(), key=lambda z: (z['data'], z['merezha'], z['id'])))
    return zvit


# ==================================================================== 4. тижневий підсумок
def mediana(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def na_den(znimky: list[dict], opublikovano: str, den: int = DEN_PORIVNIANNIA) -> dict | None:
    """Знімок на `den`-й день після публікації: останній не пізніше; якщо перший знімок пізніший (TikTok раз на
    тиждень) — найраніший. Так молоді й старі ролики порівнюються чесніше, ніж «за весь час»."""
    if not znimky:
        return None
    mezha = (date.fromisoformat(opublikovano[:10]) + timedelta(days=den)).isoformat()
    z = sorted(znimky, key=lambda x: x['data'])
    do = [x for x in z if x['data'] <= mezha]
    return do[-1] if do else z[0]


def hachok(varianty: str) -> str:
    m = re.search(r'гачок\s*([АБВABV])', varianty or '', re.I)
    return {'A': 'А', 'B': 'Б', 'V': 'В'}.get(m[1].upper(), m[1].upper()) if m else ''


def rishennia(rr: list[dict], akaunt: dict, ihra: bool, produkt: bool) -> tuple[str, str]:
    """Позначка й чому — правила `docs/ROLYKY-SYSTEMA.md`, розд. 4.4. rr — публікації типу в часі (старі → нові)."""
    n = len(rr)
    if n < MIN_PUBLIKATSII:
        return 'чекати', f'мало даних: {n} з {MIN_PUBLIKATSII} публікацій'
    if ihra:
        k_typu = mediana([r['kom_1000'] for r in rr])
        k_akk = akaunt['kom_1000']
        if k_typu is None or not k_akk:
            return 'тримати', 'гра: немає коментарів для порівняння'
        if k_typu >= POSYLYTY_MEDIANA * k_akk:
            return 'посилити', f'гра: коментарів на 1 000 {k_typu:.1f} ≥ 2× акаунта ({k_akk:.1f})'
        nyzhche = sum(1 for r in rr[-PRYBRATY_OSTANNI:] if r['kom_1000'] is not None and r['kom_1000'] < k_akk)
        if nyzhche >= PRYBRATY_Z:
            return 'прибрати', f'гра: коментарів менше за акаунт у {nyzhche} з {min(n, PRYBRATY_OSTANNI)} останніх'
        return 'тримати', f'гра: коментарів на 1 000 {k_typu:.1f} проти {k_akk:.1f} в акаунті'
    med, akk = mediana([r['perehliady'] for r in rr]), akaunt['perehliady']
    if med is None or not akk:
        return 'тримати', 'немає переглядів для порівняння'
    naikrashchyi = max(rr, key=lambda r: r['perehliady'] or 0)
    if med >= POSYLYTY_MEDIANA * akk:
        return 'посилити', f'медіана переглядів {med:.0f} ≥ 2× акаунта ({akk:.0f})'
    if (naikrashchyi['perehliady'] or 0) >= POSYLYTY_ODYN * akk:
        return 'посилити', (f'ролик {naikrashchyi["id"]} ≥ 3× медіани акаунта — 3 наступні на його шаблоні '
                            f'({naikrashchyi["perehliady"]:.0f} проти {akk:.0f})')
    pole = 'utrymannia_3s' if any(r['utrymannia_3s'] is not None for r in rr) and akaunt['utrymannia_3s'] \
        else 'chastka_perehliadu'
    akk_u = akaunt[pole]
    ostanni = rr[-PRYBRATY_OSTANNI:]
    if akk_u:
        nyzhche = sum(1 for r in ostanni if (r['perehliady'] or 0) < akk and r[pole] is not None and r[pole] < akk_u)
        if nyzhche >= PRYBRATY_Z:
            shcho = 'утримання на 3 с' if pole == 'utrymannia_3s' else 'частка перегляду (утримання на 3 с немає)'
            return 'прибрати', f'перегляди й {shcho} нижче за акаунт у {nyzhche} з {len(ostanni)} останніх'
    if produkt and med >= akk and sum(r['perekhody'] or 0 for r in rr) == 0:
        return 'тримати', 'продуктовий: перегляди є, дій на сайті немає — міняти кінцівку, а не ролик'
    return 'тримати', f'медіана переглядів {med:.0f} проти {akk:.0f} в акаунті' + (
        '' if akk_u else '; утримання немає — «прибрати» не судимо')


def pidsumok(zamiry: Path, sohodni: date, reiestr_typiv: dict | None = None) -> tuple[Path, str]:
    """Markdown для центрального чату: по кожній мережі — таблиця типів з позначками, гачки, що не так з даними."""
    reiestr_typiv = reiestr_typiv if reiestr_typiv is not None else CR.typy()
    reiestr_ = chytaty_csv(zamiry / 'rolyky.csv')
    znimky = chytaty_csv(zamiry / 'znimky.csv')
    pn = sohodni - timedelta(days=sohodni.weekday())
    ch = [f'# Ролики — підсумок тижня до {pn.strftime("%d.%m.%Y")}', '',
          f'Зібрано {sohodni.strftime("%d.%m.%Y")} з `zamiry/rolyky.csv` і `zamiry/znimky.csv`. Правила позначок — '
          '`docs/ROLYKY-SYSTEMA.md`, розд. 4.4: тип судимо після 5 публікацій, порівнюємо з медіаною свого акаунта; '
          f'перегляди — на {DEN_PORIVNIANNIA}-й день після публікації (молодші — останні). Пороги — наші, не з досліджень.', '']
    poza = sorted({r['typ'] for r in reiestr_} - set(reiestr_typiv))
    if poza:
        ch += [f'> Типи не з реєстру `docs/ROLYKY-TYPY.md`: {", ".join(f"«{t}»" for t in poza)} — перевірити назви.', '']
    tyzhden = [r for r in reiestr_ if pn - timedelta(days=7) <= date.fromisoformat(r['opublikovano'][:10]) < pn]
    ch += [f'Минулого тижня вийшло роликів: {len({r["id"] for r in tyzhden})}, публікацій: {len(tyzhden)}.', '']
    ye_chysla = False
    for m in ('tiktok', 'youtube', 'instagram', 'facebook', 'telegram'):
        rr = []
        for r in (x for x in reiestr_ if x['merezha'] == m):
            z = na_den([s for s in znimky if s['id'] == r['id'] and s['merezha'] == m], r['opublikovano'])
            if not z:
                continue
            p = chyslo(z.get('perehliady'))
            k = chyslo(z.get('komentari'))
            rr.append({'id': r['id'], 'typ': r['typ'], 'opublikovano': r['opublikovano'], 'hachok': hachok(r['varianty']),
                       'perehliady': p, 'kom_1000': (k / p * 1000) if p and k is not None else None,
                       'utrymannia_3s': chyslo(z.get('utrymannia_3s')),
                       'chastka_perehliadu': chyslo(z.get('chastka_perehliadu')),
                       'perekhody': chyslo(z.get('perekhody')), 'zaiavky': chyslo(z.get('zaiavky'))})
        if not rr:
            continue
        ye_chysla = True
        rr.sort(key=lambda r: r['opublikovano'])
        akaunt = {k: mediana([r[k] for r in rr]) for k in ('perehliady', 'kom_1000', 'utrymannia_3s', 'chastka_perehliadu')}
        ch += [f'## {NAZVY[m]}', '',
               f'Роликів з числами: {len(rr)}. Медіана акаунта: переглядів {_f(akaunt["perehliady"], 0)}, '
               f'утримання на 3 с {_v(akaunt["utrymannia_3s"])}, частка перегляду {_v(akaunt["chastka_perehliadu"])}, '
               f'коментарів на 1 000 {_f(akaunt["kom_1000"], 1)}.', '',
               '| Тип | Публікацій | Медіана переглядів | Утримання 3 с | Частка перегляду | Коментарів на 1 000 '
               '| Дії на сайті | Позначка | Чому |', '|---|---|---|---|---|---|---|---|---|']
        typy_ = sorted({r['typ'] for r in rr}, key=lambda t: -(mediana([r['perehliady'] for r in rr if r['typ'] == t]) or 0))
        for t in typy_:
            tr = [r for r in rr if r['typ'] == t]
            ihra = 'гра' in (reiestr_typiv.get(t, {}).get('format', ''))
            poz, chomu = rishennia(tr, akaunt, ihra, t in PRODUKTOVI)
            dii = sum(r['perekhody'] or 0 for r in tr) + sum(r['zaiavky'] or 0 for r in tr)
            ch.append(f'| {t} | {len(tr)} | {_f(mediana([r["perehliady"] for r in tr]), 0)} '
                      f'| {_v(mediana([r["utrymannia_3s"] for r in tr]))} | {_v(mediana([r["chastka_perehliadu"] for r in tr]))} '
                      f'| {_f(mediana([r["kom_1000"] for r in tr]), 1)} | {dii:.0f} | **{poz}** | {chomu} |')
        hachky = []
        for t in typy_:
            hr = {}
            for r in rr:
                if r['typ'] == t and r['hachok'] and r['utrymannia_3s'] is not None:
                    hr.setdefault(r['hachok'], []).append(r['utrymannia_3s'])
            if len(hr) >= 2:
                med = {h: mediana(v) for h, v in hr.items()}
                kr = max(med, key=med.get)
                riznytsia = med[kr] - min(med.values())
                hachky.append(f'- {t}: ' + ', '.join(f'{h} {_v(v)} ({len(hr[h])})' for h, v in sorted(med.items()))
                              + (f' — різниця {riznytsia * 100:.0f} п., випадковість' if riznytsia < HACHOK_VYPADKOVIST
                                 else f' — кращий гачок {kr}'))
        if hachky:
            ch += ['', 'Гачки (утримання на 3 с; менше 5 пунктів різниці — випадковість):', ''] + hachky
        ch.append('')
    if not ye_chysla:
        ch += ['Чисел ще немає: ролики не виходили або мережі не налаштовано.', '']
    ch += ['## Що не перевірено', '',
           '- Справжні відповіді мереж: запити й розбір — за документацією, на штучних відповідях у тестах.',
           '- Колонки вивантаження TikTok Studio — розпізнаємо за назвами; якщо файл не прочитався, це видно в журналі збору.',
           '- «Дії на сайті» — події сторінок і заявки з міткою ролика, не відвідування.', '']
    f = zamiry / f'tyzhden-{pn.isoformat()}.md'
    f.write_text('\n'.join(ch), encoding='utf-8')
    return f, '\n'.join(ch)


def _f(x, znakiv: int) -> str:
    return '—' if x is None else f'{x:.{znakiv}f}'


def _v(x) -> str:
    return '—' if x is None else f'{x * 100:.0f} %'


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Заміри роликів: щоденний збір і тижневий підсумок.')
    p.add_argument('--cherha', type=Path, required=True, help='cherha.db автопостингу (гілка avtopostynh-stan)')
    p.add_argument('--zamiry', type=Path, required=True, help='тека zamiry/ приватного репозиторію')
    p.add_argument('--data', help='«сьогодні» за Києвом (для перевірки), РРРР-ММ-ДД')
    p.add_argument('--pidsumok', action='store_true', help='тижневий підсумок не лише в понеділок')
    p.add_argument('--bez-merezh', action='store_true', help='лише реєстр, TikTok і підсумок — без запитів до мереж')
    a = p.parse_args(argv)
    sohodni = date.fromisoformat(a.data) if a.data else datetime.now(timezone.utc).astimezone(KYIV).date()
    zvit = zibraty(a.cherha, a.zamiry, sohodni, not a.bez_merezh)
    md = ''
    if a.pidsumok or sohodni.weekday() == DEN_PIDSUMKU:
        f, md = pidsumok(a.zamiry, sohodni)
        zvit.append(f'підсумок: {f}')
    for x in zvit:
        print(x)
    s = os.environ.get('GITHUB_STEP_SUMMARY')
    if s:
        with open(s, 'a', encoding='utf-8') as h:
            h.write('```\n' + '\n'.join(zvit) + '\n```\n\n' + md + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

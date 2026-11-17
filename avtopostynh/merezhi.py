"""Перехідники мереж: опублікувати й видалити (ZAVDANNYA-107, п. 2).

Telegram — повністю. YouTube, Facebook, Instagram, TikTok — за офіційними інтерфейсами, вмикаються змінною
`MV_MEREZHI` (через кому), коли партнер отримає дозволи. Умови перевірено 17.11.2026 — `docs/AVTOPOSTYNH.md`, розд. 3.
Без сторонніх бібліотек (urllib). Ключі й токени — лише змінні середовища; у журнал і помилки токен не потрапляє.

Пробний режим (`Probna`) нічого не надсилає: кладе кожен «допис» у теку `opublikovano/<мережа>/<канал>/`.

Кожен виклик повертає `Rezultat`. Тип помилки керує чергою:
  tymchasova  — повторити пізніше (мережа впала, ліміт, 429);
  odynytsia   — саме ця одиниця не підходить мережі (повторювати марно);
  blokuvannia — мережа нас не пускає (токен відкликано, бота вигнали, акаунт обмежено): зупинити всю мережу.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Rezultat:
    ok: bool
    id: str = ''
    url: str = ''
    pomylka: str = ''
    typ: str = ''            # tymchasova | odynytsia | blokuvannia | ne_vmiie (видалення)
    chekaty_s: int = 0


class Vidpovid:
    def __init__(self, status: int, zaholovky: dict, tilo: bytes):
        self.status, self.zaholovky, self.tilo = status, {k.lower(): v for k, v in zaholovky.items()}, tilo

    def json(self) -> dict:
        try:
            return json.loads(self.tilo.decode('utf-8') or '{}')
        except ValueError:
            return {}


def http(metod: str, url: str, zaholovky: dict | None = None, tilo: bytes | None = None, chas: int = 120) -> Vidpovid:
    """Один запит. Замінюється в тестах."""
    z = urllib.request.Request(url, data=tilo, method=metod, headers=zaholovky or {})
    try:
        with urllib.request.urlopen(z, timeout=chas) as v:
            return Vidpovid(v.status, dict(v.headers), v.read())
    except urllib.error.HTTPError as e:
        return Vidpovid(e.code, dict(e.headers or {}), e.read() or b'')
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return Vidpovid(0, {}, json.dumps({'merezha_nedostupna': type(e).__name__}).encode())


def multipart(polia: dict, faily: dict) -> tuple[bytes, str]:
    mezha = uuid.uuid4().hex
    ch = []
    for k, v in polia.items():
        ch.append(f'--{mezha}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, f in faily.items():
        f = Path(f)
        typ = mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
        ch.append(f'--{mezha}\r\nContent-Disposition: form-data; name="{k}"; filename="{f.name}"\r\n'
                  f'Content-Type: {typ}\r\n\r\n'.encode() + f.read_bytes() + b'\r\n')
    ch.append(f'--{mezha}--\r\n'.encode())
    return b''.join(ch), f'multipart/form-data; boundary={mezha}'


def bez_sekretiv(t: str, *sekrety: str) -> str:
    for s in sekrety:
        if s:
            t = t.replace(s, '***')
    return t[:500]


def merezha_vpala(v: Vidpovid) -> bool:
    return v.status == 0 or v.status >= 500


class Merezha:
    imia = ''
    vydaliaie = True

    def __init__(self, http_=None, teka_media: Path | None = None, spaty=time.sleep):
        self.http = http_ or http
        self.teka_media = Path(teka_media) if teka_media else None
        self.spaty = spaty

    def fail(self, o: dict) -> Path:
        return self.teka_media / o['fail']

    def opublikuvaty(self, o: dict) -> Rezultat:
        raise NotImplementedError

    def vydalyty(self, o: dict) -> Rezultat:
        return Rezultat(False, pomylka='мережа не дає видалити через інтерфейс', typ='ne_vmiie')


def zminna(imia: str) -> str:
    v = os.environ.get(imia, '').strip()
    if not v:
        raise NeNalashtovano(f'не задано змінну середовища {imia}')
    return v


class NeNalashtovano(Exception):
    pass


# ==================================================================== пробний режим
class Probna(Merezha):
    """Нічого не надсилає: «публікує» у теку."""

    def __init__(self, imia: str, teka: Path, teka_media: Path | None = None):
        super().__init__(teka_media=teka_media)
        self.imia, self.teka = imia, Path(teka)

    def opublikuvaty(self, o: dict) -> Rezultat:
        d = self.teka / 'opublikovano' / o['merezha'] / (o.get('kanal_slug') or o.get('kanal') or 'osnovnyi')
        d.mkdir(parents=True, exist_ok=True)
        (d / f'{o["id"]}.json').write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding='utf-8')
        if o.get('fail') and self.teka_media and self.fail(o).is_file():
            shutil.copy2(self.fail(o), d / f'{o["id"]}{self.fail(o).suffix}')
        return Rezultat(True, id=f'probnyi-{o["id"]}', url=(d / f'{o["id"]}.json').resolve().as_uri())

    def vydalyty(self, o: dict) -> Rezultat:
        d = self.teka / 'opublikovano' / o['merezha'] / (o.get('kanal_slug') or o.get('kanal') or 'osnovnyi')
        for f in d.glob(f'{o["id"]}.*'):
            f.unlink()
        return Rezultat(True)


# ==================================================================== Telegram
class Telegram(Merezha):
    """Bot API: бот — адміністратор кожного районного каналу з правами «публікувати» й «видаляти».
    Змінні: MV_TELEGRAM_TOKEN; канали — файл `kanaly.json` (район → @канал або числовий id, не секрет)."""
    imia = 'telegram'

    def __init__(self, kanaly: dict, **k):
        super().__init__(**k)
        self.token = zminna('MV_TELEGRAM_TOKEN')
        self.kanaly = kanaly

    def _vyklyk(self, metod: str, polia: dict, fail: Path | None = None, pole_failu: str = '') -> tuple[Vidpovid, dict]:
        url = f'https://api.telegram.org/bot{self.token}/{metod}'
        if fail:
            prosti = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in polia.items()}
            tilo, typ = multipart(prosti, {pole_failu: fail})
        else:
            tilo, typ = json.dumps(polia, ensure_ascii=False).encode(), 'application/json'
        v = self.http('POST', url, {'Content-Type': typ}, tilo)
        return v, v.json()

    def _pomylka(self, v: Vidpovid, j: dict) -> Rezultat:
        opys = bez_sekretiv(str(j.get('description') or j or v.status), self.token)
        kod = j.get('error_code', v.status)
        if merezha_vpala(v):
            return Rezultat(False, pomylka=f'мережа недоступна: {opys}', typ='tymchasova')
        if kod == 429:
            return Rezultat(False, pomylka=opys, typ='tymchasova',
                            chekaty_s=int((j.get('parameters') or {}).get('retry_after', 60)))
        if kod in (401, 403) or re.search(r'kicked|not enough rights|not a member|have no rights', opys, re.I):
            return Rezultat(False, pomylka=opys, typ='blokuvannia')
        if kod == 400 and re.search(r'chat not found', opys, re.I):
            return Rezultat(False, pomylka=opys, typ='blokuvannia')
        return Rezultat(False, pomylka=opys, typ='odynytsia' if kod == 400 else 'tymchasova')

    @staticmethod
    def _knopky(o: dict) -> dict | None:
        k = [b for b in o.get('knopky') or [] if b.get('url')]
        return {'inline_keyboard': [[{'text': b['tekst'], 'url': b['url']}] for b in k]} if k else None

    def opublikuvaty(self, o: dict) -> Rezultat:
        chat = self.kanaly.get(o.get('kanal', ''))
        if not chat:
            return Rezultat(False, pomylka=f'немає каналу для «{o.get("kanal")}» у kanaly.json', typ='odynytsia')
        rozm = self._knopky(o)
        dod = {'reply_markup': rozm} if rozm else {}
        if o['typ'] == 'vikteryna':
            v, j = self._vyklyk('sendPoll', {'chat_id': chat, 'question': o['pytannia'],
                                             'options': [{'text': x} for x in o['varianty']], 'type': 'quiz',
                                             'correct_option_id': o['pravylna'], 'explanation': o.get('poiasnennia', ''),
                                             'is_anonymous': True, **dod})
        elif o.get('fail'):
            metod, pole = ('sendVideo', 'video') if o['typ'] == 'rolyk' else ('sendPhoto', 'photo')
            v, j = self._vyklyk(metod, {'chat_id': chat, 'caption': o['tekst'], **dod}, self.fail(o), pole)
        else:
            v, j = self._vyklyk('sendMessage', {'chat_id': chat, 'text': o['tekst'],
                                                'link_preview_options': {'is_disabled': True}, **dod})
        if not j.get('ok'):
            return self._pomylka(v, j)
        m = j['result']
        id_ = str(m['message_id'])
        imia = (m.get('chat') or {}).get('username') or str(chat).lstrip('@')
        return Rezultat(True, id=id_, url=f'https://t.me/{imia}/{id_}' if not imia.lstrip('-').isdigit() else '')

    def vydalyty(self, o: dict) -> Rezultat:
        chat = self.kanaly.get(o.get('kanal', ''))
        v, j = self._vyklyk('deleteMessage', {'chat_id': chat, 'message_id': int(o['zovnishnii_id'])})
        if j.get('ok'):
            return Rezultat(True)
        r = self._pomylka(v, j)
        if r.typ != 'tymchasova':          # 48 год минуло або немає права видаляти — лише вручну
            r.typ = 'ne_vmiie'
        return r


# ==================================================================== спільне для Meta
def _meta_pomylka(v: Vidpovid, *sekrety) -> Rezultat:
    e = v.json().get('error') or {}
    opys = bez_sekretiv(f'{e.get("code", v.status)}: {e.get("message", v.tilo[:200])}', *sekrety)
    kod, pidkod = e.get('code'), e.get('error_subcode')
    if merezha_vpala(v) or e.get('is_transient'):
        return Rezultat(False, pomylka=opys, typ='tymchasova')
    if kod in (4, 17, 32, 613, 80001) or v.status == 429:
        return Rezultat(False, pomylka=opys, typ='tymchasova', chekaty_s=3600)
    if kod in (190, 200, 10, 368) or pidkod in (2207050,) or v.status in (401, 403):
        return Rezultat(False, pomylka=opys, typ='blokuvannia')
    return Rezultat(False, pomylka=opys, typ='odynytsia')


def publichna_adresa(o: dict) -> str:
    """Instagram і TikTok забирають файл самі за публічною адресою (MV_MEDIA_URL — тека пачок на сервері)."""
    return zminna('MV_MEDIA_URL').rstrip('/') + '/' + urllib.parse.quote(o['fail'])


# ==================================================================== Facebook
class Facebook(Merezha):
    """Сторінка Facebook: Reels (`/{page}/video_reels`, 3 кроки), картка (`/{page}/photos`), текст (`/{page}/feed`).
    Змінні: MV_META_PAGE_ID, MV_META_PAGE_TOKEN (токен сторінки), MV_META_VERSIA (типово v27.0).
    Видалення: DELETE /{id}; документація Meta суперечлива — якщо не вийде, «прибрати вручну»."""
    imia = 'facebook'

    def __init__(self, **k):
        super().__init__(**k)
        self.page, self.token = zminna('MV_META_PAGE_ID'), zminna('MV_META_PAGE_TOKEN')
        self.baza = f'https://graph.facebook.com/{os.environ.get("MV_META_VERSIA", "v27.0")}'

    def _post(self, shliakh: str, polia: dict) -> Vidpovid:
        tilo = urllib.parse.urlencode({**polia, 'access_token': self.token}).encode()
        return self.http('POST', f'{self.baza}/{shliakh}', {'Content-Type': 'application/x-www-form-urlencoded'}, tilo)

    def opublikuvaty(self, o: dict) -> Rezultat:
        if o['typ'] == 'rolyk':
            v = self._post(f'{self.page}/video_reels', {'upload_phase': 'start'})
            if v.status != 200:
                return _meta_pomylka(v, self.token)
            vid = v.json()['video_id']
            dani = self.fail(o).read_bytes()
            v = self.http('POST', f'https://rupload.facebook.com/video-upload/{self.baza.rsplit("/", 1)[1]}/{vid}',
                          {'Authorization': f'OAuth {self.token}', 'offset': '0', 'file_size': str(len(dani))}, dani)
            if v.status != 200:
                return _meta_pomylka(v, self.token)
            v = self._post(f'{self.page}/video_reels', {'upload_phase': 'finish', 'video_id': vid,
                                                        'video_state': 'PUBLISHED', 'description': o['tekst']})
            if v.status != 200 or not v.json().get('success'):
                return _meta_pomylka(v, self.token)
            return Rezultat(True, id=vid, url=f'https://www.facebook.com/reel/{vid}')
        if o['typ'] == 'kartka':
            tilo, typ = multipart({'message': o['tekst'], 'access_token': self.token}, {'source': self.fail(o)})
            v = self.http('POST', f'{self.baza}/{self.page}/photos', {'Content-Type': typ}, tilo)
        else:
            v = self._post(f'{self.page}/feed', {'message': o['tekst'], 'link': o.get('posylannia', '')})
        if v.status != 200:
            return _meta_pomylka(v, self.token)
        j = v.json()
        id_ = j.get('post_id') or j.get('id', '')
        return Rezultat(True, id=id_, url=f'https://www.facebook.com/{id_}')

    def vydalyty(self, o: dict) -> Rezultat:
        v = self.http('DELETE', f'{self.baza}/{o["zovnishnii_id"]}?access_token={urllib.parse.quote(self.token)}')
        if v.status == 200 and v.json().get('success'):
            return Rezultat(True)
        r = _meta_pomylka(v, self.token)
        r.typ = 'tymchasova' if r.typ == 'tymchasova' else 'ne_vmiie'
        return r


# ==================================================================== Instagram
class Instagram(Merezha):
    """Професійний акаунт, прив'язаний до сторінки Facebook (Instagram API with Facebook Login).
    Контейнер (`/{ig}/media`, REELS або картинка за публічною адресою) → чекати FINISHED → `/{ig}/media_publish`.
    Змінні: MV_INSTAGRAM_ID, MV_META_PAGE_TOKEN, MV_MEDIA_URL. Ліміт — 100 дописів за добу.
    Видалення: DELETE /{ig-media-id} (дозвіл instagram_manage_contents)."""
    imia = 'instagram'
    CHEKATY_RAZIV = 30

    def __init__(self, **k):
        super().__init__(**k)
        self.ig, self.token = zminna('MV_INSTAGRAM_ID'), zminna('MV_META_PAGE_TOKEN')
        self.baza = f'https://graph.facebook.com/{os.environ.get("MV_META_VERSIA", "v27.0")}'

    def _post(self, shliakh, polia):
        tilo = urllib.parse.urlencode({**polia, 'access_token': self.token}).encode()
        return self.http('POST', f'{self.baza}/{shliakh}', {'Content-Type': 'application/x-www-form-urlencoded'}, tilo)

    def _get(self, shliakh, polia):
        q = urllib.parse.urlencode({**polia, 'access_token': self.token})
        return self.http('GET', f'{self.baza}/{shliakh}?{q}')

    def opublikuvaty(self, o: dict) -> Rezultat:
        try:
            adresa = publichna_adresa(o)
        except NeNalashtovano as e:
            return Rezultat(False, pomylka=str(e), typ='blokuvannia')
        polia = ({'media_type': 'REELS', 'video_url': adresa} if o['typ'] == 'rolyk' else {'image_url': adresa})
        v = self._post(f'{self.ig}/media', {**polia, 'caption': o['tekst']})
        if v.status != 200:
            return _meta_pomylka(v, self.token)
        kont = v.json()['id']
        for _ in range(self.CHEKATY_RAZIV):
            v = self._get(kont, {'fields': 'status_code'})
            st = v.json().get('status_code')
            if st == 'FINISHED':
                break
            if st in ('ERROR', 'EXPIRED'):
                return Rezultat(False, pomylka=f'Instagram не прийняв файл: {st}', typ='odynytsia')
            self.spaty(10)
        else:
            return Rezultat(False, pomylka='Instagram довго обробляє файл', typ='tymchasova')
        v = self._post(f'{self.ig}/media_publish', {'creation_id': kont})
        if v.status != 200:
            return _meta_pomylka(v, self.token)
        id_ = v.json()['id']
        p = self._get(id_, {'fields': 'permalink'}).json().get('permalink', '')
        return Rezultat(True, id=id_, url=p)

    def vydalyty(self, o: dict) -> Rezultat:
        v = self.http('DELETE', f'{self.baza}/{o["zovnishnii_id"]}?access_token={urllib.parse.quote(self.token)}')
        if v.status == 200 and v.json().get('success', True):
            return Rezultat(True)
        r = _meta_pomylka(v, self.token)
        r.typ = 'tymchasova' if r.typ == 'tymchasova' else 'ne_vmiie'
        return r


# ==================================================================== YouTube
class YouTube(Merezha):
    """YouTube Data API v3: `videos.insert` (завантаження з відновленням), вертикальний до 3 хв = Shorts.
    Змінні: MV_YOUTUBE_CLIENT_ID, MV_YOUTUBE_CLIENT_SECRET, MV_YOUTUBE_REFRESH_TOKEN (застосунок Google — у стані
    «In production», інакше ключ оновлення живе 7 днів). Ліміт — 100 завантажень на добу. Видалення — `videos.delete`."""
    imia = 'youtube'

    def __init__(self, **k):
        super().__init__(**k)
        self.cid, self.sekret = zminna('MV_YOUTUBE_CLIENT_ID'), zminna('MV_YOUTUBE_CLIENT_SECRET')
        self.refresh = zminna('MV_YOUTUBE_REFRESH_TOKEN')
        self._dostup = ''

    def _token(self) -> str | Rezultat:
        if self._dostup:
            return self._dostup
        v = self.http('POST', 'https://oauth2.googleapis.com/token', {'Content-Type': 'application/x-www-form-urlencoded'},
                      urllib.parse.urlencode({'client_id': self.cid, 'client_secret': self.sekret,
                                              'refresh_token': self.refresh, 'grant_type': 'refresh_token'}).encode())
        if v.status != 200:
            typ = 'tymchasova' if merezha_vpala(v) else 'blokuvannia'
            return Rezultat(False, pomylka=bez_sekretiv(f'вхід Google: {v.json().get("error", v.status)}',
                                                        self.sekret, self.refresh), typ=typ)
        self._dostup = v.json()['access_token']
        return self._dostup

    def _pomylka(self, v: Vidpovid) -> Rezultat:
        e = v.json().get('error') or {}
        prychyny = {x.get('reason') for x in e.get('errors') or []}
        opys = bez_sekretiv(f'{v.status}: {e.get("message", "")} {",".join(sorted(p for p in prychyny if p))}', self._dostup)
        if merezha_vpala(v):
            return Rezultat(False, pomylka=opys, typ='tymchasova')
        if prychyny & {'quotaExceeded', 'uploadLimitExceeded', 'rateLimitExceeded', 'userRateLimitExceeded'}:
            return Rezultat(False, pomylka=opys, typ='tymchasova', chekaty_s=6 * 3600)
        if v.status in (401, 403):
            return Rezultat(False, pomylka=opys, typ='blokuvannia')
        return Rezultat(False, pomylka=opys, typ='odynytsia')

    def opublikuvaty(self, o: dict) -> Rezultat:
        t = self._token()
        if isinstance(t, Rezultat):
            return t
        meta = {'snippet': {'title': o['nazva'], 'description': o['tekst'], 'categoryId': '22',
                            'defaultLanguage': 'uk', 'defaultAudioLanguage': 'uk'},
                'status': {'privacyStatus': os.environ.get('MV_YOUTUBE_PRYVATNIST', 'public'),
                           'selfDeclaredMadeForKids': False,
                           # голос диктора синтезований (MV-93); позначку YouTube вимагає для «реалістичних» підробок —
                           # ставимо за змінною, типово так (безпечніше)
                           'containsSyntheticMedia': os.environ.get('MV_YOUTUBE_SYNTETYCHNYI', '1') == '1'}}
        dani = self.fail(o).read_bytes()
        v = self.http('POST', 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
                      {'Authorization': f'Bearer {t}', 'Content-Type': 'application/json; charset=UTF-8',
                       'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': str(len(dani))},
                      json.dumps(meta, ensure_ascii=False).encode())
        if v.status != 200 or 'location' not in v.zaholovky:
            return self._pomylka(v)
        v = self.http('PUT', v.zaholovky['location'], {'Authorization': f'Bearer {t}', 'Content-Type': 'video/mp4'}, dani,
                      chas=1800)
        if v.status not in (200, 201):
            return self._pomylka(v)
        id_ = v.json()['id']
        return Rezultat(True, id=id_, url=f'https://www.youtube.com/shorts/{id_}')

    def vydalyty(self, o: dict) -> Rezultat:
        t = self._token()
        if isinstance(t, Rezultat):
            return t
        v = self.http('DELETE', f'https://www.googleapis.com/youtube/v3/videos?id={o["zovnishnii_id"]}',
                      {'Authorization': f'Bearer {t}'})
        if v.status in (200, 204):
            return Rezultat(True)
        return self._pomylka(v)


# ==================================================================== TikTok
class TikTok(Merezha):
    """Content Posting API, пряма публікація з публічної адреси (PULL_FROM_URL; домен MV_MEDIA_URL треба підтвердити
    в кабінеті розробника TikTok). До аудиту застосунку — лише SELF_ONLY (MV_TIKTOK_PRYVATNIST).
    Змінні: MV_TIKTOK_CLIENT_KEY, MV_TIKTOK_CLIENT_SECRET, MV_TIKTOK_REFRESH_TOKEN, MV_MEDIA_URL.
    Ключ оновлення TikTok змінюється при кожному оновленні: новий пишемо у файл MV_TIKTOK_TOKEN_FAIL (поза
    репозиторієм, права 600) — це єдиний виняток з «ключі — лише змінні», див. docs/AVTOPOSTYNH.md, розд. 6.
    Видалення через інтерфейс не знайдено — «прибрати вручну»."""
    imia = 'tiktok'
    vydaliaie = False
    BAZA = 'https://open.tiktokapis.com/v2'

    def __init__(self, **k):
        super().__init__(**k)
        self.key, self.sekret = zminna('MV_TIKTOK_CLIENT_KEY'), zminna('MV_TIKTOK_CLIENT_SECRET')
        self.fail_tokena = Path(os.environ['MV_TIKTOK_TOKEN_FAIL']) if os.environ.get('MV_TIKTOK_TOKEN_FAIL') else None
        if self.fail_tokena and self.fail_tokena.is_file():
            self.refresh = self.fail_tokena.read_text().strip()
        else:
            self.refresh = zminna('MV_TIKTOK_REFRESH_TOKEN')
        self._dostup = ''

    def _token(self):
        if self._dostup:
            return self._dostup
        v = self.http('POST', f'{self.BAZA}/oauth/token/', {'Content-Type': 'application/x-www-form-urlencoded'},
                      urllib.parse.urlencode({'client_key': self.key, 'client_secret': self.sekret,
                                              'grant_type': 'refresh_token', 'refresh_token': self.refresh}).encode())
        j = v.json()
        if v.status != 200 or 'access_token' not in j:
            return Rezultat(False, pomylka=bez_sekretiv(f'вхід TikTok: {j.get("error", v.status)}', self.sekret, self.refresh),
                            typ='tymchasova' if merezha_vpala(v) else 'blokuvannia')
        self._dostup = j['access_token']
        if j.get('refresh_token') and j['refresh_token'] != self.refresh:
            self.refresh = j['refresh_token']
            if self.fail_tokena:
                self.fail_tokena.write_text(self.refresh)
                os.chmod(self.fail_tokena, 0o600)
        return self._dostup

    def _pomylka(self, v: Vidpovid) -> Rezultat:
        e = v.json().get('error') or {}
        kod = e.get('code', '')
        opys = bez_sekretiv(f'{v.status}: {kod} {e.get("message", "")}', self._dostup)
        if merezha_vpala(v) or kod == 'rate_limit_exceeded' or v.status == 429:
            return Rezultat(False, pomylka=opys, typ='tymchasova', chekaty_s=3600)
        if kod in ('spam_risk_too_many_posts', 'spam_risk_user_banned_from_posting', 'access_token_invalid',
                   'scope_not_authorized', 'unaudited_client_can_only_post_to_private_accounts',
                   'url_ownership_unverified', 'privacy_level_option_mismatch') or v.status in (401, 403):
            return Rezultat(False, pomylka=opys, typ='blokuvannia')
        return Rezultat(False, pomylka=opys, typ='odynytsia')

    def opublikuvaty(self, o: dict) -> Rezultat:
        t = self._token()
        if isinstance(t, Rezultat):
            return t
        try:
            adresa = publichna_adresa(o)
        except NeNalashtovano as e:
            return Rezultat(False, pomylka=str(e), typ='blokuvannia')
        zah = {'Authorization': f'Bearer {t}', 'Content-Type': 'application/json; charset=UTF-8'}
        v = self.http('POST', f'{self.BAZA}/post/publish/creator_info/query/', zah, b'{}')
        if v.status != 200:
            return self._pomylka(v)
        pryv = os.environ.get('MV_TIKTOK_PRYVATNIST', 'SELF_ONLY')
        dozv = v.json().get('data', {}).get('privacy_level_options') or []
        if dozv and pryv not in dozv:
            return Rezultat(False, pomylka=f'TikTok не дозволяє {pryv}; можна: {", ".join(dozv)}', typ='blokuvannia')
        tilo = {'post_info': {'title': o['tekst'][:2200], 'privacy_level': pryv, 'disable_comment': False,
                              'disable_duet': True, 'disable_stitch': True, 'is_aigc': True},
                'source_info': {'source': 'PULL_FROM_URL', 'video_url': adresa}}
        v = self.http('POST', f'{self.BAZA}/post/publish/video/init/', zah, json.dumps(tilo, ensure_ascii=False).encode())
        if v.status != 200:
            return self._pomylka(v)
        pid = v.json()['data']['publish_id']
        for _ in range(30):
            v = self.http('POST', f'{self.BAZA}/post/publish/status/fetch/', zah, json.dumps({'publish_id': pid}).encode())
            d = v.json().get('data') or {}
            if d.get('status') == 'PUBLISH_COMPLETE':
                ids = d.get('publicaly_available_post_id') or d.get('publicly_available_post_id') or []
                return Rezultat(True, id=str(ids[0]) if ids else pid, url='')
            if d.get('status') == 'FAILED':
                return Rezultat(False, pomylka=f'TikTok: {d.get("fail_reason", "")}', typ='odynytsia')
            self.spaty(10)
        return Rezultat(True, id=pid, url='', pomylka='TikTok ще обробляє — перевірити в застосунку')


KLASY = {'telegram': Telegram, 'youtube': YouTube, 'facebook': Facebook, 'instagram': Instagram, 'tiktok': TikTok}


def uvimkneni() -> list[str]:
    return [m.strip() for m in os.environ.get('MV_MEREZHI', 'telegram').split(',') if m.strip() in KLASY]

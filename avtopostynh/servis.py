"""Автопостинг «Моєї вулиці» — сервіс на сервері партнера (ZAVDANNYA-107, MV-91, MV-111, MV-114).

Одна команда в розкладі (щогодини, cron):
    python avtopostynh/servis.py hodyna --indeks /srv/mv/indeks.json --media /srv/mv/media
  — побачив новий випуск (поле `versiia` покажчика) або настала п'ятниця → пачка на наступний тиждень;
  — публікує все, чий час настав; повторні спроби; зупинка мережі при блокуванні.
Окремо:
    pachka      --tyzhden 2026-11-23 …   зібрати пачку тижня (перевірка правил → черга, тека з переглядом)
    publikuvaty [--zaraz ISO]            лише публікація
    perehliad   [--port 8107]            сторінка-перегляд (пароль — змінна MV_PEREHLIAD_PAROL)
    prybraty ID --prychyna "…" [--mistse] [--usi-merezhi]
    vidnovyty MEREZHA                    зняти зупинку мережі після того, як партнер розібрався
    tiktok ID ПОСИЛАННЯ                  ролик з черги поставлено в TikTok вручну (ZAVDANNYA-159)
    zhurnal [--dniv 7]
Пробний режим (`--probnyi` або MV_PROBNYI=1): нічого не надсилає — «публікує» у теку `<тека>/opublikovano/`.
Публікує сам, без попереднього схвалення (MV-114); Андрій переглядає вже опубліковане й за потреби прибирає.
Змінні середовища — `docs/AVTOPOSTYNH.md`, розд. 5.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parent
sys.path.insert(0, str(TUT))
sys.path.insert(0, str(KORIN / 'video'))

import cherha as C  # noqa: E402
import cherha_rolykiv as CR  # noqa: E402
import dzherela as D  # noqa: E402
import merezhi as M  # noqa: E402
import pravyla as P  # noqa: E402
import rozklad as R  # noqa: E402

ADRESA_SAITU = os.environ.get('MV_ADRESA_SAITU', 'https://moya-vulytsya.pages.dev')
ZAPIZNENNIA_GOD = 24          # допис, що запізнився більше, не публікуємо (сервер стояв) — щоб не було зливи
DEN_NASTUPNOI_PACHKY = 4      # п'ятниця: пачка наступного тижня, навіть якщо нового випуску не було


class Servis:
    def __init__(self, teka: Path, probnyi: bool = False, media: Path | None = None, adresa_saitu: str = ADRESA_SAITU,
                 kanaly: dict | None = None, http_=None, merezhi_: dict | None = None):
        self.teka = Path(teka)
        self.teka.mkdir(parents=True, exist_ok=True)
        self.q = C.Cherha(self.teka / 'cherha.db')
        self.probnyi = probnyi
        self.media = Path(media) if media else None
        self.sait = adresa_saitu
        self.kanaly = kanaly or {}
        self.http = http_
        self._merezhi = merezhi_ or {}

    # ------------------------------------------------------------ мережі
    def uvimkneni(self) -> list[str]:
        return list(P.MEREZHI) if self.probnyi else M.uvimkneni()

    def merezha(self, imia: str) -> M.Merezha:
        if imia not in self._merezhi:
            if self.probnyi:
                self._merezhi[imia] = M.Probna(imia, self.teka, self.media)
            else:
                k = {'http_': self.http, 'teka_media': self.media}
                self._merezhi[imia] = (M.Telegram(self.kanaly, **k) if imia == 'telegram' else M.KLASY[imia](**k))
        return self._merezhi[imia]

    # ------------------------------------------------------------ перевірка
    def pereviryty(self, o: dict, nedavni: set | None = None) -> list[str]:
        """nedavni — події з черги за 90 днів, порахувані ДО додавання пачки (той самий ролик іде в 4 мережі).
        Під час публікації — None: повтори вже відсіяно, лишається перевірити прибране Андрієм."""
        zh = P.pereviryty(o, self.sait, self.media, self.q.zaboroneno(), nedavni)
        if o.get('stsenarii') and self.media:
            try:
                import perevirka as V
                s = json.loads((self.media / o['stsenarii']).read_text(encoding='utf-8'))
                zh += V.pereviryty(V.pidhotuvaty(s), o['stsenarii'])
            except (OSError, ValueError, KeyError) as e:
                zh.append(f'сценарій ролика не прочитано: {e}')
        return zh

    # ------------------------------------------------------------ пачка
    def pachka(self, pn: date, indeks: dict | None, bot_teka: Path | None = None, zaraz: datetime | None = None) -> dict:
        zaraz = zaraz or C.teper()
        pn = R.ponedilok(pn)
        tyzhden = R.nazva_tyzhnia(pn)
        odynytsi, propusky = [], []
        if indeks:
            tg, chomu = D.telegram_tyzhnia(indeks, pn, self.q.vsi_podii(), bot_teka, self.sait)
            odynytsi += tg
            if chomu:
                propusky.append(chomu)
        else:
            propusky.append('немає покажчика (indeks.json) — дописів Telegram не буде')
        vykorystani = {o.get('pozytsiia') for o in self.q.vsi() if o.get('pozytsiia')}
        md, pr = D.media_tyzhnia(D.chytaty_manifest(self.media), pn, vykorystani, self.sait)
        odynytsi += md
        propusky += pr
        novi = vidkhyleni = 0
        nedavni = self.q.nedavni_podii(zaraz, P.DNIV_BEZ_POVTORU)
        for o in odynytsi:
            zh = self.pereviryty(o, nedavni)
            if self.q.dodaty(o, zh):
                novi += 1
                vidkhyleni += bool(zh)
        for p in propusky:
            self.q.zapys('propusk', p)
        self.q.zapys('pachka', f'{tyzhden}: нових {novi}, відхилено перевіркою {vidkhyleni}, пропусків {len(propusky)}')
        self.eksport(tyzhden)
        return {'tyzhden': tyzhden, 'novi': novi, 'vidkhyleni': vidkhyleni, 'propusky': propusky}

    def rolyky_z_cherhy(self, zaraz: datetime | None = None) -> list[str]:
        """Нові ролики з теки черги (ZAVDANNYA-159) → вільні слоти на тиждень уперед, кожна одиниця — через перевірку."""
        zaraz = zaraz or C.teper()
        novi, povidomlennia = CR.zaplanuvaty(self.q, self.media, self.sait, zaraz)
        for p in povidomlennia:
            self.q.zapys('propusk', p)
        nedavni = self.q.nedavni_podii(zaraz, P.DNIV_BEZ_POVTORU)
        zvit, tyzhni = [], set()
        for o in novi:
            zh = self.pereviryty(o, nedavni)
            if self.q.dodaty(o, zh):
                tyzhni.add(o['tyzhden'])
                zvit.append(f'черга роликів: {o["rolyk_id"]} → {o["merezha"]} {R.po_kyievu(o["chas"])}'
                            + (f' — НЕ ПРОЙШЛО: {"; ".join(zh)}' if zh else ''))
        for t in sorted(tyzhni):
            self.eksport(t)
        return zvit + [f'черга роликів: {p}' for p in povidomlennia]

    def eksport(self, tyzhden: str) -> Path:
        """Пачка тижня у теку: pachka.json і perehliad.html (той самий вигляд, що й сторінка-перегляд, без кнопок)."""
        import perehliad as H
        d = self.teka / 'pachky' / tyzhden
        d.mkdir(parents=True, exist_ok=True)
        vsi = self.q.vsi(tyzhden)
        (d / 'pachka.json').write_text(json.dumps(vsi, ensure_ascii=False, indent=1), encoding='utf-8')
        media_url = os.path.relpath(self.media, d) if self.media else ''
        (d / 'perehliad.html').write_text(H.storinka(self, tyzhden, statychna=True, media_url=media_url), encoding='utf-8')
        return d

    # ------------------------------------------------------------ публікація
    def publikuvaty(self, zaraz: datetime | None = None) -> list[str]:
        zaraz = zaraz or C.teper()
        uvimk = self.uvimkneni()
        zvit, zaniati = [], set()
        for o in self.q.chas_nastav(zaraz):
            m, kluch = o['merezha'], (o['merezha'], o.get('kanal', ''))
            zapizn = zaraz - datetime.fromisoformat(o['chas']) > timedelta(hours=ZAPIZNENNIA_GOD)
            if m not in uvimk:
                if zapizn:
                    self.q.stan(o['id'], 'propushcheno')
                    self.q.zapys('propushcheno', 'мережу не ввімкнено (MV_MEREZHI)', o)
                continue
            if self.q.merezha_zupynena(m, zaraz) or kluch in zaniati:
                continue
            if zapizn:
                self.q.stan(o['id'], 'propushcheno')
                self.q.zapys('propushcheno', f'запізнення понад {ZAPIZNENNIA_GOD} год', o)
                continue
            zh = self.pereviryty(o)
            if zh:
                self.q.stan(o['id'], 'vidkhyleno', zauvazhennia=json.dumps(zh, ensure_ascii=False))
                self.q.zapys('vidkhyleno', '; '.join(zh), o)
                continue
            zaniati.add(kluch)
            try:
                r = self.merezha(m).opublikuvaty(o)
            except M.NeNalashtovano as e:
                r = M.Rezultat(False, pomylka=str(e), typ='blokuvannia')
            except Exception as e:  # noqa: BLE001 — збій одного допису не зупиняє решту
                r = M.Rezultat(False, pomylka=f'{type(e).__name__}: {e}'[:300], typ='tymchasova')
            zvit.append(self._pislia(o, r, zaraz))
        return zvit

    def _pislia(self, o: dict, r: M.Rezultat, zaraz: datetime) -> str:
        m = o['merezha']
        if r.ok:
            self.q.stan(o['id'], 'opublikovano', zovnishnii_id=r.id, url_dopysu=r.url, opublikovano=C.iso(zaraz))
            self.q.uspikh_merezhi(m)
            self.q.zapys('opublikovano', (r.url or r.id) + (f' ({r.pomylka})' if r.pomylka else ''), o, koly=zaraz)
            return f'{m} {o.get("kanal", "")}: опубліковано {r.url or r.id}'
        self.q.zapys('pomylka', f'{r.typ}: {r.pomylka}', o, koly=zaraz)
        if r.typ == 'blokuvannia':
            self.q.zupynyty(m, C.NAZAVZHDY, r.pomylka)
            return f'{m}: ЗУПИНЕНО — {r.pomylka}'
        if r.typ == 'odynytsia':
            self.q.stan(o['id'], 'pomylka', sproby=o['sproby'] + 1)
            return f'{m} {o.get("kanal", "")}: не вийшло — {r.pomylka}'
        sproby = o['sproby'] + 1
        if sproby >= C.MAKS_SPROB:
            self.q.stan(o['id'], 'pomylka', sproby=sproby)
        else:
            chekaty = max(r.chekaty_s, 3600 * 2 ** (sproby - 1))
            self.q.stan(o['id'], 'chekaie', sproby=sproby, nastupna=C.iso(zaraz + timedelta(seconds=chekaty)))
        if self.q.pomylka_merezhi(m) >= C.ZUPYNKA_PISLIA_POMYLOK:
            self.q.zupynyty(m, C.iso(zaraz + timedelta(hours=24)), f'{C.ZUPYNKA_PISLIA_POMYLOK} помилки підряд: {r.pomylka}')
        return f'{m} {o.get("kanal", "")}: спроба {sproby} — {r.pomylka}'

    # ------------------------------------------------------------ прибрати
    def prybraty(self, id_: str, prychyna: str, mistse: bool = False, usi_merezhi: bool = False) -> list[str]:
        """Андрій прибирає опубліковане: видалити в мережі, причину — в журнал, і більше такого не робити."""
        o = self.q.odna(id_)
        if not o:
            return [f'немає одиниці {id_}']
        prychyna = (prychyna or 'без причини').strip()[:300]
        for p in o.get('podii') or []:
            self.q.zaboronyty('podiia', p, prychyna)
        self.q.zaboronyty('tekst', P.khesh_tekstu(o.get('tekst', '')), prychyna)
        if o.get('pozytsiia'):
            self.q.zaboronyty('pozytsiia', o['pozytsiia'], prychyna)
        if mistse and o.get('mistse', {}).get('shliakh'):
            self.q.zaboronyty('mistse', o['mistse']['shliakh'], prychyna)
        tsili = [o]
        if usi_merezhi and o.get('pozytsiia'):
            tsili += [x for x in self.q.vsi(o['tyzhden']) if x.get('pozytsiia') == o['pozytsiia'] and x['id'] != o['id']]
        return [self._prybraty_odnu(x, prychyna) for x in tsili]

    def _prybraty_odnu(self, o: dict, prychyna: str) -> str:
        m = o['merezha']
        if o['stan'] == 'chekaie':
            self.q.stan(o['id'], 'vidkhyleno', zauvazhennia=json.dumps([f'прибрано до публікації: {prychyna}'],
                                                                      ensure_ascii=False))
            self.q.zapys('prybrano', f'до публікації: {prychyna}', o)
            return f'{m}: знято з черги'
        if o['stan'] != 'opublikovano':
            return f'{m}: стан «{o["stan"]}», прибирати нічого'
        try:
            r = self.merezha(m).vydalyty(o)
        except M.NeNalashtovano as e:
            r = M.Rezultat(False, pomylka=str(e), typ='ne_vmiie')
        if r.ok:
            self.q.stan(o['id'], 'prybrano')
            self.q.zapys('prybrano', prychyna, o)
            return f'{m}: видалено'
        if r.typ == 'tymchasova':
            self.q.zapys('pomylka', f'видалити не вдалося, спробуйте ще: {r.pomylka}', o)
            return f'{m}: мережа не відповіла, спробуйте ще раз'
        self.q.stan(o['id'], 'prybraty_vruchnu')
        self.q.zapys('prybraty_vruchnu', f'{prychyna} — мережа: {r.pomylka}', o)
        return f'{m}: мережа не дала видалити — партнер прибере вручну'

    # ------------------------------------------------------------ щогодини
    def hodyna(self, indeks_shliakh: Path | None, bot_teka: Path | None = None, zaraz: datetime | None = None) -> list[str]:
        zaraz = zaraz or C.teper()
        zvit = []
        indeks = None
        if indeks_shliakh and Path(indeks_shliakh).is_file():
            indeks = json.loads(Path(indeks_shliakh).read_text(encoding='utf-8'))
        sohodni = zaraz.astimezone(R.KYIV).date()
        nastupnyi = R.ponedilok(sohodni) + timedelta(days=7)
        versiia = f'indeks:{(indeks or {}).get("versiia", "")}'
        novyi = bool(indeks) and not self.q.vypusk_obroblenyi(versiia)
        if novyi:
            self.q.zapys('vypusk', f'новий випуск {versiia}')
        for pn in (R.ponedilok(sohodni), nastupnyi):
            maie = bool(self.q.vsi(R.nazva_tyzhnia(pn)))
            if not maie and (pn == R.ponedilok(sohodni) or novyi or sohodni.weekday() >= DEN_NASTUPNOI_PACHKY):
                r = self.pachka(pn, indeks, bot_teka, zaraz)
                zvit.append(f'пачка {r["tyzhden"]}: {r["novi"]} одиниць, відхилено {r["vidkhyleni"]}')
        if novyi:
            self.q.vypusk_obrobleno(versiia)
        zvit += self.rolyky_z_cherhy(zaraz)
        zvit += self.publikuvaty(zaraz)
        return zvit


def zchytaty_kanaly() -> dict:
    f = os.environ.get('MV_KANALY')
    return json.loads(Path(f).read_text(encoding='utf-8')) if f and Path(f).is_file() else {}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Автопостинг «Моєї вулиці».')
    p.add_argument('--teka', type=Path, default=Path(os.environ.get('MV_AVTOPOSTYNH_TEKA', 'avtopostynh-stan')),
                   help='стан: черга, журнал, пачки (не в репозиторії)')
    p.add_argument('--media', type=Path, default=os.environ.get('MV_MEDIA_TEKA') or None,
                   help='тека з manifest.json і файлами роликів і карток')
    p.add_argument('--probnyi', action='store_true', default=os.environ.get('MV_PROBNYI') == '1')
    p.add_argument('--adresa-saitu', default=ADRESA_SAITU)
    p.add_argument('--zaraz', help='«зараз» для перевірки (ISO), типово справжній час')
    sp = p.add_subparsers(dest='komanda', required=True)
    for imia in ('hodyna', 'pachka'):
        s = sp.add_parser(imia)
        s.add_argument('--indeks', type=Path, default=os.environ.get('MV_INDEKS') or None)
        s.add_argument('--bot-teka', type=Path, default=os.environ.get('MV_BOT_TEKA') or None,
                       help='тека з bot/kanaly.py, якщо 97 ще не злито')
        if imia == 'pachka':
            s.add_argument('--tyzhden', required=True, help='будь-який день тижня, РРРР-ММ-ДД')
    sp.add_parser('publikuvaty')
    s = sp.add_parser('perehliad')
    s.add_argument('--host', default='127.0.0.1')
    s.add_argument('--port', type=int, default=8107)
    s = sp.add_parser('prybraty')
    s.add_argument('id')
    s.add_argument('--prychyna', required=True)
    s.add_argument('--mistse', action='store_true', help='і більше не писати про це місце')
    s.add_argument('--usi-merezhi', action='store_true', help='той самий ролик чи картку — з усіх мереж')
    s = sp.add_parser('vidnovyty')
    s.add_argument('merezha', choices=P.MEREZHI)
    s = sp.add_parser('zhurnal')
    s.add_argument('--dniv', type=int, default=7)
    s = sp.add_parser('tiktok', help='ролик поставлено в TikTok вручну')
    s.add_argument('id', help='id ролика з черги, напр. 129-t5')
    s.add_argument('posylannia')
    a = p.parse_args(argv)
    zaraz = datetime.fromisoformat(a.zaraz).astimezone(timezone.utc) if a.zaraz else None
    sv = Servis(a.teka, a.probnyi, a.media, a.adresa_saitu, zchytaty_kanaly())
    if a.komanda in ('hodyna', 'pachka'):
        indeks = a.indeks
        if a.komanda == 'pachka':
            ind = json.loads(Path(indeks).read_text(encoding='utf-8')) if indeks else None
            r = sv.pachka(date.fromisoformat(a.tyzhden), ind, a.bot_teka, zaraz)
            print(f'{r["tyzhden"]}: нових {r["novi"]}, відхилено перевіркою {r["vidkhyleni"]}')
            for x in r['propusky']:
                print('  пропуск:', x)
            print('тека:', sv.teka / 'pachky' / r['tyzhden'])
        else:
            for x in sv.hodyna(indeks, a.bot_teka, zaraz):
                print(x)
    elif a.komanda == 'publikuvaty':
        for x in sv.publikuvaty(zaraz):
            print(x)
    elif a.komanda == 'perehliad':
        import perehliad as H
        H.zapustyty(sv, a.host, a.port)
    elif a.komanda == 'prybraty':
        for x in sv.prybraty(a.id, a.prychyna, a.mistse, a.usi_merezhi):
            print(x)
    elif a.komanda == 'vidnovyty':
        sv.q.vidnovyty(a.merezha)
        print(f'{a.merezha}: відновлено')
    elif a.komanda == 'tiktok':
        print(CR.tiktok_postavleno(sv.q, a.id, a.posylannia, zaraz or C.teper()))
    elif a.komanda == 'zhurnal':
        vid = C.iso((zaraz or C.teper()) - timedelta(days=a.dniv))
        for z in reversed(sv.q.zhurnal(vid)):
            print(f'{R.po_kyievu(z["chas"])} {z["merezha"]:9} {z["kanal"][:14]:14} {z["podiia"]:16} {z["povidomlennia"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

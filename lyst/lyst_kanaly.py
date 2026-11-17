"""Канали «Нове біля дому» і щотижнева розсилка (ZAVDANNYA-119, п. 2).

  python lyst/lyst_kanaly.py --strichka nove-<дата>.json --baza lyst.db [--bot-baza stezhennia.db --indeks indeks.json]
                             [--sait https://…] [--teka вихід/]

  * **Пошта** — сервіс зі змінної `MV_POSHTA_SERVIS`; зараз є лише `zahlushka`: лист (.eml, текст + HTML, заголовки
    відписки в один дотик — RFC 8058) пишеться в теку `--teka`, нікуди не йде. Справжній сервіс обирає партнер; для нього
    дописується один клас із методом `nadislaty(lyst_poshty)`.
  * **Telegram** — бот «Мій будинок» (`bot/telegram.py`, токен — `MV_TELEGRAM_TOKEN`). Підписнику — повна версія;
    безкоштовно (записи стеження бота, `--bot-baza`) — лише числа (MV-124). Без токена — заглушка в теку.
  * **Застосунок** — сповіщення Web Push (`docs/ANDROID.md`, розд. 6): тут лише вміст (`lyst.push`); надсилає сервер
    продажу ключем VAPID. Заглушка — у теку.
Перед надсиланням кожен текст перевіряється (`lyst.vady_tekstu`); з вадою — не йде, рахується в `zatrymano`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from email import policy as _policy
from email.message import EmailMessage
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parent
sys.path.insert(0, str(TUT))
sys.path.insert(0, str(KORIN / 'bot'))

import lyst as L  # noqa: E402
import lyst_skhovyshche as S  # noqa: E402

ZMINNA_POSHTY = 'MV_POSHTA_SERVIS'
# Довгий заголовок відписки не можна ламати й кодувати (поштові програми його тоді не впізнають): рядок до 998 знаків.
POLITYKA = _policy.default.clone(max_line_length=998)
VID_KOHO = 'Моя вулиця <nove@moya-vulytsya.example>'     # справжня адреса — домен партнера


def lyst_poshty(l: L.Lyst, komu: str, posylannia: dict, vid_koho: str = VID_KOHO) -> EmailMessage:
    m = EmailMessage(policy=POLITYKA)
    m['Subject'] = L.tema(l)
    m['From'] = vid_koho
    m['To'] = komu
    # Відписка в один дотик у самій поштовій програмі (Gmail, Yahoo вимагають з 2024 року для розсилок).
    m['List-Unsubscribe'] = f'<{posylannia["vidpyska"]}>'
    m['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
    m.set_content(L.tekst(l, posylannia))
    m.add_alternative(L.html_lysta(l, posylannia), subtype='html')
    return m


class PoshtaZahlushka:
    """Лист нікуди не йде: файл .eml у теці (або в пам'яті, якщо теки немає)."""

    def __init__(self, teka: Path | None = None):
        self.teka, self.nadislani = teka, []

    def nadislaty(self, m: EmailMessage) -> bool:
        self.nadislani.append(m)
        if self.teka:
            self.teka.mkdir(parents=True, exist_ok=True)
            (self.teka / f'lyst-{len(self.nadislani):04d}.eml').write_bytes(bytes(m))
        return True


def poshta(teka: Path | None = None):
    servis = os.environ.get(ZMINNA_POSHTY, 'zahlushka')
    if servis == 'zahlushka':
        return PoshtaZahlushka(teka)
    raise SystemExit(f'{ZMINNA_POSHTY}={servis!r}: перехідника для цього сервісу ще немає — є лише «zahlushka».')


class Zahlushka:
    """Telegram або сповіщення без справжнього каналу: записати, що пішло б."""

    def __init__(self, teka: Path | None, imia: str):
        self.teka, self.imia, self.nadislani = teka, imia, []

    def nadislaty(self, kudy, vmist) -> bool:
        self.nadislani.append((kudy, vmist))
        if self.teka:
            self.teka.mkdir(parents=True, exist_ok=True)
            with open(self.teka / f'{self.imia}.jsonl', 'a', encoding='utf-8') as f:
                f.write(json.dumps({'kudy': kudy, 'vmist': vmist}, ensure_ascii=False, default=str) + '\n')
        return True


def telegram_vmist(l: L.Lyst, posylannia: dict) -> dict:
    """Текст і кнопки для sendMessage."""
    import tsiny as T
    if l.platno:
        knopky = [[{'text': 'Відкрити «Стежу»', 'url': posylannia['stezhu']}],
                  [{'text': 'Не надсилати в Telegram', 'url': posylannia['vidpyska_telegram']}]]
        return {'text': L.telegram_pidpysnyk(l), 'reply_markup': {'inline_keyboard': knopky}}
    knopky = [[{'text': f'Підписка — {T.tsina("pidpyska")}', 'url': posylannia['pidpyska']}],
              [{'text': 'Не стежити', 'callback_data': 'x:'}]]          # бот видаляє запис одразу (bot/rozmova.py)
    return {'text': L.telegram_bezkoshtovno(l), 'reply_markup': {'inline_keyboard': knopky}}


def bezkoshtovni_z_bota(bot_baza: Path, indeks: dict) -> list[tuple[L.Pidpysnyk, dict]]:
    """Записи стеження бота (номер чату + сторінка будинку) -> безкоштовні підписники з однією адресою."""
    import stezhennia as BS
    za_url = {b['u']: b for b in indeks['budynky']}
    out = []
    for z in BS.Skhovyshche(bot_baza).usi():
        b = za_url.get(z['url'])
        if b:
            out.append((L.Pidpysnyk(f'bot-{z["chat_id"]}', 'bezkoshtovno', [L.Adresa(b['a'], b['la'], b['lo'])]),
                        {'telegram': z['chat_id']}))
    return out


def rozsylka(strichka: dict, pidpysnyky: list, kanaly: dict, sait: str, klyuch: bytes, skh=None,
             sohodni: str = '') -> dict:
    """pidpysnyky — [(Pidpysnyk, {канал: куди})]; kanaly — {'poshta': …, 'telegram': …, 'push': …} з методом nadislaty."""
    sohodni = sohodni or date.today().isoformat()
    zvit = {'pidpysnykiv': 0, 'lystiv': 0, 'tykhykh': 0, 'bez_novoho': 0, 'zatrymano': 0,
            'poshta': 0, 'telegram': 0, 'push': 0}
    for p, kudy in pidpysnyky:
        zvit['pidpysnykiv'] += 1
        l = L.zibraty(strichka, p)
        if l is None:
            zvit['bez_novoho'] += 1
            continue
        pos = {'stezhu': f'{sait.rstrip("/")}/stezhu/?dzherelo=lyst',
               'pidpyska': f'{sait.rstrip("/")}/oplata/?tovar=pidpyska&dzherelo=bot',
               'vidpyska': S.posylannia_vidpysky(sait, klyuch, p.id, 'poshta'),
               'vidpyska_telegram': S.posylannia_vidpysky(sait, klyuch, p.id, 'telegram')}
        if any(L.vady_tekstu(t) for t in L.usi_teksty(l, pos)):
            zvit['zatrymano'] += 1
            continue
        zvit['lystiv'] += 1
        zvit['tykhykh'] += l.tykhyi
        if 'poshta' in kudy and l.platno and 'poshta' in kanaly:
            zvit['poshta'] += kanaly['poshta'].nadislaty(lyst_poshty(l, kudy['poshta'], pos))
        if 'telegram' in kudy and 'telegram' in kanaly and not (l.tykhyi and not l.platno):
            zvit['telegram'] += kanaly['telegram'].nadislaty(kudy['telegram'], telegram_vmist(l, pos))
        if 'push' in kudy and 'push' in kanaly:
            for x in L.push(l):
                zvit['push'] += kanaly['push'].nadislaty(kudy['push'], x)
        if skh is not None and p.platno:
            skh.nadislano(p.id, sohodni)
    return zvit


class TelegramKanal:
    def __init__(self, tg):
        self.tg = tg

    def nadislaty(self, chat_id, vmist) -> bool:
        r = self.tg.vyklyk('sendMessage', chat_id=chat_id, disable_web_page_preview=True, **vmist)
        return bool(r.get('ok'))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Щотижнева розсилка «Нове біля дому».')
    ap.add_argument('--strichka', type=Path, required=True, help='nove-<дата>.json (dani-edrsr/src/nove_tyzhnia.py)')
    ap.add_argument('--baza', type=Path, help='SQLite підписників (до злиття ZAVDANNYA-99)')
    ap.add_argument('--bot-baza', type=Path, help='сховище стеження бота — безкоштовні, лише числа')
    ap.add_argument('--indeks', type=Path, help='покажчик бота (bot/indeks.py) — для --bot-baza')
    ap.add_argument('--sait', default=L.ADRESA_SAITU)
    ap.add_argument('--teka', type=Path, help='куди писати заглушки (листи .eml, Telegram і сповіщення)')
    a = ap.parse_args(argv)
    strichka = json.loads(a.strichka.read_text(encoding='utf-8'))
    klyuch = S.sekret()
    skh = S.Skhovyshche(a.baza) if a.baza else None
    pidp = skh.pidpysnyky() if skh else []
    if a.bot_baza:
        pidp += bezkoshtovni_z_bota(a.bot_baza, json.loads(a.indeks.read_text(encoding='utf-8')))
    token = os.environ.get('MV_TELEGRAM_TOKEN', '')
    if token:
        from telegram import Telegram
        tg = TelegramKanal(Telegram(token))
    else:
        tg = Zahlushka(a.teka, 'telegram')
    kanaly = {'poshta': poshta(a.teka), 'telegram': tg, 'push': Zahlushka(a.teka, 'push')}
    print(rozsylka(strichka, pidp, kanaly, a.sait, klyuch, skh))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Переказ події через API Claude для генератора довідок (ZAVDANNYA-133, п. 3; docs/PLATNA-CHASTYNA.md, розд. 4).

Генератор `dani-edrsr/src/zvit/perekazy.py` викликає команду зі змінної ZVIT_SHI_KOMANDA: запит — у stdin, відповідь — JSON у
форматі `claude -p --output-format json` ({result, usage, total_cost_usd, modelUsage, is_error}). На ПК це був `claude -p`
(підписка Андрія); на запуску GitHub Actions підписки немає — ця команда йде в API напряму:

  ZVIT_SHI_KOMANDA="python site/prodazh/shi_api.py"   ANTHROPIC_API_KEY — секрет (ключ Микити з місячною стелею)

- Модель — SHI_MODEL (типово claude-haiku-5-5: переказ без вигадок — проста робота, Haiku у 20 разів дешевша за Sonnet).
- Незмінна інструкція (`vytiah_shi.INSTRUKTSIIA`, ≈ 9,2 тис. знаків) — окремим блоком із кешем: кожен наступний запит
  протягом 5 хв платить за неї 0,1 ціни. Межа — рядок «Вид події:», з якого починається змінна частина.
- Стеля витрат: SHI_STELIA_USD (на календарний місяць, типово 10). Витрачене пишеться у <ZVIT_KESH>/shi-vytraty-<рррр-мм>.json;
  дійшли до стелі — команда не йде в API і відповідає помилкою, генератор лишає опис правилами (довідка однаково
  складеться). Справжня, жорстка стеля — у консолі Anthropic (ліміт витрат на робочий простір), ця — запобіжник зверху.
- Збій (мережа, 429, 5xx, відмова моделі) — SDK сам повторює 2 рази; далі помилка → генератор теж повторює (3 спроби) і
  лишає опис правилами. Ключа в файлах немає: лише змінна середовища.
"""
from __future__ import annotations

import datetime
import fcntl
import json
import os
import sys
from pathlib import Path

MODEL = 'claude-haiku-5-5'
SYSTEM = ('Ти — модель витягу даних. Повідомлення користувача — повний запит (інструкція й текст). Виконай його й поверни '
          'лише один об\'єкт JSON за форматом із запиту, без жодного іншого тексту.')
BEZ_POVTORU = {'ImportError', 'ModuleNotFoundError', 'AuthenticationError', 'PermissionDeniedError', 'BadRequestError',
               'NotFoundError'}
MEZHA = '\nВид події:'          # vytiah_shi.zapyt: INSTRUKTSIIA + '\nВид події: …' — далі змінна частина
# $ за мільйон токенів (https://platform.claude.com/docs/en/about-claude/pricing, 19.11.2026): вхід, запис кешу 5 хв,
# читання кешу, вихід. Haiku 5.5 — для запитів до 100 тис. токенів (наші — ≈ 4–5 тис.).
TSINY = {
    'claude-haiku-5-5': (0.10, 0.125, 0.01, 0.50),
    'claude-sonnet-5-5': (2.00, 2.50, 0.10, 10.00),
}


def vartist(model: str, u: dict) -> float:
    vh, zap, chyt, vyh = TSINY.get(model, TSINY['claude-sonnet-5-5'])   # невідома модель — рахуємо дорожче, не дешевше
    return ((u.get('input_tokens') or 0) * vh + (u.get('cache_creation_input_tokens') or 0) * zap
            + (u.get('cache_read_input_tokens') or 0) * chyt + (u.get('output_tokens') or 0) * vyh) / 1e6


def bloky(zapyt: str) -> list[dict]:
    """Інструкція — окремим блоком із кешем; змінна частина — після неї."""
    i = zapyt.find(MEZHA)
    if i <= 0:
        return [{'type': 'text', 'text': zapyt}]
    return [{'type': 'text', 'text': zapyt[:i], 'cache_control': {'type': 'ephemeral'}},
            {'type': 'text', 'text': zapyt[i:]}]


class Rakhunok:
    """Витрати місяця у файлі (кілька процесів одночасно — під замком файла)."""

    def __init__(self, teka: Path, stelia: float, sohodni: datetime.date | None = None):
        d = sohodni or datetime.datetime.now(datetime.timezone.utc).date()
        teka.mkdir(parents=True, exist_ok=True)
        self.f = teka / f'shi-vytraty-{d:%Y-%m}.json'
        self.stelia = stelia

    def _z_zamkom(self, zmina: float | None):
        with open(self.f, 'a+', encoding='utf-8') as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.seek(0)
            t = fh.read().strip()
            st = json.loads(t) if t else {'usd': 0.0, 'zapytiv': 0}
            if zmina is not None:
                st['usd'] = round(st['usd'] + zmina, 6)
                st['zapytiv'] += 1
                fh.seek(0)
                fh.truncate()
                fh.write(json.dumps(st))
            return st

    def vytracheno(self) -> float:
        return self._z_zamkom(None)['usd']

    def dodaty(self, usd: float) -> None:
        self._z_zamkom(usd)


def vidpovid(result=None, usage=None, cost=0.0, model=MODEL, pomylka=None, bez_povtoru=False) -> dict:
    # bez_povtoru — повтор нічого не змінить (стеля, відмова): генератор не чекає 3 спроби, одразу лишає правила
    if pomylka:
        return {'is_error': True, 'bez_povtoru': bez_povtoru, 'result': pomylka, 'usage': {}, 'total_cost_usd': 0, 'modelUsage': {}}
    return {'is_error': False, 'result': result, 'usage': usage or {}, 'total_cost_usd': cost, 'modelUsage': {model: {}}}


def vyklykaty(zapyt: str, klient=None, env=os.environ) -> dict:
    model = env.get('SHI_MODEL', MODEL)
    rakhunok = Rakhunok(Path(env.get('ZVIT_KESH') or '.'), float(env.get('SHI_STELIA_USD', '10')))
    if klient is None and not env.get('ANTHROPIC_API_KEY'):
        return vidpovid(pomylka='немає ANTHROPIC_API_KEY — опис правилами', bez_povtoru=True)
    if rakhunok.vytracheno() >= rakhunok.stelia:
        return vidpovid(pomylka=f'стеля витрат місяця {rakhunok.stelia} $ — опис правилами', bez_povtoru=True)
    try:
        if klient is None:
            import anthropic                               # лише на запуску з ключем; тести підставляють свій клієнт
            klient = anthropic.Anthropic(max_retries=2, timeout=120.0)
        r = klient.messages.create(
            model=model, max_tokens=4000, system=SYSTEM,
            output_config={'effort': 'low'},              # переказ і цитати — не задача на роздуми; думки — теж токени виходу
            messages=[{'role': 'user', 'content': bloky(zapyt)}],
        )
    except Exception as err:                               # мережа, ліміт, 5xx — після повторів SDK; генератор лишить правила
        # налаштування (немає бібліотеки чи ключа, ключ хибний, запит негодящий) повтором не виправити — одразу правила
        nazva = type(err).__name__
        return vidpovid(pomylka=f'API: {nazva}', bez_povtoru=nazva in BEZ_POVTORU)
    u = r.usage.to_dict() if hasattr(r.usage, 'to_dict') else dict(r.usage)
    usd = vartist(model, u)
    rakhunok.dodaty(usd)
    if r.stop_reason == 'refusal':
        return vidpovid(pomylka='модель відмовила — опис правилами', bez_povtoru=True)
    tekst = ''.join(b.text for b in r.content if getattr(b, 'type', '') == 'text')
    return vidpovid(tekst, u, usd, model)


def main() -> int:
    print(json.dumps(vyklykaty(sys.stdin.read()), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())

"""Розклад тижня (docs/KOMPAS.md, розд. 3а — «Тиждень (порада)»; MV-111).

Ролики: 7 на тиждень, по одному на день, о 18:00 за Києвом —
  пн «Що болить вулиці», вт історія, ср гра, чт «Що буває за…», пт історія, сб гра, нд видовищний;
  «Історії з даних» — щосереди о 12:00, лише Facebook (KOMPAS: «переважно Facebook»);
  «Як це працює» — по вівторках парних тижнів о 12:00.
Кожен ролик — у YouTube, Facebook, Instagram і TikTok (той самий файл, свій підпис і своя мітка `?dzherelo=`).
Картки «Вулиця в цифрах» — вт і пт о 13:00, Facebook і Instagram.
Районні канали Telegram — щодня о 09:00, канали по черзі з кроком 2 хв (ліміт Telegram ≈ 20 повідомлень на хвилину).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

KYIV = ZoneInfo('Europe/Kyiv')

HRUPY = {
    'shcho_bolyt': '«Що болить вулиці»',
    'istorii': 'Історії «під боком»',
    'hry': 'Ігри',
    'zghory': 'Місто згори',
    'yak_pratsiuie': 'Як це працює',
    'shcho_buvaie': '«Що буває за…»',
    'istorii_z_danykh': 'Історії з даних',
}
MEREZHI_ROLYKA = ('youtube', 'facebook', 'instagram', 'tiktok')
MEREZHI_KARTKY = ('facebook', 'instagram')

# (день тижня 0=пн, година, група, мережі, умова)
ROLYKY = [
    (0, 18, 'shcho_bolyt', MEREZHI_ROLYKA, None),
    (1, 18, 'istorii', MEREZHI_ROLYKA, None),
    (2, 18, 'hry', MEREZHI_ROLYKA, None),
    (3, 18, 'shcho_buvaie', MEREZHI_ROLYKA, None),
    (4, 18, 'istorii', MEREZHI_ROLYKA, None),
    (5, 18, 'hry', MEREZHI_ROLYKA, None),
    (6, 18, 'zghory', MEREZHI_ROLYKA, None),
    (2, 12, 'istorii_z_danykh', ('facebook',), None),
    (1, 12, 'yak_pratsiuie', MEREZHI_ROLYKA, 'parnyi'),
]
KARTKY = [(1, 13), (4, 13)]
TELEGRAM_HODYNA = 9
TELEGRAM_KROK_KHV = 2


def ponedilok(d: date) -> date:
    return d - timedelta(days=d.weekday())


def nazva_tyzhnia(pn: date) -> str:
    r, t, _ = pn.isocalendar()
    return f'{r}-W{t:02d}'


def chas(den: date, hodyna: int, khvylyna: int = 0) -> str:
    """Час за Києвом → рядок ISO в UTC (у черзі все в UTC, показуємо за Києвом)."""
    return datetime.combine(den, time(hodyna, khvylyna), KYIV).astimezone(timezone.utc).isoformat(timespec='minutes')


def po_kyievu(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(KYIV).strftime('%d.%m %H:%M')


def sloty_rolykiv(pn: date) -> list[dict]:
    """Місця для роликів на тиждень, що починається з понеділка pn."""
    parnyi = pn.isocalendar()[1] % 2 == 0
    r = []
    for den, hod, hrupa, merezhi, umova in ROLYKY:
        if umova == 'parnyi' and not parnyi:
            continue
        r.append({'den': pn + timedelta(days=den), 'chas': chas(pn + timedelta(days=den), hod), 'hrupa': hrupa,
                  'merezhi': merezhi})
    return sorted(r, key=lambda s: s['chas'])


def sloty_kartok(pn: date) -> list[dict]:
    return [{'den': pn + timedelta(days=d), 'chas': chas(pn + timedelta(days=d), h), 'merezhi': MEREZHI_KARTKY}
            for d, h in KARTKY]


def chas_telegram(den: date, nomer_kanalu: int) -> str:
    return chas(den, TELEGRAM_HODYNA, nomer_kanalu * TELEGRAM_KROK_KHV)

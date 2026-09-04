# -*- coding: utf-8 -*-
"""Написання вулиць — вимір і геоперевірка кластерів-кандидатів.

Крок 1 нормалізації адрес (yakist-adres.md, розділ 3): «спершу міра — які
пари зливаються і скільки». Це саме міра, вона нічого на карті не змінює.

Запускати ТАМ, ДЕ Є data/events.db — справжня база (у пісочниці Claude її
нема, вона в .gitignore):

  python3 src/diag_addr_variants.py

Групує різні написання вулиці (без огляду на тип — вул./просп./пров.) за
останнім значущим словом назви (родові слова на кшталt «шосе», «дорога»,
«набережна» до уваги не беруться, інакше «Харківське шосе» і «Столичне шосе»
зіллються в одне тільки тому, що обидва закінчуються на «шосе»).

Для кожного кластера рахує, наскільки далеко на карті стоять події з різними
написаннями. Це і є справжня перевірка: однакова назва тексту нічого не
доводить (Київ має окрему «Васильківську» і окрему «Велику Васильківську» —
дві різні вулиці, самé лише злиття текстом об’єднало б їх помилково). Якщо
всі написання лежать близько (<=400 м від найбільшого) — кластер підтверджено,
це кандидат на об'єднання. Якщо ні — писати правило для нього руками й
дивитися на кожен варіант окремо.

Пише data/adres_klastery.txt — список кластерів для перегляду. Це РЕЗУЛЬТАТ,
не вхід, і в git не потрапляє (як top100_dlya_pereviryky.txt).

Наступні кроки з yakist-adres.md, у порядку: міра (це) -> правила (мапа
написання -> канонічна форма, лише для підтверджених кластерів) -> перевірка
на переліку відомих пар -> і лише тоді ввімкнення в step2_geocode.py.
"""
import os, sys, sqlite3, re, collections, json, statistics, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
DB = os.path.join(DATA, 'events.db')
OUT = os.path.join(DATA, 'adres_klastery.txt')

TYPES = ['проспект', 'просп', 'вулиця', 'вул', 'провулок', 'пров', 'бульвар',
         'б-р', 'бул', 'узвіз', 'шосе', 'набережна', 'наб', 'площа', 'пл',
         'алея', 'тупик', 'дорога']
TYPE_RE = re.compile(r'^(' + '|'.join(TYPES) + r')\.?\s+', re.IGNORECASE)
GENERIC_TAIL = {'шосе', 'дорога', 'дороги', 'набережна', 'набережної',
                'площа', 'площі', 'провулок', 'бульвар', 'узвіз', 'алея',
                'вулиця', 'проспект', 'тупик'}
NEAR_M = 400   # поріг геозбігу; для дуже довгих вулиць затісний — див. звіт


def split_type(s):
    m = TYPE_RE.match(s)
    if m:
        return m.group(1).lower(), s[m.end():].strip()
    return '', s.strip()


def norm_punct(s):
    s = re.sub(r'\s*\.\s*', '.', s)
    s = re.sub(r'\.', '. ', s)
    return re.sub(r'\s+', ' ', s).strip()


def tail_word(name_n):
    words = [w.strip('.').lower() for w in name_n.split()]
    for w in reversed(words):
        if len(w) >= 3 and w not in GENERIC_TAIL:
            return w
    return 'CILA:' + name_n


def dist_m(p1, p2):
    mlat, mlon = 111320.0, 111320.0 * 0.6374
    return math.hypot((p1[0] - p2[0]) * mlat, (p1[1] - p2[1]) * mlon)


def main():
    if not os.path.exists(DB):
        print('data/events.db немає — цей вимір потребує справжньої бази '
              '(запустіть на комп’ютері, не в пісочниці)')
        return 1

    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""
        select e.street, g.lat, g.lon
        from events e join geo g on g.doc_id = e.doc_id
        where e.street is not null and e.street != ''
    """)
    raw = cur.fetchall()
    con.close()

    by_street = collections.defaultdict(lambda: {'n': 0, 'lats': [], 'lons': []})
    for street, lat, lon in raw:
        d = by_street[street]
        d['n'] += 1
        if lat is not None and lon is not None:
            d['lats'].append(lat); d['lons'].append(lon)

    info = {}
    for street, d in by_street.items():
        typ, name = split_type(street)
        info[street] = {'name_norm': norm_punct(name).lower(), 'n': d['n'],
                         'lats': d['lats'], 'lons': d['lons']}

    groups = collections.defaultdict(list)
    for street, d in info.items():
        groups[tail_word(d['name_norm'])].append(street)
    candidates = {tw: sts for tw, sts in groups.items() if len(sts) > 1}

    def centroid(d):
        return (statistics.mean(d['lats']), statistics.mean(d['lons'])) if d['lats'] else None

    report = []
    for tw, sts in candidates.items():
        cents = sorted(((s, centroid(info[s]), info[s]['n']) for s in sts),
                        key=lambda x: -x[2])
        total_n = sum(n for _, _, n in cents)
        main = cents[0]
        max_dist, all_close = None, True
        if main[1]:
            for s, c, n in cents[1:]:
                if c is None:
                    all_close = False; continue
                dm = dist_m(main[1], c)
                max_dist = dm if max_dist is None else max(max_dist, dm)
                if dm > NEAR_M: all_close = False
        else:
            all_close = False
        report.append({'tail': tw, 'total_n': total_n, 'points': cents,
                        'max_dist': max_dist, 'confirmed': all_close})
    report.sort(key=lambda r: -r['total_n'])

    confirmed = [r for r in report if r['confirmed']]
    unconfirmed = [r for r in report if not r['confirmed']]
    minority = sum(r['total_n'] - r['points'][0][2] for r in confirmed)

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('# Кластери написань вулиць — кандидати на об’єднання.\n')
        f.write(f'# Різних написань серед геокодованих подій: {len(by_street)}\n')
        f.write(f'# Кластерів-кандидатів: {len(report)}\n')
        f.write(f'# Геоперевірено (<= {NEAR_M} м від головного написання): '
                f'{len(confirmed)} кластерів, {minority} подій не на головному написанні.\n')
        f.write(f'# Не підтверджено геометрією — писати правило вручну для кожного: '
                f'{len(unconfirmed)} кластерів, {sum(r["total_n"] for r in unconfirmed)} подій.\n')
        f.write('# Не підтверджено НЕ значить «різні вулиці» — часто це просто довга вулиця\n')
        f.write(f'# (поріг {NEAR_M} м затісний для проспектів у кілька кілометрів). Але і не значить\n')
        f.write('# «одна вулиця» — так знайшлося, що вул. Васильківська і вул. Велика Васильківська\n')
        f.write('# в Києві різні вулиці (окремі статті Вікіпедії), хоча звучать як одна.\n\n')

        f.write('== ПІДТВЕРДЖЕНО ГЕОМЕТРІЄЮ ==\n\n')
        for r in confirmed:
            f.write(f"{r['total_n']:6}  {r['tail']}  (розкид {r['max_dist'] or 0:.0f} м)\n")
            for s, c, n in r['points']:
                f.write(f"          {n:5}  {s}\n")
            f.write('\n')

        f.write('\n== ПОТРЕБУЄ РУЧНОЇ ПЕРЕВІРКИ ==\n\n')
        for r in unconfirmed:
            f.write(f"{r['total_n']:6}  {r['tail']}  (розкид {r['max_dist'] or '?'} м)\n")
            for s, c, n in r['points']:
                f.write(f"          {n:5}  {s}\n")
            f.write('\n')

    print(f'написань: {len(by_street)}; кластерів: {len(report)}; '
          f'підтверджено: {len(confirmed)} ({minority} подій не на головному написанні); '
          f'на ручний розбір: {len(unconfirmed)} ({sum(r["total_n"] for r in unconfirmed)} подій)')
    print(f'звіт: data/adres_klastery.txt')


if __name__ == '__main__':
    sys.exit(main() or 0)

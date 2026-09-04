# -*- coding: utf-8 -*-
"""Розвідка перед збереженням фабул: що насправді написано в рішеннях.

Питання, на які відповідає цей скрипт, і на які з пісочниці відповісти
неможливо — реєстр за межами дозволеної мережі:

  1. Скільки важить фабула. Від цього залежить, чи вміщається текст у файл
     карти взагалі: 68 тисяч подій помножити на середню довжину.
  2. Чи названо в тексті людину. Кримінальні рішення в реєстрі знеособлені
     («ОСОБА_1»), адміністративні постанови часто несуть повне ім'я, дату
     народження й адресу проживання. Перш ніж класти це на відкритий сайт,
     треба побачити, що там.

Качає невелику вибірку — по кілька документів кожної теми — і пише звіт
FABULA_REZULTAT.txt: спершу цифри, потім самі тексти, щоб подивитися очима.

Нічого не зберігає в базу і нічого не змінює. Запуск: FABULA.bat

Працює і без data/events.db: якщо бази немає, перелік подій береться зі
знімка data/events.csv.gz, який лежить у репозиторії.
"""
import os, re, sys, csv, gzip, glob, time, random, sqlite3, collections
import urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import labels as L
import addr as A
from step1_download import rtf_to_text, UA

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
DB = os.path.join(DATA, 'events.db')
SNAP = os.path.join(DATA, 'events.csv.gz')
OUT = os.path.join(ROOT, 'FABULA_REZULTAT.txt')

PER_THEME = 8          # документів на тему
SHOW = 900             # скільки знаків фабули показувати у звіті

# ---- ознаки персональних даних ----
SIGNS = [
    ('знеособлено «ОСОБА_N»', re.compile(r'ОСОБА_\d+')),
    ('прізвище з ініціалами', re.compile(r'[А-ЯІЇЄҐ][а-яіїєґ\']{2,}\s+[А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ]\.')),
    ('три слова з великої (схоже на ПІБ)',
     re.compile(r'[А-ЯІЇЄҐ][а-яіїєґ\']{2,}\s+[А-ЯІЇЄҐ][а-яіїєґ\']{2,}\s+[А-ЯІЇЄҐ][а-яіїєґ\']{2,}')),
    ('дата народження', re.compile(r'\d{2}[\.\s]\d{2}[\.\s]\d{4}\s*р\w*\s*народж|народився|народжен')),
    ('РНОКПП або ІПН (10 цифр)', re.compile(r'(?<!\d)\d{10}(?!\d)')),
    ('серія і номер паспорта', re.compile(r'[А-ЯA-Z]{2}\s?\d{6}(?!\d)')),
    ('місце проживання', re.compile(r'прожива|зареєстрован')),
]


def on_map():
    """doc_id -> код статті. Спершу база, інакше знімок із репозиторію."""
    if os.path.exists(DB):
        c = sqlite3.connect(DB)
        if c.execute("SELECT name FROM sqlite_master WHERE name='geo'").fetchone():
            d = {r[0]: r[1] for r in c.execute(
                "SELECT e.doc_id, e.cat FROM events e JOIN geo g ON g.doc_id=e.doc_id")}
            if d:
                print(f'перелік подій із data/events.db: {len(d):,}')
                return d
    if os.path.exists(SNAP):
        # у знімку немає координат, зате є витягнута адреса — а це та сама
        # множина документів, з якої потім виходять точки карти
        d = {}
        with gzip.open(SNAP, 'rt', encoding='utf-8', newline='') as fh:
            rd = csv.reader(fh, delimiter='\t')
            head = next(rd, None)
            i_doc, i_cat, i_st = head.index('doc_id'), head.index('cat'), head.index('street')
            for r in rd:
                if len(r) > i_st and r[i_st]:
                    d[r[i_doc]] = r[i_cat]
        print(f'перелік подій зі знімка data/events.csv.gz: {len(d):,}')
        print('   (бази events.db немає — для розвідки знімка досить)')
        return d
    print('немає ні data/events.db, ні data/events.csv.gz'); sys.exit(1)


def load_docs():
    """doc_id -> (url, cause_num, cat) для документів, що потрапили на карту"""
    mapped = on_map()
    docs = {}
    for fp in sorted(glob.glob(os.path.join(DATA, 'kyiv_*.csv'))):
        with open(fp, encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                d = r['doc_id']
                if d in mapped and r.get('doc_url'):
                    docs[d] = (r['doc_url'], r.get('cause_num', ''), mapped[d])
    if not docs:
        print('немає data/kyiv_*.csv із посиланнями — покладіть дампи в data/')
        sys.exit(1)
    return docs


def sample(docs):
    by_theme = collections.defaultdict(list)
    for d, (u, cn, cat) in docs.items():
        lb = L.CODE.get(cat)
        by_theme[lb[0] if lb else 'СЕР'].append((d, u, cn, cat))
    rnd = random.Random(20260903)          # та сама вибірка при повторі
    out = []
    for th in sorted(by_theme):
        rows = by_theme[th]
        rnd.shuffle(rows)
        out += [(th,) + r for r in rows[:PER_THEME]]
    return out


def fabula(text):
    bs = A.body_start(text)
    t = text[bs:] if bs else text
    return re.sub(r'\s+', ' ', t).strip()


def main():
    docs = load_docs()
    rows = sample(docs)
    print(f'з посиланнями: {len(docs):,}; качаю вибірку: {len(rows)}')
    got, lens, hits = [], [], collections.Counter()
    for i, (th, doc, url, cn, cat) in enumerate(rows, 1):
        try:
            rq = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(rq, timeout=45) as resp:
                raw = resp.read()
        except Exception as e:
            print(f'   {i}/{len(rows)} не завантажено: {e}')
            continue
        txt = rtf_to_text(raw)
        fb = fabula(txt)
        if not fb:
            print(f'   {i}/{len(rows)} порожня фабула')
            continue
        lens.append(len(fb))
        found = [name for name, rx in SIGNS if rx.search(fb[:2000])]
        for f in found: hits[f] += 1
        lb = L.CODE.get(cat)
        got.append((th, lb[1] if lb else cat, cn, url, fb, found))
        print(f'   {i}/{len(rows)} {len(fb):6,} знаків  {th}')
        time.sleep(0.15)

    if not got:
        print('нічого не завантажено — перевірте інтернет'); sys.exit(1)

    lens.sort()
    med = lens[len(lens) // 2]
    avg = sum(lens) // len(lens)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('РОЗВІДКА ФАБУЛ — що насправді написано в рішеннях\n')
        f.write('=' * 64 + '\n\n')
        f.write(f'документів з посиланнями: {len(docs):,}\n')
        f.write(f'у вибірці: {len(got)}\n\n')
        f.write('ДОВЖИНА ФАБУЛИ, знаків\n')
        f.write(f'  найкоротша {lens[0]:,}   медіана {med:,}   '
                f'середня {avg:,}   найдовша {lens[-1]:,}\n')
        f.write(f'  чверть найдовших від {lens[int(len(lens)*.75)]:,}\n\n')
        f.write('СКІЛЬКИ ЗАЙМЕ ТЕКСТ (за медіаною)\n')
        for label, n in (('усі події на карті', len(docs)), ('лише проблеми (≈3 000)', 3000)):
            f.write(f'  {label}: {med*n/1048576:.1f} МБ\n')
        f.write('  (стиснення зменшує приблизно втричі)\n\n')
        f.write('ПЕРСОНАЛЬНІ ДАНІ — у скількох фабулах трапляється\n')
        for name, _ in SIGNS:
            n = hits.get(name, 0)
            f.write(f'  {name:<38} {n:>3} з {len(got)}\n')
        f.write('\n' + '=' * 64 + '\n')
        f.write('САМІ ТЕКСТИ — подивитися очима\n')
        f.write('=' * 64 + '\n')
        for th, art, cn, url, fb, found in got:
            f.write(f'\n--- {L.THEMES.get(th, th)} · {art} · справа {cn}\n')
            f.write(f'    {url}\n')
            if found:
                f.write(f'    ЗНАЙДЕНО: {", ".join(found)}\n')
            f.write(f'    {fb[:SHOW]}\n')
            if len(fb) > SHOW:
                f.write(f'    […ще {len(fb)-SHOW:,} знаків]\n')
    print(f'\n=== ГОТОВО === звіт: {os.path.basename(OUT)}')
    print(f'   медіана фабули {med:,} знаків, у вибірці {len(got)} рішень')


if __name__ == '__main__':
    main()

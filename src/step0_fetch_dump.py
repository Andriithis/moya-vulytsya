# -*- coding: utf-8 -*-
"""Крок 0. Качає свіжий дамп ЄДРСР з data.gov.ua і фільтрує до kyiv_YYYY.csv.

Під час міграції це лишається compatibility-export для старих кроків pipeline.
Сам формат офіційного snapshot тепер читає pipeline.edrsr_snapshot, щоб однаково
валідувати структуру й рахувати hash рядків/архіву для майбутнього DB-upsert.

Портал data.gov.ua лягає регулярно. Якщо свіжий дамп недоступний, але старі
kyiv_*.csv існують, наступні кроки продовжують працювати на них.
"""
import os, sys, json, time, datetime, glob, collections
import urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import labels as L
from pipeline.edrsr_snapshot import iter_documents, sha256_file

DATA = os.path.join(ROOT, 'data')
CKAN = 'https://data.gov.ua/api/3/action/package_search?q=%D1%81%D1%83%D0%B4%D0%BE%D0%B2%D0%B8%D1%85+%D1%80%D1%96%D1%88%D0%B5%D0%BD%D1%8C&rows=50'
UA = {'User-Agent': 'edrsr-academy-ci/1.0'}
TRIES = 4
PAUSE = 20

COURTS = {"2601":"Golosiivskyi","2602":"Darnytskyi","2603":"Desnianskyi","2604":"Dniprovskyi",
 "2605":"Obolonskyi","2606":"Pecherskyi","2607":"Podilskyi","2608":"Sviatoshynskyi",
 "2609":"Solomianskyi","2610":"Shevchenkivskyi"}
SKIP_THEME = {'ДОМ'}


def have_data():
    return sorted(glob.glob(os.path.join(DATA, 'kyiv_*.csv')))


def give_up(msg):
    have = have_data()
    print(msg)
    if not have:
        print('   і жодного kyiv_*.csv у папці data немає — далі йти нема з чим')
        sys.exit(1)
    print('   АЛЕ дані за попередні прогони на місці:')
    for p in have:
        print(f'      {os.path.basename(p)}')
    print('   продовжуємо на них. Свіжі рішення доберемо наступного разу.')
    sys.exit(0)


def find_url(year):
    """Шукає посилання на архів за рік через API порталу."""
    for i in range(1, TRIES + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(CKAN, headers=UA), timeout=90) as r:
                js = json.loads(r.read().decode())
            for pkg in js['result']['results']:
                if str(year) not in pkg.get('title', ''):
                    continue
                for res in pkg.get('resources', []):
                    u = res.get('url', '')
                    if u.endswith(f'edrsr_data_{year}.zip'):
                        return u
            print(f'   у переліку порталу немає архіву за {year} рік')
            return None
        except Exception as e:
            print(f'   спроба {i} з {TRIES}: API порталу недоступне ({type(e).__name__})', flush=True)
            if i < TRIES:
                time.sleep(PAUSE)
    return None


def download(url, zpath):
    """Качає архів; повертає True, якщо файл приїхав."""
    for i in range(1, TRIES + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=1800) as r, open(zpath, 'wb') as f:
                n = 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    n += len(chunk)
                    if n % (50 << 20) < (1 << 20):
                        print(f'   {n/1048576:.0f} МБ', flush=True)
            print(f'   завантажено {os.path.getsize(zpath)/1048576:.0f} МБ')
            return True
        except Exception as e:
            print(f'   спроба {i} з {TRIES}: завантаження обірвалось ({type(e).__name__})', flush=True)
            if os.path.exists(zpath):
                os.remove(zpath)
            if i < TRIES:
                time.sleep(PAUSE)
    return False


def export_compatibility_csv(zpath, year):
    """Створює старий kyiv_YYYY.csv через новий валідований snapshot-reader."""
    out = os.path.join(DATA, f'kyiv_{year}.csv')
    tmp = out + '.tmp'
    total = found = inactive = 0
    grp = collections.Counter()

    try:
        with open(tmp, 'w', encoding='utf-8-sig', newline='') as o:
            o.write('doc_id\tcourt_code\tcourt\tgroup\tcategory_code\tcause_num\tdate\tdoc_url\n')
            for doc in iter_documents(zpath):
                total += 1
                if doc.status == 0:
                    inactive += 1
                    continue
                if doc.court_code not in COURTS:
                    continue
                lb = L.CODE.get(doc.category_code)
                if not lb or lb[0] in SKIP_THEME:
                    continue
                o.write(
                    f'{doc.doc_id}\t{doc.court_code}\t{COURTS[doc.court_code]}\t{lb[0]}\t'
                    f'{doc.category_code}\t{doc.cause_num}\t{doc.adjudication_date}\t{doc.doc_url}\n'
                )
                found += 1
                grp[lb[0]] += 1
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

    os.replace(tmp, out)
    return out, total, found, inactive, grp


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today().year
    os.makedirs(DATA, exist_ok=True)
    print(f'=== Крок 0: дамп ЄДРСР за {year} рік ===')

    url = find_url(year) or os.environ.get('EDRSR_URL')
    if not url:
        give_up('НЕ ЗНАЙДЕНО посилання на архів (портал data.gov.ua не відповідає).')

    print(f'   {url}')
    zpath = os.path.join(DATA, f'_dump_{year}.zip')
    if not download(url, zpath):
        give_up('Архів не завантажився.')

    try:
        archive_hash = sha256_file(zpath)
        print(f'   sha256: {archive_hash}')
        out, total, found, inactive, grp = export_compatibility_csv(zpath, year)
    except Exception as e:
        if os.path.exists(zpath):
            os.remove(zpath)
        give_up(f'Архів пошкоджений або формат змінився ({type(e).__name__}: {e}).')

    os.remove(zpath)
    print(f'   прочитано {total:,}, неактивних {inactive:,}, відібрано {found:,} -> {os.path.basename(out)}')
    for k, v in grp.most_common():
        print(f'      {L.THEMES.get(k,k):28} {v:>8,}')


if __name__ == '__main__':
    main()

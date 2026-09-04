# -*- coding: utf-8 -*-
"""Крок 1. Качає тексти рішень, витягає адресу і час. З відновленням після зупинки."""
import os, re, sys, csv, glob, time, sqlite3, threading, queue
import urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addr as A

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
DB   = os.path.join(DATA, 'events.db')
SNAP = os.path.join(DATA, 'events.csv.gz')   # стан для зберігання в репозиторії

def snapshot_load(conn):
    import gzip, csv as _csv
    if not os.path.exists(SNAP): return 0
    n = 0
    with gzip.open(SNAP, 'rt', encoding='utf-8', newline='') as fh:
        rd = _csv.reader(fh, delimiter='\t')
        next(rd, None)
        rows = []
        for r in rd:
            if len(r) < 9: continue
            rows.append(tuple(x if x != '' else None for x in r[:9]) + (None,))
            n += 1
            if len(rows) >= 5000:
                conn.executemany('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?,?,?)', rows); rows = []
        if rows: conn.executemany('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?,?,?)', rows)
    conn.commit()
    return n

def snapshot_save(conn):
    import gzip, csv as _csv
    with gzip.open(SNAP, 'wt', encoding='utf-8', newline='') as fh:
        w = _csv.writer(fh, delimiter='\t', lineterminator='\n')
        w.writerow(['doc_id','court','grp','cat','date','street','house','level','tm'])
        n = 0
        for r in conn.execute('SELECT doc_id,court,grp,cat,date,street,house,level,tm FROM events'):
            w.writerow(['' if x is None else x for x in r]); n += 1
    return n

WORKERS  = 4
DELAY    = 0.12          # пауза кожного потоку між запитами
PRIORITY = ['1_PUBLIC_ORDER','2_ALCOHOL_TRADE','4_VIOLENCE','7_ENVIRONMENT',
            '3_DRUGS','5_PROPERTY','6_TRAFFIC']
SKIP     = {'8_DOMESTIC'}   # приватні адреси - на публічну карту не йдуть

UA = 'Mozilla/5.0 (edrsr-research-academy; educational use)'

def rtf_to_text(raw: bytes) -> str:
    s = raw.decode('latin-1', 'ignore')
    s = re.sub(r'\\par\b', '\n', s)
    s = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\\[a-zA-Z]+-?[0-9]*\s?', '', s)
    s = s.replace('{', '').replace('}', '')
    t = s.encode('latin-1', 'ignore').decode('cp1251', 'ignore')
    return re.sub(r'[ \t]+', ' ', t)

def init_db():
    os.makedirs(DATA, exist_ok=True)
    c = sqlite3.connect(DB, check_same_thread=False)
    c.execute("""CREATE TABLE IF NOT EXISTS events(
        doc_id TEXT PRIMARY KEY, court TEXT, grp TEXT, cat TEXT,
        date TEXT, street TEXT, house TEXT, level TEXT, tm TEXT, err TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS i_lvl ON events(level)")
    c.commit()
    return c

def load_tasks(done):
    rows, seen = [], set()
    files = sorted(glob.glob(os.path.join(DATA, 'kyiv_*.csv')))
    if not files:
        print('ПОМИЛКА: покладіть kyiv_2024.csv тощо у папку data'); sys.exit(1)
    for fp in files:
        with open(fp, encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                d = r['doc_id']
                if d in seen or d in done: continue
                if r['group'] in SKIP: continue
                seen.add(d); rows.append(r)
    order = {g: i for i, g in enumerate(PRIORITY)}
    rows.sort(key=lambda r: (order.get(r['group'], 99), r['date']), reverse=False)
    return rows

# Маркер одноразового перерахунку адрес. Зберігається як рядок у базі,
# тож потрапляє у знімок і переживає перезапуски. Геокоду в нього немає,
# тож ні на карті, ні в моделі він не з'являється.
SENTINEL = '__vypravlennia_adres_2026_09__'

def recheck_addresses(conn):
    """Одноразово прибирає записи, де старий витягувач підставив АДРЕСУ СУДУ
    замість місця події (див. addr.py: раніше при відсутності чистого
    кандидата функція повертала відкинутий — тобто шапку вироку).
    Видалені підуть на повторне завантаження вже з виправленим кодом.

    ВАЖЛИВО: чіпаємо лише ті документи, які є в наявних kyiv_*.csv.
    Інакше на сервері, де крок 0 качає тільки поточний рік, записи 2024
    року було б видалено й ніколи не відновлено.
    """
    if conn.execute('SELECT 1 FROM events WHERE doc_id=?', (SENTINEL,)).fetchone():
        return 0
    excl = set()
    for f in ('vykluchennya.txt', 'vykluchennya_moyi.txt'):
        p = os.path.join(DATA, f)
        if not os.path.exists(p): continue
        for ln in open(p, encoding='utf-8'):
            ln = ln.split('#')[0].strip()
            if ln: excl.add(ln.lower())
    if not excl:
        return 0            # без списку установ вирішувати немає чим — не чіпаємо
    have = set()
    for fp in sorted(glob.glob(os.path.join(DATA, 'kyiv_*.csv'))):
        with open(fp, encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                have.add(r['doc_id'])
    if not have:
        return 0
    bad = []
    for doc, st, hs in conn.execute(
            "SELECT doc_id, street, house FROM events WHERE level='house'"):
        if doc not in have: continue
        a = ((st + ', ' + hs) if (st and hs) else (st or '')).lower()
        if a in excl: bad.append((doc,))
    if bad:
        conn.executemany('DELETE FROM events WHERE doc_id=?', bad)
    conn.execute('INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?,?,?,?)',
                 (SENTINEL, '', '', '', '', None, None, 'marker', None,
                  'адреси перераховано після виправлення addr.py'))
    conn.commit()
    return len(bad)

def main():
    conn = init_db()
    if not conn.execute('SELECT 1 FROM events LIMIT 1').fetchone():
        k = snapshot_load(conn)
        if k: print(f'відновлено зі знімка: {k:,}')
    n = recheck_addresses(conn)
    if n:
        print(f'на повторне завантаження (була адреса установи): {n:,}')
    done = {r[0] for r in conn.execute('SELECT doc_id FROM events')}
    print(f'вже оброблено: {len(done):,}')
    tasks = load_tasks(done)
    print(f'до обробки:    {len(tasks):,}')
    lim = int(os.environ.get('MAX_DOCS', '0'))
    if lim and len(tasks) > lim:
        tasks = tasks[:lim]
        print(f'обмеження MAX_DOCS: цього запуску {lim:,}')
    if not tasks:
        print('усе вже завантажено.'); return
    est = len(tasks) * DELAY / WORKERS / 3600
    print(f'орієнтовний час: {est:.1f} год\n')

    q = queue.Queue()
    for t in tasks: q.put(t)
    lock = threading.Lock()
    stats = {'ok': 0, 'hit': 0, 'err': 0}
    buf = []

    def flush(force=False):
        with lock:
            if len(buf) >= 200 or (force and buf):
                try:
                    conn.executemany('INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?,?,?,?)', buf)
                    conn.commit(); buf.clear()
                except Exception as e:
                    print('ПОМИЛКА ЗАПИСУ В БАЗУ:', e)
                    raise

    def worker():
      try:
        while True:
            try: r = q.get_nowait()
            except queue.Empty: return
            rec = None
            for attempt in range(3):
                try:
                    rq = urllib.request.Request(r['doc_url'], headers={'User-Agent': UA})
                    with urllib.request.urlopen(rq, timeout=45) as resp:
                        raw = resp.read()
                    res = A.extract(rtf_to_text(raw))
                    rec = (r['doc_id'], r['court'], r['group'], r['category_code'], r['date'],
                           res['street'], res['house'], res['level'], res['time'], None)
                    break
                except Exception as e:
                    if attempt == 2:
                        rec = (r['doc_id'], r['court'], r['group'], r['category_code'], r['date'],
                               None, None, 'error', None, str(e)[:120])
                    else:
                        time.sleep(1.5 * (attempt + 1))
            with lock:
                buf.append(rec)
                if rec[7] == 'error': stats['err'] += 1
                else:
                    stats['ok'] += 1
                    if rec[7] == 'house': stats['hit'] += 1
                n = stats['ok'] + stats['err']
            flush()
            if n % 500 == 0:
                pct = 100 * stats['hit'] / max(stats['ok'], 1)
                print(f"  {n:,} / {len(tasks):,}   з адресою {stats['hit']:,} ({pct:.0f}%)   помилок {stats['err']}")
            time.sleep(DELAY)
      except Exception:
        import traceback; traceback.print_exc()

    ths = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
    t0 = time.time()
    for t in ths: t.start()
    try:
        for t in ths: t.join()
    except KeyboardInterrupt:
        print('\nзупинено. прогрес збережено, наступний запуск продовжить.')
    flush(True)
    k = snapshot_save(conn)
    print(f"\n=== ГОТОВО за {(time.time()-t0)/60:.0f} хв ===")
    print(f"оброблено {stats['ok']:,}, з адресою {stats['hit']:,}, помилок {stats['err']}")
    print(f"знімок збережено: {k:,} записів -> data/events.csv.gz")

if __name__ == '__main__':
    main()

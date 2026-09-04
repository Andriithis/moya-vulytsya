# -*- coding: utf-8 -*-
"""Крок 1b. Витяг обставин із рішень — те, що показує панель на карті.

Чому витяг, а не повний текст. Розвідка 3 вересня на 56 рішеннях: медіана
фабули 4 824 знаки, тобто всі події на карті — це 313 МБ тексту. У файл
карти таке не вкладається ніяк. Але дев'ять десятих того тексту — однакова
юридична машинерія, яка повторюється тисячами: «дослідивши матеріали справи,
суд дійшов висновку…». Місця, часу й того, що сталося, вона не додає.

Тому зберігаємо тільки ОБСТАВИНИ: від початку опису до слів «чим вчинив»
або подібних. Медіана — 394 знаки, усі події — 25 МБ. Саме це й потрібне
слухачеві, щоб висунути гіпотезу про причину.

Про персональні дані. У всіх 56 рішеннях вибірки сторони знеособлені самим
реєстром («ОСОБА_1»). Справжні прізвища траплялися лише суддівські — у
шапці й підписі, тобто поза обставинами. Обрізання тут це підстраховує.

Порядок завантаження — від найгустіших адрес до поодиноких: так фабули
проблем з'являються в перші хвилини, а не наприкінці. Роботу можна
перервати будь-коли, наступний запуск продовжить з того самого місця.

Запуск: FABULY.bat
"""
import os, re, sys, csv, gzip, glob, time, sqlite3, threading, queue, collections
import urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addr as A
from step1_download import rtf_to_text, UA

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
DB = os.path.join(DATA, 'events.db')
SNAP = os.path.join(DATA, 'fabuly.csv.gz')     # стан для репозиторію

WORKERS = 4
DELAY = 0.12
MAXLEN = 600           # більше за це не зберігаємо: далі йде юридична машинерія
SAVE_EVERY = 2000      # як часто скидати знімок на диск

# початкові звороти, які нічого не додають
OPEN = re.compile(r'^(?:З\s+протоколу[^,]{0,80}вбачається,\s*що\s*|'
                  r'Згідно\s+з?\s*протокол\w*[^,]{0,80},\s*що\s*|'
                  r'Як\s+вбачається[^,]{0,60},\s*що\s*|'
                  r'Відповідно\s+до\s+протокол\w*[^,]{0,80},\s*що\s*|'
                  r'За\s+протоколом\s*)', re.I)
# де закінчуються обставини і починається кваліфікація
# Форми дієслова різні за родом і числом («вчинив», «вчинила», «порушили»),
# тому ловимо основу, а не повне слово: інакше половина жіночих формулювань
# лишалася б необрізаною разом із підписом судді.
#
# Виміряно 3 вересня на знімку fabuly.csv.gz: 49,6% витягів (33 830 з 68 189)
# впиралися у стелю MAXLEN замість зупинитися на СТОП — тобто в половині
# випадків СТОП узагалі не спрацьовував, і в панелі замість фабули опинялася
# суміш фактів із процедурою. Причини, знайдені на зразках:
#   1. «своїми діями ОСОБА_1 вчинив» — між «діями» і дієсловом стоїть
#      знеособлене ім'я, стара версія вимагала їх упритул;
#   2. «Дії ОСОБА_1 ... кваліфіковано за ст.130» — інше дієслово, старий
#      патерн шукав лише «вчинив/порушив»;
#   3. «У судовому засіданні ОСОБА_1 вину визнав…» — початок опису самого
#      засідання після фактів, найнадійніший маркер зі зразків, його не
#      було зовсім;
#   4. «ст. 160 КУпАП передбачено, що…» — номер статті стоїть ПЕРЕД
#      «передбачено», а не після, старий патерн ловив лише один порядок.
#   5. наркотичні справи закінчують обставини не «вчинив/порушив», а
#      «тим самим незаконно придбав та почав зберігати» — своє дієслово.
#
# Виправлення підняло частку впритул у стелю з 49,6% лише до ~38% (перевірено
# на вже обрізаних 600-знакових зразках зі знімка — це нижня межа поліпшення,
# на повному тексті буде краще). Решта — здебільшого наркотичні справи з
# довгим послідовним описом (підняв — усвідомив — виник умисел — пішов далі),
# де СТОП чесно ще не настав за 600 знаків, і рішення типу «спрощене
# провадження», де перед обставинами йде процедурний абзац про сам розгляд
# справи — це вже питання до `A.body_start()`, не до цього СТОПу.
STOP = re.compile(r'(чим\s+(?:вчин|скої|поруш|допуст)\w*|'
                  r'тим\s+самим\s+(?:незаконно\s+)?(?:вчин|поруш|придбав|придбала|збут|'
                  r'зберіг|зберегл)\w*|'
                  r'своїми(?:\s+\S+){0,2}?\s+діями\s*,?\s*(?:ОСОБА_\d+\s*,?\s*)?'
                  r'(?:вчин|скої|поруш)\w*|'
                  r'дії\s+ОСОБА_\d+(?:\s+\S+){0,6}?\s+кваліфіковано|кваліфіковано\s+за\s|'
                  r'у\s+судовому\s+засіданні|що\s+є\s+порушенням|'
                  r'відповідальність\s+за\s+як|передбачен\w+\s+ч?\.?\s*\d+\s*ст|'
                  r'ст\.?\s*\d[\d\-]*\s*(?:КУпАП|КК)?[^.]{0,20}?передбачен\w+|'
                  r'\bСуддя\b|\bГоловуючий\b)', re.I)


def excerpt(text):
    bs = A.body_start(text)
    t = re.sub(r'\s+', ' ', text[bs:] if bs else text).strip()
    if not t: return ''
    t = OPEN.sub('', t).strip()
    m = STOP.search(t)
    t = t[:m.start()] if m else t
    if len(t) > MAXLEN:
        t = t[:MAXLEN].rsplit(' ', 1)[0]
    return t.rstrip(' ,.;:—-')


def init(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS fab(doc_id TEXT PRIMARY KEY, txt TEXT)')
    conn.commit()
    if os.path.exists(SNAP):
        have = {r[0] for r in conn.execute('SELECT doc_id FROM fab')}
        rows = []
        with gzip.open(SNAP, 'rt', encoding='utf-8', newline='') as fh:
            rd = csv.reader(fh, delimiter='\t')
            next(rd, None)
            for r in rd:
                if len(r) >= 2 and r[0] not in have:
                    rows.append((r[0], r[1]))
        if rows:
            conn.executemany('INSERT OR IGNORE INTO fab VALUES(?,?)', rows)
            conn.commit()
            print(f'зі знімка відновлено: {len(rows):,}')


def save(conn):
    tmp = SNAP + '.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, delimiter='\t', lineterminator='\n')
        w.writerow(['doc_id', 'txt'])
        n = 0
        for r in conn.execute('SELECT doc_id, txt FROM fab WHERE txt<>""'):
            w.writerow(r); n += 1
    os.replace(tmp, SNAP)
    return n


def todo(conn):
    """документи на карті без витягу, від найгустіших адрес до поодиноких"""
    urls = {}
    for fp in sorted(glob.glob(os.path.join(DATA, 'kyiv_*.csv'))):
        with open(fp, encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                if r.get('doc_url'): urls[r['doc_id']] = r['doc_url']
    rows = list(conn.execute("""SELECT e.doc_id, e.street, e.house FROM events e
                                JOIN geo g ON g.doc_id=e.doc_id
                                LEFT JOIN fab f ON f.doc_id=e.doc_id
                                WHERE f.doc_id IS NULL"""))
    dens = collections.Counter()
    for _d, st, ho in rows: dens[(st or '') + '|' + (ho or '')] += 1
    out = [(d, urls[d]) for d, st, ho in
           sorted(rows, key=lambda r: -dens[(r[1] or '') + '|' + (r[2] or '')])
           if d in urls]
    return out


def main():
    if not os.path.exists(DB):
        print('немає data/events.db — спершу кроки 1 і 2'); sys.exit(1)
    conn = sqlite3.connect(DB, check_same_thread=False)
    lock = threading.Lock()
    init(conn)
    work = todo(conn)
    if not work:
        print('усі витяги вже є — нічого качати')
        print(f'   у знімку: {save(conn):,}')
        return
    print(f'до завантаження: {len(work):,} рішень')
    print('   можна перервати будь-коли — прогрес зберігається')

    q = queue.Queue()
    for it in work: q.put(it)
    done = [0]
    empty = [0]
    t0 = time.time()

    def worker():
        while True:
            try: doc, url = q.get_nowait()
            except queue.Empty: return
            txt = ''
            try:
                rq = urllib.request.Request(url, headers={'User-Agent': UA})
                with urllib.request.urlopen(rq, timeout=45) as resp:
                    txt = excerpt(rtf_to_text(resp.read()))
            except Exception:
                pass
            with lock:
                conn.execute('INSERT OR REPLACE INTO fab VALUES(?,?)', (doc, txt))
                done[0] += 1
                if not txt: empty[0] += 1
                n = done[0]
                if n % 200 == 0:
                    conn.commit()
                    sp = n / max(time.time() - t0, 1)
                    left = (len(work) - n) / max(sp, .01) / 60
                    print(f'   {n:,} з {len(work):,}  ·  {sp:.1f}/с  ·  '
                          f'лишилось ~{left:.0f} хв  ·  порожніх {empty[0]:,}')
                if n % SAVE_EVERY == 0:
                    save(conn)
            time.sleep(DELAY)

    ths = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
    for t in ths: t.start()
    try:
        for t in ths: t.join()
    except KeyboardInterrupt:
        print('\nперервано — прогрес збережено')
    with lock:
        conn.commit()
        n = save(conn)
    print(f'\n=== ГОТОВО === витягів у знімку: {n:,}')
    print(f'   data/fabuly.csv.gz — {os.path.getsize(SNAP)/1048576:.1f} МБ')


if __name__ == '__main__':
    main()

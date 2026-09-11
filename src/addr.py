# -*- coding: utf-8 -*-
import re
from dataclasses import dataclass, asdict

EXTRACTION_VERSION = 'location-roles-v1'

TYPES = [
 (r'вул(?:иц[іяею])?\.?', 'вул.'),
 (r'просп(?:ект[уі]?)?\.?', 'просп.'),
 (r'бульв(?:ар[уі]?)?\.?|б-р\.?', 'бульв.'),
 (r'пров(?:улок|улку|\.)?', 'пров.'),
 (r'площ[аіі]|пл\.', 'пл.'),
 (r'шосе', 'шосе'),
 (r'наб(?:ережн\w*)?\.?', 'наб.'),
 (r'узвіз|узвозу', 'узвіз'),
 (r'алея|алеї', 'алея'),
 (r'мікрорайон|м-н', 'мкр.'),
]
TYPE_RE = '(?:' + '|'.join(t for t,_ in TYPES) + ')'
NAME = r"[А-ЯІЇЄҐ][А-Яа-яІіЇїЄєҐґ'`’\-\s\.]{1,40}?"
HOUSE = r"(\d{1,4}\s*(?:[-/]\s*\d{1,3})?\s*(?:[А-ЯA-Za-zа-я])?)"

# variant A: type before name   "вул. Лугова, 16"
PA = re.compile(rf"\b({TYPE_RE})\s*({NAME})[,\s]+(?:буд(?:инок|\.)?\s*)?№?\s*{HOUSE}\b", re.U)
# variant B: name before type   "Дніпровська набережна, буд. 33"
PB = re.compile(rf"\b({NAME})\s+(вулиц[іяею]|проспект[уі]?|бульвар[уі]?|провулок|провулку|набережн\w+|площ[аіі]|шосе|узвіз)[,\s]+(?:буд(?:инок|\.)?\s*)?№?\s*{HOUSE}\b", re.U)
# street only, no house
PS = re.compile(rf"\b({TYPE_RE})\s*({NAME})(?=[,\.\s])", re.U)

TIME = re.compile(r"(?:о|близько|приблизно|орієнтовно)?\s*(\d{1,2})\s*(?:год|:)\s*(\d{2})?", re.U)
NOISE = re.compile(r"(суд|прокурат|поліці|управлінн|відділ|райвідділ|адвокат|канцеляр|проживає|зареєстрован|мешка|місце проживання|УПП|ГУНП|РУП)", re.I|re.U)
STOP = {'києва','київ','києві','україни','район','районного','районний','місто','міста'}

def norm_street(t, n):
    n = re.sub(r'\s+', ' ', n).strip(" ,.-'`’")
    n = re.sub(r'\s*(м\.?\s*Києв\w*|міста Києва|Київ\w*)\s*$', '', n, flags=re.I).strip()
    for pat, canon in TYPES:
        if re.fullmatch(pat, t, re.U): t = canon; break
    return t, n

def norm_house(h):
    h = re.sub(r'\s+', '', h).upper().strip('.,')
    # "буд. 6 у м. Києві" -> парсер ловить "6У"; літера У як індекс будинку не вживається
    h = re.sub(r'У$', '', h)
    # провідні нулі: "04" -> "4"
    h = re.sub(r'^0+(\d)', r'\1', h)
    return h or None

def find_all(text):
    """returns list of (street_type, street_name, house|None, position)"""
    out = []
    for m in PA.finditer(text):
        t, n = norm_street(m.group(1), m.group(2))
        if not n or n.lower() in STOP or len(n) < 3: continue
        out.append((t, n, norm_house(m.group(3)), m.start()))
    for m in PB.finditer(text):
        raw_t = m.group(2)
        t = ('наб.' if 'абережн' in raw_t else 'вул.' if 'улиц' in raw_t
             else 'просп.' if 'роспект' in raw_t else 'бульв.' if 'ульвар' in raw_t
             else 'пров.' if 'ровул' in raw_t else 'пл.' if 'лощ' in raw_t
             else 'шосе' if 'шосе' in raw_t else 'узвіз')
        n = re.sub(r'\s+',' ',m.group(1)).strip(" ,.-'`")
        if not n or n.lower() in STOP or len(n) < 3: continue
        full = n if t!='наб.' else n
        out.append((t, full, norm_house(m.group(3)), m.start()))
    return out

def context_ok(text, pos, win=170, floor=0):
    """чи немає перед адресою слів, що виказують адресу установи.
    `floor` не дає вікну зазирнути в шапку: слова «суд», «прокуратура»
    там стоять завжди й не стосуються адреси, названої вже у фабулі."""
    seg = text[max(floor, pos-win):pos]
    return not NOISE.search(seg)

# Фабула починається після слова ВСТАНОВИВ. Усе, що ДО нього, — шапка:
# назва суду, склад суду й АДРЕСА ПРИМІЩЕННЯ СУДУ. Саме звідти бралася
# адреса у 63% кримінальних справ (у КУпАП — лише 3,5%, бо там місце
# вчинення названо в самому протоколі).
BODY = re.compile(r'(?:в|у)\s*с\s*т\s*а\s*н\s*о\s*в\s*и\s*(?:в|л[аио])\s*[:,\.]?', re.I|re.U)

def body_start(text):
    """позиція, з якої починається опис події; 0 — якщо маркера немає"""
    best = None
    for m in BODY.finditer(text):
        # маркер-заголовок: з нового рядка або з двокрапкою після
        head = (m.start() == 0 or text[m.start()-1] in '\n\r\t ')
        colon = m.group(0).rstrip().endswith(':')
        if head and colon: return m.end()
        if best is None: best = m.end()
    return best or 0

def extract(text):
    """best (street, house, time) for the offence event"""
    candidates = extract_candidates(text)
    selected = select_event_candidate(candidates)
    result = dict(street=None, house=None, level='none', time=None,
                  candidates=[asdict(c) for c in candidates],
                  extraction_version=EXTRACTION_VERSION)
    if selected:
        result.update(street=selected.street, house=selected.house,
                      level='house' if selected.house else 'street',
                      time=find_time(selected.context))
    return result


@dataclass(frozen=True)
class AddressCandidate:
    street: str
    house: str | None
    start: int
    end: int
    raw: str
    context: str
    context_start: int
    role: str
    reason: str
    version: str = EXTRACTION_VERSION


# Заборонені ролі мають пріоритет над ознаками події в тому самому фрагменті.
ROLE_PATTERNS = [(role, re.compile(pattern, re.I)) for role, pattern in (
    ('COURT', r'\bсуд\w*|\bканцеляр\w*'),
    ('RESIDENCE', r'прожива\w*|проживан\w*|мешка\w*|зареєстрован\w*|реєстраці\w*|житл\w*'),
    ('WORKPLACE', r'працю\w*|робоч\w*\s+місц\w*|місц\w*\s+робот\w*|роботодав\w*'),
    ('PROPERTY', r'власност\w*|належ\w*|нерухом\w*|оренд\w*'),
    ('INSTITUTION', r'прокурат\w*|поліці\w*|управлін\…4112 tokens truncated…:,} записів')
        print('усе вже завантажено.'); return

    est = len(tasks) * DELAY / WORKERS / 3600
    print(f'орієнтовний час: {est:.1f} год\n')

    q = queue.Queue()
    for t in tasks: q.put(t)
    lock = threading.Lock()
    stats = {'ok': 0, 'hit': 0, 'err': 0}
    buf = []
    evidence_buf = []
    completed = []

    def flush(force=False):
        with lock:
            if len(buf) >= 200 or (force and buf):
                try:
                    conn.executemany('INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?,?,?,?)', buf)
                    for doc_id, candidates in evidence_buf:
                        LE.save_evidence(conn, doc_id, candidates)
                    conn.commit(); buf.clear(); evidence_buf.clear()
                except Exception as e:
                    print('ПОМИЛКА ЗАПИСУ В БАЗУ:', e)
                    raise

    def worker():
      try:
        while True:
            try: r = q.get_nowait()
            except queue.Empty: return
            rec = None
            candidates = []
            for attempt in range(3):
                try:
                    rq = urllib.request.Request(r['doc_url'], headers={'User-Agent': UA})
                    with urllib.request.urlopen(rq, timeout=45) as resp:
                        raw = resp.read()
                    res = A.extract(rtf_to_text(raw))
                    candidates = res['candidates']
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
                evidence_buf.append((r['doc_id'], candidates))
                completed.append(r['doc_id'])
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

    if database_url:
        from pipeline.postgres_tasks import mark_processed
        changed = mark_processed(database_url, completed + inactive_ids + skipped_db_ids)
        print(f'позначено обробленими у PostgreSQL: {changed:,}')

    print(f"\n=== ГОТОВО за {(time.time()-t0)/60:.0f} хв ===")
    print(f"оброблено {stats['ok']:,}, з адресою {stats['hit']:,}, помилок {stats['err']}")
    print(f"знімок збережено: {k:,} записів -> data/events.csv.gz")

if __name__ == '__main__':
    main()

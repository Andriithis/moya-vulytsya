# -*- coding: utf-8 -*-
import re

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
    cands = find_all(text)
    bs = body_start(text)
    # 1) чисті кандидати з ОПИСУ ПОДІЇ (після ВСТАНОВИВ) — найнадійніші
    inb = [c for c in cands if c[3] >= bs and context_ok(text, c[3], floor=bs)]
    # 2) якщо опису немає або в ньому адреси немає — чисті з усього тексту
    good = [c for c in cands if context_ok(text, c[3])]
    pool = inb or good
    if not pool:
        # Свідомо НЕ повертаємось до відкинутих кандидатів. Раніше тут стояло
        # `pool = good if good else cands`, і коли чистих не було, функція
        # віддавала адресу суду з позначкою level='house' — тобто вигадувала
        # місце події. Краще чесне «адреси немає», ніж хибна точність.
        m = PS.search(text[bs:] or text)
        if m:
            t, n = norm_street(m.group(1), m.group(2))
            if n and n.lower() not in STOP and len(n) >= 3 and context_ok(text, bs + m.start(), floor=bs):
                return dict(street=f"{t} {n}", house=None, level='street', time=find_time(text))
        return dict(street=None, house=None, level='none', time=None)
    t, n, h, p = pool[0]
    return dict(street=f"{t} {n}", house=h, level='house' if h else 'street',
                time=find_time(text, p))

def find_time(text, pos=None):
    seg = text[max(0,(pos or 0)-320):(pos or 0)+120] if pos else text[:2500]
    best=None
    for m in re.finditer(r"(?:о|близько|приблизно|орієнтовно)\s*(\d{1,2})\s*(?:год|:)\s*(\d{2})?", seg, re.U):
        hh=int(m.group(1)); mm=int(m.group(2) or 0)
        if 0<=hh<=23 and 0<=mm<=59: best=f"{hh:02d}:{mm:02d}"
    return best

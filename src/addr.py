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
    ('INSTITUTION', r'прокурат\w*|поліці\w*|управлін\w*|відділ\w*|лікарн\w*|установ\w*|підприємств\w*|\bТОВ\b|\bГУНП\b|\bРУП\b|\bУПП\b'),
)]
EVENT_CUE = re.compile(
    r'\b(?:керував|керувала|викрав|викрала|вчинив|вчинила|скоїв|скоїла|'
    r'наніс|нанесла|завдав|завдала|пошкодив|пошкодила|збував|збувала)\b|'
    r'\b(?:сталася|сталось|сталося)\s+(?:ДТП|крадіжка|зіткнення)\b', re.I)
LOCATIVE = re.compile(r'\b(?:за\s+адресою|по|на|біля|поблизу)\s*$', re.I)
UNSAFE_CONTEXT = re.compile(
    r'\bне\b|\bнібито\b|\bможливо\b|\bякби\b|\bзапереч\w*|'
    r'\bклопотан\w*|\bобшук\w*|\bогляд\w*|\bдостав\w*|\bзобов\w*|'
    r'\bзатрим\w*|\bповіст\w*|\bвиклик\w*|'
    r'\bпросить\b|\bдозвіл\b|\bтимчасов\w*\s+доступ\w*', re.I)
# Крапки у «вул.», «буд.», «м.» та 01.09.2026 не є межами речення.
CLAUSE_BREAK = re.compile(r'[;!?\n\r]+|(?<=[а-яіїєґ0-9»])\.(?=\s+[А-ЯІЇЄҐ])')


def extract_candidates(text):
    """Усі розпізнані згадки адрес, без втрати повторів та їхнього контексту.

    Це консервативні правила, не виміряна ймовірність і не повне розуміння
    судового тексту. Непідтриманий або неоднозначний опис лишається UNKNOWN.
    """
    matches = []
    for pattern, reverse in ((PA, False), (PB, True)):
        for m in pattern.finditer(text):
            t, n = norm_street(m.group(2 if reverse else 1), m.group(1 if reverse else 2))
            if not n or n.lower() in STOP or len(n) < 3:
                continue
            if any(m.start() < end and m.end() > start for start, end, *_ in matches):
                continue
            matches.append((m.start(), m.end(), f'{t} {n}', norm_house(m.group(3))))
    # Вулиця без номера: повна назва до пунктуації, не перше слово назви.
    street_only = re.compile(rf'\b({TYPE_RE})\s*({NAME})(?=[,;\n.!?]|$)', re.U)
    for m in street_only.finditer(text):
        if any(m.start() < end and m.end() > start for start, end, *_ in matches):
            continue
        t, n = norm_street(m.group(1), m.group(2))
        if n and n.lower() not in STOP and len(n) >= 3:
            matches.append((m.start(), m.end(), f'{t} {n}', None))
    matches.sort()
    # Не розбиваємо речення всередині самої адреси.
    breaks = [m for m in CLAUSE_BREAK.finditer(text)
              if not any(a <= m.start() < b for a, b, *_ in matches)]
    bs = body_start(text)
    out = []
    for start, end, street, house in matches:
        left = max([m.end() for m in breaks if m.end() <= start] + [0])
        right = min([m.start() for m in breaks if m.start() >= end] + [len(text)])
        if start >= bs:
            left = max(left, bs)
        context = text[left:right]
        # Назва вулиці «Судова» / «Лікарняна» не визначає роль адреси.
        masked = list(context)
        for a, b, *_ in matches:
            if left <= a and b <= right:
                masked[a-left:b-left] = ' ' * (b-a)
        prose = ''.join(masked)
        role, reason = 'UNKNOWN', 'no_explicit_event_link'
        for name, pattern in ROLE_PATTERNS:
            if pattern.search(prose):
                role, reason = name, 'non_event_context'
                break
        else:
            count = sum(left <= a and b <= right for a, b, *_ in matches)
            if start < bs:
                reason = 'document_header'
            elif count != 1:
                reason = 'multiple_addresses_in_clause'
            elif UNSAFE_CONTEXT.search(prose):
                reason = 'negated_or_procedural_context'
            else:
                prefix = text[left:start]
                cue = EVENT_CUE.search(prefix)
                locative = LOCATIVE.search(prefix)
                if cue and locative and cue.end() <= locative.start():
                    bridge = prefix[cue.end():locative.start()]
                    if not re.search(r'[,;:]|\b(?:а|але|потім|після|де|коли)\b', bridge, re.I):
                        role, reason = 'EVENT_LOCATION', 'explicit_event_and_locative'
        out.append(AddressCandidate(street, house, start, end, text[start:end],
                                    context, left, role, reason))
    return out


def select_event_candidate(candidates):
    """Один підтверджений адресний ключ; конфлікт ролей не вирішуємо навмання."""
    events = [c for c in candidates if c.role == 'EVENT_LOCATION']
    keys = {(c.street.casefold(), c.house) for c in events}
    if len(keys) != 1:
        return None
    if any((c.street.casefold(), c.house) in keys and c.role != 'EVENT_LOCATION'
           for c in candidates):
        return None
    return events[0]

def find_time(text, pos=None):
    seg = text[max(0,(pos or 0)-320):(pos or 0)+120] if pos else text[:2500]
    best=None
    for m in re.finditer(r"(?:о|близько|приблизно|орієнтовно)\s*(\d{1,2})\s*(?:год|:)\s*(\d{2})?", seg, re.U):
        hh=int(m.group(1)); mm=int(m.group(2) or 0)
        if 0<=hh<=23 and 0<=mm<=59: best=f"{hh:02d}:{mm:02d}"
    return best

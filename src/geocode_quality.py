"""Консервативне геокодування: точний будинок, однозначний збіг, межа міста.

Confidence — клас доказу за правилами, не виміряна ймовірність правильності.
"""
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

POLICY_VERSION = 'kyiv-exact-house-v2'
MIN_CONFIDENCE = 1.0
DATA = Path(__file__).resolve().parents[1] / 'data'
REFERENCE = DATA.parent / 'config/geocoding'
BOUNDARY = REFERENCE / 'kyiv_boundary.geojson'
ALIASES = REFERENCE / 'street_aliases.json'
OSM = DATA / 'osm_kyiv_city.json'

TYPES = {
    'вулиця': 'вул', 'вулиці': 'вул', 'вулицю': 'вул', 'вул': 'вул',
    'проспект': 'просп', 'проспекті': 'просп', 'проспекту': 'просп', 'просп': 'просп',
    'провулок': 'пров', 'провулку': 'пров', 'пров': 'пров',
    'бульвар': 'б-р', 'бульвару': 'б-р', 'бульварі': 'б-р', 'бульв': 'б-р', 'б-р': 'б-р',
    'площа': 'пл', 'площі': 'пл', 'пл': 'пл', 'узвіз': 'узвіз', 'узвозу': 'узвіз',
    'набережна': 'наб', 'набережної': 'наб', 'наб': 'наб', 'шосе': 'шосе',
}


def clean(value):
    value = unicodedata.normalize('NFC', value or '').casefold()
    for apostrophe in ('’', 'ʼ', '`'):
        value = value.replace(apostrophe, "'")
    return re.sub(r'\s+', ' ', value).strip(' ,.')


def street_key(value):
    value = clean(value)
    words = value.replace('.', ' ').split()
    if len(words) < 2:
        return ''
    if words[0] in TYPES:
        return TYPES[words[0]] + '|' + ' '.join(words[1:])
    if words[-1] in TYPES:
        return TYPES[words[-1]] + '|' + ' '.join(words[:-1])
    # Тип невідомий: не вгадуємо вулицю замість проспекту/провулка.
    return ''


def house_key(value):
    value = clean(value).upper().replace('\\', '/')
    value = re.sub(r'\s+', '', value)
    # Не відкидаємо корпус, літеру чи частину дробового номера.
    return value if re.fullmatch(r'\d+[А-ЯІЇЄҐA-Z]?(?:/\d+[А-ЯІЇЄҐA-Z]?)?', value) else ''


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def segments_intersect(a, b, c, d):
    def cross(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
    ab = cross(a, b, c), cross(a, b, d)
    cd = cross(c, d, a), cross(c, d, b)
    return (max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0]))
            and max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1]))
            and ab[0]*ab[1] <= 0 and cd[0]*cd[1] <= 0)


class Boundary:
    def __init__(self, feature):
        props = feature.get('properties', {})
        if (feature.get('type') != 'Feature' or props.get('name') != 'Київ'
                or props.get('boundary') != 'administrative'
                or str(props.get('admin_level')) != '4'
                or not str(props.get('source_url', '')).startswith('https://')
                or not props.get('reviewed_at')):
            raise ValueError('Потрібна перевірена адміністративна межа Києва з джерелом і датою')
        geom = feature.get('geometry', {})
        if geom.get('type') not in ('Polygon', 'MultiPolygon'):
            raise ValueError('Межа має бути Polygon або MultiPolygon')
        polygons = geom.get('coordinates', [])
        self.polygons = [polygons] if geom['type'] == 'Polygon' else polygons
        if not self.polygons:
            raise ValueError('Порожня межа')
        for polygon in self.polygons:
            if not polygon:
                raise ValueError('Порожній полігон')
            for ring in polygon:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError('Незамкнене кільце межі')
                if any(len(p) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in p)
                       or not (29 < p[0] < 32 and 49 < p[1] < 52) for p in ring):
                    raise ValueError('Непридатні координати межі Києва')
                edges = list(zip(ring, ring[1:]))
                if abs(sum(a[0]*b[1]-b[0]*a[1] for a, b in edges)) < 1e-12:
                    raise ValueError('Нульова площа межі')
                for i, (a, b) in enumerate(edges):
                    if a == b:
                        raise ValueError('Нульовий відрізок межі')
                    for j in range(i+2, len(edges)):
                        if i == 0 and j == len(edges)-1:
                            continue
                        if segments_intersect(a, b, *edges[j]):
                            raise ValueError('Самоперетин межі')
            for i, hole in enumerate(polygon[1:], 1):
                if self.ring_contains(polygon[0], *hole[0]) is not True:
                    raise ValueError('Внутрішнє кільце поза зовнішнім')
                for other in polygon[:i]:
                    if any(segments_intersect(a, b, c, d)
                           for a, b in zip(hole, hole[1:]) for c, d in zip(other, other[1:])):
                        raise ValueError('Перетин кілець межі')
        self.hash = fingerprint(feature)

    @staticmethod
    def ring_contains(ring, x, y):
        inside = False
        for (ax, ay), (bx, by) in zip(ring, ring[1:]):
            cross = (x-ax)*(by-ay) - (y-ay)*(bx-ax)
            if abs(cross) < 1e-12 and min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by):
                return None  # На самій межі точку не допускаємо.
            if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
                inside = not inside
        return inside

    def contains(self, lat, lon):
        if not all(type(v) in (int, float) and math.isfinite(v) for v in (lat, lon)):
            return False
        for polygon in self.polygons:
            if self.ring_contains(polygon[0], lon, lat) is True:
                if all(self.ring_contains(hole, lon, lat) is False for hole in polygon[1:]):
                    return True
        return False


class Resolver:
    def __init__(self, rows, boundary, aliases=(), blocked=()):
        self.boundary = boundary
        self.blocked = set()
        for item in blocked:
            key = street_key(item['street'])
            if not key or not item.get('reason') or not item.get('source_url'):
                raise ValueError('Неоднозначна назва потребує джерела та причини')
            self.blocked.add(key)
        self.aliases = {}
        for item in aliases:
            old, new = street_key(item['old']), street_key(item['new'])
            if (not old or not new or old == new or not item.get('reviewed_at')
                    or not str(item.get('source_url', '')).startswith('https://')):
                raise ValueError('Перейменування потребує повних назв, джерела та перевірки')
            if old in self.aliases and self.aliases[old] != new:
                raise ValueError('Неоднозначне перейменування')
            self.aliases[old] = new
        # Цикли заборонені; послідовні перейменування підтримуються.
        for key in self.aliases:
            self.canonical(key)
        self.reference_hash = fingerprint([POLICY_VERSION, rows, boundary.hash, aliases, blocked])
        self.index = {}
        for street, house, lat, lon in rows:
            key = self.key(street, house)
            if key:
                self.index.setdefault(key, set()).add((lat, lon))

    def canonical(self, key):
        seen = set()
        while key in self.aliases:
            if key in seen:
                raise ValueError('Цикл перейменувань')
            seen.add(key)
            key = self.aliases[key]
        return key

    def key(self, street, house):
        original = street_key(street)
        st, h = self.canonical(original), house_key(house)
        if original in self.blocked or st in self.blocked:
            return ''
        return st + '|' + h if st and h else ''

    def resolve(self, street, house):
        matches = self.index.get(self.key(street, house), set())
        if len(matches) != 1:
            return None
        lat, lon = next(iter(matches))
        if not self.boundary.contains(lat, lon):
            return None
        return [lat, lon, 'house', 1.0]

    def cached(self, conn, street, house):
        key = self.key(street, house)
        conn.execute('''CREATE TABLE IF NOT EXISTS geocode_cache (
            reference_hash TEXT, address_key TEXT, result TEXT NOT NULL,
            PRIMARY KEY(reference_hash,address_key))''')
        found = conn.execute('SELECT result FROM geocode_cache WHERE reference_hash=? AND address_key=?',
                             (self.reference_hash, key)).fetchone()
        if found:
            return json.loads(found[0])
        result = self.resolve(street, house)
        conn.execute('INSERT INTO geocode_cache VALUES(?,?,?)',
                     (self.reference_hash, key, json.dumps(result)))
        return result


def load_resolver(rows=None):
    boundary = Boundary(json.loads(BOUNDARY.read_text(encoding='utf-8')))
    aliases = json.loads(ALIASES.read_text(encoding='utf-8'))
    if rows is None:
        rows = json.loads(OSM.read_text(encoding='utf-8'))
    return Resolver(rows, boundary, aliases['aliases'], aliases['blocked'])


def eligible_geo_ids(conn, resolver=None):
    """Повторна перевірка перед картою: старі geo не обходять нову політику."""
    try:
        from .location_evidence import confirmed_rows
    except ImportError:
        from location_evidence import confirmed_rows
    columns = {r[1] for r in conn.execute('PRAGMA table_info(geo)')}
    if not {'geocode_confidence', 'policy_version', 'reference_hash', 'address_key'} <= columns:
        return set()
    resolver = resolver or load_resolver()
    eligible = set()
    for doc, street, house in confirmed_rows(conn):
        row = conn.execute('''SELECT lat,lon,precision,geocode_confidence,policy_version,
                              reference_hash,address_key FROM geo WHERE doc_id=?''', (doc,)).fetchone()
        if not row or row[4:] != (POLICY_VERSION, resolver.reference_hash, resolver.key(street, house)):
            continue
        expected = resolver.resolve(street, house)
        if expected and list(row[:4]) == expected and row[3] >= MIN_CONFIDENCE:
            eligible.add(doc)
    return eligible

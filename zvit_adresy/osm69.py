# -*- coding: utf-8 -*-
"""ZAVDANNYA-69, крок 2: шари OpenStreetMap для табло й «Місць довкола» — з файлу міста (Geofabrik, як конвеєр).

  python zvit_adresy/osm69.py <misto.osm.pbf> <вихід.pkl>

Що береться (теги — у документі `docs/ZVIT-ADRESY-69.md`):
  * пішохідна мережа — усі `highway`, якими можна йти (без автомагістралей, будов і `foot=no`);
  * житлові будинки — `building=apartments|residential|house|detached|terrace|semidetached_house` (контур, поверхи);
  * зелень — `leisure=park|garden`, `landuse=forest|grass|meadow|village_green`, `natural=wood|scrub`;
  * об'єкти — метро, школи, садки, ТЦ, ринки, заклади з алкоголем, парки й сквери (з назвою), зупинки;
  * вулиці з назвою — для довжини вулиці.
Координати — метри від центру Києва (рівнопроміжна проєкція: на 40 км похибка < 0,1 %).
"""
import sys, re, pickle, math, collections
import osmium
import shapely
from shapely.geometry import Polygon, MultiPolygon

LAT0, LON0 = 50.45, 30.52
KY = 111132.0
KX = 111320.0 * math.cos(math.radians(LAT0))


def xy(lat, lon):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


NE_PISHKY = {'motorway', 'motorway_link', 'trunk_link', 'construction', 'proposed', 'raceway', 'bus_guideway', 'abandoned',
             'platform', 'elevator', 'escape', 'corridor', 'via_ferrata', 'services', 'rest_area'}
DOROGY_AVTO = {'trunk', 'primary', 'secondary', 'tertiary', 'unclassified', 'residential', 'living_street', 'service',
               'primary_link', 'secondary_link', 'tertiary_link', 'road', 'pedestrian'}
ZHYTLO = {'apartments', 'residential', 'house', 'detached', 'terrace', 'semidetached_house'}
ZELEN = [('leisure', {'park', 'garden'}), ('landuse', {'forest', 'grass', 'meadow', 'village_green'}),
         ('natural', {'wood', 'scrub'})]
NE_SHKOLA = re.compile(r'курс|автошкол|музич|мистецт|спортив|танц|англ|english|мовн|позашк|центр|студі|академі|'
                       r'коледж|технікум|університет', re.I)   # як karta-kyiv/src/mistse_zvit.py


def typ_obiekta(t):
    """теги -> тип об'єкта для «Місць довкола» або None"""
    a, sh, le, rw, hw = t.get('amenity'), t.get('shop'), t.get('leisure'), t.get('railway'), t.get('highway')
    nm = t.get('name:uk') or t.get('name') or ''
    if t.get('station') == 'subway' and rw == 'station':
        return 'metro'
    if a == 'school' and not NE_SHKOLA.search(nm):
        return 'shkola'
    if a == 'kindergarten':
        return 'sadok'
    if sh == 'mall':
        return 'tts'
    if a == 'marketplace':
        return 'rynok'
    if a in ('bar', 'pub', 'nightclub') or sh in ('alcohol', 'wine'):
        return 'alko'
    if le in ('park', 'garden') and nm:
        return 'park'
    if hw == 'bus_stop' or rw == 'tram_stop':
        return 'zupynka'
    return None


class Zbir(osmium.SimpleHandler):
    def __init__(s):
        super().__init__()
        s.vuzly = {}                 # id вузла -> індекс
        s.xy = []
        s.rebra = []                 # (i, j, довжина)
        s.vulytsi = collections.defaultdict(list)   # назва -> [лінія [(x, y)...]]
        s.dorogy = []                # (клас, назва, лінія) — для малюнка карти
        s.budynky = []               # dict
        s.zelen = []                 # полігони shapely
        s.obiekty = []               # dict(typ, nazva, x, y, poly)

    def _v(s, n):
        i = s.vuzly.get(n.ref)
        if i is None:
            i = s.vuzly[n.ref] = len(s.xy)
            s.xy.append(xy(n.lat, n.lon))
        return i

    def node(s, n):
        t = dict(n.tags)
        if not t:
            return
        k = typ_obiekta(t)
        if k:
            x, y = xy(n.location.lat, n.location.lon)
            s.obiekty.append(dict(typ=k, nazva=t.get('name:uk') or t.get('name') or '', x=x, y=y, poly=None,
                                  osm=f'n{n.id}'))

    def way(s, w):
        t = w.tags
        hw = t.get('highway')
        if hw and hw not in NE_PISHKY and t.get('area') != 'yes':
            try:
                ids = [s._v(n) for n in w.nodes]
            except osmium.InvalidLocationError:
                return
            # пішохідна мережа — без `foot=no` і приватних; вулиці й малюнок карти — усі дороги
            if t.get('foot') != 'no' and t.get('access') not in ('private', 'no'):
                for a, b in zip(ids, ids[1:]):
                    (x1, y1), (x2, y2) = s.xy[a], s.xy[b]
                    s.rebra.append((a, b, math.hypot(x2 - x1, y2 - y1)))
            linia = [s.xy[i] for i in ids]
            nm = t.get('name')
            if nm and hw in DOROGY_AVTO | {'trunk'}:
                s.vulytsi[nm].append(linia)
            klas = ('holovna' if hw in ('trunk', 'primary', 'secondary') else
                    'vulytsia' if hw in ('tertiary', 'unclassified', 'residential', 'living_street', 'pedestrian',
                                         'primary_link', 'secondary_link', 'tertiary_link', 'road') else
                    'proizd' if hw == 'service' else 'pish')
            s.dorogy.append((klas, nm or '', linia))

    def area(s, a):
        t = a.tags
        b = t.get('building')
        k = typ_obiekta(t)
        zel = any(t.get(kk) in vv for kk, vv in ZELEN)
        if not (b or k or zel):
            return
        try:
            polys = []
            for o in a.outer_rings():
                obr = [xy(n.lat, n.lon) for n in o]
                inn = [[xy(n.lat, n.lon) for n in i] for i in a.inner_rings(o)]
                if len(obr) >= 4:
                    polys.append(Polygon(obr, [i for i in inn if len(i) >= 4]))
        except osmium.InvalidLocationError:
            return
        if not polys:
            return
        g = polys[0] if len(polys) == 1 else MultiPolygon(polys)
        if not g.is_valid:
            g = g.buffer(0)
        if g.is_empty:
            return
        if b:
            lv = t.get('building:levels') or ''
            m = re.match(r'\s*(\d+)', lv)
            c = g.representative_point()
            s.budynky.append(dict(typ=b, rivni=int(m.group(1)) if m else None, x=c.x, y=c.y, poly=g,
                                  vul=t.get('addr:street') or '', nom=t.get('addr:housenumber') or '',
                                  osm=('w' if a.from_way() else 'r') + str(a.orig_id())))
        if zel:
            s.zelen.append(g)
        if k:
            c = g.representative_point()
            s.obiekty.append(dict(typ=k, nazva=t.get('name:uk') or t.get('name') or '', x=c.x, y=c.y, poly=g,
                                  osm=('w' if a.from_way() else 'r') + str(a.orig_id())))


def main():
    pbf, out = sys.argv[1], sys.argv[2]
    h = Zbir()
    h.apply_file(pbf, locations=True)
    print(f'мережа: {len(h.xy)} вузлів, {len(h.rebra)} ребер; будинків {len(h.budynky)} '
          f'(житлових {sum(1 for b in h.budynky if b["typ"] in ZHYTLO)}); зелені {len(h.zelen)}; '
          f'об\'єктів {collections.Counter(o["typ"] for o in h.obiekty)}; вулиць з назвою {len(h.vulytsi)}')
    pickle.dump(dict(xy=h.xy, rebra=h.rebra, vulytsi=dict(h.vulytsi), dorogy=h.dorogy,
                     budynky=h.budynky, zelen=h.zelen, obiekty=h.obiekty, LAT0=LAT0, LON0=LON0, KX=KX, KY=KY),
                open(out, 'wb'), protocol=pickle.HIGHEST_PROTOCOL)
    print('->', out)


if __name__ == '__main__':
    main()

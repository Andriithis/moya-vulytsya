# -*- coding: utf-8 -*-
"""Крок 0d. Щільність населення Києва з Kontur Population (400-м шестикутники H3).

GeoPackage — це база SQLite, тому читаємо без сторонніх бібліотек.
Файл завантажується один раз вручну (HDX блокує автоматичні запити).
"""
import os, sys, gzip, json, math, struct, sqlite3, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT  = os.path.join(DATA, 'population.json')
BBOX = (50.20, 30.22, 50.60, 30.86)   # Київ з запасом

HELP = """
Потрібен файл Kontur Population по Україні.

1. Відкрийте:  https://data.humdata.org/dataset/kontur-population-ukraine
2. Завантажте ресурс виду  kontur_population_UA_YYYYMMDD.gpkg.gz
3. Покладіть його в папку data (розпаковувати не треба)

Ліцензія Creative Commons Attribution — використання вільне
за умови посилання на Kontur.
"""

# ---------- WKB ----------
def wkb_centroid(blob):
    """центроїд полігона з GeoPackage BLOB (заголовок GP + WKB)"""
    if not blob or len(blob) < 8 or blob[:2] != b'GP':
        return None
    flags = blob[3]
    env = (flags >> 1) & 0x07
    env_len = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get(env)
    if env_len is None: return None
    off = 8 + env_len
    if len(blob) < off + 5: return None
    # якщо є огортаючий прямокутник — центр беремо з нього, це швидше й точніше
    if env == 1:
        minx, maxx, miny, maxy = struct.unpack_from('<4d', blob, 8)
        return ((miny + maxy) / 2, (minx + maxx) / 2)
    byte_order = blob[off]
    end = '<' if byte_order == 1 else '>'
    gtype = struct.unpack_from(end + 'I', blob, off + 1)[0] & 0xFF
    p = off + 5
    if gtype == 3:      # Polygon
        nring = struct.unpack_from(end + 'I', blob, p)[0]; p += 4
        if nring == 0: return None
        npt = struct.unpack_from(end + 'I', blob, p)[0]; p += 4
        xs = ys = 0.0
        for _ in range(npt):
            x, y = struct.unpack_from(end + '2d', blob, p); p += 16
            xs += x; ys += y
        return (ys / npt, xs / npt)
    if gtype == 6:      # MultiPolygon — беремо перший
        npoly = struct.unpack_from(end + 'I', blob, p)[0]; p += 4
        if npoly == 0: return None
        p += 5
        nring = struct.unpack_from(end + 'I', blob, p)[0]; p += 4
        npt = struct.unpack_from(end + 'I', blob, p)[0]; p += 4
        xs = ys = 0.0
        for _ in range(npt):
            x, y = struct.unpack_from(end + '2d', blob, p); p += 16
            xs += x; ys += y
        return (ys / npt, xs / npt)
    return None

def find_file():
    for f in sorted(os.listdir(DATA)):
        lf = f.lower()
        if 'kontur' in lf and lf.endswith(('.gpkg', '.gpkg.gz')):
            return os.path.join(DATA, f)
    return None

def main():
    os.makedirs(DATA, exist_ok=True)
    src = find_file()
    if not src:
        print(HELP); sys.exit(1)
    print(f'файл: {os.path.basename(src)}  ({os.path.getsize(src)/1048576:.0f} МБ)')

    gpkg = src
    if src.endswith('.gz'):
        gpkg = src[:-3]
        if not os.path.exists(gpkg):
            print('розпаковую...')
            with gzip.open(src, 'rb') as fi, open(gpkg, 'wb') as fo:
                shutil.copyfileobj(fi, fo, 1 << 22)
        print(f'   розпаковано: {os.path.getsize(gpkg)/1048576:.0f} МБ')

    conn = sqlite3.connect(gpkg)
    tabs = [r[0] for r in conn.execute(
        "SELECT table_name FROM gpkg_contents WHERE data_type='features'")]
    if not tabs:
        print('не знайдено шарів у GeoPackage'); sys.exit(1)
    t = tabs[0]
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
    print(f'   шар: {t}   поля: {", ".join(cols)}')

    geo = next((c for c in cols if c.lower() in ('geom', 'geometry', 'shape')), None)
    pop = next((c for c in cols if 'population' in c.lower() or c.lower() == 'pop'), None)
    if not geo or not pop:
        print('не знайдено полів геометрії або населення'); sys.exit(1)

    s, w, n, e = BBOX
    out, total, kept = [], 0, 0
    for g, p in conn.execute(f'SELECT "{geo}", "{pop}" FROM "{t}"'):
        total += 1
        c = wkb_centroid(g)
        if not c: continue
        la, lo = c
        # Kontur у метричній проєкції 3857 — переводимо, якщо треба
        if abs(la) > 90:
            lo = lo / 20037508.34 * 180
            la = la / 20037508.34 * 180
            la = 180 / math.pi * (2 * math.atan(math.exp(la * math.pi / 180)) - math.pi / 2)
        if s <= la <= n and w <= lo <= e:
            out.append([round(la, 5), round(lo, 5), int(p or 0)])
            kept += 1
    print(f'   прочитано шестикутників: {total:,}   у межах Києва: {kept:,}')
    if not kept:
        print('   нічого не потрапило в межі — перевірте проєкцію файлу'); sys.exit(1)

    tot = sum(x[2] for x in out)
    out.sort(key=lambda x: -x[2])
    json.dump({'title': 'Щільність населення (Kontur, 400 м)', 'items': out},
              open(OUT, 'w', encoding='utf-8'), separators=(',', ':'))
    print(f'\n=== ГОТОВО ===')
    print(f'   населення в межах: {tot:,}')
    print(f'   найщільніший шестикутник: {out[0][2]:,} осіб')
    print(f'   медіана: {out[len(out)//2][2]:,}')
    print(f'   -> data/population.json ({os.path.getsize(OUT)/1024:.0f} КБ)')

if __name__ == '__main__':
    main()

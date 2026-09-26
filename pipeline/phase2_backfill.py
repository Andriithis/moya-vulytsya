"""Обмежений приватний прогін QA-плану. Без PostgreSQL і без публікації."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import urllib.request
from urllib.parse import urlparse

from src import addr, location_evidence
from src.geocode_quality import load_resolver
from src.step1_download import rtf_to_text

PRIVATE = Path(__file__).resolve().parents[1] / 'private'
MAX_BYTES = 8 * 1024 * 1024


def allowed_url(url):
    p = urlparse(url)
    return (p.scheme == 'https' and p.hostname == 'od.reyestr.court.gov.ua'
            and p.port in (None, 443) and not p.username and not p.password
            and not p.query and not p.fragment
            and re.fullmatch(r'/files/\d+/[a-f0-9]{32}\.rtf', p.path) is not None)


class OfficialRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError('Перенаправлення поза офіційним open-data ресурсом заборонене')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_text(url):
    if not allowed_url(url):
        raise ValueError('Дозволені тільки RTF-ресурси офіційного open-data дампу')
    opener = urllib.request.build_opener(OfficialRedirects())
    req = urllib.request.Request(url, headers={'User-Agent': 'moya-vulytsya-qa/1.0'})
    with opener.open(req, timeout=30) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES or not raw.lstrip().startswith(b'{\\rtf'):
        raise ValueError('Замість придатного RTF отримано інший або завеликий вміст')
    text = rtf_to_text(raw)
    if not text.strip():
        raise ValueError('Порожній текст')
    return raw, text


def run(packet, download=False):
    packet = Path(packet).resolve()
    if not packet.is_relative_to(PRIVATE.resolve()) or packet == PRIVATE.resolve():
        raise ValueError('Контрольний прогін дозволено тільки в private/<пакет>')
    plan = json.loads((packet / 'backfill_plan.json').read_text(encoding='utf-8'))
    if len(plan) > 200:
        raise ValueError('Контрольний прогін обмежено 200 документами')
    if any(not re.fullmatch(r'[0-9]+', item['doc_id']) or not allowed_url(item['source_url'])
           or not re.fullmatch(r'[a-f0-9]{64}', item['source_row_hash']) for item in plan):
        raise ValueError('Непридатний QA-план')
    if len({item['doc_id'] for item in plan}) != len(plan):
        raise ValueError('Повторний ID у QA-плані')
    # Результати алгоритму відокремлені від сліпої людської розмітки.
    work = packet / 'withheld'
    work.mkdir(exist_ok=True)
    texts = packet / 'texts'
    texts.mkdir(exist_ok=True)
    resolver = load_resolver()
    conn = sqlite3.connect(work / 'backfill.sqlite')
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS events(doc_id TEXT PRIMARY KEY,
                        street TEXT,house TEXT,level TEXT,err TEXT)''')
        location_evidence.init_evidence(conn)
        conn.execute('''CREATE TABLE IF NOT EXISTS outcomes(doc_id TEXT PRIMARY KEY,
                        source_row_hash TEXT,text_sha256 TEXT,raw_sha256 TEXT,geocode TEXT,error TEXT)''')
        conn.commit()
        totals = {'planned': len(plan), 'downloaded': 0, 'reused': 0, 'errors': 0,
                  'event_locations': 0, 'geocoded': 0, 'human_review_complete': False,
                  'production_precision_established': False, 'scope': 'private_sqlite_sample'}
        for i, item in enumerate(plan, 1):
            doc = item['doc_id']
            path = texts / f'{doc}.txt'
            meta = texts / f'{doc}.json'
            try:
                previous = json.loads(meta.read_text(encoding='utf-8')) if meta.exists() else {}
                text = path.read_bytes().decode('utf-8') if path.exists() else ''
                text_hash = hashlib.sha256(text.encode()).hexdigest()
                if (previous.get('source_row_hash') == item['source_row_hash']
                        and previous.get('text_sha256') == text_hash and text):
                    totals['reused'] += 1
                else:
                    if not download:
                        raise ValueError('Немає перевіреного приватного тексту; потрібен --download')
                    raw, text = fetch_text(item['source_url'])
                    text_hash = hashlib.sha256(text.encode()).hexdigest()
                    previous = {**item, 'text_sha256': text_hash,
                                'raw_sha256': hashlib.sha256(raw).hexdigest()}
                    # Хеш і байти тексту незмінні також на Windows із CRLF.
                    path.write_bytes(text.encode('utf-8'))
                    meta.write_text(json.dumps(previous, ensure_ascii=False), encoding='utf-8')
                    totals['downloaded'] += 1
                    time.sleep(0.2)
                result = addr.extract(text)
                with conn:
                    conn.execute('INSERT OR REPLACE INTO events VALUES(?,?,?,?,NULL)',
                                 (doc, result['street'], result['house'], result['level']))
                    location_evidence.save_evidence(conn, doc, result['candidates'],
                                                    item['source_row_hash'], text_hash)
                    hit = resolver.cached(conn, result['street'], result['house']) if result['street'] else None
                    conn.execute('INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?,?,NULL)',
                                 (doc, item['source_row_hash'], text_hash, previous['raw_sha256'], json.dumps(hit)))
                totals['event_locations'] += bool(result['street'])
                totals['geocoded'] += hit is not None
            except Exception as exc:
                with conn:
                    conn.execute('DELETE FROM events WHERE doc_id=?', (doc,))
                    conn.execute('DELETE FROM address_evidence WHERE doc_id=?', (doc,))
                    conn.execute('INSERT OR REPLACE INTO outcomes VALUES(?,?,NULL,NULL,NULL,?)',
                                 (doc, item['source_row_hash'], type(exc).__name__))
                totals['errors'] += 1
            if i % 25 == 0:
                print(f'Оброблено {i}/{len(plan)}; помилок {totals["errors"]}', flush=True)
        totals['stored_outcomes'] = conn.execute('SELECT count(*) FROM outcomes').fetchone()[0]
        (work / 'summary.json').write_text(json.dumps(totals, ensure_ascii=False, indent=2), encoding='utf-8')
        return totals
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    result = run(args.packet, args.download)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

"""Приватний сліпий QA-пакет і план backfill з локального офіційного ZIP.

Нічого не завантажує, не публікує і не розмічає замість людини.
"""
import argparse
import hashlib
import heapq
import json
from pathlib import Path
from urllib.parse import urlparse

from pipeline.edrsr_snapshot import iter_documents, sha256_file
from pipeline.document_scope import admission, case_key, document_stream, validate_dictionaries, SCOPE_VERSION
from collections import Counter

PRIVATE = Path(__file__).resolve().parents[1] / 'private'
DEVELOPMENT_MANIFEST = PRIVATE.parent / 'data/fixtures/location_qa.json'
COURTS = {str(code) for code in range(2601, 2611)}


def select_sample(rows, limit, seed, excluded_cases=(), *, courts=None, audit=None, balanced=False):
    """Вибір за хешем ID, без текстів, адрес та прогнозів. Відмова без номера справи."""
    if limit < 1 or limit > 200:
        raise ValueError('Розмір вибірки має бути від 1 до 200')
    excluded = {case_key(c) for c in excluded_cases}
    counts = audit if audit is not None else Counter()
    def eligible():
        for row in rows:
            if row.status != 1 or row.court_code not in COURTS:
                continue
            reason = admission(row.justice_kind, row.judgment_code, row.category_code,
                               courts.get(row.court_code, {}).get('instance_code') if courts else '3')
            counts[reason] += 1
            if reason == 'unknown_category':
                counts['unknown:' + row.category_code] += 1
            if reason != 'analysis_candidate' or not case_key(row.cause_num) or case_key(row.cause_num) in excluded:
                continue
            yield row
    key = lambda row: (hashlib.sha256(f'{seed}|{row.doc_id}'.encode()).digest(), row.doc_id)
    if not balanced:
        return heapq.nsmallest(limit, eligible(), key=key)
    # Невеликі резервуари двох потоків; кількість пам'яті не залежить від ZIP.
    pools = {'criminal': [], 'kupap': []}
    for row in eligible():
        pool = pools[document_stream(row.justice_kind, row.judgment_code)]
        pool.append(row)
        pool.sort(key=key)
        del pool[limit:]
    return pools['criminal'][:limit//2] + pools['kupap'][:limit-limit//2]


def prepare(archive, dataset_url, text_dir, output, limit=200, seed='target-holdout-v1', *, excluded_cases=(), balanced=False):
    parsed = urlparse(dataset_url)
    if parsed.scheme != 'https' or parsed.hostname != 'data.gov.ua' or not parsed.path.startswith('/dataset/'):
        raise ValueError('Потрібне посилання на офіційний набір data.gov.ua')
    output = Path(output).resolve()
    if not output.is_relative_to(PRIVATE.resolve()) or output == PRIVATE.resolve():
        raise ValueError('QA-пакет дозволено записувати тільки у private/<назва>')
    development = json.loads(DEVELOPMENT_MANIFEST.read_text(encoding='utf-8'))
    excluded = {item['case_number'] for item in development['cases']} | set(excluded_cases)
    archive_hash = sha256_file(archive)
    courts = validate_dictionaries(archive)
    audit = Counter()
    selected = select_sample(iter_documents(archive), limit, seed, excluded, courts=courts, audit=audit, balanced=balanced)
    if sha256_file(archive) != archive_hash:
        raise ValueError('Архів змінився під час відбору: повторіть на незмінному ZIP')
    if any(not row.doc_id.isascii() or not row.doc_id.isdigit() for row in selected):
        raise ValueError('ID документа має бути числовим')
    # Новий каталог: повтор не перезаписує ручну розмітку.
    output.mkdir(parents=True, exist_ok=False)
    ready = 0
    plan = []
    with (output / 'review.jsonl').open('w', encoding='utf-8') as review:
        for row in selected:
            path = (Path(text_dir) / f'{row.doc_id}.txt').resolve()
            if not path.is_relative_to(Path(text_dir).resolve()):
                raise ValueError('Текст поза каталогом джерела')
            text = path.read_bytes().decode('utf-8') if path.exists() else None
            ready += text is not None
            plan.append({'doc_id': row.doc_id, 'source_row_hash': row.source_row_hash,
                         'justice_kind': row.justice_kind, 'judgment_code': row.judgment_code,
                         'category_code': row.category_code, 'case_number': row.cause_num,
                         'instance_code': courts[row.court_code]['instance_code'],
                         'source_url': row.doc_url, 'text_available': text is not None})
            review.write(json.dumps({
                'doc_id': row.doc_id, 'source_url': row.doc_url,
                'source_row_hash': row.source_row_hash,
                'text_sha256': hashlib.sha256(text.encode()).hexdigest() if text is not None else None,
                'text': text, 'reviewer': None, 'reviewed_at': None,
                'expected_candidates': None, 'expected_event_location': None,
                'expected_geocode': None, 'notes': None,
            }, ensure_ascii=False) + '\n')
    summary = {'archive_sha256': archive_hash, 'dataset_url': dataset_url,
               'document_scope': SCOPE_VERSION, 'admission_counts': dict(audit),
               'excluded_cases': sorted(excluded), 'balanced': balanced,
               'seed': seed, 'requested': limit, 'selected': len(selected),
               'texts_available': ready, 'texts_missing': len(selected)-ready,
               'independent_human_review_complete': False,
               'production_precision_established': False, 'backfill_executed': False}
    (output / 'manifest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'backfill_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def hydrate_review(packet):
    """Окремий сліпий файл із перевіреними текстами; не читає прогнози."""
    packet = Path(packet).resolve()
    if not packet.is_relative_to(PRIVATE.resolve()) or packet == PRIVATE.resolve():
        raise ValueError('QA-пакет має бути приватним')
    reviews = [json.loads(line) for line in (packet / 'review.jsonl').read_text(encoding='utf-8').splitlines()]
    for row in reviews:
        if any(row.get(key) is not None for key in ('reviewer', 'reviewed_at', 'expected_candidates',
                'expected_event_location', 'expected_geocode', 'notes')):
            raise ValueError('Розмітку вже розпочато: автоматичне доповнення заборонене')
        if not row['doc_id'].isascii() or not row['doc_id'].isdigit():
            raise ValueError('Непридатний ID')
        base = packet / 'texts' / row['doc_id']
        text = base.with_suffix('.txt').read_bytes().decode('utf-8')
        meta = json.loads(base.with_suffix('.json').read_text(encoding='utf-8'))
        digest = hashlib.sha256(text.encode()).hexdigest()
        if (meta['source_row_hash'] != row['source_row_hash'] or meta['source_url'] != row['source_url']
                or meta['text_sha256'] != digest):
            raise ValueError('Приватний текст не відповідає джерелу QA')
        row.update(text=text, text_sha256=digest)
    with (packet / 'review-ready.jsonl').open('x', encoding='utf-8') as out:
        for row in reviews:
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
    return {'ready_for_human_review': len(reviews), 'human_review_complete': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--dataset-url', required=True)
    parser.add_argument('--text-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=200)
    parser.add_argument('--seed', default='target-holdout-v1')
    parser.add_argument('--exclude-cases', type=Path, help='JSON-масив усіх пов’язаних справ налагодження')
    parser.add_argument('--balanced', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.dataset_url, args.text_dir, args.output,
                             args.limit, args.seed,
                             excluded_cases=json.loads(args.exclude_cases.read_text(encoding='utf-8')) if args.exclude_cases else (),
                             balanced=args.balanced), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

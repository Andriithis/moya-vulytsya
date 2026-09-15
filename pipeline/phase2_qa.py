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

PRIVATE = Path(__file__).resolve().parents[1] / 'private'
DEVELOPMENT_MANIFEST = PRIVATE.parent / 'data/fixtures/location_qa.json'
COURTS = {str(code) for code in range(2601, 2611)}


def select_sample(rows, limit, seed, excluded_cases=()):
    """Вибір не залежить від адреси, ролі або прогнозу extractor-а."""
    if limit < 1:
        raise ValueError('Розмір вибірки має бути додатним')
    eligible = (row for row in rows if row.status == 1 and row.court_code in COURTS
                and row.cause_num not in excluded_cases)
    return heapq.nsmallest(limit, eligible, key=lambda row:
        (hashlib.sha256(f'{seed}|{row.doc_id}'.encode()).digest(), row.doc_id))


def prepare(archive, dataset_url, text_dir, output, limit=200, seed='phase2-holdout-v1'):
    parsed = urlparse(dataset_url)
    if parsed.scheme != 'https' or parsed.hostname != 'data.gov.ua' or not parsed.path.startswith('/dataset/'):
        raise ValueError('Потрібне посилання на офіційний набір data.gov.ua')
    output = Path(output).resolve()
    if not output.is_relative_to(PRIVATE.resolve()) or output == PRIVATE.resolve():
        raise ValueError('QA-пакет дозволено записувати тільки у private/<назва>')
    development = json.loads(DEVELOPMENT_MANIFEST.read_text(encoding='utf-8'))
    excluded = {item['case_number'] for item in development['cases']}
    archive_hash = sha256_file(archive)
    selected = select_sample(iter_documents(archive), limit, seed, excluded)
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
    parser.add_argument('--seed', default='phase2-holdout-v1')
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.dataset_url, args.text_dir, args.output,
                             args.limit, args.seed), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

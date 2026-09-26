"""Локальна сліпа форма: читає лише review-ready, не прогнози."""
import argparse
import hashlib
import json
from pathlib import Path

from pipeline.phase2_qa import PRIVATE


def build(source, output, limit=20):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not all(p.is_relative_to(PRIVATE.resolve()) for p in (source, output)):
        raise ValueError('Тексти й форма мають залишатися у private')
    if source.name != 'review-ready.jsonl' or limit < 1:
        raise ValueError('Потрібен сліпий review-ready.jsonl і додатний розмір')
    raw = source.read_bytes()
    rows = []
    for line in raw.decode('utf-8').splitlines()[:limit]:
        item = json.loads(line)
        text = item['text']
        if not isinstance(text, str) or hashlib.sha256(text.encode()).hexdigest() != item['text_sha256']:
            raise ValueError('Текст не відповідає контрольній сумі')
        # Явний список: людські відповіді та випадкові поля прогнозів не копіюються.
        rows.append({k: item[k] for k in ('doc_id', 'source_row_hash', 'text_sha256', 'text')})
    if not rows:
        raise ValueError('Порожня порція')
    payload = json.dumps({'fingerprint': hashlib.sha256(raw).hexdigest(), 'rows': rows}, ensure_ascii=True)
    payload = payload.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = Path(__file__).with_name('qa_review_form.html').read_text(encoding='utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as f:
        f.write(template.replace('/*PAYLOAD*/', payload))
    return {'documents': len(rows), 'predictions_included': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.limit)))

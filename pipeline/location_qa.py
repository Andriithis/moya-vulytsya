"""Відтворювана перевірка на вже збережених уривках, без мережі й нових текстів у Git."""
import argparse
import hashlib
import json
from pathlib import Path

from src import addr


def read_excerpts(path):
    items = {}
    for block in Path(path).read_text(encoding='utf-8').split('\n--- ')[1:]:
        lines = block.splitlines()
        case = lines[0].split(' · справа ')[-1]
        url = next((line.strip() for line in lines if line.strip().startswith('https://od.reyestr.court.gov.ua/')), None)
        text = next((line.strip() for line in lines[3:]
                     if line.startswith('    ') and not line.strip().startswith('[…')), '')
        if case in items or not url or not text:
            raise ValueError('Непридатний або дубльований уривок')
        items[case] = (url, text)
    return items


def summarize(cases):
    tp = fp = fn = selected = positives = 0
    for expected, actual in cases:
        positives += expected is not None
        selected += actual is not None
        tp += actual is not None and actual == expected
        fp += actual is not None and actual != expected
        fn += expected is not None and actual != expected
    return dict(total=len(cases), expected_locations=positives, selected=selected,
                true_positive=tp, false_positive=fp, false_negative=fn,
                precision=tp/selected if selected else None,
                recall=tp/positives if positives else None)


def evaluate(root, manifest):
    fixture = json.loads(Path(manifest).read_text(encoding='utf-8'))
    excerpts = read_excerpts(Path(root) / fixture['source_artifact'])
    cases = []
    misses = []
    for item in fixture['cases']:
        url, text = excerpts[item['case_number']]
        if url != item['source_url'] or hashlib.sha256(text.encode('utf-8')).hexdigest() != item['text_sha256']:
            raise ValueError('Джерело QA змінилося: потрібна повторна перевірка розмітки')
        result = addr.extract(text)
        actual = [result['street'], result['house']] if result['street'] else None
        expected = item['expected_location']
        cases.append((expected, actual))
        if expected != actual:
            misses.append(item['case_number'])
    return dict(scope='cached_excerpt_development_set', reviewer='assistant',
                independent_human_review=False, production_precision_established=False,
                extraction_version=addr.EXTRACTION_VERSION, **summarize(cases),
                cases_needing_work=misses)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(evaluate(args.root, args.root / 'data/fixtures/location_qa.json'),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

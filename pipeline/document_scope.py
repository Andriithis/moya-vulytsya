"""Допуск до аналізу, не підтвердження епізоду чи законної сили."""
import csv
import io
import json
import re
import zipfile
from pathlib import Path

SCOPE_VERSION = 'target-corpus-v1'
CATALOG = json.loads((Path(__file__).resolve().parents[1] /
                     'config/document_categories.json').read_text(encoding='utf-8'))
CATEGORIES = CATALOG['categories']


def document_stream(justice_kind, judgment_code):
    return {('2', '1'): 'criminal', ('5', '2'): 'kupap'}.get(
        (justice_kind, judgment_code))


def case_key(value):
    return re.sub(r'\s+', '', value or '').casefold()


def admission(justice_kind, judgment_code, category_code, instance='3'):
    """Вища інстанція лишається в контурі перевірки, але не створення."""
    if justice_kind in {'2', '5'} and instance in {'1', '2'}:
        return 'review_only'
    if instance != '3' or not document_stream(justice_kind, judgment_code):
        return 'unsupported_document'
    category = CATEGORIES.get(category_code)
    if not category:
        return 'unknown_category'
    if category['excluded']:
        return 'privacy_excluded'
    if category['mismatch'] or category['justice_kind'] != justice_kind:
        return 'category_mismatch'
    return 'analysis_candidate'


def validate_dictionaries(archive):
    """Зупинка при зміні значення коду; жодного вгадування за номером."""
    with zipfile.ZipFile(archive) as zf:
        def read(name, key):
            matches = [n for n in zf.namelist() if n.split('/')[-1] == name]
            if len(matches) != 1:
                raise ValueError(f'Немає однозначного довідника {name}')
            return {r[key]: r for r in csv.DictReader(io.StringIO(
                zf.read(matches[0]).decode('utf-8-sig')), delimiter='\t')}
        for name, key, expected in [
            ('justice_kinds.csv', 'justice_kind', {'2': 'Кримінальне', '4': 'Адміністративне', '5': 'Адмінправопорушення'}),
            ('judgment_forms.csv', 'judgment_code', {'1': 'Вирок', '2': 'Постанова'}),
            ('instances.csv', 'instance_code', {'1': 'Касаційна', '2': 'Апеляційна', '3': 'Перша'}),
        ]:
            rows = read(name, key)
            if any(rows.get(k, {}).get('name', '').strip() != v for k, v in expected.items()):
                raise ValueError(f'Змінилися коди {name}: потрібна перевірка')
        categories = read('cause_categories.csv', 'category_code')
        for code, item in CATEGORIES.items():
            if categories.get(code, {}).get('name', '').strip() != item['source_name']:
                raise ValueError(f'Категорія {code} не відповідає перевіреному довіднику')
        return read('courts.csv', 'court_code')

"""Допуск документів до поточного корпусу: тільки кримінальні вироки.

Коди звірені зі словниками офіційного дампу 2026. Це допуск до аналізу,
не доказ вини, набрання законної сили або дозвіл публікувати подію.
"""
SCOPE_VERSION = 'criminal-verdicts-v1'


def is_criminal_verdict(justice_kind, judgment_code):
    return justice_kind == '2' and judgment_code == '1'

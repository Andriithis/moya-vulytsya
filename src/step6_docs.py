# -*- coding: utf-8 -*-
"""Крок 6. Документи, які збираються самі з даних кроків 1-4.

Три файли на кожну версію сайту:
  doslidzhennya.html — повне дослідження ризиків: джерела, методика, результати,
                       перевірка й поіменний розбір кожної ризикованої вулиці;
  rezyume.html       — те саме на одну сторінку, без таблиць;
  analiz.html        — загальний аналіз поточного стану: що показують дані,
                       де концентрація, коли і де саме, з можливими причинами
                       (тільки викладацька версія).

Жодного тексту не написано «наперед» під конкретні цифри: усі числа беруться
з engine_report.json, risk.json, network.json, factors.json і бази подій, а
формулювання добираються від самих чисел. Тому після кожного щотижневого
запуску документи оновлюються разом із картою.

Сам код поділено на три файли лише через розмір: step6_base — дані й обчислення,
step6_research — текст дослідження, step6_state — резюме й аналіз стану.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from step6_base import load, analyse, SITE
from step6_research import doc_research
from step6_state import doc_summary, doc_analysis

# ============================================================ ЗБІРКА
def build(outdir, A=None, D=None):
    """Кладе всі три документи в задану папку. Версія одна для всіх."""
    if D is None: D = load()
    if A is None: A = analyse(D)
    os.makedirs(outdir, exist_ok=True)
    open(os.path.join(outdir, 'doslidzhennya.html'), 'w', encoding='utf-8').write(
        doc_research(A, D))
    open(os.path.join(outdir, 'rezyume.html'), 'w', encoding='utf-8').write(
        doc_summary(A, D))
    open(os.path.join(outdir, 'analiz.html'), 'w', encoding='utf-8').write(
        doc_analysis(A, D))
    return ['doslidzhennya.html', 'rezyume.html', 'analiz.html']

def main():
    D = load()
    if not D['ER']:
        print('немає data/engine_report.json — документи будуть без розділу результатів')
    A = analyse(D)
    made = build(SITE, A, D)
    print('   ' + ', '.join(made))
    print('=== ГОТОВО === документи зібрано')

if __name__ == '__main__':
    main()

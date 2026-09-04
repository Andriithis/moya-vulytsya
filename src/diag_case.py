# -*- coding: utf-8 -*-
"""Скільки РЕАЛЬНИХ подій ми можемо покласти на карту.

Одна аварія дає багато документів: обвинувальний акт, призначення розгляду,
експертиза, привід, вирок. Опис місця є лише в частині з них. Досі кожен
документ рахувався окремою подією — тобто одна аварія могла давати п'ять
«подій» на адресі суду.

Тут рахуємо по СПРАВАХ (cause_num), а не по документах:
  * скільки документів припадає на одну справу;
  * у скількох справах ХОЧА Б ОДИН документ дає адресу з будинком.
Друге число і є те, скільки аварій реально можна показати.

  python3 src/diag_case.py 40696 60
"""
import os, re, sys, csv, glob, random, collections, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addr as A
import labels as L
import step1_download as S1

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
UA = 'Mozilla/5.0 (edrsr-research-academy; educational use)'
MAXDOC = 6          # більше шести документів однієї справи не качаємо

def main():
    cat = sys.argv[1] if len(sys.argv) > 1 else '40696'
    ncase = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    lb = L.CODE.get(cat)
    print(f'=== Справи чи документи: код {cat} — {lb[1] if lb else "?"} ===')

    by_case = collections.defaultdict(list)
    for fp in sorted(glob.glob(os.path.join(DATA, 'kyiv_*.csv'))):
        with open(fp, encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                if r['category_code'] == cat:
                    by_case[r['cause_num'] or r['doc_id']].append(r)
    if not by_case:
        print('немає справ цього коду в data/kyiv_*.csv'); return

    docs = sum(len(v) for v in by_case.values())
    sizes = collections.Counter(len(v) for v in by_case.values())
    print(f'документів: {docs:,}')
    print(f'окремих справ: {len(by_case):,}')
    print(f'у середньому документів на справу: {docs/len(by_case):.1f}\n')
    print('скільки справ мають N документів:')
    for n in sorted(sizes)[:10]:
        print(f'   {n} док. — {sizes[n]:,} справ')
    print()

    keys = list(by_case)
    random.seed(2); random.shuffle(keys)
    keys = keys[:ncase]
    print(f'перевіряю {len(keys)} справ (до {MAXDOC} документів кожної)...\n')

    with_house = with_street = empty = 0
    dl = 0
    blank = []
    for i, k in enumerate(keys, 1):
        best = 'none'
        for r in by_case[k][:MAXDOC]:
            try:
                rq = urllib.request.Request(r['doc_url'], headers={'User-Agent': UA})
                with urllib.request.urlopen(rq, timeout=60) as resp:
                    txt = S1.rtf_to_text(resp.read())
                dl += 1
            except Exception:
                continue
            lv = A.extract(txt)['level']
            if lv == 'house': best = 'house'; break
            if lv == 'street' and best == 'none': best = 'street'
        if best == 'house': with_house += 1
        elif best == 'street': with_street += 1
        else:
            empty += 1
            if len(blank) < 6 and by_case[k]:
                blank.append(k)
        if i % 10 == 0: print(f'   справ опрацьовано {i}, завантажень {dl}...')

    tot = with_house + with_street + empty or 1
    print(f'\n--- РЕЗУЛЬТАТ на {tot} справах ({dl} завантажень) ---')
    print(f'   є адреса з будинком : {with_house:4}  ({100*with_house/tot:.0f}%)')
    print(f'   лише вулиця         : {with_street:4}  ({100*with_street/tot:.0f}%)')
    print(f'   нічого              : {empty:4}  ({100*empty/tot:.0f}%)')
    est = len(by_case) * with_house / tot
    print(f'\n   ОЦІНКА: з {len(by_case):,} справ адресу дадуть приблизно {est:,.0f}')
    if blank:
        print('\n   номери справ без адреси (для перевірки вручну):')
        for k in blank: print('     ', k)

if __name__ == '__main__':
    main()

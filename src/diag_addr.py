# -*- coding: utf-8 -*-
"""Діагностика витягування адреси. Запускати ТАМ, ДЕ Є ДОСТУП до reyestr
(GitHub Actions або ваш комп'ютер) — у пісочниці Claude реєстр недоступний.

  python3 src/diag_addr.py 40696 150     # ст.286 КК, 150 рішень

Качає вибірку рішень, проганяє витягувач і показує:
  * скільки справ дають адресу з номером будинку;
  * скільки з них — насправді адреса суду (є у vykluchennya.txt);
  * шматки тексту там, де адресу знайти не вдалося.
Останнє — головне: саме з цих уривків видно, яких формулювань бракує.
Персональні дані в ЄДРСР уже знеособлені (ОСОБА_1), уривки короткі.
"""
import os, re, sys, csv, glob, random, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addr as A
import labels as L
import step1_download as S1

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
UA = 'Mozilla/5.0 (edrsr-research-academy; educational use)'

def load_excl():
    ex = set()
    for f in ('vykluchennya.txt', 'vykluchennya_moyi.txt'):
        p = os.path.join(DATA, f)
        if not os.path.exists(p): continue
        for ln in open(p, encoding='utf-8'):
            ln = ln.split('#')[0].strip()
            if ln: ex.add(ln.lower())
    return ex

def main():
    cat = sys.argv[1] if len(sys.argv) > 1 else '40696'
    want = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    lb = L.CODE.get(cat)
    print(f'=== Діагностика адрес: код {cat} — {lb[1] if lb else "?"} ===')

    tasks = []
    for fp in sorted(glob.glob(os.path.join(DATA, 'kyiv_*.csv'))):
        with open(fp, encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                if r['category_code'] == cat: tasks.append(r)
    if not tasks:
        print('немає справ цього коду в data/kyiv_*.csv'); return
    random.seed(1); random.shuffle(tasks)
    total = len(tasks)
    tasks = tasks[:want]
    print(f'у вибірці: {len(tasks)} з {total} доступних\n')

    excl = load_excl()
    n_house = n_street = n_none = n_court = 0
    misses = []
    for i, r in enumerate(tasks, 1):
        try:
            rq = urllib.request.Request(r['doc_url'], headers={'User-Agent': UA})
            with urllib.request.urlopen(rq, timeout=60) as resp:
                txt = S1.rtf_to_text(resp.read())
        except Exception as e:
            print(f'   {i}: не завантажено ({type(e).__name__})'); continue
        res = A.extract(txt)
        key = ((res['street'] + ', ' + res['house'])
               if (res['street'] and res['house']) else (res['street'] or '')).lower()
        if res['level'] == 'house':
            n_house += 1
            if key in excl: n_court += 1
        elif res['level'] == 'street': n_street += 1
        else:
            n_none += 1
            bs = A.body_start(txt)
            if len(misses) < 12:
                misses.append(re.sub(r'\s+', ' ', txt[bs:bs+320]))
        if i % 25 == 0: print(f'   опрацьовано {i}...')

    tot = n_house + n_street + n_none or 1
    print(f'\n--- РЕЗУЛЬТАТ на {tot} рішеннях ---')
    print(f'   адреса з будинком : {n_house:4}  ({100*n_house/tot:.0f}%)')
    print(f'      з них адреса суду: {n_court:4}  <- має бути 0')
    print(f'   лише вулиця       : {n_street:4}  ({100*n_street/tot:.0f}%)')
    print(f'   адреси не знайдено: {n_none:4}  ({100*n_none/tot:.0f}%)')
    print('\n--- ПОЧАТОК ФАБУЛИ ТАМ, ДЕ АДРЕСУ НЕ ЗНАЙДЕНО ---')
    print('(покажіть цей блок Claude — з нього видно, яких формулювань бракує)\n')
    for k, m in enumerate(misses, 1):
        print(f'[{k}] {m}\n')

if __name__ == '__main__':
    main()

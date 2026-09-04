# -*- coding: utf-8 -*-
"""Створює data/events.csv.gz зі своєї бази — для завантаження на GitHub."""
import os, sys, gzip, csv, sqlite3
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
DB   = os.path.join(DATA, 'events.db')
SNAP = os.path.join(DATA, 'events.csv.gz')

if not os.path.exists(DB):
    print('ПОМИЛКА: не знайдено data/events.db')
    print('Покладіть цей скрипт у папку karta, де є data з вашою базою.')
    input('Enter'); sys.exit(1)

conn = sqlite3.connect(DB)
n_all = conn.execute('SELECT count(*) FROM events').fetchone()[0]
n_adr = conn.execute("SELECT count(*) FROM events WHERE street IS NOT NULL").fetchone()[0]
print(f'у базі записів: {n_all:,}   з них з адресою: {n_adr:,}')

with gzip.open(SNAP, 'wt', encoding='utf-8', newline='') as fh:
    w = csv.writer(fh, delimiter='\t', lineterminator='\n')
    w.writerow(['doc_id','court','grp','cat','date','street','house','level','tm'])
    k = 0
    for r in conn.execute('SELECT doc_id,court,grp,cat,date,street,house,level,tm FROM events'):
        w.writerow(['' if x is None else x for x in r]); k += 1

sz = os.path.getsize(SNAP)/1024
print(f'\n=== ГОТОВО ===')
print(f'записано {k:,} записів')
print(f'файл: data/events.csv.gz  ({sz:.0f} КБ)')
print('\nЦей файл треба покласти в репозиторій на GitHub.')
input('\nEnter щоб закрити')

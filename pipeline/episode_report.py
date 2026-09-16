"""Приватна таблиця результатів; тексти та фрагменти не потрапляють у Git."""
import argparse
import html
import json
import sqlite3
from pathlib import Path
from pipeline.phase2_qa import PRIVATE


def render(packet):
    packet = Path(packet).resolve()
    if packet == PRIVATE.resolve() or not packet.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Звіт має залишатися у private')
    with sqlite3.connect(packet / 'withheld/backfill.sqlite') as conn:
        analyses = [json.loads(r[0]) for r in conn.execute('SELECT payload FROM document_analysis ORDER BY doc_id')]
    rows = []
    esc = lambda value: html.escape(str(value))
    for a in analyses:
        for e in a['episodes'] or [{}]:
            evidence = e.get('evidence', {})
            fragments = '<hr>'.join('<b>'+esc(k)+'</b>: '+esc(v['quote']) for k,v in evidence.items())
            location = e.get('location')
            place = (location['street'] + ', ' + (location['house'] or 'номер невідомий')) if location else 'Не підтверджене'
            cells = [esc(a['doc_id']), esc(e.get('outcome', a['hint']['outcome']) + (' (підказка)' if not e else '')),
                     esc(e.get('episode_id', 'Не розмічено'))+'<br>'+esc(e.get('subject','')),
                     fragments or 'Немає перевіреної розмітки', esc(place),
                     esc(', '.join(e.get('reasons', ['episode_unreviewed']))),
                     'Ні' if not e.get('publication_allowed') else 'Кандидат після перевірок']
            rows.append('<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>')
    page = '''<!doctype html><html lang="uk"><meta charset="utf-8"><title>Розробницький набір</title>
<style>body{font:16px system-ui;margin:24px;color:#18232f}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:10px;vertical-align:top}td:nth-child(4){min-width:380px}th{background:#eef2f5}hr{border:0;border-top:1px solid #ddd}</style>
<h1>Цільовий розробницький набір</h1><p>Приватне налагодження асистентом. Не незалежна людська перевірка; точність не виміряна. Результати й причини — службові коди правил.</p>
<table><thead><tr>'''+''.join('<th>'+h+'</th>' for h in ['Документ','Результат','Епізод / особа','Фрагменти джерела','Місце','Причини відмови','Публікація'])+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></html>'
    target=packet/'report.html'; target.write_text(page,encoding='utf-8')
    return {'documents':len(analyses),'rows':len(rows),'path':str(target)}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('packet'); args=p.parse_args()
    print(json.dumps(render(args.packet),ensure_ascii=False))

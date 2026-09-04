# -*- coding: utf-8 -*-
"""Крок 6: блок одної теми в дослідженні ризиків.

Показники якості, перелік чинників, таблиця ризикованих вулиць,
розбір верхівки, аномалії та попередження. У версії для слухачів
поіменних переліків немає — лише чинники.
"""
import labels as L
import mech as M
from step6_base import (esc, num, page, stamp, bar, fac_human,
                        parse_factor, THSLUG, TRAIN_Y, TEST_Y)

def theme_block(th, i, A, D):
    ER = A['ER']; d = ER.get(th, {})
    rows = A['streets'].get(th, [])
    sl = THSLUG.get(th, th)
    # Прогноз рахується по МЕХАНІЗМАХ, а розділ документа поки один на тему.
    # Щоб посилання з картки ризику («Розбір вулиці в дослідженні»)
    # не вело в нікуди, кожен механізм теми отримує власний якір тут-таки.
    mech = [m for m in M.all_groups() if M.simtheme(m) == th]
    anch = ''.join(f'<span id="t-{M.anchor(m)}"></span>' for m in mech)
    b = [anch + f'<h3 id="t-{sl}">6.{i+1}. {esc(d.get("тема", L.THEMES.get(th, th)))}</h3>']
    g = d.get('hit_інший_район')
    b.append('<div class="cards">'
             f'<div class="card"><div class="lab">справ на навчання ({TRAIN_Y})</div>'
             f'<div class="big">{num(d.get("навчання",0))}</div></div>'
             f'<div class="card"><div class="lab">справ на перевірку</div>'
             f'<div class="big">{num(d.get("перевірка",0))}</div></div>'
             f'<div class="card"><div class="lab">у верхніх 10% вулиць</div>'
             f'<div class="big">{100*d.get("hit_середовище",0):.0f}%</div></div>'
             f'<div class="card"><div class="lab">краще за випадок</div>'
             f'<div class="big">×{d.get("PAI_середовище","—")}</div></div>'
             f'<div class="card"><div class="lab">на іншій половині міста</div>'
             f'<div class="big">{"—" if g is None else f"{100*g:.0f}%"}</div></div>'
             + (f'<div class="card"><div class="lab">з показаних вулиць збулося</div>'
                f'<div class="big">{d.get("з_них_збулося", 0)}'
                f'<span class="muted"> з {d.get("вулиць_показано")}</span>'
                f'</div></div>' if d.get('вулиць_показано') else '')
             + '</div>')

    fac = [(n, w) for n, w in d.get('фактори', [])]
    if fac:
        pos = [x for x in fac if x[1] > 0][:12]
        neg = [x for x in fac if x[1] < 0][:6]
        mx = max((abs(w) for _, w in fac), default=1)
        b.append('<h4>Що модель зважила найвище</h4>')
        b.append('<table><thead><tr><th>Чинник</th><th class="n">Вага</th>'
                 '<th style="width:110px"></th></tr></thead><tbody>')
        for n, w in pos:
            b.append(f'<tr><td>{esc(fac_human(n))}</td>'
                     f'<td class="n">+{w:.3f}</td><td>{bar(abs(w), mx)}</td></tr>')
        b.append('</tbody></table>')
        if neg:
            b.append('<p class="muted">Знижують оцінку: '
                     + ', '.join(f'{esc(fac_human(n))} ({w:+.3f})' for n, w in neg)
                     + '. Від’ємна вага не означає «безпечно» — вона означає, що за '
                       'інших рівних умов подій цього типу там фіксують менше.</p>')

    an = A['anom'].get(th, [])
    if an:
        b.append('<h4>Аномалії: подій багато, а середовище їх не пояснює</h4>')
        b.append('<p class="muted">Ці відрізки дають чимало подій, але модель ставить '
                 'їх у нижню половину переліку. Причина є, але її немає в даних: '
                 'подія, режим роботи закладу, конкретна група людей, ділянка ремонту. '
                 'Такі місця треба дивитися на місці — саме вони найцікавіші для '
                 'навчальної роботи.</p><ul>')
        for r in an[:8]:
            b.append(f"<li><b>{esc(r['name'])}</b> — {r['ev24']} подій, "
                     f"а за середовищем лише {r['rank']}-те місце з {len(rows)}.</li>")
        b.append('</ul>')

    fr = A['fresh'].get(th, [])
    if fr:
        b.append('<h4>Попередження: умови є, подій ще не фіксували</h4>')
        b.append('<p class="muted">Верхні за оцінкою вулиці, де в навчальному році '
                 'подій теми не було. Це саме те, чого не дає прогноз за '
                 'історією.</p><ul>')
        for r in fr[:8]:
            near = ', '.join(f'{n.lower()} — {q}' for n, q, _, _ in r['near'][:3])
            b.append(f"<li><b>{esc(r['name'])}</b> — оцінка {r['score']:.2f}"
                     + (f'; поруч {near}' if near else '') + '.</li>')
        b.append('</ul>')
    return '\n'.join(b)

# -*- coding: utf-8 -*-
"""Крок 6: збірка документа «Дослідження ризиків» (doslidzhennya.html).

Текст методики — у step6_intro.py, блок теми — у step6_theme.py.
Поділ на файли суто технічний, через розмір.
"""
import labels as L
from step6_base import (esc, num, page, stamp, bar, fac_human,
                        parse_factor, THSLUG, TRAIN_Y, TEST_Y)
from step6_intro import sect_intro, sect_tail
from step6_theme import theme_block

# ============================================================ ДОКУМЕНТ 1
FSEARCH = """<script>
(function(){
 function norm(s){return (s||'').toLowerCase().replace(/[’'`]/g,"'").trim()}
 document.querySelectorAll('input.f').forEach(function(inp){
  var tb=document.querySelector(inp.dataset.for);
  if(!tb)return;
  inp.addEventListener('input',function(){
   var q=norm(inp.value);
   tb.querySelectorAll('tbody tr').forEach(function(tr){
    tr.style.display=(!q||norm(tr.dataset.nm).indexOf(q)>=0)?'':'none'})})});
 // перехід з картки ризику на карті: ?st=<вулиця>#t-<тема>
 var p=new URLSearchParams(location.search), st=p.get('st');
 if(st){
  var want=norm(st), found=null;
  document.querySelectorAll('tbody tr').forEach(function(tr){
   if(!found&&norm(tr.dataset.nm)===want){found=tr}});
  if(!found)document.querySelectorAll('tbody tr').forEach(function(tr){
   if(!found&&norm(tr.dataset.nm).indexOf(want)>=0){found=tr}});
  if(found){found.classList.add('hl');
   setTimeout(function(){found.scrollIntoView({block:'center'})},60)}
  document.querySelectorAll('input.f').forEach(function(i){i.value=st;
   i.dispatchEvent(new Event('input'))});
  if(found)found.style.display='';
 }
})();
</script>"""

def doc_research(A, D):
    ER = A['ER']
    b = []
    b += sect_intro(A, D)
    b.append('<h2 id="rez">6. Результати за темами</h2>')
    if not ER:
        b.append('<div class="box warn">Модель ще не рахована — немає '
                 '<code>engine_report.json</code>. Запустіть крок 4.</div>')
    else:
        b.append('<div class="tw"><table><thead><tr><th>Тема</th>'
                 '<th class="n">Навчання<br>' + TRAIN_Y + '</th>'
                 '<th class="n">Перевірка<br>' + TEST_Y[0] + '–' + TEST_Y[1] + '</th>'
                 '<th class="n">Влучність<br>середовище</th>'
                 '<th class="n">PAI</th>'
                 '<th class="n">Інша половина<br>міста</th>'
                 '<th class="n">Тільки<br>історія</th></tr></thead><tbody>')
        for th in sorted(ER, key=lambda t: -ER[t].get('hit_середовище', 0)):
            d = ER[th]
            g = d.get('hit_інший_район')
            b.append(f"<tr><td>{esc(d.get('тема', th))}</td>"
                     f"<td class='n'>{num(d.get('навчання', 0))}</td>"
                     f"<td class='n'>{num(d.get('перевірка', 0))}</td>"
                     f"<td class='n'><b>{100*d.get('hit_середовище',0):.0f}%</b></td>"
                     f"<td class='n'>{d.get('PAI_середовище','—')}</td>"
                     f"<td class='n'>{'—' if g is None else f'{100*g:.0f}%'}</td>"
                     f"<td class='n'>{100*d.get('hit_історія',0):.0f}%</td></tr>")
        b.append('</tbody></table></div>')
        best = max(ER, key=lambda t: ER[t].get('hit_середовище', 0))
        worst = min(ER, key=lambda t: ER[t].get('hit_середовище', 0))
        b.append(f"<p>Найкраще середовищем пояснюється «{esc(ER[best].get('тема',best))}» "
                 f"({100*ER[best].get('hit_середовище',0):.0f}% подій у верхніх 10% "
                 f"вулиць), найгірше — «{esc(ER[worst].get('тема',worst))}» "
                 f"({100*ER[worst].get('hit_середовище',0):.0f}%). Це закономірно: "
                 f"що сильніше подія прив’язана до конкретного об’єкта, то краще її "
                 f"видно за середовищем.</p>")
        gt = [t for t in ER if ER[t].get('hit_інший_район') is not None]
        if gt:
            mn = min(100 * ER[t]['hit_інший_район'] for t in gt)
            mx = max(100 * ER[t]['hit_інший_район'] for t in gt)
            b.append(f'<div class="box ok"><h4>Головне про якість</h4>'
                     f'<p>На половині міста, якої модель не бачила, вона утримує '
                     f'{mn:.0f}–{mx:.0f}% подій у верхніх 10% вулиць — у {mn/10:.1f}–'
                     f'{mx/10:.1f} рази краще за випадковий відбір. Тобто знайдено '
                     f'закономірність, а не список адрес. Водночас це помітно гірше '
                     f'за результат на «своїй» половині, і це чесно означає: у різних '
                     f'частинах міста однакові умови працюють неоднаково.</p></div>')

        for i, th in enumerate(A['themes_ok']):
            b.append(theme_block(th, i, A, D))

        if A['themes_no']:
            b.append('<h3>Теми, для яких моделі немає</h3><p>')
            for t in A['themes_no']:
                b.append(f'<span class="k">{esc(L.THEMES.get(t,t))} — '
                         f'{num(A["by_theme"].get(t,0))} подій усього</span> ')
            b.append('</p><p class="muted">Причина одна: в навчальному році подій '
                     'менше за поріг у 250, і будь-яка модель на такій кількості '
                     'відтворювала б випадковість. На карті ці теми лишаються в '
                     'переліку з поміткою «замало подій» — щоб перелік тем у '
                     '«Прогнозі ризику» збігався з переліком у «Правопорушеннях».</p>')

    b += sect_tail(A, D)

    return page('Дослідження ризиків', 'Методика, результати, перевірка та поіменний '
                'розбір ризикованих вулиць Києва. Оновлюється автоматично.',
                '\n'.join(b), script=FSEARCH)

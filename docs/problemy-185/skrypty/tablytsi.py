# -*- coding: utf-8 -*-
import json, re, collections, math
NOM = re.compile(r'((?:вул|вулиц\w*|просп\w*|пр-т|бульв\w*|пров\w*|пл|площ\w*|шосе|набережн\w*|узвіз\w*|Науки|Зодчих|Метрологічн\w*|Кіото|Бориспільське шосе|Набережному)\.?\s*[^\d,;()«»]{0,40}?)[,\s]*(?:буд\.\s*)?(?:№\s*)?\d+(?:\s?[-/]?\s?\d+)?(?:\s?-?[А-ЯҐЄІЇа-яґєіїA-Za-z](?![А-ЯҐЄІЇа-яґєії]))?(?![\d.,]\d)')
def chyste(t):
    t = re.sub(r'\s+', ' ', str(t or '')).replace('|', '/')
    t = NOM.sub(lambda m: m.group(1).rstrip() + ' ██', t)
    t = re.sub(r'(будин\w* |№\s?)\d+[\w\-/]*', r'\1██', t)
    t = re.sub(r'([А-ЯІЇЄҐ][\w’\'\-\.]+),\s*(?:буд\.\s*)?\d+[\w/\-]*', r'\1 ██', t)
    return t
def wilson(k, n, z=1.96):
    p = k/n; d = 1+z*z/n; c = p+z*z/(2*n); r = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return round(100*(c-r)/d), round(100*(c+r)/d)
I = json.load(open('/home/user/work/k185/krytyk.json'))
# підсумок критика (розд. 4 звіту): арбітр + моя перевірка (переглянуто вручну)
RUCHNE = {  # місце -> (підсумок, причина, пояснення)
 ('скупчення','вул. Д. Щербаківського'): ('сумнівно','фон ДТП','арбітр вважає «наїзди ззаду на регульованому перехресті» точкою; за методикою «дистанція» без напрямку — фон міста'),
 ('скупчення','вул. О. Теліги'): ('сумнівно','фон ДТП','арбітр прив\'язує до АЗС поруч, але описи — переважно «дистанція» на ділянці; за методикою — фон'),
 ('скупчення','вул. Механізаторів'): ('сумнівно','межа ДТП у дворі','«зачіпають авто на парковці будинку» — та сама картина, яку арбітр в інших місцях назвав фоном'),
 ('скупчення','пров. Моторному'): ('сумнівно','межа ДТП у дворі','задній хід у провулку біля кількох будинків — межа «фон чи картина» не визначена'),
 ('скупчення','вул. Дмитрівська'): ('ні','—','5 крадіжок у 2017–2019: картина розтягнута на понад 2 роки — за MV-195 так і задумано, не помилка'),
 ('не пройшло сито','вул. Велика Васильківська'): ('так','сито: самовключення','крадіжки в одному супермаркеті; без самого місця в «схожих» проходить (P ≈ 0,03)'),
 ('не пройшло сито','просп. Науки'): ('так','сито: самовключення','29–44 крадіжки за 2 роки в одному супермаркеті різними людьми; у клітинці лише він — «у схожих» = він сам'),
 ('не пройшло сито','вул. Кибальчича'): ('так','сито: самовключення','крадіжки в одному супермаркеті; у клітинці 5 місць, і він сам тягне середнє вгору'),
 ('не пройшло сито','вул. Заболотного'): ('так','сито: самовключення','крадіжки з полиць одного гіпермаркету; у клітинці лише він'),
 ('не пройшло сито','вул. Деревообробна'): ('так','сито: самовключення','куріння учнів на території одного училища (таке саме місце в 183 — «проблема»); у клітинці лише воно'),
 ('не пройшло сито','вул. Метрологічна'): ('сумнівно','серія','12 протоколів за 5 тижнів о ≈ 23:00 — схоже на одну людину; без них — 5 крадіжок у різних кварталах'),
}
for i in I:
    rz = i.get('rozbir') or {}
    if i['zgoda']: pid, pr = ('так' if i['grupa'] == 'проблема' else 'ні'), '—'
    else: pid, pr = rz.get('spravzhnia') or 'ні', rz.get('prychyna') or '—'
    if i['grupa'] == 'не пройшло сито' and pid == 'так': pr = 'сито: самовключення' if (i.get('loo') or {}).get('p', 1) < 0.05 else 'сито: поріг надлишку'
    pr = {'fon': 'фон (ніч, маневр)', 'shi': 'ШІ неправильно прочитав', 'mistse': 'місце не те', 'syto': 'сито'}.get(pr, pr)
    poyas = rz.get('chomu') or (i['krytyk'] or {}).get('chomu') or ''
    if (i['grupa'], i['mistse']) in RUCHNE: pid, pr, poyas = RUCHNE[(i['grupa'], i['mistse'])]
    i['fin'] = dict(pidsumok=pid, prychyna=pr, poyas=poyas)
rows = ['| Група | Вид | Місце | Подій | Метод | Критик наосліп | Арбітр | Підсумок | Причина помилки | Чому (одним реченням) |', '|---|---|---|---|---|---|---|---|---|---|']
for i in I:
    m = i.get('metod') or {}
    met = (m.get('rishennia') or 'не кандидат') + (f" — {chyste(m.get('nazva') or m.get('spilne') or '')[:90]}" if m else '')
    kr = i['krytyk'] or {}; rz = i.get('rozbir') or {}
    rows.append(f"| {i['grupa']} | {i['vyd']} | {chyste(i['mistse'])} | {i['oz']['n']} | {met} | {kr.get('spravzhnia')}: {chyste(kr.get('shcho'))[:80]} | "
                f"{rz.get('pravyi') or 'згоден'} | **{i['fin']['pidsumok']}** | {i['fin']['prychyna']} | {chyste(i['fin']['poyas'])[:260]} |")
open('/home/user/moya-vulytsya/docs/problemy-185/usi-140.md', 'w').write(
    '# ZAVDANNYA-185 — усі 140 місць: метод, критик, арбітр, підсумок\n\nМісця — без номерів будинків. Критик і арбітр — Opus через `claude -p`; підсумок — '
    'арбітр, а в 11 випадках — моя ручна перевірка (див. `ZVIT-185.md`, розд. 4). **Це не розмітка людини.**\n\n' + '\n'.join(rows) + '\n')
s = collections.Counter((i['grupa'], i['fin']['pidsumok']) for i in I); print(s)
print(collections.Counter((i['grupa'], i['fin']['prychyna']) for i in I if (i['grupa']=='проблема') == (i['fin']['pidsumok'] != 'так') or i['fin']['pidsumok']=='сумнівно'))
for g in ('проблема', 'скупчення', 'не пройшло сито'):
    n = sum(1 for i in I if i['grupa'] == g); k = sum(i['fin']['pidsumok'] == 'так' for i in I if i['grupa'] == g); print(g, k, n, wilson(k, n))
json.dump([dict(grupa=i['grupa'], vyd=i['vyd'], sim=i['sim'], mistse=chyste(i['mistse']), podii=i['oz']['n'], metod=(i.get('metod') or {}).get('rishennia', 'не кандидат'),
                metod_nazva=chyste((i.get('metod') or {}).get('nazva') or (i.get('metod') or {}).get('spilne') or ''), status=((i.get('metod') or {}).get('stan') or {}).get('status'),
                krytyk=dict(spravzhnia=(i['krytyk'] or {}).get('spravzhnia'), shcho=chyste((i['krytyk'] or {}).get('shcho')), chomu=chyste((i['krytyk'] or {}).get('chomu')),
                            oznaky=(i['krytyk'] or {}).get('oznaky')),
                arbitr=dict(pravyi=(i.get('rozbir') or {}).get('pravyi'), spravzhnia=(i.get('rozbir') or {}).get('spravzhnia'), prychyna=(i.get('rozbir') or {}).get('prychyna'), chomu=chyste((i.get('rozbir') or {}).get('chomu'))),
                prohrama=dict(dat=i['oz']['dat'], maks_v_odnu_datu=i['oz']['maks_data'], sprav=i['oz']['sprav'], misto_teper_do_rokiv_mistsia=i['oz']['misto_teper_do_piku'], ustanova_60m=bool(i['ustanovy'])),
                syto=(dict(maks_za_2_roky=i['prop']['maks2r'], ochikuvano_bulo=i['prop']['och'], p_bulo=round(i['prop']['p'] or 1, 3), bez_samovkliuchennia=dict(ochikuvano=i['loo']['och'], p=round(i['loo']['p'], 4), skhozhykh_u_klityntsi=i['loo']['skhozhykh_u_klityntsi'], hrupa=i['loo']['hrupa'])) if 'prop' in i else None),
                pidsumok=dict(i['fin'], poyas=chyste(i['fin']['poyas']))) for i in I], open('/home/user/moya-vulytsya/docs/problemy-185/usi-140.json', 'w'), ensure_ascii=False, indent=1)

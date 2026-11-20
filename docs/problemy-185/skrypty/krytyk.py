# -*- coding: utf-8 -*-
"""ZAVDANNYA-185: незалежний критик. Набір: 60 «проблем» і 40 «скупчень» з повтору калібрування 183 + 40 місць, що не
пройшли сито, але мають ≥ 10 подій одного виду за якісь 2 роки. Крок 1 — критик наосліп (Opus, не бачить рішення методу,
інша інструкція — CHEERS своїми словами). Крок 2 — де критик і метод розходяться: розбір з обома відповідями й причиною.
Ознаки, які рахує програма: рейд (одна дата), справи, установа поруч, тренд міста, свіжість.
python krytyk.py <k183/problemy-183.json> <kand.pkl> <propushcheni.pkl> <тека>"""
import sys, os, json, pickle, collections, hashlib, re, math
sys.path.insert(0, '/home/user/d103/src'); sys.path.insert(0, '/home/user/d103/perevirka')
import problemy_varianty as PV, problemy_shi as PS, problemy_183 as K, mech as M

kal = json.load(open(sys.argv[1])); kand = pickle.load(open(sys.argv[2], 'rb')); prop = pickle.load(open(sys.argv[3], 'rb'))
out = sys.argv[4]; os.makedirs(out, exist_ok=True)
B = pickle.load(open('/home/user/work/baza.pkl', 'rb')); S, P = B['S'], B['P']
SPR = pickle.load(open('/home/user/work/sprava.pkl', 'rb'))
UST = json.load(open('/home/user/karta-kyiv-kod/data/ustanovy.json'))
po_k = {PS.kliuch(k): k for k in kand}
DOBA = PV.doba_po_mistu(B['evs'])
h = lambda s: hashlib.sha256(s.encode()).hexdigest()

# ряд міста за роками для кожного механізму (усі події з точкою)
RIAD = collections.defaultdict(collections.Counter)
for e in B['evs']: RIAD[e['sim']][int(e['data'][:4])] += 1

KRYTYK = """Ти — досвідчений аналітик проблемно-орієнтованої поліцейської діяльності (POP, Clarke & Eck). Проблема за
тестом CHEERS — це повторювані (Recurring), схожі між собою (Similar) події (Events), що шкодять (Harm) людям громади
(Community) саме в цьому місці. Нижче — пронумеровані описи подій із рішень судів, які програма віднесла до одного місця
міста (дата · стаття · опис), і довідка.

Оціни незалежно й суворо, як критик:
1. Чи це справжня повторювана проблема цього місця для громади? «так» — та сама дія в схожих обставинах повторюється тут
   у різний час, і їй можна було б протидіяти на цьому місці (магазин, вхід до метро, двір, виїзд, перехрестя);
   «ні» — подій багато, але спільного, крім виду статті й близькості, немає, або це не події цього місця;
   «сумнівно» — є ознаки, але їх мало чи вони неоднозначні.
2. Познач ознаки (true/false):
   - ne_tut: більшість подій сталися не тут (тут адреса установи, оформлення, затримання, реєстрації, або тут лише виявили те, що
     привезли/придбали деінде);
   - ustanova: місце — установа (відділ поліції, суд, лікарня, ТЦК, ізолятор), а не місце дії;
   - odna_seriia: більшість подій — одна особа чи одна група / одна справа (той самий опис, ті самі обставини, один епізод
     розбитий на кілька);
   - reid: багато подій в одну-дві дати — разова операція поліції;
   - mezhi: події розкидані по різних точках широкої території (проспект, площа, масив) і разом їх тримає лише широке місце;
   - fon_mista: спільне лише те, що звичайне для всього міста (ніч, вихідні, «не дотримався дистанції», «не впевнився в
     безпеці маневру»), без конкретної точки чи об'єкта;
   - politsiia: більшість подій виявила сама поліція без заяви людей.
3. Що саме повторюється (3–10 слів, без номерів будинків) і одне речення — чому так вирішив.

Відповідь — лише JSON:
{"spravzhnia": "так" | "ні" | "сумнівно", "shcho": "...", "chomu": "...", "oznaky": {"ne_tut": false, "ustanova": false,
"odna_seriia": false, "reid": false, "mezhi": false, "fon_mista": false, "politsiia": false}}

"""

ROZBIR = """Ти — арбітр. Два аналітики по-різному оцінили одне місце міста з подіями з рішень судів.
Метод проєкту (правила: «проблема» — одна спільна картина «дія + обставина» щонайменше в 5 описах, у ≥ 3 кварталах і в
половині показаних описів; «скупчення» — сито пройдено, але спільної картини немає чи замало; «ні» — події сталися не тут;
«не кандидат» — програма відсіяла до ШІ) і незалежний критик (тест CHEERS). Прочитай описи й вирішуй, хто правий.

Причина помилки — рівно одна з переліку:
- mistse — місце не те: установа, адреса ролі, оформлення, події не цього місця;
- seriia — одна справа, особа чи серія;
- reid — разовий рейд (багато подій в одну дату);
- mezhi — межі місця: широке місце (перехрестя, площа, проспект) розсипалось або злилось надто широко;
- fon — «вночі», «вихідні», звичайний маневр ДТП — фон міста, а не картина;
- trend — «згасла» лише тому, що вид подій упав по всьому місту (війна, зміна закону);
- svizhi — свіжі дані неповні (рішення ще не опубліковані), тому «згасла» чи не дотягнуло;
- shi — ШІ методу неправильно прочитав описи (пропустив чи вигадав картину);
- syto — сито відкинуло справжню проблему (надлишок проти схожих, пороги);
- inshe — інше (напиши словами).

Відповідь — лише JSON:
{"pravyi": "метод" | "критик" | "обидва частково", "spravzhnia": "так" | "ні", "prychyna": "<код або порожньо, якщо правий метод>",
"chomu": "<одне речення>"}

"""


def ustanova_poruch(la, lo, r=60):
    return [u[2] for u in UST if PV.vidstan((la, lo), (u[0], u[1])) <= r]


def oznaky_prohramy(evs, sim):
    daty = collections.Counter(e['data'] for e in evs)
    spr = collections.Counter(SPR.get(e['eid'], '') for e in evs)
    roky = sorted({int(e['data'][:4]) for e in evs})
    adr = collections.Counter((e['adr'] or '').strip() for e in evs)
    r = RIAD[sim]
    # тренд міста: середнє за роки місця проти останніх 2 повних років
    pik = sum(r[y] for y in roky) / max(len(roky), 1)
    teper = (r[2024] + r[2025]) / 2
    return dict(n=len(evs), dat=len(daty), maks_data=daty.most_common(1)[0][1], sprav=len(spr), maks_sprava=spr.most_common(1)[0][1],
                adres=len(adr), top_adresa=round(adr.most_common(1)[0][1] / len(evs), 2), roky=roky,
                misto_teper_do_piku=round(teper / pik, 2) if pik else None, ostannia=max(e['data'] for e in evs))


def zapyt_krytyka(k, evs, sim):
    z = PS.zapyt(dict(k, s=dict(k['s'], evs=evs)), '')
    tekst = z['user']
    return KRYTYK + tekst, z


def nabir():
    vv = kal['vidpovidi']
    probl = [x for x in vv if x['rishennia'] == 'проблема']
    probl = sorted(probl, key=lambda x: h(x['id']))[:60]
    skup = [x for x in vv if x['rishennia'] == 'скупчення' and not x.get('dodatkovyi')]
    kvota = {'ДТП на дорозі': 16, 'ДТП': 8, 'ДОР': 8}
    po = collections.defaultdict(list)
    for x in sorted(skup, key=lambda x: h(x['id'])): po[x['vyd'] if x['vyd'] in kvota else 'інше'].append(x)
    sk = []
    for t, n in list(kvota.items()) + [('інше', 8)]: sk += po[t][:n]
    if len(sk) < 40:   # інших скупчень у вибірці мало — добираємо з ДТП
        rest = [x for x in sorted(skup, key=lambda x: h(x['id'])) if x not in sk]; sk += rest[:40 - len(sk)]
    items = []
    for x in probl: items.append(dict(grupa='проблема', id=x['id'], metod=x))
    for x in sk: items.append(dict(grupa='скупчення', id=x['id'], metod=x))
    # пропущені ситом: усі не-ДТП-на-дорозі + ДТП на дорозі до 40
    pr = sorted(prop, key=lambda o: (o['sim'] == 'ДОР_ДТП_дорога', h(o['sim'] + o['nazva'])))[:40]
    for o in pr:
        items.append(dict(grupa='не пройшло сито', id=f"{o['sim']}|{o['m'][1]:.6f}|{o['m'][2]:.6f}", prop=o))
    return items


def pidhotuvaty(it):
    if it['grupa'] != 'не пройшло сито':
        k = po_k[it['id']]; evs = k['s']['evs']; sim = k['sim']; mistse = k['mistse']; la, lo = k['lat'], k['lon']
    else:
        o = it['prop']; sim = o['sim']; xs = P[(sim, o['m'])]
        u = PV.unikalni(xs, S); qs = [PV.kv(e['data']) for e in u]
        best = max(PV.povtoriuvani_vikna(qs, PV.kv(S)), key=lambda w: len(w[2]))
        evs = [u[i] for i in best[2]]; mistse = o['nazva']; la, lo = o['m'][1], o['m'][2]
        k = dict(sim=sim, riven='точка', mistse=mistse, lat=la, lon=lo, n=len(evs), roky_tekst=PV.roky_tekst(sorted({int(e['data'][:4]) for e in evs})),
                 periody=[1], n_vsi=len(u), s=dict(evs=evs, n=len(evs), kvartaly=sorted({PV.kv(e['data']) for e in evs})),
                 doba_misto=DOBA.get(sim), zriz=S)
    tekst, z = zapyt_krytyka(k, evs, sim)
    it.update(sim=sim, vyd=('ДТП на дорозі' if sim == 'ДОР_ДТП_дорога' else M.simtheme(sim)), mistse=K.bez_nomera(mistse),
              mistse_povne=mistse, oz=oznaky_prohramy(z['evs'], sim), ustanovy=ustanova_poruch(la, lo), zapyt=tekst, opysy_tekst=z['user'])
    return it


def rozibraty(t):
    if not t: return None
    m = re.search(r'\{.*\}', t, re.S)
    try: return json.loads(m.group(0)) if m else None
    except ValueError: return None


if __name__ == '__main__':
    items = [pidhotuvaty(it) for it in nabir()]
    print(collections.Counter(i['grupa'] for i in items), flush=True)
    log = lambda *x: print(*x, flush=True)
    vk = PS.Vyklyky(os.path.join(out, 'kesh'), 8, log)
    tt = vk('opus', [i['zapyt'] for i in items], 'критик наосліп')
    for i, t in zip(items, tt): i['krytyk'] = rozibraty(t)
    # розбір розбіжностей
    def metod_rish(i):
        return i['metod']['rishennia'] if 'metod' in i else 'не кандидат'
    spirni = []
    for i in items:
        kr = (i['krytyk'] or {}).get('spravzhnia'); m = metod_rish(i)
        zgoda = (m == 'проблема' and kr == 'так') or (m != 'проблема' and kr == 'ні')
        i['zgoda'] = zgoda
        if not zgoda: spirni.append(i)
    zz = []
    for i in spirni:
        mt = i.get('metod') or {}
        md = (f"Метод: {metod_rish(i)}" + (f" — {mt.get('nazva') or ''}; спільне: {mt.get('spilne') or ''}; {mt.get('obgr') or ''}; "
              f"{mt.get('znizheno') or ''}; статус: {K.stan_slovo(mt)}" if mt else
              f" (сито: у найсильніші 2 роки {i['prop']['maks2r']} подій, але «у схожих місцях» очікувано {i['prop']['och']}, P = {round(i['prop']['p'] or 1, 3)})"))
        kr = i['krytyk'] or {}
        zz.append(ROZBIR + md + f"\nКритик: {kr.get('spravzhnia')} — {kr.get('shcho')}; {kr.get('chomu')}; ознаки: "
                  + ', '.join(k for k, v in (kr.get('oznaky') or {}).items() if v) +
                  f"\nПрограма: подій {i['oz']['n']}, різних дат {i['oz']['dat']} (найбільше в одну дату {i['oz']['maks_data']}), "
                  f"різних справ {i['oz']['sprav']}; ряд цього виду по Києву зараз = {i['oz']['misto_teper_do_piku']} від років місця; "
                  f"установа ≤ 60 м: {', '.join(i['ustanovy']) or 'немає'}\n\n" + i['opysy_tekst'])
    tt = vk('opus', zz, 'розбір розбіжностей')
    for i, t in zip(spirni, tt): i['rozbir'] = rozibraty(t)
    json.dump([{k: v for k, v in i.items() if k not in ('zapyt',)} for i in items], open(os.path.join(out, 'krytyk.json'), 'w'),
              ensure_ascii=False, indent=1, default=str)
    print('статистика', vk.stat())

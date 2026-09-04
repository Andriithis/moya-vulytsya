# -*- coding: utf-8 -*-
"""Крок 5. Збирає сайт: оглядова сторінка + ОДНА карта. Версія одна.

Районних файлів більше немає. Карта міста несе межі всіх районів і їхні
власні переліки проблем, а перехід у район — це клік або адреса виду
kyiv.html#desna. Плитки оглядової сторінки ведуть саме туди.

Поділу на викладацьку й слухацьку версії теж немає. Проблеми бачать усі:
перший крок ланцюга — «обрати проблему зі списку», а робота слухача починається
далі, за SARA — встановити причину й перевірити її на місці. Ховати перелік
означало б залишити слухачеві пошук найлюднішої вулиці, тобто ту саму
реактивність, яку проєкт прибирає.

Було 22 файли по 12 МБ, стало 1 на 4 МБ.
"""
import os, sys, json, sqlite3, collections, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import labels as L
import step3_map as M3
import step6_docs as D6

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
SITE = os.path.join(ROOT, 'site')

SLUG = M3.SLUG          # спільний з картою, щоб посилання збігалися

def stats():
    """кількість проблем, аномалій та інцидентів і профіль кожного району"""
    conn = sqlite3.connect(os.path.join(DATA, 'events.db'))
    rows = conn.execute("""SELECT e.court, e.cat FROM events e
                           JOIN geo g ON g.doc_id=e.doc_id WHERE g.precision='house'""").fetchall()
    per = collections.defaultdict(collections.Counter)
    for court, cat in rows:
        lb = L.CODE.get(cat)
        if lb: per[M3.COURTS.get(court, court)][lb[0]] += 1
    return per

INDEX = """<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Проблеми громад Києва</title><style>
*{box-sizing:border-box}body{margin:0;background:#0f1117;color:#e8eaf0;
 font:15px/1.5 system-ui,sans-serif;padding:34px 22px 60px}
.wrap{max-width:1020px;margin:0 auto}
h1{font-size:27px;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:#79839a;font-size:14px;margin-bottom:30px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:13px}
a.card{display:block;text-decoration:none;color:inherit;background:#171a23;
 border:1px solid #252a37;border-radius:11px;padding:15px 16px;transition:.14s}
a.card:hover{background:#1c2030;border-color:#3a4256;transform:translateY(-2px)}
.nm{font-size:16.5px;font-weight:600;margin-bottom:9px}
.ev{font-size:26px;font-weight:600;letter-spacing:-.02em;line-height:1}
.evl{color:#6d7789;font-size:11.5px;margin:3px 0 11px}
.bar{display:flex;height:5px;border-radius:3px;overflow:hidden;margin-bottom:9px;background:#232838}
.bar i{display:block}
.leg{font-size:11px;color:#79839a;line-height:1.65}
.leg b{color:#c4cbd8;font-weight:500}
.dot{display:inline-block;width:7px;height:7px;border-radius:2px;margin-right:5px}
.note{margin-top:34px;color:#5f6878;font-size:12.5px;line-height:1.65;max-width:660px}
.note b{color:#8b95a8;font-weight:500}
</style></head><body><div class="wrap">
<h1>Проблеми громад Києва</h1>
<div class="sub">Аналіз правопорушень за даними Єдиного державного реєстру судових рішень. Оберіть район.</div>
<div class="grid">__CARDS__</div>
<div class="note">__NOTE__</div>
</div></body></html>"""

COLORS = {'ГП':'#e0533d','АЛК':'#e8a33d','НАР':'#8b5cf6','НАС':'#ef4444',
          'МАЙ':'#3b82f6','ДОР':'#22c55e','СЕР':'#14b8a6','ДОМ':'#94a3b8'}

def build_index(per):
    cards = []
    for d in sorted(per, key=lambda x: -sum(per[x].values())):
        c = per[d]; tot = sum(c.values()) or 1
        bar = ''.join(f'<i style="background:{COLORS.get(k,"#555")};width:{100*v/tot:.1f}%"></i>'
                      for k, v in c.most_common())
        leg = '<br>'.join(
            f'<span class="dot" style="background:{COLORS.get(k,"#555")}"></span>'
            f'{L.THEMES.get(k,k)} <b>{100*v/tot:.0f}%</b>'
            for k, v in c.most_common(3))
        cards.append(f'<a class="card" href="kyiv.html#{SLUG[d]}"><div class="nm">{d}</div>'
                     f'<div class="ev">{tot:,}</div><div class="evl">подій з адресою</div>'
                     f'<div class="bar">{bar}</div><div class="leg">{leg}</div></a>'.replace(',', ' '))
    doc = ('<a class="card" href="doslidzhennya.html"><div class="nm">Дослідження ризиків</div>'
           '<div class="ev">&#9998;</div><div class="evl">методика, джерела, перевірка</div>'
           '<div class="leg">на чому побудована модель і наскільки вона справджується</div></a>'
           '<a class="card" href="rezyume.html"><div class="nm">Резюме</div>'
           '<div class="ev">&#8801;</div><div class="evl">одна сторінка</div>'
           '<div class="leg">коротко: що зроблено, що вийшло, чого не можна робити</div></a>')
    doc += ('<a class="card" href="analiz.html"><div class="nm">Аналіз стану</div>'
            '<div class="ev">&#9776;</div><div class="evl">що показують дані</div>'
            '<div class="leg">концентрація, райони, час, виявлені проблеми '
            'та можливі причини</div></a>')
    cards.append(doc)
    cards.append('<a class="card" href="kyiv.html"><div class="nm">Весь Київ</div>'
                 '<div class="ev">&#8721;</div><div class="evl">та сама карта, без вибраного району</div>'
                 '<div class="leg">межі районів на ній видно, район відкривається кліком</div></a>')
    note = ('<b>Як читати.</b> Карта одна на все місто. Район відкривається кліком — '
            'у ньому свій перелік проблем, бо найгірше місце тихого району важливіше '
            'за десяте місце Києва. ')
    note += ('<b>Проблема</b> — не будь-яке скупчення, а пара «адреса + механізм», яка '
             'повторюється роками: інцидент стався раз випадково, проблема має причину '
             'в місці. Перелік дається готовим — робота починається далі: встановити '
             'причину й перевірити її на місці. Кнопка «Що поруч» у вікні будь-якої '
             'адреси показує, що є в радіусі 250 метрів; які з цих об’єктів справді '
             'пояснюють скупчення — вирішуєте ви.')
    note += ('<br><br>Джерело: відкриті дані ЄДРСР (розпорядник — Державна судова адміністрація України) '
             'та OpenStreetMap. Показані лише справи, розглянуті судом.')
    return INDEX.replace('__CARDS__', '\n'.join(cards)).replace('__NOTE__', note)

def main():
    if not os.path.exists(os.path.join(DATA, 'events.db')):
        print('немає data/events.db'); sys.exit(1)
    by_court = stats()          # які райони взагалі є в базі
    out = SITE
    os.makedirs(out, exist_ok=True)
    M3.main(district=None, out=os.path.join(out, 'kyiv.html'))
    # Числа плиток беремо з тієї самої збірки, на яку плитка веде: раніше
    # плитка рахувала за судом, а карта — за географією меж, і Деснянський
    # показував 2 319 проти 3 839. Тепер джерело одне.
    meta = M3.LAST_META
    names, dth = meta.get('dnames', []), meta.get('dtheme', [])
    per = {d: collections.Counter(dth[i]) for i, d in enumerate(names)
           if i < len(dth) and dth[i]}
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(
        build_index(per or by_court))
    # крок 6 — після карти: step3_map дорогою будує data/factors.json,
    # без якого в документах не було б розділу «що поруч»
    try:
        made = D6.build(out)
        print('   документи: ' + ', '.join(made))
    except Exception as e:
        print('   документи не зібрано:', e)
    print(f'\n=== ГОТОВО === сайт у папці site/')
    print('   site/index.html — оглядова сторінка')
    print('   site/kyiv.html  — карта, райони відкриваються кліком')

if __name__ == '__main__':
    main()

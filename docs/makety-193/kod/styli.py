# -*- coding: utf-8 -*-
"""Вісім настроїв (+ другий варіант «Вектора») для ZAVDANNYA-193. Кожен: шрифти, CSS, підкладка карти, вигляд сот."""

KAMERA = {'pk': {'center': [30.56, 50.452], 'zoom': 10.15}, 'tel': {'center': [30.56, 50.45], 'zoom': 8.85}}
PIDPYSY = [{'t': r} for r in ['Голосіївський', "Солом'янський", 'Святошинський', 'Дарницький', 'Дніпровський', 'Деснянський',
                               'Оболонський', 'Подільський', 'Шевченківський', 'Печерський']]
DNIPRO = {'t': 'Дніпро', 'n': 'Дніпро', 'll': [30.585, 50.405], 'kl': 'pidpys--richka'}


def karta(**kw):
    k = {'kamera': KAMERA, 'pidpysy': PIDPYSY + [DNIPRO]}
    k.update(kw)
    return k


S = {}

# =====================================================================================================================
# 1. Спокійна й чиста — як дорогий журнал
S['spokiyna'] = dict(
    nazva='Спокійна й чиста', grafik='line',
    shryfty=[('Source Serif 4', 'source-serif-4', [300, 400, 600], True), ('Source Sans 3', 'source-sans-3', [400, 600], False)],
    znak='<span class="zn">Моя вулиця</span>',
    hrupy_kol=['#9A978F', '#8A8646', '#3E7470', '#9A5A6B', '#6E6390', '#9A7C47', '#4E7458'],
    haslo='Що болить вашому будинку — у фактах.',
    karta=karta(pidkladka=dict(tlo='#F2F0EA', voda='#D8E0E2', park='#E7E7DD', doroha='#DEDAD0', doroha2='#E8E5DD'),
                ramp=['#DCE5E0', '#B6CBC4', '#86A9A1', '#517F77', '#21504A'], sotaOp=.9, mezhaSoty='#F2F0EA', mezhaSotyW=.5,
                mezhaRayonu='#A39E93', mezhaRayonuW=.6, vybrana='#1C1B19', vybranaW=1.6,
                problema=dict(vyd='kilce', kolir='#1C1B19', tlo='#F5F3EE'),
                temna=dict(pidkladka=dict(tlo='#171715', voda='#20282A', park='#1C1E19', doroha='#2C2B27', doroha2='#232220'),
                           ramp=['#26302D', '#33504A', '#4A7770', '#78A79F', '#BFDCD4'], mezhaSoty='#171715', mezhaRayonu='#4A4741',
                           vybrana='#F1EDE4', problema=dict(vyd='kilce', kolir='#F1EDE4', tlo='#171715'))),
    css='''
:root{--tlo:#F5F3EE;--surface:#FBFAF7;--ink:#1C1B19;--ink-2:#3D3B37;--muted:#77736B;--line:#DEDAD2;--line-strong:#BDB8AE;
--akcent:#1F4A44;--na-akcenti:#F5F3EE;--f-tekst:'Source Sans 3',sans-serif;--f-ui:'Source Sans 3',sans-serif;--f-serif:'Source Serif 4',serif;
--h-shapka:64px;--pole:40px;--kolonka:700px;--h1:54px;--h1-tel:36px;--h2:28px;--chyslo:64px;--g-kolir:#1F4A44;--g-tiho:#CFCAC0;--g-osnova:#BDB8AE;
--smuha-h:6px;--smuha-tlo:#E9E6DF;--smuha-kolir:#1F4A44;--smuha-sus:#B4AFA5;--pidpys:#5E5A52;--f-pidpys:'Source Serif 4',serif;--pidpys-rozmir:13px}
[data-t=temna]{--tlo:#171715;--surface:#1D1D1B;--ink:#EFEBE2;--ink-2:#CFCAC0;--muted:#8E897F;--line:#2E2D29;--line-strong:#4A4741;--akcent:#9CC8BF;--na-akcenti:#171715;--pidpys:#A39E93}
body{font-size:17px}
.shapka{border-bottom:1px solid var(--line)}
.zn{font-family:var(--f-serif);font-style:italic;font-size:23px;letter-spacing:-.01em}
.menu{font-size:14px;letter-spacing:.06em;text-transform:uppercase;gap:28px}.menu a{color:var(--muted)}.menu a.aktyvne{color:var(--ink)}
.tema{border:0;background:none;color:var(--muted)}
h1,h2,.k-zag h2,.hrupa-zag h3{font-family:var(--f-serif);font-weight:400;letter-spacing:-.015em}
.chyslo{font-family:var(--f-serif);font-weight:300;font-variant-numeric:lining-nums tabular-nums;letter-spacing:-.02em}
.mitka,.haslo,.k-rozdil h3,.smuha-shapka,.tabl thead th,.hrupa-vydy-zag{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:600}
.mitka{margin-bottom:22px}
.kryhty{font-size:12.5px;margin-bottom:56px}.kryhty a:after{content:"/";margin-left:14px;color:var(--line-strong)}
.vstup{font-family:var(--f-serif);font-size:20px;line-height:1.6;color:var(--ink-2)}
[data-prystrii=tel] .vstup{font-size:18px}
.zaholovok{margin-bottom:56px}
.chysla{border-top:1px solid var(--ink);border-bottom:1px solid var(--line);padding:28px 0;gap:0;margin-bottom:72px}
.chyslo-blok{padding-right:24px}.chyslo-blok+.chyslo-blok{border-left:1px solid var(--line);padding-left:24px}
[data-prystrii=tel] .chysla--3 .chyslo-blok:nth-child(2){border-left:0;padding-left:0}
[data-prystrii=tel] .chysla--3 .chyslo-blok:first-child{border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:20px}
.chyslo-blok span{color:var(--muted);font-size:14px}
.rozdil{margin-bottom:72px;padding-top:20px;border-top:1px solid var(--line)}
.rozdil h2{margin-bottom:14px}
.tabl td,.tabl th{border-color:var(--line);font-size:15px}
.knopka{border-bottom:1px solid var(--ink);padding:0 2px;min-height:36px;background:none;margin-right:18px}
.knopka--holovna{background:var(--ink);color:var(--tlo);padding:0 26px;border:0;min-height:50px}
.holovne{font-family:var(--f-serif);font-size:20px;counter-reset:n}
.holovne li{counter-increment:n;padding-left:36px;position:relative}
.holovne li:before{content:counter(n);position:absolute;left:0;top:2px;font-size:13px;color:var(--muted);font-family:var(--f-ui)}
.hrupy-sitka{gap:0;grid-template-columns:1fr 1fr;border-top:1px solid var(--line)}
.hrupa{padding:24px 24px 28px 0;border-bottom:1px solid var(--line)}
.hrupa:nth-child(even){padding-left:24px;border-left:1px solid var(--line)}
[data-prystrii=tel] .hrupa:nth-child(even){padding-left:0;border-left:0}
.hr{width:6px;height:6px;border-radius:50%}
.trend{font-weight:600;color:var(--ink)}
.storinka--rayon{max-width:880px}
/* карта */
.poshuk{border:1px solid var(--line-strong);height:50px}
.filtr{border:1px solid var(--line);background:var(--tlo)}
.kartka-soty{border:1px solid var(--line);padding:28px 30px;gap:18px}
.k-zag h2{font-size:26px}
.k-chyslo .chyslo{font-size:58px}
.k-rozdil{border-top:1px solid var(--line);padding-top:12px}
.k-knopky .knopka--holovna{min-height:44px}
.legenda{background:var(--tlo);border:1px solid var(--line)}
.pidpys{font-style:italic}.pidpys--richka{font-size:15px;color:#6E8C92;letter-spacing:.2em}
[data-prystrii=tel] .kartka-soty{border:0;border-top:1px solid var(--ink)}
''')

# =====================================================================================================================
# 2. Тепла й людська — записник уважного сусіда
S['tepla'] = dict(
    nazva='Тепла й людська', grafik='bars',
    shryfty=[('Alegreya', 'alegreya', [400, 500, 700, 800], True), ('Alegreya Sans', 'alegreya-sans', [400, 500, 700], True)],
    znak='<span class="zn">моя вулиця</span><svg class="zn-rys" viewBox="0 0 120 10" width="104" height="9"><path d="M2 6 C 30 2, 60 9, 118 3" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/></svg>',
    hrupy_kol=['#8D877B', '#8A8A2E', '#2E7C7E', '#A9466C', '#7A5AA0', '#A47B22', '#3F7A48'],
    haslo='Що болить вашому будинку — у фактах.',
    poshuk_znak='<svg width="18" height="18" viewBox="0 0 18 18"><circle cx="7.5" cy="7.5" r="5.3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M11.5 11.8 L16 16.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    karta=karta(pidkladka=dict(tlo='#F3EAD7', voda='#CBD9DC', park='#E2E2C4', doroha='#E4D5B8', doroha2='#ECE1CA'),
                sotaVyd='jitter', ramp=['#E7DFCC', '#C9CFD3', '#97A8BF', '#5E759D', '#2C4877'], sotaOp=.82,
                mezhaSoty='#2C4877', mezhaSotyW=.45, mezhaRayonu='#8F7E62', mezhaRayonuW=.9, mezhaRayonuDash=[3, 2],
                vybrana='#2A2620', vybranaW=2.2, problema=dict(vyd='ruka', kolir='#2A2620', tlo='#F3EAD7'),
                temna=dict(pidkladka=dict(tlo='#221D17', voda='#25302F', park='#29291E', doroha='#3A3226', doroha2='#2E281F'),
                           ramp=['#3A3328', '#4A5160', '#62779A', '#8FA6CB', '#D4E0F2'], mezhaSoty='#D4E0F2', mezhaRayonu='#6E604A',
                           vybrana='#F3D36B', problema=dict(vyd='ruka', kolir='#F3D36B', tlo='#221D17'))),
    css='''
:root{--tlo:#F7F0E1;--surface:#FFFBF2;--ink:#2A2620;--ink-2:#4A4238;--muted:#857A6A;--line:#E2D6BF;--line-strong:#CBBB9C;
--akcent:#2D4A7A;--na-akcenti:#FFFBF2;--marker:#F3D36B;--f-tekst:'Alegreya Sans',sans-serif;--f-serif:'Alegreya',serif;
--h-shapka:64px;--pole:28px;--kolonka:760px;--h1:46px;--h1-tel:34px;--h2:28px;--chyslo:58px;--g-kolir:#2D4A7A;--g-tiho:#D8CCB4;--g-osnova:#CBBB9C;
--smuha-h:9px;--smuha-kolir:#2D4A7A;--smuha-sus:#CBBB9C;--pidpys:#5A5044;--f-pidpys:'Alegreya',serif;--pidpys-rozmir:14.5px;--pidpys-rozmir-tel:12px}
[data-t=temna]{--tlo:#221D17;--surface:#2A241D;--ink:#F1E8D8;--ink-2:#D8CCB4;--muted:#A29581;--line:#3A3226;--line-strong:#5A4E3D;--akcent:#F3D36B;--na-akcenti:#221D17;--pidpys:#C9BBA2}
body{font-size:18px;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='30'%3E%3Cline x1='0' y1='29.5' x2='8' y2='29.5' stroke='%23EADFC8' stroke-width='1'/%3E%3C/svg%3E")}
.je-karta{background-image:none}
.shapka{border-bottom:1.5px solid var(--ink);background:var(--tlo)}
.znak{flex-direction:column;align-items:flex-start;gap:0;color:var(--akcent)}
.zn{font-family:var(--f-serif);font-style:italic;font-weight:700;font-size:26px;line-height:1;color:var(--ink)}
.zn-rys{margin-top:-1px}
.menu{font-family:var(--f-serif);font-size:17px}.menu a.aktyvne{color:var(--ink);text-decoration:underline;text-decoration-color:var(--marker);text-decoration-thickness:6px;text-underline-offset:-2px;text-decoration-skip-ink:none}
.tema{border:1.5px solid var(--ink);border-radius:50% 45% 52% 48%;background:var(--surface)}
h1,h2,.k-zag h2,.hrupa-zag h3{font-family:var(--f-serif);font-weight:700;letter-spacing:-.005em}
h2{display:inline-block;padding-bottom:8px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='8' viewBox='0 0 200 8' preserveAspectRatio='none'%3E%3Cpath d='M1 5 C 40 1, 80 7, 120 3 S 180 6, 199 2' stroke='%232D4A7A' stroke-width='1.8' fill='none' stroke-linecap='round'/%3E%3C/svg%3E") left bottom/100% 8px no-repeat}
.rozdil h2{display:table}
.chyslo{font-family:var(--f-serif);font-weight:800;font-variant-numeric:oldstyle-nums proportional-nums;position:relative;z-index:0;display:inline-block}
.chyslo-blok .chyslo:before,.k-chyslo .chyslo:before{content:"";position:absolute;left:-6px;right:-8px;bottom:.12em;height:.42em;background:var(--marker);opacity:.85;transform:rotate(-1.6deg) skewX(-8deg);border-radius:3px 8px 4px 9px;z-index:-1}
.mitka{font-family:var(--f-serif);font-style:italic;font-size:17px;color:var(--ink-2)}
.kryhty{font-family:var(--f-serif);font-style:italic;font-size:15px}.kryhty a:after{content:"›";margin-left:12px}
.vstup{font-size:19px;line-height:1.62}
.chysla{gap:20px}
.chyslo-blok{background:var(--surface);border:1.5px solid var(--ink);padding:18px 20px;border-radius:3px 10px 4px 12px;transform:rotate(-.5deg)}
.chyslo-blok+.chyslo-blok{transform:rotate(.6deg)}
.chyslo-blok span{font-size:15px}
.rozdil-pidpys{font-size:16px}
.smuha{border-radius:2px 6px 3px 5px}.smuha i{border-radius:2px 6px 3px 5px}
.tabl{background:var(--surface);border:1.5px solid var(--ink);border-radius:3px 10px 4px 12px}
.tabl th,.tabl td{border-bottom:1px dashed var(--line-strong)}
.tabl thead th{font-family:var(--f-serif);font-style:italic;font-size:14px;color:var(--ink-2);font-weight:400}
.knopka{border:1.5px solid var(--ink);border-radius:4px 12px 5px 14px;font-family:var(--f-serif);font-size:17px;font-weight:500;background:var(--surface)}
.knopka--holovna{background:var(--akcent);border-color:var(--akcent);color:var(--na-akcenti)}
.rozdil--prodazh{background:var(--surface);border:1.5px dashed var(--line-strong);padding:22px 24px;border-radius:6px}
.haslo{font-family:var(--f-serif);font-style:italic;font-size:16px;color:var(--akcent)}
.holovne{font-size:18.5px;list-style:none}.holovne li{padding-left:28px;position:relative}
.holovne li:before{content:"";position:absolute;left:2px;top:.55em;width:14px;height:9px;border:1.6px solid var(--akcent);border-radius:50% 40% 55% 45%;transform:rotate(-12deg)}
.hrupa{background:var(--surface);border:1.5px solid var(--ink);border-radius:3px 12px 4px 10px;transform:rotate(-.35deg)}
.hrupa:nth-child(3n+2){transform:rotate(.4deg)}.hrupa:nth-child(3n){transform:rotate(-.15deg)}
.hr{width:12px;height:12px;border-radius:50% 45% 55% 40%}
.trend{font-family:var(--f-serif);font-style:italic}
.grafik text{font-family:var(--f-serif);font-size:10px}
/* карта */
.poshuk,.filtr,.legenda{border:1.5px solid var(--ink);border-radius:4px 12px 5px 14px;background:var(--surface)}
.kartka-soty{border:1.5px solid var(--ink);border-radius:4px 16px 6px 14px;padding:22px 24px;transform:rotate(-.3deg);background:var(--surface)}
[data-prystrii=tel] .kartka-soty{transform:none;border-radius:16px 16px 0 0;border-bottom:0}
.k-zag h2{font-size:25px}
.k-rozdil h3{font-family:var(--f-serif);font-style:italic;font-weight:400;font-size:15px;color:var(--ink-2)}
.k-hrupy{font-size:15.5px}
.k-chyslo .chyslo{font-size:52px}
.k-problema{font-family:var(--f-serif);font-style:italic;font-size:16px}
.pidpys{font-style:italic;text-shadow:0 0 3px #F3EAD7,0 0 3px #F3EAD7}
.pidpys--richka{color:#47727A;font-size:17px}
''')

# =====================================================================================================================
# 3. Чітка й упевнена — добрий сучасний сервіс
S['chitka'] = dict(
    nazva='Чітка й упевнена', grafik='bars',
    shryfty=[('Onest', 'onest', [400, 500, 600, 700], False)],
    znak='<span class="zn-kv"></span><span class="zn">Моя вулиця</span>',
    hrupy_kol=['#8A8F98', '#9AA400', '#0097A7', '#D6336C', '#7B4DFF', '#C88A00', '#2E9E4F'],
    haslo='Що болить вашому будинку — у фактах.',
    poshuk_znak='<svg width="18" height="18" viewBox="0 0 18 18"><circle cx="7.5" cy="7.5" r="5.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M11.6 11.6 L16 16" stroke="currentColor" stroke-width="2"/></svg>',
    karta=karta(pidkladka=dict(tlo='#EFEFEC', voda='#D6DEE6', park='#E3E8DD', doroha='#FFFFFF', doroha2='#F7F7F5'),
                ramp=['#D9D9D4', '#B2B2AC', '#86867F', '#4B4B46', '#1F4DFF'], sotaOp=.95, mezhaSoty='#FFFFFF', mezhaSotyW=.7,
                mezhaRayonu='#111111', mezhaRayonuW=.7, mezhaRayonuDash=[2, 2], vybrana='#111111', vybranaW=2.4,
                problema=dict(vyd='kvadrat-povnyi', kolir='#111111', tlo='#FFFFFF'),
                temna=dict(pidkladka=dict(tlo='#0F0F10', voda='#16202B', park='#141813', doroha='#26262A', doroha2='#1C1C1F'),
                           ramp=['#2A2A2D', '#45454A', '#6E6E74', '#A9A9AF', '#4D74FF'], mezhaSoty='#0F0F10', mezhaRayonu='#8A8A90',
                           vybrana='#FFFFFF', problema=dict(vyd='kvadrat-povnyi', kolir='#FFFFFF', tlo='#0F0F10'))),
    css='''
:root{--tlo:#F4F4F2;--surface:#FFFFFF;--ink:#111111;--ink-2:#333333;--muted:#6B6B66;--line:#E4E4E0;--line-strong:#CFCFCA;
--akcent:#1F4DFF;--na-akcenti:#FFFFFF;--f-tekst:'Onest',sans-serif;--h-shapka:60px;--pole:24px;--kolonka:1040px;--h1:44px;--h1-tel:30px;--h2:22px;--chyslo:52px;
--g-kolir:#111111;--g-tiho:#DCDCD7;--g-osnova:#CFCFCA;--smuha-h:8px;--smuha-tlo:#EFEFEC;--smuha-kolir:#111111;--smuha-sus:#B9B9B3;--pidpys:#55554F;--pidpys-rozmir:11px;--pidpys-rozmir-tel:9px}
[data-t=temna]{--tlo:#0F0F10;--surface:#18181A;--ink:#F2F2F0;--ink-2:#D4D4D0;--muted:#8E8E8A;--line:#2A2A2D;--line-strong:#3D3D41;--akcent:#4D74FF;--pidpys:#9A9A96}
body{font-size:16px;letter-spacing:-.005em}
.shapka{background:var(--surface);border-bottom:1px solid var(--line)}
.zn-kv{width:20px;height:20px;background:var(--ink);position:relative}.zn-kv:after{content:"";position:absolute;right:0;bottom:0;width:8px;height:8px;background:var(--akcent)}
.zn{font-weight:700;font-size:18px;letter-spacing:-.02em}
.menu{font-weight:500;font-size:14.5px;gap:6px}.menu a{padding:7px 12px;border-radius:6px;color:var(--ink-2)}.menu a.aktyvne{background:var(--ink);color:#fff}
.tema{border:1px solid var(--line-strong);border-radius:6px}
h1,h2,.k-zag h2,.hrupa-zag h3{font-weight:700;letter-spacing:-.025em}
.chyslo{font-weight:600;letter-spacing:-.03em}
.mitka{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--akcent)}
.storinka{display:grid;grid-template-columns:repeat(12,1fr);column-gap:24px;align-items:start}
.storinka>*{grid-column:1/-1}
[data-prystrii=pk] .storinka--budynok .zaholovok{grid-column:1/9}
[data-prystrii=pk] .storinka--budynok .chysla{grid-column:9/13;grid-row:2/4;grid-template-columns:1fr;position:sticky;top:20px}
[data-prystrii=pk] .storinka--budynok .rozdil{grid-column:1/9}
[data-prystrii=pk] .storinka--budynok .rozdil--prodazh{grid-column:9/13;grid-row:4/6}
[data-prystrii=pk] .storinka--budynok>.prymitka{grid-column:1/9}
.zaholovok{margin-bottom:24px}
.vstup{font-size:16.5px;line-height:1.6;color:var(--ink-2)}
.chyslo-blok{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:18px 20px}
.chyslo-blok span{color:var(--muted);font-size:13.5px}
.rozdil{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:22px 24px;margin-bottom:20px}
[data-prystrii=tel] .rozdil{padding:18px 16px}
.rozdil h2{font-size:19px}
.rozdil-pidpys{font-size:14px}
.smuha,.smuha i{border-radius:2px}
.tabl th,.tabl td{padding:11px 8px}.tabl tbody tr:last-child td,.tabl tbody tr:last-child th{border-bottom:0}
.tabl thead th{text-transform:uppercase;letter-spacing:.05em;font-size:11.5px}
.knopka{border:1px solid var(--line-strong);border-radius:6px;font-weight:600;font-size:15px;min-height:46px}
.knopka--holovna{border-color:var(--akcent)}
.rozdil--prodazh{background:var(--ink);color:#fff;border-color:var(--ink)}.rozdil--prodazh .prymitka,.rozdil--prodazh .haslo{color:#A9A9A4}
.rozdil--prodazh .knopka:not(.knopka--holovna){background:transparent;color:#fff;border-color:#4A4A46}
.haslo{text-transform:uppercase;letter-spacing:.06em;font-size:11.5px;font-weight:600}
.holovne{font-size:17px;counter-reset:n;gap:0;border-top:1px solid var(--line)}
.holovne li{counter-increment:n;display:grid;grid-template-columns:36px 1fr;padding:12px 0;border-bottom:1px solid var(--line)}
.holovne li:before{content:"0" counter(n);font-weight:600;color:var(--akcent);font-size:14px;padding-top:2px}
.chysla--3{grid-template-columns:repeat(3,1fr)}
.hrupy-sitka{gap:12px;grid-template-columns:repeat(3,1fr)}
[data-prystrii=tel] .hrupy-sitka{grid-template-columns:1fr}
.storinka--rayon .rozdil:has(.hrupy-sitka){background:transparent;border:0;padding:0}
.hrupa{background:var(--surface);border:1px solid var(--line);border-radius:8px}
.hrupa-zag{padding-bottom:10px;border-bottom:1px solid var(--line)}
.hr{width:10px;height:10px;border-radius:2px}
.trend{display:inline-block;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;padding:2px 7px;border-radius:4px;background:#EFEFEC}
.trend--vgoru{background:#111;color:#fff}
/* карта */
.poshuk{border:1px solid var(--line-strong);border-radius:8px}
.filtr{border:1px solid var(--line-strong);border-radius:8px}
.legenda{border:1px solid var(--line);border-radius:8px}.legenda-shkala i{width:24px;height:8px;margin-right:2px}
.legenda-pr i{width:10px;height:10px;background:#111;outline:1.5px solid #fff}
.kartka-soty{border:1px solid var(--line);border-radius:10px;gap:0;padding:0}
.kartka-soty>*{padding:14px 20px;border-bottom:1px solid var(--line)}
.kartka-soty>.k-knopky{border:0}
.k-zag{padding-right:44px}.k-zakryty{right:14px;top:12px}
.k-chyslo .chyslo{font-size:46px}
.k-rozdil h3{text-transform:uppercase;letter-spacing:.06em;font-size:11px}
.k-zamok{background:#F4F4F2}
.k-knopky .knopka{flex:1}
[data-prystrii=tel] .kartka-soty{border-radius:14px 14px 0 0}
.pidpys{font-weight:600;text-transform:uppercase;letter-spacing:.08em;text-shadow:0 0 2px #EFEFEC,0 0 2px #EFEFEC,0 0 2px #EFEFEC}
.pidpys--richka{color:#5C7A99;font-size:12px;letter-spacing:.3em}
''')

# =====================================================================================================================
# 4. Нічне місто
S['nich'] = dict(
    nazva='Нічне місто', grafik='bars', tema='temna',
    shryfty=[('Unbounded', 'unbounded', [500, 700], False), ('IBM Plex Sans Condensed', 'ibm-plex-sans-condensed', [400, 500, 600], False)],
    znak='<span class="zn">моя вулиця</span><i class="zn-krapka"></i>',
    hrupy_kol=['#A8AFBF', '#D4E157', '#4FB3FF', '#FF6FA3', '#B78CFF', '#FFC857', '#6FD08C'],
    haslo='Що болить вашому будинку — у фактах.',
    karta=karta(pidkladka=dict(tlo='#0B0C0F', voda='#101B26', park='#0E130F', doroha='#272B33', doroha2='#191C22', zaliznytsia='#22262D'),
                ramp=['#3A2B17', '#6E4A18', '#B0711C', '#EE9F30', '#FFE2A3'], sotaOp=.96, mezhaRayonu='#3A3F4B', mezhaRayonuW=.7,
                vybrana='#FFFFFF', vybranaW=2, problema=dict(vyd='kvadrat', kolir='#FFFFFF', tlo='#0B0C0F')),
    css='''
:root{--tlo:#0B0C0F;--surface:#13151A;--ink:#F3F1EA;--ink-2:#C9C6BE;--muted:#8B8F99;--line:#252932;--line-strong:#3A3F4B;
--akcent:#FFB547;--na-akcenti:#0B0C0F;--f-tekst:'IBM Plex Sans Condensed',sans-serif;--f-disp:'Unbounded',sans-serif;--h-shapka:60px;--pole:28px;--kolonka:820px;
--h1:42px;--h1-tel:28px;--h2:20px;--chyslo:56px;--g-kolir:#FFB547;--g-tiho:#2C303A;--g-osnova:#3A3F4B;--smuha-h:6px;--smuha-tlo:#1C1F26;--smuha-kolir:#FFB547;--smuha-sus:#5A606D;
--pidpys:#8F95A1;--pidpys-rozmir:10.5px;--pidpys-rozmir-tel:8.5px}
body{font-size:17px}
.shapka{border-bottom:1px solid var(--line);background:#08090B}
.zn{font-family:var(--f-disp);font-weight:700;font-size:15px;text-transform:uppercase;letter-spacing:.02em}
.zn-krapka{width:8px;height:8px;background:var(--akcent);display:block}
.menu{text-transform:uppercase;letter-spacing:.12em;font-size:13px;font-weight:500}.menu a{color:var(--muted)}.menu a.aktyvne{color:var(--akcent)}
.tema{background:transparent;border:1px solid var(--line-strong);color:var(--akcent)}
h1,h2,.k-zag h2,.hrupa-zag h3{font-family:var(--f-disp);font-weight:700;letter-spacing:-.01em}
h1{line-height:1.12}
.hrupa-zag h3{font-size:14px;line-height:1.35}
.chyslo{font-family:var(--f-disp);font-weight:700;color:var(--akcent);letter-spacing:-.03em}
.mitka,.haslo,.k-rozdil h3,.smuha-shapka,.tabl thead th,.hrupa-vydy-zag{text-transform:uppercase;letter-spacing:.14em;font-size:12px;color:var(--akcent);font-weight:600}
.kryhty{text-transform:uppercase;letter-spacing:.1em;font-size:11.5px}.kryhty a:after{content:"/";margin-left:14px;color:var(--line-strong)}
.vstup{color:var(--ink-2);font-size:18px}
.chyslo-blok{border-left:2px solid var(--akcent);padding:4px 0 4px 18px}
.chyslo-blok span{color:var(--muted)}
.rozdil{border-top:1px solid var(--line);padding-top:22px;margin-bottom:44px}
.rozdil h2{text-transform:uppercase;font-size:17px;letter-spacing:.02em}
.tabl th,.tabl td{border-color:var(--line)}
.knopka{border:1px solid var(--line-strong);background:transparent;text-transform:uppercase;letter-spacing:.1em;font-size:13.5px;font-weight:600;min-height:48px}
.knopka--holovna{background:var(--akcent);color:#0B0C0F;border-color:var(--akcent)}
.holovne{counter-reset:n}.holovne li{counter-increment:n;padding-left:40px;position:relative;color:var(--ink-2)}
.holovne li:before{content:"0" counter(n);position:absolute;left:0;top:3px;font-family:var(--f-disp);font-size:12px;color:var(--akcent)}
.hrupa{background:var(--surface);border:1px solid var(--line)}
.hr{width:8px;height:8px}
.trend{color:var(--akcent);text-transform:uppercase;font-size:12px;letter-spacing:.08em}
.grafik text{font-family:var(--f-tekst)}
/* карта */
.poshuk,.filtr,.legenda,.dzherela{background:#13151Ae6;border:1px solid var(--line-strong)}
.poshuk-znak{color:var(--akcent)}
.filtr{text-transform:uppercase;letter-spacing:.1em;font-size:12.5px}
.kartka-soty{border:1px solid var(--line-strong);background:#101216}
.k-zag h2{font-size:18px}
.k-chyslo .chyslo{font-size:50px}
.k-hrupy{font-size:15px}
.k-problema{color:var(--akcent)}
.k-knopky .knopka{font-size:12.5px}
.pidpys{text-transform:uppercase;letter-spacing:.18em;font-weight:500}
.pidpys--richka{color:#4E6E8E;font-size:12px;letter-spacing:.5em}
''')

# =====================================================================================================================
# 5. Сміла й гучна — плакат
S['smila'] = dict(
    nazva='Сміла й гучна', grafik='bars',
    shryfty=[('Unbounded', 'unbounded', [600, 800, 900], False), ('Manrope', 'manrope', [400, 600, 800], False)],
    znak='<span class="zn">МОЯ<br>ВУЛИЦЯ</span>',
    hrupy_kol=['#6B6B6B', '#9C9A00', '#007C89', '#E0245E', '#6C3CE0', '#E8A000', '#1E8A3E'],
    haslo='Що болить вашому будинку — у фактах.',
    karta=karta(pidkladka=dict(tlo='#ECEAE2', voda='#D3D0C6', park='#E2E0D6', doroha='#FFFFFF', doroha2='#F6F4EE'),
                ramp=['#D7D4C9', '#B0AC9E', '#757168', '#2D2B27', '#FFD60A'], sotaOp=1, mezhaSoty='#ECEAE2', mezhaSotyW=.6,
                vershyna='#0A0A0A', vershynaW=1.4, mezhaRayonu='#0A0A0A', mezhaRayonuW=1.2, vybrana='#0A0A0A', vybranaW=3.5,
                problema=dict(vyd='kolo', kolir='#0A0A0A', tlo='#FFD60A'),
                temna=dict(pidkladka=dict(tlo='#0A0A0A', voda='#1C1C1A', park='#131311', doroha='#2A2A27', doroha2='#1A1A18'),
                           ramp=['#2A2925', '#4A4842', '#8A877E', '#D9D6CB', '#FFD60A'], mezhaSoty='#0A0A0A', vershyna='#FFFFFF',
                           mezhaRayonu='#FFFFFF', vybrana='#FFFFFF', problema=dict(vyd='kolo', kolir='#FFD60A', tlo='#0A0A0A'))),
    css='''
:root{--tlo:#F1EFE6;--surface:#FFFFFF;--ink:#0A0A0A;--ink-2:#1F1F1C;--muted:#5E5B52;--line:#0A0A0A;--line-strong:#0A0A0A;--zhovtyi:#FFD60A;
--akcent:#0A0A0A;--na-akcenti:#FFD60A;--f-tekst:'Manrope',sans-serif;--f-disp:'Unbounded',sans-serif;--h-shapka:68px;--pole:24px;--kolonka:1100px;
--h1:76px;--h1-tel:31px;--h2:30px;--chyslo:132px;--g-kolir:#0A0A0A;--g-tiho:#CFCBBE;--g-osnova:#0A0A0A;--smuha-h:18px;--smuha-tlo:transparent;--smuha-kolir:#0A0A0A;--smuha-sus:#BDB9AC;
--pidpys:#0A0A0A;--f-pidpys:'Unbounded',sans-serif;--pidpys-rozmir:10px;--pidpys-rozmir-tel:8px}
[data-t=temna]{--tlo:#0A0A0A;--surface:#161614;--ink:#F5F3EA;--akcent:#FFD60A;--na-akcenti:#0A0A0A;--line:#F5F3EA;--pidpys:#F5F3EA}
body{font-size:17px;font-weight:600}
.shapka{border-bottom:4px solid var(--ink);background:var(--tlo)}
.znak{background:var(--zhovtyi);padding:6px 10px;margin-left:-4px}
.zn{font-family:var(--f-disp);font-weight:900;font-size:15px;line-height:.95;letter-spacing:-.01em;color:#0A0A0A}
.menu{font-weight:800;text-transform:uppercase;font-size:13px;letter-spacing:.04em}.menu a{color:var(--ink)}.menu a.aktyvne{background:var(--ink);color:var(--zhovtyi);padding:2px 8px}
.tema{border:3px solid var(--ink);background:var(--zhovtyi)}
h1,h2,.k-zag h2,.hrupa-zag h3{font-family:var(--f-disp);font-weight:800;text-transform:uppercase;letter-spacing:-.02em}
h1{line-height:.98;margin-bottom:24px}
.chyslo{font-family:var(--f-disp);font-weight:900;letter-spacing:-.05em}
.mitka{background:var(--ink);color:var(--zhovtyi);font-family:var(--f-disp);font-weight:600;text-transform:uppercase;font-size:12px;padding:6px 10px;letter-spacing:.04em}
.kryhty{text-transform:uppercase;font-weight:800;font-size:12px;letter-spacing:.04em}.kryhty a{color:var(--ink)}.kryhty a:after{content:"→";margin-left:10px}
.vstup{font-size:19px;font-weight:600;max-width:62ch}
.chysla{gap:0;border:4px solid var(--ink);margin-bottom:48px}
.chyslo-blok{background:var(--zhovtyi);padding:20px 24px 24px}
.chyslo-blok+.chyslo-blok{background:var(--surface);border-left:4px solid var(--ink)}
.chyslo-blok span{font-size:16px;font-weight:800;text-transform:uppercase;color:var(--ink);letter-spacing:.01em}
[data-prystrii=tel] .chysla{grid-template-columns:1fr}
[data-prystrii=tel] .chyslo-blok+.chyslo-blok{border-left:0;border-top:4px solid var(--ink)}
[data-prystrii=tel] .chyslo-blok .chyslo{font-size:96px}
.chysla--3 .chyslo-blok .chyslo{font-size:96px}
[data-prystrii=tel] .chysla--3 .chyslo-blok .chyslo{font-size:72px}
[data-prystrii=tel] .chysla--3 .chyslo-blok+.chyslo-blok{border-left:0;border-top:4px solid var(--ink)}
[data-prystrii=tel] .chysla--3 .chyslo-blok:nth-child(3){border-left:4px solid var(--ink)}
.rozdil{border-top:4px solid var(--ink);padding-top:18px;margin-bottom:56px}
.rozdil-pidpys{color:var(--ink-2);font-weight:500}
.prymitka{font-weight:500}
.smuha-ryad{font-weight:700}
.smuha-ryad b{font-family:var(--f-disp);font-weight:800}
.tabl{border:3px solid var(--ink)}.tabl th,.tabl td{border-bottom:2px solid var(--ink);font-weight:700}
.tabl td{font-family:var(--f-disp);font-weight:800;font-size:18px}
.tabl thead th{background:var(--ink);color:var(--zhovtyi);text-transform:uppercase}
.knopka{border:3px solid var(--ink);font-weight:800;text-transform:uppercase;font-size:15px;min-height:56px;letter-spacing:.02em}
.knopka--holovna{background:var(--ink);color:var(--zhovtyi)}
.rozdil--prodazh{background:var(--zhovtyi);border:4px solid var(--ink);padding:24px}
.rozdil--prodazh .knopka:not(.knopka--holovna){background:transparent}
.haslo{font-family:var(--f-disp);font-weight:800;text-transform:uppercase;color:var(--ink);font-size:14px}
.holovne{font-size:21px;font-weight:700;gap:14px;list-style:none}.holovne li{border-left:10px solid var(--zhovtyi);padding-left:16px}
.hrupy-sitka{gap:0;border:3px solid var(--ink)}
.hrupa{border:0;border-bottom:3px solid var(--ink);padding:22px}
.hrupa:nth-child(odd){border-right:3px solid var(--ink)}
[data-prystrii=tel] .hrupa{border-right:0!important}
.hrupa-zag h3{font-size:16px}
.chyslo--s{font-size:44px}
.hr{width:16px;height:16px}
.trend{background:var(--ink);color:var(--zhovtyi);padding:1px 6px;text-transform:uppercase;font-size:12px}
.grafik text{font-family:var(--f-disp);font-weight:600;fill:#0A0A0A}
/* карта */
.poshuk,.filtr,.legenda{border:3px solid var(--ink);font-weight:700}
.poshuk{height:54px}
.legenda-pr i{width:10px;height:10px;border-radius:50%;background:#0A0A0A;outline:2px solid #FFD60A}
.kartka-soty{border:4px solid var(--ink);padding:0;gap:0}
.kartka-soty>*{padding:12px 20px}
.k-zag{background:var(--ink);color:var(--zhovtyi);padding:14px 50px 14px 20px}.k-zag h2{font-size:18px}.k-pidpys{color:#CFCBBE}.k-zakryty{color:var(--zhovtyi);right:14px;top:10px}
.k-chyslo{background:var(--zhovtyi);flex-direction:column;align-items:flex-start;gap:4px}
.k-chyslo .chyslo{font-size:92px;line-height:.9}
.k-chyslo span{font-weight:800;text-transform:uppercase;font-size:13px}
.k-chyslo em{color:var(--ink)}
.k-rozdil h3{font-family:var(--f-disp);text-transform:uppercase;color:var(--ink);font-size:11px}
.k-hrupy{font-weight:700}.k-hrupy b{font-family:var(--f-disp)}
.k-knopky .knopka{font-size:13px;min-height:46px}
[data-prystrii=tel] .kartka-soty{border-left:0;border-right:0;border-bottom:0;max-height:56%}
[data-prystrii=tel] .k-chyslo .chyslo{font-size:76px}
.pidpys{font-weight:600;text-transform:uppercase;letter-spacing:.02em;text-shadow:0 0 3px #ECEAE2,0 0 3px #ECEAE2,0 0 2px #ECEAE2}
.pidpys--richka{font-size:16px;font-weight:900;letter-spacing:.2em}
''')

# =====================================================================================================================
# 6. Свій Київ
_MOZ = ['#1F5C6B', '#2F7C82', '#C89B3C', '#24508C', '#6FA6A3', '#1E4D6B', '#A9C9C2', '#B0743A', '#2F7C82', '#24508C']
def _mozaika(n=140, r=5.0):
    import random
    rnd = random.Random(7)
    out = [f'<svg class="mozaika" viewBox="0 0 {n * 9} 12" preserveAspectRatio="xMinYMid slice" aria-hidden="true">']
    for i in range(n):
        c = rnd.choice(_MOZ)
        x = i * 9 + 4.5
        y = 6 + (2.6 if i % 2 else -2.6) * 0
        pts = ' '.join(f'{x + r * __import__("math").cos(a / 3 * 3.14159 + .5236):.1f},{y + r * __import__("math").sin(a / 3 * 3.14159 + .5236):.1f}' for a in range(6))
        out.append(f'<polygon points="{pts}" fill="{c}"/>')
    out.append('</svg>')
    return ''.join(out)

S['kyiv'] = dict(
    nazva='Свій Київ', grafik='tiles',
    shryfty=[('Literata', 'literata', [400, 600, 700], True), ('Manrope', 'manrope', [400, 600, 700], False)],
    znak='<svg class="zn-pl" width="30" height="26" viewBox="0 0 30 26"><polygon points="8,1 15,5 15,13 8,17 1,13 1,5" fill="#1F5C6B"/><polygon points="22,1 29,5 29,13 22,17 15,13 15,5" fill="#C89B3C" transform="translate(-0.5,0)"/><polygon points="15,9 22,13 22,21 15,25 8,21 8,13" fill="#24508C"/></svg><span class="zn">Моя вулиця</span><span class="zn-misto">Київ</span>',
    hrupy_kol=['#8E9AA0', '#9A8F2E', '#1F7A80', '#A3475E', '#5D4E8C', '#B8862F', '#3C7A4F'],
    dekor_verkh=_mozaika(),
    haslo='Що болить вашому будинку — у фактах.',
    karta=karta(pidkladka=dict(tlo='#ECE6D9', voda='#9CC2C3', park='#DCDDC6', doroha='#E0D6C2', doroha2='#E6DECD'),
                sotaVyd='mosaic', ramp=['#D9E3DC', '#CFDCD5', '#A9C9C2', '#9DBFB9', '#6FA6A3', '#649D9B', '#2F7C82', '#28727A', '#1E4D6B', '#183F5C'],
                mezhaSoty='#ECE6D9', mezhaSotyW=1.3, mezhaRayonu='#7E6C4C', mezhaRayonuW=.8, vybrana='#C89B3C', vybranaW=3,
                problema=dict(vyd='romb', kolir='#7A4E1D', tlo='#F8F5EE'),
                pidpysy=PIDPYSY + [DNIPRO, {'t': 'Правий берег', 'n': 'Правий берег', 'll': [30.40, 50.335], 'kl': 'pidpys--bereh', 'pk': 1},
                                   {'t': 'Лівий берег', 'n': 'Лівий берег', 'll': [30.73, 50.37], 'kl': 'pidpys--bereh', 'pk': 1}],
                temna=dict(pidkladka=dict(tlo='#10191C', voda='#163A40', park='#141F1A', doroha='#22302F', doroha2='#1A2626'),
                           ramp=['#1C2B2B', '#1F302F', '#24474A', '#274D50', '#2F6E73', '#327478', '#4E9EA0', '#55A6A7', '#B9DCD5', '#C8E4DD'],
                           mezhaSoty='#10191C', mezhaRayonu='#5E5440', vybrana='#C89B3C', problema=dict(vyd='romb', kolir='#C89B3C', tlo='#10191C'))),
    css='''
:root{--tlo:#EFEAE0;--surface:#F8F5EE;--ink:#1E2426;--ink-2:#3B4446;--muted:#6E716A;--line:#D8D1C2;--line-strong:#B9B09C;
--akcent:#1F5C6B;--na-akcenti:#F8F5EE;--vokhra:#C89B3C;--smalta:#24508C;--f-tekst:'Manrope',sans-serif;--f-serif:'Literata',serif;
--h-shapka:64px;--pole:28px;--kolonka:860px;--h1:48px;--h1-tel:32px;--h2:26px;--chyslo:56px;--g-kolir:#1F5C6B;--g-tiho:#CFC6B3;--g-osnova:#B9B09C;
--smuha-h:12px;--smuha-tlo:#E5DFD2;--smuha-kolir:#2F7C82;--smuha-sus:#C89B3C;--pidpys:#4A4A40;--f-pidpys:'Literata',serif;--pidpys-rozmir:13px;--pidpys-rozmir-tel:10.5px}
[data-t=temna]{--tlo:#10191C;--surface:#162226;--ink:#EDE8DC;--ink-2:#CFC9BB;--muted:#8E958F;--line:#25363A;--line-strong:#3D5257;--akcent:#6FB7B5;--pidpys:#B7BDB3}
.mozaika{display:block;width:100%;height:12px;background:var(--tlo)}
.je-karta .mozaika{height:8px}
body{font-size:16.5px}
.shapka{border-bottom:1px solid var(--line-strong)}
.zn{font-family:var(--f-serif);font-weight:700;font-size:20px}
.zn-misto{font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--akcent);border-left:1px solid var(--line-strong);padding-left:10px}
.menu{font-weight:600;font-size:14.5px}.menu a.aktyvne{color:var(--akcent);box-shadow:inset 0 -3px 0 var(--vokhra)}
.menu a{padding:20px 0}
.tema{border:1px solid var(--line-strong);border-radius:2px}
h1,h2,.k-zag h2,.hrupa-zag h3{font-family:var(--f-serif);font-weight:600;letter-spacing:-.01em}
.chyslo{font-family:var(--f-serif);font-weight:700;color:var(--akcent)}
.mitka,.haslo,.k-rozdil h3,.smuha-shapka,.tabl thead th,.hrupa-vydy-zag{font-size:11.5px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--akcent)}
.mitka:before{content:"";display:inline-block;width:18px;height:3px;background:var(--vokhra);vertical-align:middle;margin-right:10px}
.kryhty a:after{content:"·";margin-left:12px}
.vstup{font-family:var(--f-serif);font-size:18.5px;line-height:1.62}
.chysla{gap:0;background:var(--surface);border:1px solid var(--line)}
.chyslo-blok{padding:20px 22px}.chyslo-blok+.chyslo-blok{border-left:1px solid var(--line)}
.chyslo-blok:nth-child(2) .chyslo{color:var(--smalta)}.chyslo-blok:nth-child(3) .chyslo{color:#8C6A23}
[data-prystrii=tel] .chysla--3 .chyslo-blok:nth-child(2){border-left:0}
[data-prystrii=tel] .chysla--3 .chyslo-blok:first-child{border-bottom:1px solid var(--line)}
.chyslo-blok span{color:var(--ink-2)}
.rozdil h2{display:flex;align-items:center;gap:12px}
.rozdil h2:before{content:"";width:22px;height:22px;flex:none;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 22 22'%3E%3Cpolygon points='6,1 11,4 11,10 6,13 1,10 1,4' fill='%231F5C6B'/%3E%3Cpolygon points='16,1 21,4 21,10 16,13 11,10 11,4' fill='%23C89B3C'/%3E%3Cpolygon points='11,9 16,12 16,18 11,21 6,18 6,12' fill='%2324508C'/%3E%3C/svg%3E") center/contain no-repeat}
.tabl{background:var(--surface);border:1px solid var(--line)}
.knopka{border:1px solid var(--akcent);color:var(--akcent);font-weight:700;border-radius:2px;background:var(--surface)}
.knopka--holovna{background:var(--akcent);color:var(--na-akcenti)}
.rozdil--prodazh{border-top:6px solid var(--vokhra);background:var(--surface);padding:22px 24px}
.holovne{font-family:var(--f-serif);font-size:18.5px;list-style:none}.holovne li{border-left:3px solid var(--vokhra);padding-left:16px}
.hrupa{background:var(--surface);border:1px solid var(--line);border-top:5px solid var(--hk-t,var(--akcent));border-radius:2px}
.hr{width:12px;height:13px;clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%)}
.trend{color:var(--akcent)}
.grafik text{font-family:var(--f-tekst);font-weight:600}
/* карта */
.poshuk,.filtr,.legenda{border:1px solid var(--line-strong);border-radius:2px;background:var(--surface)}
.legenda-shkala i{clip-path:polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%);width:18px;height:16px;margin-right:2px}
.legenda-pr i{width:10px;height:10px;border:1.5px solid #7A4E1D;transform:rotate(45deg)}
.kartka-soty{border:1px solid var(--line-strong);border-top:6px solid var(--vokhra);border-radius:2px}
.k-zag h2{font-size:23px}
.k-chyslo .chyslo{font-size:52px}
.pidpys{font-style:italic;text-shadow:0 0 3px #ECE6D9,0 0 3px #ECE6D9,0 0 2px #ECE6D9}
.pidpys--richka{font-size:22px;color:#1F5C6B;font-weight:600;letter-spacing:.06em;text-shadow:0 0 3px #9CC2C3}
[data-prystrii=tel] .pidpys--richka{font-size:15px}
.pidpys--bereh{font-family:var(--f-tekst);font-style:normal;font-size:10.5px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:#8C6A23}
''')

# =====================================================================================================================
# 7. Вектор — не бачиш цілі, бачиш напрям. Два варіанти: «ніч» (темний, штриховка) і «рух» (світлий, риски змін).
def _shtrykh_legenda(kol, tlo):
    out = []
    for c, w in enumerate([1, 1.6, 2.4, 3.4, 4.6], 1):
        k = '#EEEBE4' if c == 5 else kol
        out.append(f'<svg width="22" height="12" viewBox="0 0 22 12"><rect width="22" height="12" fill="{tlo}"/>'
                   + ''.join(f'<line x1="{x}" y1="12" x2="{x + 12}" y2="0" stroke="{k}" stroke-width="{w * .6:.1f}"/>' for x in range(-12, 24, 4))
                   + '</svg>')
    return ('<div class="legenda"><span>менше подій</span><span class="legenda-shkala">' + ''.join(out)
            + '</span><span>більше</span><span class="legenda-pr"><i></i>проблема</span></div>')


_VEKTOR_SPILNE = '''
--f-tekst:'IBM Plex Sans Condensed',sans-serif;--f-mono:'JetBrains Mono',monospace;--h-shapka:58px;--pole:28px;--kolonka:820px;
--h1:50px;--h1-tel:32px;--h2:17px;--chyslo:60px;--pidpys-rozmir:10.5px;--pidpys-rozmir-tel:8.5px}
html,body{overflow-x:clip}body{font-size:17px}
.shapka{border-bottom:0}
.shapka:after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:12px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1000' height='12' preserveAspectRatio='none'%3E%3Cline x1='0' y1='11.5' x2='1000' y2='0.5' stroke='VK' stroke-width='1.2' vector-effect='non-scaling-stroke'/%3E%3C/svg%3E") 0 0/100% 100% no-repeat}
.znak{gap:12px}
.zn{font-weight:700;font-size:15px;letter-spacing:.24em;text-transform:uppercase}
.zn-v{display:block;width:34px;height:12px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 34 12'%3E%3Cline x1='0' y1='11' x2='32' y2='1' stroke='VK' stroke-width='1.6'/%3E%3Cpolyline points='24,0.5 32.5,1 27,7' fill='none' stroke='VK' stroke-width='1.6'/%3E%3C/svg%3E") no-repeat}
.menu{text-transform:uppercase;letter-spacing:.14em;font-size:12.5px;font-weight:500}.menu a{color:var(--muted)}.menu a.aktyvne{color:var(--ink-strong)}
.tema{background:transparent;border:1px solid var(--line-strong)}
h1,h2,.k-zag h2,.hrupa-zag h3{font-weight:600;text-transform:uppercase;letter-spacing:.03em;color:var(--ink-strong)}
h1{line-height:1.02;letter-spacing:.01em}
.chyslo{font-family:var(--f-mono);font-weight:500;letter-spacing:-.04em;color:var(--ink-strong)}
.mitka,.haslo,.k-rozdil h3,.smuha-shapka,.tabl thead th,.hrupa-vydy-zag,.kryhty{font-family:var(--f-mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:400}
.kryhty a:after{content:"\\2192";margin-left:12px}
.zaholovok:after{content:"";display:block;height:14px;margin:28px calc((100% - 100vw) / 2) 0 0;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='2000' height='14'%3E%3Cline x1='0' y1='7' x2='2000' y2='7' stroke='VK' stroke-width='1'/%3E%3C/svg%3E") 0 0 no-repeat}
.vstup{font-size:18px;color:var(--ink)}
.chysla{gap:0;margin-bottom:52px}
.chyslo-blok{border-top:1px solid var(--line-strong);padding:16px 24px 0 0}
.chyslo-blok span{font-family:var(--f-mono);font-size:12px;letter-spacing:.02em;color:var(--muted)}
.rozdil{margin-bottom:56px}
.rozdil h2{display:flex;align-items:center;gap:14px;margin-bottom:14px}
.rozdil h2:before{content:"";width:46px;height:12px;flex:none;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 46 12'%3E%3Cline x1='0' y1='11' x2='44' y2='1' stroke='VK' stroke-width='1.4'/%3E%3Cpolyline points='36,0.5 44.6,1 39,7' fill='none' stroke='VK' stroke-width='1.4'/%3E%3C/svg%3E") no-repeat}
.tabl td{font-family:var(--f-mono);font-size:14px}
.tabl th,.tabl td{border-color:var(--line)}
.knopka{border:1px solid var(--line-strong);background:transparent;text-transform:uppercase;letter-spacing:.12em;font-size:13px;font-weight:600;min-height:48px;gap:14px}
.knopka:after{content:"";width:28px;height:8px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 28 8'%3E%3Cline x1='0' y1='4' x2='27' y2='4' stroke='VK' stroke-width='1.2'/%3E%3Cpolyline points='22,0.5 27,4 22,7.5' fill='none' stroke='VK' stroke-width='1.2'/%3E%3C/svg%3E") no-repeat}
.knopka--holovna{background:var(--ink-strong);color:var(--tlo);border-color:var(--ink-strong)}
.knopka--holovna:after{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 28 8'%3E%3Cline x1='0' y1='4' x2='27' y2='4' stroke='VT' stroke-width='1.2'/%3E%3Cpolyline points='22,0.5 27,4 22,7.5' fill='none' stroke='VT' stroke-width='1.2'/%3E%3C/svg%3E")}
.k-knopky .knopka:after{display:none}
.holovne{list-style:none;font-size:18px;gap:14px}.holovne li{padding-left:34px;position:relative}
.holovne li:before{content:"";position:absolute;left:0;top:.45em;width:22px;height:8px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 22 8'%3E%3Cline x1='0' y1='7' x2='21' y2='1' stroke='VK' stroke-width='1.3'/%3E%3C/svg%3E") no-repeat}
.hrupy-sitka{gap:0}
.hrupa{border-top:1px solid var(--line-strong);padding:18px 24px 26px 0}
.hrupa:nth-child(even){padding-left:24px;padding-right:0}
[data-prystrii=tel] .hrupa:nth-child(even){padding-left:0}
.hr{width:14px;height:2px}
.trend{font-family:var(--f-mono);font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;font-weight:500}
.grafik text{font-family:var(--f-mono);font-size:8.5px}
.k-zag h2{font-size:17px}.k-pidpys{font-family:var(--f-mono);font-size:11px}
.k-chyslo .chyslo{font-size:54px}
.k-chyslo span{font-family:var(--f-mono);font-size:12px}
.k-hrupy{font-size:15px}.k-hrupy b{font-family:var(--f-mono);font-weight:500}
.k-pik,.k-zamok{font-size:14px}
.filtr{font-family:var(--f-mono);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.pidpys{text-transform:uppercase;letter-spacing:.22em;font-weight:500}
.pidpys--richka{letter-spacing:.6em;font-size:11px}
'''

S['vektor-nich'] = dict(
    nazva='Вектор · ніч', grafik='vector', tema='temna',
    shryfty=[('IBM Plex Sans Condensed', 'ibm-plex-sans-condensed', [400, 500, 600, 700], False), ('JetBrains Mono', 'jetbrains-mono', [400, 500], False)],
    znak='<span class="zn">Моя вулиця</span><span class="zn-v"></span>',
    hrupy_kol=['#5E5C58', '#76736E', '#8E8B85', '#A6A39D', '#BEBBB4', '#D6D3CC', '#EEEBE4'],
    haslo='Що болить вашому будинку — у фактах.',
    legenda=_shtrykh_legenda('#7A7873', '#262626'),
    karta=karta(pidkladka=dict(tlo='#121212', voda='#1B1E21', park='#151614', doroha='#272727', doroha2='#1C1C1C', zaliznytsia='#232323'),
                sotaVyd='hatch', ramp=['#333'] * 5, hatch='#86837D', hatchPik='#EEEBE4', hatchTlo='#2A2A2A',
                mezhaRayonu='#3E3E3E', mezhaRayonuW=.8, mezhaRayonuDash=[4, 3], vybrana='#EEEBE4', vybranaW=1.6,
                problema=dict(vyd='shevron', kolir='#EEEBE4', tlo='#121212')),
    css=(':root{--tlo:#121212;--surface:#171717;--ink:#BDBAB4;--ink-strong:#EEEBE4;--ink-2:#A9A6A0;--muted:#6F6D69;--line:#262626;--line-strong:#3A3A3A;'
         '--akcent:#EEEBE4;--na-akcenti:#121212;--g-kolir:#EEEBE4;--g-tiho:#3A3A3A;--g-osnova:#4A4A4A;--smuha-h:2px;--smuha-tlo:#262626;'
         '--smuha-kolir:#EEEBE4;--smuha-sus:#5E5C58;--pidpys:#6F6D69;'
         + _VEKTOR_SPILNE.replace('VK', '%23EEEBE4').replace('VT', '%23121212') + '''
.shapka{background:#0E0E0E}
.poshuk,.filtr,.legenda,.dzherela{background:#121212;border:1px solid #333}
.legenda-shkala svg{margin-right:2px;display:block}
.legenda-pr i{width:9px;height:9px;border-right:1.6px solid #EEEBE4;border-top:1.6px solid #EEEBE4;transform:rotate(45deg)}
.kartka-soty{background:#121212;border:1px solid #333;border-left:1px solid #EEEBE4}
.smuha-ryad b{font-family:var(--f-mono);font-weight:500}
'''))

S['vektor-rukh'] = dict(
    nazva='Вектор · рух', grafik='vector',
    shryfty=[('IBM Plex Sans Condensed', 'ibm-plex-sans-condensed', [400, 500, 600, 700], False), ('JetBrains Mono', 'jetbrains-mono', [400, 500, 700], False)],
    znak='<span class="zn">Моя вулиця</span><span class="zn-v"></span>',
    hrupy_kol=['#9A9790', '#86837C', '#726F68', '#5E5B55', '#4A4843', '#36342F', '#161616'],
    haslo='Що болить вашому будинку — у фактах.',
    legenda=('<div class="legenda"><svg width="40" height="14" viewBox="0 0 40 14"><line x1="4" y1="12" x2="30" y2="3" stroke="#161616" stroke-width="1.8"/><circle cx="30" cy="3" r="2.2" fill="#161616"/></svg>'
             '<span>риска — як змінилось 2025 проти 2024: вгору — більше подій, униз — менше; товща — більше подій у соті</span><span class="legenda-pr"><i></i>проблема</span></div>'),
    karta=karta(pidkladka=dict(tlo='#E2E0DB', voda='#CDCFCC', park='#D9D8D0', doroha='#F0EEE9', doroha2='#E9E7E2'),
                sotaVyd='vector', ramp=['#D9D7D1', '#CFCCC5', '#C2BFB7', '#B1ADA4', '#99958B'], sotaOp=.85, vektor='#161616',
                mezhaRayonu='#8F8C85', mezhaRayonuW=.8, mezhaRayonuDash=[4, 3], vybrana='#161616', vybranaW=2,
                problema=dict(vyd='shevron', kolir='#161616', tlo='#E2E0DB')),
    css=(':root{--tlo:#E4E2DD;--surface:#ECEAE5;--ink:#2B2A27;--ink-strong:#111111;--ink-2:#3B3A36;--muted:#6A6862;--line:#CFCCC5;--line-strong:#A8A59E;'
         '--akcent:#111111;--na-akcenti:#E4E2DD;--g-kolir:#111111;--g-tiho:#BDBAB2;--g-osnova:#8F8C85;--smuha-h:3px;--smuha-tlo:#D3D0C9;'
         '--smuha-kolir:#111111;--smuha-sus:#9A978F;--pidpys:#6A6862;'
         + _VEKTOR_SPILNE.replace('VK', '%23111111').replace('VT', '%23E4E2DD') + '''
.shapka{background:var(--tlo)}
.chyslo{font-weight:700}
h1{font-weight:700}
.poshuk,.filtr,.legenda,.dzherela{background:#ECEAE5;border:1px solid #A8A59E}
.legenda{max-width:520px;line-height:1.3}
.legenda-pr i{width:9px;height:9px;border-right:1.8px solid #161616;border-top:1.8px solid #161616;transform:rotate(45deg)}
.kartka-soty{background:#ECEAE5;border:1px solid #A8A59E;border-left:2px solid #111}
.smuha-ryad b{font-family:var(--f-mono)}
.pidpys{text-shadow:0 0 3px #E2E0DB,0 0 3px #E2E0DB}
'''))

# =====================================================================================================================
# 8. Нинішній «Індиго й м'ята» (MV-58) — для порівняння, за docs/STYL.md
S['nynishniy'] = dict(
    nazva="Нинішній: «Індиго й м'ята»", grafik='bars',
    shryfty=[('IBM Plex Sans', 'ibm-plex-sans', [400, 600, 700], False)],
    znak='<svg width="26" height="28" viewBox="0 0 26 28"><polygon points="13,1 25,7.5 25,20.5 13,27 1,20.5 1,7.5" fill="#4447A6"/><polygon points="13,8 19,11.5 19,17.5 13,21 7,17.5 7,11.5" fill="#fff"/></svg><span class="zn">Моя вулиця</span>',
    karta=karta(pidkladka=dict(tlo='#EFF0F6', voda='#CADDF6', park='#E4F2DE', doroha='#FFFFFF', doroha2='#F7F7FB'),
                ramp=['#9CA1E3', '#7E83D2', '#6065C0', '#4549A3', '#31B88D'], sotaOp=.72, mezhaSoty='#FFFFFF', mezhaSotyW=.4,
                mezhaRayonu='#9EA1B8', mezhaRayonuW=.7, vybrana='#3C3CA1', vybranaW=2.6, problema=dict(vyd='kilce', kolir='#4447A6', tlo='#FFFFFF'),
                temna=dict(pidkladka=dict(tlo='#11142A', voda='#122343', park='#002528', doroha='#3E4360', doroha2='#272B45'),
                           ramp=['#444885', '#56599E', '#6A6DB8', '#8A8BDD', '#4DCB9E'], mezhaSoty='#11142A', mezhaRayonu='#4B506F',
                           vybrana='#B37BFF', problema=dict(vyd='kilce', kolir='#66E6BA', tlo='#11142A'))),
    css='''
:root{--tlo:#F4F5FB;--surface:#FFFFFF;--ink:#1C1E2D;--ink-2:#3E4155;--muted:#5F6275;--line:#DFE1E9;--line-strong:#B5B7C4;--mezha:#76798C;--bort:#585B69;
--akcent:#4447A6;--akcent-soft:#DFE3FC;--na-akcenti:#FFFFFF;--f-tekst:'IBM Plex Sans',sans-serif;--h-shapka:56px;--kolonka:760px;--h1:40px;--h1-tel:30px;--h2:24px;--chyslo:34px;
--g-kolir:#4447A6;--g-tiho:#B5B7C4;--g-osnova:#B5B7C4;--smuha-h:10px;--smuha-tlo:transparent;--smuha-kolir:#4447A6;--smuha-sus:#9CA1E3;--pidpys:#444658;--pidpys-rozmir:12px;--pidpys-rozmir-tel:9.5px}
[data-t=temna]{--tlo:#11142A;--surface:#1B1F39;--ink:#F0F1FA;--ink-2:#D1D3E2;--muted:#A6A9C1;--line:#2A2E47;--line-strong:#4B506F;--akcent:#66E6BA;--na-akcenti:#11142A;--pidpys:#D3D6EC}
.shapka{background:var(--surface)}
.zn{font-weight:700;font-size:18px}
.menu{font-weight:600}.menu a.aktyvne{color:var(--akcent)}
.tema,.knopka,.poshuk,.filtr{border:1.5px solid var(--mezha);border-radius:12px;box-shadow:0 3px 0 var(--bort)}
h1,h2,.k-zag h2,.hrupa-zag h3{font-weight:700}
.chyslo{font-weight:800}
.mitka{background:var(--akcent-soft);border-radius:999px;padding:6px 14px;font-weight:600}
.chyslo-blok{border-top:3px solid var(--ink);padding-top:14px}.chyslo-blok+.chyslo-blok{border-left:1px solid var(--line);padding-left:16px}
.chysla{gap:0}
.knopka{font-weight:600}
.knopka--holovna{border-color:var(--akcent)}
.kartka,.hrupa,.tabl{background:var(--surface);border-radius:16px}
.hrupa{border:1px solid var(--line)}
.tabl{border:1px solid var(--line)}
.hr{width:10px;height:10px;border-radius:3px}
.holovne{list-style:disc;padding-left:20px}
.kartka-soty{border-radius:16px;border:1.5px solid var(--mezha)}
[data-prystrii=tel] .kartka-soty{border-radius:16px 16px 0 0}
.k-chyslo .chyslo{font-size:34px}
.k-problema{background:var(--akcent-soft);padding:4px 8px;border-radius:6px}
.k-zamok{border:1.5px dashed var(--line-strong);border-radius:12px;padding:8px 10px;text-align:center}
.legenda{border-radius:12px;border:1.5px solid var(--mezha)}
.pidpys{font-weight:600;text-shadow:0 0 2px #fff,0 0 2px #fff,0 0 3px #fff}
.pidpys--richka{color:#4D6E9C;font-style:italic}
''')

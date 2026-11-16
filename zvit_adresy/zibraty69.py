# -*- coding: utf-8 -*-
"""ZAVDANNYA-69, крок 4: сторінки звіту адреси — перший екран (адреса, 3 висновки, табло), «Місця довкола»,
розділи з 64 нижче, і «Мої адреси» (3 адреси поруч).

  python zvit_adresy/zibraty69.py <тека tmp/zvit-v69> <тека tmp/zvit-v64>

Читає <вихід>/adresy.json і <вихід>/dani/*.json (dani69.py). Пише <вихід>/<slug>.html, mapa-<slug>.js,
mii-adresy.html, index.html; бере оформлення 64 (zvit.css, шрифти) і додає zvit69.css, zvit69.js.
Оформлення — MV-79: «Карта-супутник» на ПК, «Аркуш» на телефоні. Без атрибутів style; ціни — лише 599 / 199 / 399.
"""
import os, sys, re, json, math, html, shutil, collections, datetime

E = lambda s: html.escape(str(s), quote=True)
TUT = os.path.dirname(os.path.abspath(__file__))
KROKY = ['значно менше', 'менше', 'як зазвичай', 'більше', 'значно більше']
MIS = ['січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень', 'жовтень', 'листопад', 'грудень']
MIS_R = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня']
MIS_M = ['січні', 'лютому', 'березні', 'квітні', 'травні', 'червні', 'липні', 'серпні', 'вересні', 'жовтні', 'листопаді', 'грудні']
HR = {'ДТП': 'ДТП', 'ДОР': 'Дороги', 'ГП': 'Громадський порядок', 'МАЙ': 'Майно', 'НАР': 'Наркотики', 'АЛК': 'Алкоголь', 'НАС': 'Насильство'}
HR_SLOVA = {'МАЙ': 'крадіжки та інші майнові', 'НАР': 'наркотики', 'ГП': 'порушення порядку', 'АЛК': 'алкоголь',
            'ДОР': 'водії напідпитку чи без прав', 'ДТП': 'ДТП', 'НАС': 'насильство'}
RAION_R = {'Оболонський': 'Оболонського', 'Шевченківський': 'Шевченківського', 'Дарницький': 'Дарницького',
           'Голосіївський': 'Голосіївського', 'Деснянський': 'Деснянського', 'Дніпровський': 'Дніпровського',
           'Печерський': 'Печерського', 'Подільський': 'Подільського', 'Святошинський': 'Святошинського',
           "Солом'янський": "Солом'янського"}
RAION_M = {'Оболонський': 'Оболонському', 'Шевченківський': 'Шевченківському', 'Дарницький': 'Дарницькому',
           'Голосіївський': 'Голосіївському', 'Деснянський': 'Деснянському', 'Дніпровський': 'Дніпровському',
           'Печерський': 'Печерському', 'Подільський': 'Подільському', 'Святошинський': 'Святошинському',
           "Солом'янський": "Солом'янському"}
TYP_IK = {'metro': 'М', 'shkola': 'Ш', 'sadok': 'С', 'tts': 'ТЦ', 'rynok': 'Р', 'alko': 'А', 'park': 'П', 'zupynka': 'З', 'skup': '•'}
TYP_NAZVA = {'metro': 'метро', 'shkola': 'школа', 'sadok': 'садок', 'tts': 'ТЦ', 'rynok': 'ринок', 'alko': 'заклад з алкоголем',
             'park': 'парк', 'zupynka': 'зупинка', 'skup': 'скупчення'}
TYP_TYPOVYI = {'metro': 'типової станції метро', 'shkola': 'типової школи', 'sadok': 'типового садка', 'tts': 'типового ТЦ',
               'rynok': 'типового ринку', 'alko': 'типового закладу з алкоголем', 'zupynka': 'типової зупинки'}


ZNAKHIDNYI = {'вода': 'воду', "дах, під'їзд, підвал": "дах, під'їзд і підвал", 'шум і незручності від закладів': 'шум від закладів',
              'сусіди й порядок': 'сусідів і порядок', 'торгівля з рук і МАФи': 'торгівлю з рук і МАФи',
              'сміття, прибирання, сніг': 'сміття, прибирання й сніг', 'двір, дерева, майданчики': 'двір, дерева й майданчики',
              'дороги, тротуари, ліхтарі': 'дороги, тротуари й ліхтарі', 'труби, каналізація, газ': 'труби, каналізацію й газ',
              'безпритульні': 'безпритульних'}


def znakh(h):
    return ZNAKHIDNYI.get(h, h)


def mn(n, a, b, c):
    n = abs(int(n))
    return a if n % 10 == 1 and n % 100 != 11 else b if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else c


def podii_s(n):
    return f'{ch(n)} {mn(n, "подія", "події", "подій")}'


def skarh_s(n):
    return f'{ch(n)} {mn(n, "скарга", "скарги", "скарг")}'


def ch(n):
    if isinstance(n, float) and not n.is_integer() and abs(n) < 10:
        return f'{n:.1f}'.replace('.', ',')
    return f'{int(round(n)):,}'.replace(',', ' ')


def dr(x, nk=1):
    """дробове число українською: 0,1; 6,8"""
    s = f'{x:.{nk}f}'.replace('.', ',')
    return s[:-2] if s.endswith(',0') else s


def z_nb(t):
    """текст -> HTML, номер будинку після «№» — у <span class="nb"> (ховається на знімках)"""
    return re.sub(r'№ (\d[^\s,.:;]*)', lambda m: '№ ' + nb(m.group(1)), E(t))


def nb(n):
    return f'<span class="nb">{E(n)}</span>'


def misiats(d):
    return f'{MIS[int(d[5:7]) - 1]} {d[:4]}'


def data_povna(d):
    return f'{int(d[8:10])} {MIS_R[int(d[5:7]) - 1]} {d[:4]}'


def metry(m):
    if m is None:
        return ''
    if m < 25:
        return 'поруч'
    return f'≈ {ch(int(round(m / 10.0) * 10))} м' if m < 1000 else f'≈ {dr(m / 1000)} км'


def khv(m):
    return max(1, int(round(m / 80.0)))


def z_10(pr):
    """частка нижчих у районі -> «9 з 10»"""
    return max(1, min(9, int(pr * 10)))


def adr_html(a):
    a = (a or '').replace('`', 'ʼ')
    m = re.match(r'(.*),\s*([^,]+)$', a)
    return f'{E(m.group(1))}, {nb(m.group(2))}' if m else E(a)


def nazva_mistsia(m):
    if m['typ'] == 'skup':
        a = (m['nazva'] or '').replace('`', 'ʼ')
        if ' / ' in a:
            return 'перехрестя ' + E(a.replace(' / ', ' і '))
        mm = re.match(r'(.*),\s*([^,]+)$', a)
        if mm:
            return f'ділянка {E(mm.group(1))} біля № {nb(mm.group(2))}'
        return E(a)
    n = (m['nazva'] or '').strip()
    t = TYP_NAZVA[m['typ']]
    if m['typ'] == 'metro':
        return f'метро «{E(n)}»'
    if m['typ'] == 'park':
        return E(n) if n else 'парк'
    if m['typ'] == 'zupynka':
        return f'зупинка «{E(n)}»' if n else 'зупинка'
    if not n:
        return t
    n2 = n.strip('«»"')
    if t.lower() in n2.lower() or n2.lower().startswith(('днз', 'дошкільн', 'дитячий садок', 'гімназ', 'ліцей', 'школа', 'тц ', 'трц')):
        return E(n2)
    return f'{t} «{E(n2)}»'


# назви подій людською мовою — за статтею (як у 64)
NAZVY = [
    ('ст.124 КУпАП', 'ДТП: пошкоджено машини'), ('ст.130 КУпАП', 'Водій напідпитку'), ('ст.126 КУпАП', 'Водій без прав чи документів'),
    ('ст.122-4 КУпАП', 'Поїхав з місця ДТП'), ('ст.309 КК', 'Наркотики для себе'), ('ст.178 КУпАП', 'Розпивання чи п\'яний вигляд на вулиці'),
    ('ст.156 КУпАП', 'Порушення торгівлі алкоголем'), ('ст.173 КУпАП', 'Дрібне хуліганство'), ('ст.51 КУпАП', 'Дрібна крадіжка'),
    ('ст.122-2 КУпАП', 'Не зупинився на вимогу поліції'), ('ст.185 КК', 'Крадіжка'), ('ст.160 КУпАП', 'Торгівля з рук'),
    ('ст.44 КУпАП', 'Наркотики, невеликий розмір'), ('ст.185 КУпАП', 'Непокора поліцейському'), ('ст.175-1 КУпАП', 'Куріння в забороненому місці'),
    ('ст.181 КУпАП', 'Гра на автоматах без дозволу'), ('ст.286 КК', 'ДТП з травмами'), ('ст.121 КУпАП', 'Несправне авто'),
    ('ст.173-2 КУпАП', 'Домашнє насильство'), ('ст.186 КК', 'Грабіж'), ('ст.125 КК', 'Легкі тілесні ушкодження'),
    ('ст.296 КК', 'Хуліганство'), ('ст.190 КК', 'Шахрайство'), ('ст.289 КК', 'Незаконне заволодіння авто'),
]


def nazva(st):
    for k, v in NAZVY:
        if st.startswith(k + ' '):
            return v
    t = st.split('·', 1)[-1].strip()
    return t[:1].upper() + t[1:]


def stattia_korotko(st):
    return st.split('·')[0].strip().replace('ст.', 'ст. ')


# ------------------------------------------------------------------ шкала й табло
def shkala(k, slovo=None):
    """5 кроків: «значно менше · менше · як зазвичай · більше · значно більше»; None — «рано казати»."""
    if k is None:
        return ('<span class="shk shk--rano" role="img" aria-label="рано казати"><i></i><i></i><i></i><i></i><i></i></span>'
                f'<span class="tk__k tk__k--rano">{E(slovo or "рано казати")}</span>')
    seg = ''.join(f'<i{" class=\"tut\"" if j == k else ""}></i>' for j in range(5))
    return (f'<span class="shk" data-k="{k}" role="img" aria-label="{E(KROKY[k])}">{seg}</span>'
            f'<span class="tk__k" data-k="{k}">{E(slovo or KROKY[k])}</span>')


def komirka(pidpys, chyslo, kk, typovo, slovo=None, dod='', kl=''):
    k = kk.get('k') if kk else None
    return (f'<div class="tk{(" " + kl) if kl else ""}"><span class="tk__l">{pidpys}</span>'
            f'<b class="tk__n">{chyslo}</b>{shkala(k, slovo)}'
            f'<span class="tk__t">{typovo}</span>{dod}</div>')


def porozhnia(tekst):
    return f'<div class="tk tk--nemaie"><span class="tk__l">&nbsp;</span><span class="tk__nemaie">{tekst}</span></div>'


def typovo(kk, f=lambda x: ch(x)):
    if not kk or kk.get('med') is None:
        return 'бази немає'
    return f'у типового: {f(kk["med"])}'


def tablo_ryadky(D):
    """-> список (ключ, назва рядка, підпис, [3 клітинки HTML]) — той самий порядок і набір у кожному звіті."""
    b, v, o, r, z = D['budynok'], D['vulytsia'], D['dovkola'], D['doroga'], D['zminy']
    rn_r = RAION_R.get(D['raion'], D['raion'])
    out = []
    # 1. Будинок
    pov = f'{D["rivni"]} {mn(D["rivni"], "поверх", "поверхи", "поверхів")}' if D.get('rivni') else 'поверховість невідома'
    t = b['tema']
    tema = ''
    if t:
        tema = (f'<span class="tk__tema">вирізняється: {E(t["h"])} — {skarh_s(t["n"])}, '
                f'{"кожного місяця" if t["mis"] >= 12 else f"у {t["mis"]} з 12 міс."}</span>')
    out.append(('budynok', 'Будинок', f'багатоквартирний, {pov}', [
        komirka('події · суд, 2024–2026', ch(b['podii']), b['podii_krok'], typovo(b['podii_krok'])),
        komirka('скарги сусідів · 1551, рік', ch(b['skargy']), b['skargy_krok'], typovo(b['skargy_krok']) +
                ('' if b['skargy_baza'] == 'та сама поверховість' else ' · з усіма будинками району'), dod=tema),
        porozhnia('')]))
    # 2. Вулиця
    if v:
        dov = f'{dr(v["dovzhyna"] / 1000)} км' if v['dovzhyna'] >= 1000 else f'{ch(v["dovzhyna"])} м'
        out.append(('vulytsia', 'Вулиця', f'{E(korotko(v["nazva"]))}, довжина {dov}', [
            komirka('події на 100 м', dr(v['na100']), v['podii_krok'], typovo(v['podii_krok'], dr), dod=f'<span class="tk__dod">усього {podii_s(v["podii"])}</span>'),
            komirka('скарги на 100 м', dr(v['sk100']), v['skargy_krok'], typovo(v['skargy_krok'], dr), dod=f'<span class="tk__dod">усього {skarh_s(v["skargy"])}</span>'),
            porozhnia('')]))
    else:
        out.append(('vulytsia', 'Вулиця', 'вулицю в OSM не знайдено', [porozhnia('немає даних')] * 3))
    # 3. Довкола
    out.append(('dovkola', 'Довкола, 10 хв пішки', f'≈ 800 м по вулицях · {dr(o["ploshcha_ga"], 0)} га', [
        komirka('події, крім аварій', ch(o['podii']), o['podii_krok'], typovo(o['podii_krok'])),
        komirka('скарги про вулицю й двір', ch(o['skargy']), o['skargy_krok'], typovo(o['skargy_krok'])),
        komirka('зелень, % площі', f'{dr(o["zelen"], 0)} %', o['zelen_krok'], typovo(o['zelen_krok'], lambda x: f'{dr(x, 0)} %'), kl='tk--zel')]))
    # 4. Дорога
    out.append(('doroga', 'Дорога', 'для тих, хто з авто', [
        komirka('аварії за 10 хв пішки', ch(r['dtp']), r['krok'], typovo(r['krok'])),
        porozhnia(''), porozhnia('')]))
    # 5. Як змінюється
    if z['tut_pct'] is not None:
        zn = f'{"+" if z["tut_pct"] > 0 else "−" if z["tut_pct"] < 0 else ""}{abs(z["tut_pct"])} %'
        out.append(('zminy', 'Як змінюється', 'останні 12 міс. проти попередніх', [
            komirka('події довкола', zn, z['krok'], f'у районі: {"+" if z["raion_pct"] > 0 else "−"}{abs(z["raion_pct"])} %', slovo=z['slovo'],
                    dod=f'<span class="tk__dod">{ch(z["ostanni"])} проти {ch(z["poperedni"])}</span>'),
            porozhnia(''), porozhnia('')]))
    else:
        out.append(('zminy', 'Як змінюється', 'останні 12 міс. проти попередніх', [
            komirka('події довкола', '—', None, f'подій замало: {z["ostanni"]} і {z["poperedni"]}'), porozhnia(''), porozhnia('')]))
    return out


def korotko(n):
    return (n or '').replace('вулиця ', 'вул. ').replace(' вулиця', '').replace('проспект ', 'просп. ').replace(' проспект', ' просп.') \
        .replace('бульвар ', 'бульв. ').replace('площа ', 'пл. ')


def tablo_html(D, ryadky):
    rn_m = RAION_M.get(D['raion'], D['raion'])
    holova = ('<div class="tablo__holova" aria-hidden="true"><span></span><span>Події · суд</span><span>Скарги сусідів · 1551</span>'
              '<span>Зелень</span></div>')
    rr = []
    for k, n, pid, kom in ryadky:
        rr.append(f'<div class="tablo__r" data-ryadok="{k}"><div class="tablo__nazva"><b>{n}</b><span>{pid}</span></div>{"".join(kom)}</div>')
    return (f'<section class="tablo" aria-label="Табло: та сама будова в кожному звіті"><div class="tablo__shap"><h2>Табло</h2>'
            f'<p>Кожен рядок — проти типового в {E(rn_m)} районі. Загального балу немає.</p></div>{holova}{"".join(rr)}'
            f'<div class="shk-legenda" aria-hidden="true">{"".join(f"<span><i data-k=\"{j}\"></i>{KROKY[j]}</span>" for j in range(5))}</div>'
            f'{prymitky_tablo(D)}</section>')


def prymitky_tablo(D):
    b = D['budynok']
    ps = []
    if b['masovi']:
        m = b['masovi'][0]
        ps.append(f'Скарги — без місяців масових відключень: у {MIS_M[int(m["ym"][5:]) - 1]} {m["ym"][:4]} {skarh_s(m["n"])} '
                  f'на {E(m["h"])} — як і весь район, у табло не входять.')
    ps.append(f'Справ про насильство без адреси в цьому випуску — {D["chutlyvi_bez_adresy"]} на все місто: суд не назвав місця, тож '
              'у табло їх немає (це не «0»).')
    ps.append('Лише те, що дійшло до суду й має адресу. Більше подій у даних — не означає «небезпечніше».')
    return '<ul class="tablo__prym">' + ''.join(f'<li>{p}</li>' for p in ps) + '</ul>'


# ------------------------------------------------------------------ «Місця довкола»
def mistsia_vidbir(D):
    ms = D['mistsia']
    z_podiiamy = [m for m in ms if m['podii'] > 0 and (m['typ'] != 'zupynka' or m['podii'] >= 3)]
    z_podiiamy.sort(key=lambda m: (-m['vaha'], -m['podii'], m['d']))
    # без подій — лише як факт на користь місця: парки й сквери, найближчі, не більше 2
    tykhi = [m for m in ms if m['typ'] == 'park' and m['podii'] <= 1 and m['nazva']]
    tykhi.sort(key=lambda m: m['d'])
    vybrani = z_podiiamy[:8] + tykhi[:2]
    reshta = [m for m in z_podiiamy[8:] if m['podii'] >= 2]
    return vybrani, reshta


def shcho_tam(m):
    if not m['podii']:
        return 'подій у даних немає'
    if m['typ'] == 'park' and m['podii'] <= 1:
        return 'подій мало: 1 за три роки'
    hr = sorted(m['hrupy'].items(), key=lambda kv: -kv[1])
    h, n = hr[0]
    s = podii_s(m['podii'])
    if n == m['podii']:
        s += f' — усі {HR_SLOVA[h]}' if m['podii'] > 1 else f' — {HR_SLOVA[h]}'
    elif n * 2 >= m['podii']:
        s += f', здебільшого {HR_SLOVA[h]} ({n})'
    else:
        s += ', ' + ', '.join(f'{HR_SLOVA[a]} {b}' for a, b in hr[:3])
    return s


STAN = {'триває': 'триває', 'нове': 'нове', 'рано казати': 'рано казати', 'затихло': 'затихло', 'росте': 'росте'}


def mistse_html(m, i):
    malo = m['typ'] == 'park' and m['podii'] <= 1
    stan = f'<span class="stan stan--{E(m["stan"].replace(" ", "-"))}">{E(STAN[m["stan"]])}</span>' if m.get('stan') and not malo else ''
    sk = ''
    if m.get('skargy'):
        h = m['skargy_hr'][0][0] if m['skargy_hr'] else ''
        sk = f'<span class="mistse__sk">{skarh_s(m["skargy"])} сусідів поруч{f", здебільшого {E(h)}" if h else ""}</span>'
    por = ''
    p = m.get('porivn')
    if p:
        k = p['malyi_krok']['k']
        por = (f'<p class="mistse__por">Проти таких самих місць Києва ({ch(p["obiektiv"])}): <b>{E(KROKY[k]) if k is not None else "рано казати"}</b>. '
               f'У {p["r_malyi"]} м — {podii_s(p["malyi"])} без дорожніх, у {E(TYP_TYPOVYI[m["typ"]])} — {ch(p["malyi_typovo"])}; '
               f'у {p["r_velykyi"]} м — {ch(p["velykyi"])} проти {ch(p["velykyi_typovo"])}.</p>')
    roky = ''
    if m['podii'] and not malo:
        roky = ' · '.join(f'{r}: {m["roky"].get(r, 0)}' for r in ('2024', '2025', '2026'))
        roky = f'<span class="mistse__roky">{roky}</span>'
    spil = f'<span class="mistse__spil">ще {m["spilni"]} — ближче до сусіднього місця</span>' if m.get('spilni') else ''
    vyd = 'skup' if m['typ'] == 'skup' else m['typ']
    khvylyny = f' · {khv(m["d"])} хв' if m['d'] >= 60 else ''
    return (f'<li class="mistse" data-mistse="{i}" data-typ="{vyd}"><span class="mistse__ik" aria-hidden="true">{i}</span>'
            f'<div class="mistse__t"><p class="mistse__h"><b>{nazva_mistsia(m)}</b><span class="mistse__d">{metry(m["d"])}{khvylyny}</span></p>'
            f'<p class="mistse__shcho">{shcho_tam(m)}{stan}</p>{sk}{roky}{spil}{por}</div></li>')


def mistsia_html(D, vybrani, reshta):
    lis = ''.join(mistse_html(m, i + 1) for i, m in enumerate(vybrani))
    dod = ''
    if reshta:
        dod = (f'<details class="mistsia__shche"><summary>Ще {len(reshta)} {mn(len(reshta), "місце", "місця", "місць")} з подіями</summary>'
               f'<ol class="mistsia__spysok" start="{len(vybrani) + 1}">{"".join(mistse_html(m, len(vybrani) + 1 + j) for j, m in enumerate(reshta))}</ol></details>')
    return (f'<section class="blok mistsia" id="mistsia" data-rezhym="dovkola"><p class="blok__nomer"><b>↘</b>Місця довкола</p>'
            f'<h2>{E(vysnovok_mistsia(vybrani))}</h2>'
            f'<p class="blok__pid">Одним списком — скупчення подій і місця, якими живе район, у межах 10 хв пішки. Зверху — де подій найбільше й вони '
            f'найсерйозніші (насильство > майнові > порядок > дорога). Подію зараховано лише одному, найближчому місцю.</p>'
            f'<ol class="mistsia__spysok">{lis}</ol>{dod}'
            f'<p class="osm-prymitka">«Біля» — у 50 м (школа — 150 м, садок — 100 м), без дорожніх подій; скупчення — адреса з 5+ подіями за '
            f'2024–2026, усі види. Стан: «триває» — остання подія за останні 12 місяців; «нове» — подій до 2025 не було; '
            f'«рано казати» — остання подія давніша, а двох повних років без подій ще не минуло. Об\'єкти — © OpenStreetMap.</p></section>')


def vysnovok_mistsia(vybrani):
    z = [m for m in vybrani if m['podii']]
    if not z:
        return 'Довкола немає місць, де події скупчуються'
    m = z[0]
    nm = re.sub(r'<[^>]+>', '', nazva_mistsia(m))
    nm = html.unescape(nm)
    return f'Найбільше — {nm}, {metry(m["d"])}: {podii_s(m["podii"])}'


# ------------------------------------------------------------------ 3 висновки
def vysnovky(D, vybrani):
    b, v, o, r, z = D['budynok'], D['vulytsia'], D['dovkola'], D['doroga'], D['zminy']
    kand = []   # (вага, ключ рядка, текст)

    def syla(kk):
        return 0 if not kk or kk.get('k') is None else abs(kk['k'] - 2)

    pk = b['podii_krok']
    if syla(pk):
        bil = pk['k'] > 2
        kand.append((3 * syla(pk) + 0.5, 'budynok',
                     f'У самому будинку — {podii_s(b["podii"])} за 2024–2026: {"більше" if bil else "менше"}, ніж у '
                     f'{z_10(pk["pr"]) if bil else 10 - z_10(pk["pr"])} з 10 багатоквартирних будинків району (у типового — {ch(pk["med"])}).'))
    elif b['podii'] == 0:
        kand.append((0.8, 'budynok', 'У самому будинку подій у даних немає — як у більшості будинків району.'))
    t = b['tema']
    if t:
        mis = 'щомісяця' if t['mis'] >= 12 else f'у {t["mis"]} з 12 місяців'
        kand.append((2.5 * syla(t['krok']) + 0.4, 'skargy',
                     f'Серед скарг сусідів найбільше вирізняються скарги на {znakh(t["h"])}: {skarh_s(t["n"])} за рік, {mis} — більше, ніж у '
                     f'{z_10(t["krok"]["pr"])} з 10 будинків району такої самої поверховості.'))
    if vybrani and vybrani[0]['podii'] >= 10:
        m = vybrani[0]
        nm = html.unescape(re.sub(r'<[^>]+>', '', nazva_mistsia(m)))
        h = max(m['hrupy'].items(), key=lambda kv: kv[1])
        # вага — за серйозністю (сума ваг видів), не лише числом: скупчення ДТП за 400 м не випереджає події в будинку
        kand.append((2.5 + min(m['vaha'], 120) / 60 + (1 if m['d'] < 300 else 0), 'mistse',
                     f'{"Найбільше подій довкола" if m["podii"] >= max(x["podii"] for x in vybrani) else "Найпомітніше місце довкола"} — '
                     f'{nm}, {metry(m["d"])} від будинку: {podii_s(m["podii"])} за три роки, '
                     f'{"усі" if h[1] == m["podii"] else "здебільшого"} {HR_SLOVA[h[0]]}.'))
    pk = o['podii_krok']
    if syla(pk):
        bil = pk['k'] > 2
        kand.append((2.2 * syla(pk), 'dovkola',
                     f'За 10 хв пішки — {podii_s(o["podii"])} (крім аварій): {"більше" if bil else "менше"}, ніж довкола '
                     f'{z_10(pk["pr"]) if bil else 10 - z_10(pk["pr"])} з 10 будинків району (типово — {ch(pk["med"])}).'))
    zk = o['zelen_krok']
    if syla(zk):
        bil = zk['k'] > 2
        kand.append((1.6 * syla(zk), 'zelen',
                     f'Зелені довкола {"більше" if bil else "менше"}, ніж зазвичай у районі: {dr(o["zelen"], 0)} % площі проти {dr(zk["med"], 0)} %.'))
    rk = r['krok']
    if syla(rk):
        bil = rk['k'] > 2
        kand.append((1.4 * syla(rk), 'doroga',
                     f'Аварій довкола — {ch(r["dtp"])}: {"більше" if bil else "менше"}, ніж за 10 хв пішки від '
                     f'{z_10(rk["pr"]) if bil else 10 - z_10(rk["pr"])} з 10 будинків району.'))
    if v and syla(v['podii_krok']):
        bil = v['podii_krok']['k'] > 2
        kand.append((1.5 * syla(v['podii_krok']), 'vulytsia',
                     f'На вулиці — {dr(v["na100"])} події на кожні 100 м: {"більше" if bil else "менше"}, ніж на '
                     f'{z_10(v["podii_krok"]["pr"]) if bil else 10 - z_10(v["podii_krok"]["pr"])} з 10 вулиць району.'))
    if z.get('krok', {}).get('k') not in (None, 2):
        kand.append((2.0, 'zminy', f'Подій довкола {z["slovo"]}: {ch(z["ostanni"])} за останні 12 місяців проти {ch(z["poperedni"])} '
                                   f'до того, тоді як у районі — {"+" if z["raion_pct"] > 0 else "−"}{abs(z["raion_pct"])} %.'))
    kand.sort(key=lambda x: -x[0])
    vybir, buly = [], set()
    for w, k, t in kand:
        if k in buly:
            continue
        # «довкола» й «місце» кажуть про те саме, якщо місце близько — лишаємо сильніше
        vybir.append(t); buly.add(k)
        if len(vybir) == 3:
            break
    if len(vybir) < 3:
        vybir.append('Решта рядків табло — як зазвичай для району: нічим не вирізняється.')
    return vybir


# ------------------------------------------------------------------ нижні розділи (як у 64)
def rish(e):
    return ' '.join(f'<a href="{E(r["url"])}" target="_blank" rel="noopener">рішення № <span class="nr">{E(r["doc"])}</span> ↗</a>'
                    for r in e['rishennia'])


STR = ('<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M3 5l4 4 4-4" fill="none" stroke="currentColor" '
       'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def kartka(e, PEREKAZY, de_tekst=None):
    p = PEREKAZY.get(e['id'])
    koly = data_povna(e['data']) + (f', ≈ {e["chas"]}' if e.get('chas') else '')
    st = ', '.join(stattia_korotko(r['st']) for r in e['rishennia'])
    meta = (de_tekst or metry(e['d'])) + ' · ' + misiats(e['data'])
    nz = p['nazva'] if p else nazva(e['st'])
    if p:
        tilo = (f'<dl class="polychka"><dt>Що</dt><dd>{E(p["shcho"])}</dd><dt>Де</dt><dd>{E(p["de"])} · {metry(e["d"]) if e["d"] >= 1 else "у будинку"}</dd>'
                f'<dt>Коли</dt><dd>{E(koly)}</dd><dt>Стаття</dt><dd>{E(st)}</dd></dl><p class="perekaz">{E(p["perekaz"])}</p>'
                f'<p class="podiya__dzh"><span>Переказано з рішення суду, нічого не додано.</span>{rish(e)}</p>')
    else:
        tilo = (f'<dl class="polychka"><dt>Що</dt><dd>{E(nz)}</dd><dt>Де</dt><dd>{adr_html(e["adr"])} · {metry(e["d"]) if e["d"] >= 1 else "у будинку"}</dd>'
                f'<dt>Коли</dt><dd>{E(koly)}</dd><dt>Стаття</dt><dd>{E(st)}</dd></dl>'
                f'<p class="podiya__dzh"><span>Переказу в макеті немає: його пише ШІ з тексту рішення, нічого не додаючи (MV-78).</span>{rish(e)}</p>')
    return (f'<article class="podiya" data-id="{E(e["id"])}"><button class="podiya__shap" type="button" aria-expanded="false">'
            f'<span class="podiya__hrupa">{HR[e["vyd"]]}</span><span class="podiya__nazva">{E(nz)}</span>'
            f'<span class="podiya__meta">{E(meta)}</span><span class="podiya__str">{STR}</span></button>'
            f'<div class="podiya__tilo">{tilo}</div></article>')


def zhortka(items, render, pokazaty=1, slovo='таких самих'):
    if len(items) <= pokazaty:
        return ''.join(render(x) for x in items)
    n = len(items) - pokazaty
    slovo = {'таких самих': mn(n, 'такий самий', 'такі самі', 'таких самих'),
             'подій поруч': mn(n, 'подія поруч', 'події поруч', 'подій поруч')}.get(slovo, slovo)
    return (f'<div class="zhortka">{"".join(render(x) for x in items[:pokazaty])}'
            f'<button class="shche" type="button"><span class="koly-zakryto">ще {n} {slovo} ▾</span><span class="koly-vidkryto">згорнути ▴</span></button>'
            f'<div class="shovane">{"".join(render(x) for x in items[pokazaty:])}</div></div>')


def ryadok(e):
    return (f'<div class="ryadok"><span class="t">{E(nazva(e["st"]))}</span><span class="a">{adr_html(e["adr"])}</span>'
            f'<span class="d">{metry(e["d"])} · {misiats(e["data"])}</span>'
            f'<a href="{E(e["rishennia"][0]["url"])}" target="_blank" rel="noopener">рішення ↗</a></div>')


def smuhy_hrup(dani):
    rows = [(h, dani.get(h, 0)) for h in ['ДТП', 'Дороги', 'Наркотики', 'Громадський порядок', 'Майно', 'Алкоголь', 'Насильство']]
    mx = max([n for _, n in rows] + [1])
    out = ['<div class="smuhy">']
    for h, n in rows:
        lab = f'{n}' if n else '0 у даних'
        malo = ' <span class="malo">мало даних</span>' if 0 < n < 5 else ''
        out.append(f'<div class="smuha-r{" slabka" if n < 5 else ""}"><span>{E(h)}</span><i><u data-shyr="{100 * n / mx:.1f}"></u></i><b>{lab}{malo}</b></div>')
    out.append('</div>')
    return ''.join(out)


def smuhy_pary(tut, tut_n, ob, ob_n):
    rows = ['ДТП', 'Дороги', 'Наркотики', 'Громадський порядок', 'Майно', 'Алкоголь']
    mx = max(max(tut.get(h, 0) / max(tut_n, 1), ob.get(h, 0) / max(ob_n, 1)) for h in rows) or 1
    out = ['<div class="smuhy smuhy--pary">']
    for h in rows:
        a = tut.get(h, 0) / max(tut_n, 1); b = ob.get(h, 0) / max(ob_n, 1)
        malo = ' <span class="malo">мало даних</span>' if tut.get(h, 0) < 5 else ''
        out.append(f'<div class="smuha-r"><span>{E(h)}</span><i><u data-shyr="{100 * a / mx:.1f}"></u><s data-shyr="{100 * b / mx:.1f}"></s></i>'
                   f'<b>{round(a * 100)} %{malo}<small>{round(b * 100)} %</small></b></div>')
    out.append('</div>')
    return ''.join(out)


def stovpchyky_roky(roky):
    mx = max(list(roky.values()) + [1])
    out = ['<div class="stovptsi stovptsi--roky">']
    for k in ('2024', '2025', '2026'):
        n = roky.get(k, 0); nep = k == '2026'
        out.append(f'<div class="stovp{" nepovn" if nep else ""}"><b>{n}</b><i><u data-vys="{100 * n / mx:.1f}"></u></i><span>{k}'
                   f'{"<small>до жовтня · суди ще публікують</small>" if nep else ""}</span></div>')
    out.append('</div>')
    return ''.join(out)


def roky_krapky(roky):
    out = []
    for r in ('2024', '2025', '2026'):
        n = roky.get(r, 0)
        out.append(f'<span><i class="{"e" if n else ""}{" nepovn" if r == "2026" and n else ""}"></i>{r[2:]}: {n}</span>')
    return '<div class="roky-krapky">' + ''.join(out) + '</div>'


def opys_skup(v):
    hr = v['hr']
    if len(hr) == 1:
        return f'усі — {hr[0][0]}' if hr[0][0] != 'Дороги' else 'усі — водії'
    h, n = hr[0]
    slovo = {'Дороги': 'водії напідпитку чи без прав', 'ДТП': 'ДТП'}.get(h, h.lower())
    return f'здебільшого {slovo} ({n})'


def blok(id_, nomer, nazva_bloku, h2, pid, tilo, rezhym):
    return (f'<section class="blok" id="{id_}" data-rezhym="{rezhym}"><p class="blok__nomer"><b>{nomer}</b>{nazva_bloku}</p>'
            f'<h2>{h2}</h2><p class="blok__pid">{pid}</p><div class="blok__tilo">{tilo}</div></section>')


def nyzhni_rozdily(D, PEREKAZY):
    dim = sorted(D['dim'], key=lambda e: e['data'], reverse=True)
    p100 = sorted(D['p100'], key=lambda e: e['data'], reverse=True)
    p300 = sorted(D['p300'], key=lambda e: e['data'], reverse=True)
    k300 = dim + p100 + p300
    hr_dim = collections.Counter(HR[e['vyd']] for e in dim)
    hr300 = collections.Counter(dict(D['hr300']))
    hr_p300 = collections.Counter(HR[e['vyd']] for e in p300)
    rn = D['raion']; rn_r = RAION_R.get(rn, rn)
    # 1. Моя адреса
    hrupy_dim = collections.OrderedDict()
    for e in dim:
        kl = e['rishennia'][0]['st'] if len(e['rishennia']) == 1 else e['id']
        hrupy_dim.setdefault(kl, []).append(e)
    shar1 = ''.join(zhortka(L, lambda e: kartka(e, PEREKAZY, 'у будинку')) for L in hrupy_dim.values())
    p300_t = collections.OrderedDict()
    for e in p300:
        p300_t.setdefault(HR[e['vyd']], collections.OrderedDict()).setdefault(nazva(e['st']), []).append(e)
    shar3 = []
    for h in sorted(p300_t, key=lambda h: -sum(len(x) for x in p300_t[h].values())):
        vs = sum(len(x) for x in p300_t[h].values())
        shar3.append(f'<div class="hrupa-ryadkiv"><h4>{E(h)} <span>· {vs}</span></h4>')
        for t, L in sorted(p300_t[h].items(), key=lambda kv: -len(kv[1])):
            shar3.append(zhortka(L, ryadok, pokazaty=1))
        shar3.append('</div>')
    if dim:
        h, n = hr_dim.most_common(1)[0]
        h2 = f'У будинку — {podii_s(len(dim))}{f", і {n} з них — {h if h.isupper() else h.lower()}" if len(dim) > 2 and n > 1 else ""}'
    else:
        h2 = 'У самому будинку подій у даних немає'
    B1 = blok('adresa', '1', 'Моя адреса', E(h2),
              f'Поруч, до 100 м, — {podii_s(len(p100))}; далі, до 300 м, — ще {len(p300)}.',
              f'''<div class="pidblok"><div class="shar__shap"><h3>У самому будинку</h3><span>{podii_s(len(dim))} · найновіші першими</span></div><div class="podii">{shar1 or '<p class="tykho">Подій з адресою цього будинку в даних немає.</p>'}</div></div>
<div class="pidblok"><div class="shar__shap"><h3>Поруч, до 100 м</h3><span>{podii_s(len(p100))} · двір і сусідні будинки</span></div><div class="podii">{zhortka(p100, lambda e: kartka(e, PEREKAZY), pokazaty=6, slovo='подій поруч')}</div></div>
<div class="pidblok"><div class="shar__shap"><h3>Далі, до 300 м</h3><span>{podii_s(len(p300))} · лише підсумок</span></div>
<div class="pidsumok-sharu">{''.join(f'<span>{E(h)} <b>{n}</b></span>' for h, n in hr_p300.most_common())}</div>
<details class="usi-300"><summary>Показати всі {len(p300)} рядком, з посиланням на рішення</summary><div class="ryadky">{''.join(shar3)}</div></details></div>''',
              'budynok')
    # 2. Моя вулиця
    V = D['vul_list']
    SKUP = [v for v in V if v['skup']]
    vul_hr = collections.Counter()
    for v in V:
        for h, n in v['hr']:
            vul_hr[h] += n
    nomerni = [v for v in V if v['n'] != 'перехрестя']
    skup_html = ''.join(
        f'<div class="skup{" ty" if v["ty"] else ""}"><span class="skup__adr">{"ваш будинок · " if v["ty"] else ""}№ {nb(v["n"])}</span>'
        f'<b>{v["k"]}<small>{mn(v["k"], "подія", "події", "подій")}</small></b><p>{E(opys_skup(v))}</p>{roky_krapky(v["roky"])}</div>'
        for v in sorted(SKUP, key=lambda v: (not v['ty'], -v['k']))[:8])
    ty_skup = any(v['ty'] for v in SKUP)
    pr = D['problemy']
    pr_html = ''.join(problema_html(p) for p in pr[:3])
    vn = korotko(D['vulytsia']['nazva']) if D['vulytsia'] else 'вулиця'
    mx = max([v['k'] for v in nomerni] + [1])
    smuha = ''.join(f'<div class="smuha-r{" ty" if v["ty"] else ("" if v["skup"] else " slabka")}"><span>№ {nb(v["n"])}{" · ваш" if v["ty"] else ""}</span>'
                    f'<i><u data-shyr="{100 * v["k"] / mx:.1f}"></u></i><b>{v["k"]}</b></div>'
                    for v in sorted(nomerni, key=lambda v: -v['k'])[:12])
    B2 = blok('vulytsia', '2', 'Моя вулиця',
              E(f'На вашій вулиці — {len(SKUP)} {mn(len(SKUP), "адреса", "адреси", "адрес")}, де подій 5 і більше' + (', і ваш будинок серед них' if ty_skup else '')),
              f'{E(vn)}: усього {podii_s(D["vul_k"])} на {len(nomerni)} адресах, здебільшого {", ".join(f"{h if h.isupper() else h.lower()} ({n})" for h, n in vul_hr.most_common(2))}. '
              'Скупчення — це лише «багато подій на одній адресі», а не проблема.',
              f'''<div class="dvi"><div class="pidblok"><h3>Адреси вулиці, де найбільше подій</h3><p class="tykho">12 адрес з найбільшим числом подій за 2024–2026.</p><div class="smuha-tel smuhy smuha-vsi">{smuha}</div></div>
<div class="pidblok"><h3>Де скупчення і чи вони тривають</h3><p class="tykho">Смужки — роки; бліда — 2026, ще неповний.</p><div class="skupchennia">{skup_html or '<p class="tykho">Скупчень немає.</p>'}</div></div></div>
<div class="pidblok"><h3>Проблеми поруч</h3><p class="tykho">Проблема — однакові події, що повторюються в одному місці щонайменше в 3 кварталах і частіше, ніж зазвичай (MV-36). У межах 1,5 км.</p>
<div class="problemy">{pr_html or '<p class="tykho">У межах 1,5 км проблем немає.</p>'}</div></div>
<p class="bez-nomera"><b>Ще ≈ {D["bez_nom"]} подій — без точного номера</b>: суд назвав лише вулицю. На карті їх немає (MV-68); число — пошуком назви в описах, приблизне.</p>''',
              'vulytsia')
    # 3. Аналітика
    st300 = D['st300']
    statti = ''.join(f'<span>{E(nazva(s))}</span><b>{n}</b>' for s, n in st300[:6])
    K300 = D['k300']
    dorohy = hr300['ДТП'] + hr300['Дороги']
    B3 = blok('analityka', '3', 'Аналітика',
              E(f'Довкола будинку, до 300 м — {podii_s(K300)}; ' + (f'передусім дорога: {dorohy}' if dorohy * 2 >= K300 else
                                                                      f'найбільше — {hr300.most_common(1)[0][0].lower()}: {hr300.most_common(1)[0][1]}')),
              'Беремо всі події до 300 м від будинку за 2024–2026.',
              f'''<div class="dvi"><div class="pidblok"><h3>Що трапляється</h3><p class="tykho">Подій за групами, до 300 м.</p><div class="hrafik">{smuhy_hrup(dict(hr300))}</div></div>
<div class="pidblok"><h3>Найчастіше — за статтями</h3><p class="tykho">Людською мовою; одна подія — одна стаття.</p><div class="statti">{statti}</div>
<p class="vyiavlene">Справи про водіїв напідпитку чи без прав і про наркотики з'являються, коли людину зупиняє поліція. Тож їх число залежить і від того, як часто тут перевіряють.</p></div></div>''',
              'podii')
    # 4. Цікаве
    rid = D['ridki'][0] if D['ridki'] else None
    B4 = ''
    if rid:
        p = PEREKAZY.get(rid['id'])
        B4 = blok('tsikave', '4', 'Цікаве', E(f'Єдина в районі за 2024–2026 справа «{(p or {}).get("nazva") or nazva(rid["st"])}» — {metry(rid["d"])}'),
                  f'Найрідша справа {E(rn_r)} району серед найближчих до вас: таких з адресою в районі більше немає.',
                  f'''<div class="tsikave"><div class="dyvna"><span class="dyvna__mitka">Найдивніша справа району · {metry(rid["d"])} · {misiats(rid["data"])}</span>
<h3>{E((p or {}).get("nazva") or nazva(rid["st"]))}</h3>{f'<p class="perekaz">{E(p["perekaz"])}</p>' if p else '<p class="tykho">Переказу в макеті немає — його пише ШІ (MV-78).</p>'}
<p class="podiya__dzh"><span>{E(stattia_korotko(rid["st"]))} · {adr_html(rid["adr"])}.</span>{rish(rid)}</p></div></div>''', 'podii')
    # 5. Район
    PRYR = K300 / D['ob_med'] if D['ob_med'] else None
    B5 = blok('rajon', '5', 'Район',
              E(f'До 300 м — {podii_s(K300)}; довкола звичайного багатоквартирного будинку {rn_r} району — {ch(D["ob_med"])}'),
              'Це більше чи менше даних, а не оцінка безпеки. Склад подій — проти всього району.',
              f'''<div class="pidblok"><h3>Склад подій: тут і в районі</h3><p class="tykho"><b>Темна смуга</b> — до 300 м від будинку ({K300}); <b>сіра</b> — увесь район ({ch(D["ob_n"])}).</p><div class="hrafik">{smuhy_pary(dict(hr300), K300, dict(D["ob_h"]), D["ob_n"])}</div></div>''',
              'dovkola')
    # 6. Куди йде
    roky = D['roky']
    z = D['zminy']
    B6 = blok('kudy', '6', 'Куди йде',
              E(f'Подій довкола {z["slovo"]}' + (f': {roky.get("2024", 0)} у 2024 і {roky.get("2025", 0)} у 2025 (до 300 м)' if roky else '')),
              f'2026 ще неповний: суди публікують рішення із запізненням. Прогнозу не даємо.',
              f'''<div class="pidblok"><h3>Події до 300 м за роками</h3><p class="tykho">Повні роки — темні; неповний — блідий.</p><div class="hrafik">{stovpchyky_roky(roky)}</div></div>''',
              'podii')
    return [('adresa', 'Моя адреса', B1), ('vulytsia', 'Моя вулиця', B2), ('analityka', 'Аналітика', B3)] + \
           ([('tsikave', 'Цікаве', B4)] if B4 else []) + [('rajon', 'Район', B5), ('kudy', 'Куди йде', B6)]


def problema_html(p):
    z_datoiu = sum(p['roky'].values())
    roky = ', '.join(f'{k} — {v}' for k, v in sorted(p['roky'].items()))
    if z_datoiu < p['podii']:
        roky = f'з датою {z_datoiu}: {roky}'
    nm = (p.get('masshtab') or {}).get('name')
    nazva_p = f'{E(p["mekh"] or HR.get(p["vyd"], ""))}' + (f' · «{E(nm)}»' if nm else '')
    ost = f' Остання — {misiats(p["ostannia"])}.' if p.get('ostannia') else ''
    stan = 'Триває' if p.get('ostannia') and p['ostannia'] >= '2025-11-01' else 'Рано казати'
    return (f'<div class="problema"><span class="problema__znak"><svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M2 7V2h5M15 2h5v5M20 15v5h-5M7 20H2v-5" fill="none" stroke="#3C3CA1" stroke-width="2"/></svg></span>'
            f'<div><b>{nazva_p}</b> · за {metry(p["d"])}<p>{p["podii"]} подій: {roky}.{ost}</p></div>'
            f'<span class="stan">{stan}</span></div>')


# ------------------------------------------------------------------ сторінка
LOGO = ('<svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true"><path d="M14 2l10.4 6v12L14 26 3.6 20V8z" fill="#4447A6"/>'
        '<path d="M14 8l5.2 3v6L14 20l-5.2-3v-6z" fill="#5DD0A9"/></svg>')


def storinka(fail, klas, nazva_v, tilo, ADR, skrypty=''):
    maket = ''.join(f'<a href="{E(a["slug"])}.html"{" class=\"tut\"" if fail == a["slug"] + ".html" else ""}>{E(a["korotko"])}</a>' for a in ADR)
    maket += f'<a href="mii-adresy.html"{" class=\"tut\"" if fail == "mii-adresy.html" else ""}>Мої адреси</a>'
    return f'''<!DOCTYPE html>
<html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self'; img-src 'self' data:; script-src 'self'">
<title>{E(nazva_v)} · Моя вулиця</title><link rel="stylesheet" href="zvit.css"><link rel="stylesheet" href="zvit69.css"></head>
<body class="{klas}">
<header class="sait"><div class="sait__in"><a class="logo" href="index.html">{LOGO}Моя вулиця</a>
<nav class="menu"><a href="#">Карта</a><a href="#">Вулиці</a><a href="#">Грати</a><a href="#">Підписка</a></nav>
<div class="sait__pr"><a class="klavisha" href="mii-adresy.html">Мої адреси <small>3</small></a></div></div></header>
<div class="maket"><div class="maket__in"><b>МАКЕТ 69</b>{maket}<a href="index.html">усі</a></div></div>
{tilo}
{skrypty}<script src="zvit69.js"></script></body></html>'''


KUPLENO = ('<p class="kupleno"><span><span class="krapka"></span><b>Звіт куплено</b> 16.11.2026 · назавжди</span><span>оновлення щокварталу · наступне — лютий 2027</span>'
           '<span class="skh-tel">адреса на стеженні</span><span class="skh-tel">дані: події до 5.11.2026, скарги 1551 до жовтня 2026</span></p>')


def povnota(D):
    return f'''<section class="povnota" id="povnota" data-rezhym="dovkola"><div><h2>Наскільки повні дані</h2><ul>
<li>Події — лише те, що дійшло до суду й опубліковано в Єдиному реєстрі судових рішень. Випуск бази {E(D["versiia"])}: частина Києва; числа зміняться після повного Києва.</li>
<li>Події з 2024 до 5 листопада 2026. 2026 рік неповний: рішення публікують із запізненням.</li>
<li>Справи про насильство без адреси в цьому випуску ({D["chutlyvi_bez_adresy"]} на місто) — не на карті й не в табло. Це межа даних, а не правило (MV-69).</li>
<li>Скарги 1551 — те, що повідомили мешканці, а не перевірені факти; з 08.2025. Активні будинки скаржаться частіше.</li>
<li>«10 хв пішки» — ≈ 800 м по вулицях і доріжках OpenStreetMap від входів будинку; через подвір'я без доріжок у OSM не рахується.</li>
<li>«У типового» — медіана: половина таких самих будинків, вулиць чи ділянок {E(RAION_R.get(D["raion"], D["raion"]))} району має менше, половина — більше.</li></ul></div>
<div class="dzherela"><h2>Джерела</h2><p>Події — ЄДРСР (річні архіви data.gov.ua), випуск бази {E(D["versiia"])}. Скарги — 1551 (відкриті дані Києва), 08.2025–10.2026.</p>
<p>Карта, будинки, зелень, об'єкти — © учасники OpenStreetMap (ODbL), знімок 07.11.2026. Межі районів — OSM.</p>
<p>Помітили помилку чи хочете прибрати подію? Напишіть — розглядаємо за 10 робочих днів.</p></div></section>'''


DALI = ('<section class="dali"><p><b>Звіт ваш назавжди.</b> Оновимо в лютому 2027. Адреса вже на стеженні: про нові події скажемо одразу. '
        'Порівняти з іншою адресою — звіт 599 грн, для підписника — 199.</p><a class="klavisha" href="mii-adresy.html">Мої адреси</a></section>')


def pershyi_ekran(D, A, vys, ryadky):
    pov = f'{D["rivni"]} {mn(D["rivni"], "поверх", "поверхи", "поверхів")}' if D.get('rivni') else 'поверховість невідома'
    m = re.match(r'(.*),\s*([^,]+)$', A['nazva'])
    h1 = f'{E(m.group(1))}, {nb(m.group(2))}' if m else E(A['nazva'])
    return (f'<section class="pershyi" id="shapka" data-rezhym="dovkola"><div class="pershyi__adr"><p class="shapka__mitka">Звіт адреси</p>'
            f'<h1 class="pershyi__h">{h1}</h1><p class="shapka__de">{E(D["raion"])} район · багатоквартирний будинок, {pov} · події 2024 — 5.11.2026</p></div>'
            f'<ol class="vysnovky">{"".join(f"<li><span>{z_nb(v)}</span></li>" for v in vys)}</ol>{tablo_html(D, ryadky)}</section>')


def mapa_js(D, vybrani, slug):
    M = D['mapa']
    mistsia = [dict(i=i + 1, x=m['x'], y=-m['y'], t=m['typ'], n=m['podii']) for i, m in enumerate(vybrani)]
    podii = [dict(x=p['x'], y=p['y'], v=p['vyd']) for p in D['podii_tochky']]
    vul_adr = [dict(n=v['n'], k=v['k'], x=round(v['x'][0]), y=round(-v['x'][1]), s=v['skup'], ty=v['ty']) for v in D['vul_list'] if v['n'] != 'перехрестя']
    dani = dict(bud=M['bud'], zel=M['zel'], dor=[dict(k=r['k'], p=r['p']) for r in M['dor']], kontur=M['kontur'], vul=M['vul'],
                mistsia=mistsia, podii=podii, vul_adr=vul_adr,
                pidpysy=pidpysy(M['dor']))
    return 'window.MAPA=' + json.dumps(dani, ensure_ascii=False, separators=(',', ':')) + ';'


def pidpysy(dor):
    best = {}
    for r in dor:
        n = r.get('n')
        if not n:
            continue
        p = r['p']
        L = sum(math.hypot(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]) for i in range(len(p) - 1))
        if L > best.get(n, (0,))[0]:
            j = max(range(len(p) - 1), key=lambda i: math.hypot(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]))
            (x1, y1), (x2, y2) = p[j], p[j + 1]
            a = math.degrees(math.atan2(y2 - y1, x2 - x1))
            a = a - 180 if a > 90 else a + 180 if a < -90 else a
            if math.hypot(x2 - x1, y2 - y1) > 90:
                best[n] = (L, (x1 + x2) / 2, (y1 + y2) / 2, round(a, 1))
    return [dict(t=korotko(n), x=round(v[1]), y=round(v[2]), a=v[3]) for n, v in best.items() if v[0] > 200]


# ------------------------------------------------------------------ «Мої адреси»
def mii_adresy(DD, ADR3):
    stovptsi = []
    for D, A in DD:
        vys = D['_vys'][0]
        stovptsi.append(f'<div class="mii__adr"><a href="{E(A["slug"])}.html"><b>{adr_html(A["nazva"])}</b></a>'
                        f'<span>{E(D["raion"])} район</span><p>{z_nb(vys)}</p></div>')
    ryadky = collections.OrderedDict()
    for D, A in DD:
        for k, n, pid, kom in D['_ryadky']:
            ryadky.setdefault(k, (n, []))[1].append(kom)
    nazvy_kom = {'budynok': ['події · суд', 'скарги 1551'], 'vulytsia': ['події на 100 м', 'скарги на 100 м'],
                 'dovkola': ['події, крім аварій', 'скарги про вулицю й двір', 'зелень'], 'doroga': ['аварії'], 'zminy': ['події довкола']}
    rr = []
    for k, (n, koms) in ryadky.items():
        for j, nk in enumerate(nazvy_kom[k]):
            komirky = ''.join(f'<div class="mii__k"><span class="mii__kh">{adr_html(A["nazva"])}</span>{kom[j]}</div>'
                              for kom, (D, A) in zip(koms, DD))
            rr.append(f'<div class="mii__r" data-ryadok="{k}"><div class="mii__nazva">{"<b>" + n + "</b>" if j == 0 else ""}<span>{nk}</span></div>{komirky}</div>')
    return (f'<main class="zvit mii"><p class="kupleno"><span><b>Мої адреси</b> · 3 куплені звіти · той самий набір рядків і та сама шкала</span></p>'
            f'<section class="mii__tablo"><div class="mii__r mii__r--holova"><div class="mii__nazva"><b>Табло поруч</b><span>кожна клітинка — проти типового будинку свого району: темніший квадрат — більше в даних, світліший — менше; «у типового» — медіана району</span></div>'
            f'{"".join(stovptsi)}</div>{"".join(rr)}'
            f'<div class="shk-legenda" aria-hidden="true">{"".join(f"<span><i data-k=\"{j}\"></i>{KROKY[j]}</span>" for j in range(5))}</div>'
            f'<p class="osm-prymitka">Шкала — проти свого району: «більше» в центрі й «більше» на Оболоні — різні числа. Порівнюйте кроки, а числа — з підписом «у типового». '
            f'Лише факти поруч: без балів, без «краще — гірше» (MV-70).</p></section></main>')


# ------------------------------------------------------------------ головне
def main():
    vykhid, v64 = sys.argv[1], sys.argv[2]
    ADR = json.load(open(os.path.join(vykhid, 'adresy.json'), encoding='utf-8'))
    for a in ADR:
        a['korotko'] = re.sub(r',\s*\S+$', '', a['nazva']).replace('вул. ', '').replace('просп. ', '')
    # оформлення 64: стилі, шрифти; перекази 64 — для будинку з 64 (там вони є)
    shutil.copy(os.path.join(v64, 'zvit.css'), os.path.join(vykhid, 'zvit.css'))
    if not os.path.isdir(os.path.join(vykhid, 'shryfty')):
        shutil.copytree(os.path.join(v64, 'shryfty'), os.path.join(vykhid, 'shryfty'))
    shutil.copy(os.path.join(TUT, 'zvit69.css'), os.path.join(vykhid, 'zvit69.css'))
    shutil.copy(os.path.join(TUT, 'zvit69.js'), os.path.join(vykhid, 'zvit69.js'))
    src = open(os.path.join(v64, 'zibraty.py'), encoding='utf-8').read()
    i0 = src.index('PEREKAZY = {'); i1 = src.index('\n}\n', i0) + 2
    ns = {}
    exec(src[i0:i1], ns)
    PEREKAZY = ns['PEREKAZY']
    DD = []
    for A in ADR:
        D = json.load(open(os.path.join(vykhid, 'dani', A['slug'] + '.json'), encoding='utf-8'))
        vybrani, reshta = mistsia_vidbir(D)
        ryadky = tablo_ryadky(D)
        vys = vysnovky(D, vybrani)
        D['_vys'], D['_ryadky'] = vys, ryadky
        bloky = nyzhni_rozdily(D, PEREKAZY)
        rozdily = ''.join(f'<details class="rozdil" data-rozdil="{k}" open><summary class="rozdil__shap"><i>{i + 1} · {n}</i>'
                          f'<b>{re.search(r"<h2>(.*?)</h2>", b).group(1)}</b>{STR}</summary>{b}</details>' for i, (k, n, b) in enumerate(bloky))
        tilo = (f'<main class="zvit">{KUPLENO}<div class="suputnyk"><div class="suputnyk__vmist">{pershyi_ekran(D, A, vys, ryadky)}'
                f'{mistsia_html(D, vybrani, reshta)}{rozdily}{povnota(D)}{DALI}</div>'
                f'<aside class="suputnyk__karta" aria-label="Карта: 10 хв пішки від будинку"><svg class="mapa" data-rezhym="dovkola"></svg>'
                f'<div class="suputnyk__pidpys"><b>10 хв пішки від будинку</b><span>Контур — ≈ 800 м по вулицях; номери — «Місця довкола».</span></div>'
                f'<span class="karta-osm">© OpenStreetMap</span></aside></div></main>')
        t = storinka(A['slug'] + '.html', 'v-v v-b v69', f'Звіт адреси — {A["nazva"]}', tilo, ADR,
                     f'<script src="mapa-{E(A["slug"])}.js"></script>')
        perevirka(t, A['slug'])
        open(os.path.join(vykhid, A['slug'] + '.html'), 'w', encoding='utf-8').write(t)
        open(os.path.join(vykhid, f'mapa-{A["slug"]}.js'), 'w', encoding='utf-8').write(mapa_js(D, vybrani, A['slug']))
        DD.append((D, A))
        print(A['slug'], '·', ' | '.join(vys))
    tri = [x for x in DD if x[1].get('mii', True)][:3]
    t = storinka('mii-adresy.html', 'v69 v-mii', 'Мої адреси', mii_adresy(tri, None), ADR)
    perevirka(t, 'mii')
    open(os.path.join(vykhid, 'mii-adresy.html'), 'w', encoding='utf-8').write(t)
    idx = ''.join(f'<li><a href="{E(A["slug"])}.html">{adr_html(A["nazva"])}</a> — {z_nb(D["_vys"][0])}</li>' for D, A in DD)
    t = storinka('index.html', 'v69', 'Звіт адреси 69', f'''<main class="zvit"><section class="blok"><p class="blok__nomer"><b>69</b>Звіт адреси — перший екран</p>
<h2>Табло для порівняння і «Місця довкола»</h2><p class="blok__pid">Справжні адреси, дані випуску 08.11.2026 і скарги 1551 до жовтня 2026. Додайте <code>?znimok=1</code>, щоб сховати номери будинків і рішень.</p>
<div class="blok__tilo"><ul class="index69">{idx}<li><a href="mii-adresy.html">Мої адреси — три звіти поруч</a></li></ul></div></section></main>''', ADR)
    perevirka(t, 'index')
    open(os.path.join(vykhid, 'index.html'), 'w', encoding='utf-8').write(t)
    print('готово')


ZABORONENI = re.compile(r'небезпечн(?!іше»)|прогноз(?! не| моделі)|бал безпеки|безпечн\w* маршрут|ispyt|іспит', re.I)


def perevirka(t, nazva_):
    assert ' style="' not in t, nazva_
    for c in re.findall(r'(?<![\d,])(\d+)\s*грн', t):
        assert c.strip() in ('599', '199', '399'), (nazva_, c)
    tekst = re.sub(r'<[^>]+>', ' ', t)
    for m in ZABORONENI.finditer(tekst):
        okil = tekst[max(0, m.start() - 60): m.end() + 30]
        if 'не означає «небезпечніше»' in okil or 'Прогнозу не даємо' in okil:
            continue
        raise AssertionError(f'{nazva_}: заборонене слово «{m.group(0)}» — {okil!r}')


if __name__ == '__main__':
    main()

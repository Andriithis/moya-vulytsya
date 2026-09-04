# -*- coding: utf-8 -*-
"""Крок 3. Карта з агрегацією по адресах + рейтинг адрес.

Класифікація спрощена до інцидент/проблема (передача, п.7.1): «проблема» —
це членство в кураторському списку ~50 адрес-напрямків (п.7.3), відібраних за
однорідністю СТАТТІ, а не теми (п.7.2). Аномалія як окрема категорія прибрана:
якщо відібраний напрямок не пояснюється моделлю ризику, картка просто каже
«причина встановлюється на місці» (п.7.1, 7.4).
"""
import os, re, sys, csv, gzip, json, glob, math, sqlite3, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import labels as L
import mech as M
import pravo as PR          # офіційні назви статей для картки і листа
# HTML-шаблон винесено в окремий файл: разом із ним модуль важив 67 КБ,
# а це один файл на дві дуже різні речі — логіку відбору й розмітку.
from step3_tpl import TPL
from map_excl import load_excl, detect_institutional
import map_layers
import map_problems
from map_problems import COURTS, SLUG

LAST_META = {}          # meta останньої збірки — читає крок 5
LAST_DOCS = []          # справи адрес для панелі, паралельно до точок карти

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data'); DB = os.path.join(DATA, 'events.db')
OUT  = os.path.join(ROOT, 'site', 'kyiv.html')
NETW  = os.path.join(DATA, 'network.json')
RISKF = os.path.join(DATA, 'risk.json')
BORD  = os.path.join(DATA, 'borders.json')
FABSNAP = os.path.join(DATA, 'fabuly.csv.gz')   # витяги обставин для збірки в CI
FACTF = os.path.join(DATA, 'factors.json')             # шар чинників середовища (крок 2e)
EXCL = os.path.join(DATA, 'vykluchennya.txt')          # формується автоматично
MANUAL = os.path.join(DATA, 'vykluchennya_moyi.txt')    # ваш список, ніколи не перезаписується
REVIEW = os.path.join(DATA, 'top100_dlya_pereviryky.txt')

# Усі 228 632 посилання починаються однаково: .../files/XX/<32 шістнадцяткові>.rtf
# Зберігаємо лише XX і хеш — решту складає сторінка. Це 34 знаки замість 70.
_REF = re.compile(r'/files/(\w{2})/([0-9a-f]{32})\.rtf$')


def docref(url):
    m = _REF.search(url or '')
    return (m.group(1) + m.group(2)) if m else ''


def main(district=None, out=None):
    """Збирає карту. Версія одна: поділу на викладацьку й слухацьку немає —
    проблеми бачать усі, слухач копає причину далі за SARA."""
    if not os.path.exists(DB): print('спочатку кроки 1 і 2'); sys.exit(1)
    c = sqlite3.connect(DB)
    if not c.execute("SELECT name FROM sqlite_master WHERE name='geo'").fetchone():
        print('немає таблиці geo — крок 2 не відпрацював'); sys.exit(1)

    extra = {}
    for fp in glob.glob(os.path.join(DATA, 'kyiv_*.csv')):
        with open(fp, encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                extra[r['doc_id']] = (r['cause_num'], docref(r['doc_url']))

    rows = list(c.execute("""SELECT e.doc_id,e.court,e.cat,e.date,e.tm,e.street,e.house,
        g.lat,g.lon,g.precision FROM events e JOIN geo g ON g.doc_id=e.doc_id"""))
    print(f'подій з координатами: {len(rows):,}')
    if not rows: return

    # витяги обставин (крок 1b). Може не бути зовсім або бути частково —
    # завантаження довге, а карта має збиратися з тим, що вже є.
    # Витяги обставин (крок 1b). Спершу таблиця в базі — вона є на комп'ютері,
    # де крок 1b і працював. Якщо таблиці немає, читаємо знімок із репозиторію:
    # саме так це відбувається в GitHub Actions, де база збирається наново з
    # events.csv.gz і жодного витягу в ній немає. Без цього на живому сайті
    # панель була б без обставин, хоча вони давно зібрані й лежать поруч.
    fab = {}
    if c.execute("SELECT name FROM sqlite_master WHERE name='fab'").fetchone():
        fab = {r[0]: r[1] for r in c.execute("SELECT doc_id, txt FROM fab WHERE txt<>''")}
        if fab: print(f'витяги обставин: {len(fab):,} (з бази)')
    if not fab and os.path.exists(FABSNAP):
        with gzip.open(FABSNAP, 'rt', encoding='utf-8', newline='') as fh:
            rd = csv.reader(fh, delimiter='\t')
            next(rd, None)
            fab = {r[0]: r[1] for r in rd if len(r) >= 2 and r[1]}
        if fab: print(f'витяги обставин: {len(fab):,} (зі знімка)')
    if not fab:
        print('витягів обставин немає — панель покаже перелік рішень без опису')

    print('перевірка на адреси установ:')
    excl = detect_institutional(rows, load_excl())
    before = len(rows)
    rows = [r for r in rows
            if ((r[5] + ', ' + r[6]) if (r[5] and r[6]) else (r[5] or '')).lower() not in excl]
    print(f'   вилучено подій: {before - len(rows):,}  ->  залишилось {len(rows):,}')

    # ---- ОДНА СПРАВА = ОДНА ПОДІЯ (борг 5.7) ----
    # У двигуні це виправлено 31 серпня, а карта досі рахувала папери. Одна
    # аварія дає ланцюжок документів — обвинувальний акт, призначення розгляду,
    # експертиза, вирок, — і кожен важив як окрема подія. Виміряно 3 вересня:
    # у майнових це 17% зайвого, у насильстві 14%, разом по місту 4%.
    #
    # Папери справи не викидаємо, а лишаємо при представнику: панель показує
    # усі рішення справи, і саме заради цього тут не просто відсів.
    cause = {d: v[0] for d, v in extra.items() if v[0]}
    groups = collections.defaultdict(list)
    for r in rows:
        cn = cause.get(r[0])
        groups[(cn, r[2]) if cn else ('#' + r[0], r[2])].append(r)
    reps, case_docs = [], {}
    for _k, g in groups.items():
        if len(g) > 1:
            # серед документів однієї справи беремо найчастішу адресу,
            # за рівності — найранішу подію (те саме правило, що у двигуні)
            addr_n = collections.Counter((x[5] or '') + ', ' + (x[6] or '') for x in g)
            top = addr_n.most_common(1)[0][0]
            same = [x for x in g if (x[5] or '') + ', ' + (x[6] or '') == top]
            rep = sorted(same, key=lambda x: x[3] or '')[0]
        else:
            rep = g[0]
        reps.append(rep)
        case_docs[rep[0]] = [x[0] for x in sorted(g, key=lambda x: x[3] or '')]
    if len(reps) < len(rows):
        print(f'   одна справа = одна подія: {len(rows):,} -> {len(reps):,}')
    rows = reps

    # ---- злиття кодів у назви ----
    cnt = collections.Counter()
    for r in rows:
        lb = L.CODE.get(r[2])
        if lb: cnt[lb] += 1
        else: cnt[('СЕР', 'інші (код ' + r[2] + ')')] += 1

    labels = sorted(cnt, key=lambda k: (L.ORDER.index(k[0]) if k[0] in L.ORDER else 9, -cnt[k]))
    li = {k: i for i, k in enumerate(labels)}
    ck = sorted({r[1] for r in rows}); ci = {v: i for i, v in enumerate(ck)}

    yc = collections.Counter(r[3][:4] for r in rows)
    yrs = sorted(y for y, n in yc.items() if n >= 200 and y.isdigit())
    ykeys = yrs + (['раніше'] if sum(n for y, n in yc.items() if y not in yrs) else [])
    yi = {y: i for i, y in enumerate(ykeys)}
    print('роки:', ', '.join(ykeys))
    print(f'статей після злиття: {len(labels)} (було би {len({r[2] for r in rows})} за кодами)')

    # група подібності (п.7.2) для кожного індексу в `labels`
    LBL2SIM = {}
    for _code, (_th, _lbl) in L.CODE.items():
        LBL2SIM[(_th, _lbl)] = M.simgroup(_code) or f'{_th}_{_code}'
    sim_of = [LBL2SIM.get(k, f'{k[0]}_i{i}') for i, k in enumerate(labels)]

    agg = collections.defaultdict(list)
    for doc, court, cat, date, tm, street, house, la, lo, prec in rows:
        lb = L.CODE.get(cat) or ('СЕР', 'інші (код ' + cat + ')')
        agg[(round(la, 5), round(lo, 5))].append(
            (ci[court], li[lb], yi.get(date[:4], yi.get('раніше', 0)),
             int(tm[:2]) if tm and tm[:2].isdigit() else -1,
             1 if prec == 'house' else 0, date, street or '', house or '',
             *extra.get(doc, ('', '')),
             [extra.get(x, ('', ''))[1] for x in case_docs.get(doc, [doc])
              if extra.get(x, ('', ''))[1]],
             next((fab[x] for x in case_docs.get(doc, [doc]) if fab.get(x)), '')))

    # ---- ЧЕСНА НАЗВА ТОЧКИ (виправлено 01.09.2026) ----
    # Крок 2 має два режими прив'язки. Коли будинок є в OpenStreetMap, подія
    # стає на свою адресу. Коли будинку немає — подія стає в ЦЕНТР ВУЛИЦІ,
    # і туди ж стають усі інші події цієї вулиці без знайденого будинку.
    # Раніше така купа підписувалася номером першої-ліпшої події: «вул.
    # Міхновського, 42 — 96 подій», хоча на самому будинку 42 сталася одна.
    # Це не установа й не помилка адреси — це загальний осередок вулиці,
    # і називати його треба саме так.
    P = []
    DOCS = []          # паралельно до P: справи адреси для правої панелі
    n_street = 0
    for (la, lo), evs in agg.items():
        hs = [e for e in evs if e[4] and e[6]]
        if hs:
            e = hs[0]
            a = f"{e[6]}, {e[7]}" if e[7] else e[6]
            prec = 1
        else:
            e = next((e for e in evs if e[6]), None)
            a = (e[6] + ' · вся вулиця') if e else ''
            prec = 0
            n_street += 1
        # p[5] — УСІ справи адреси, найновіші згори: стаття, дата, година,
        # номер справи. Раніше тут було шість прикладів — панелі зі списком
        # рішень цього мало.
        #
        # Посилань на самі документи тут НЕМАЄ навмисно: у шістнадцятковому
        # вигляді вони важать 2,4 МБ на файл. Вони їдуть окремим файлом на
        # район разом із витягами обставин — панель підтягує його, коли її
        # відкривають. Порядок справ у тому файлі той самий, що тут.
        ev_sorted = sorted(evs, key=lambda x: x[5], reverse=True)
        P.append([la, lo, a, prec,
                  [[e_[0], e_[1], e_[2], e_[3]] for e_ in evs],
                  len(ev_sorted)])
        # DOCS — те, що показує панель: справа, дата, година, номер справи,
        # папери справи. Порядок збігається з порядком у p[4] за датою.
        DOCS.append([[e_[1], e_[5], e_[3], e_[8], e_[10], e_[11]] for e_ in ev_sorted])
    print(f'унікальних адрес: {len(P):,} '
          f'(з них {n_street:,} — центри вулиць, точного будинку немає)')

    groups_idx = {}
    for ti, t in enumerate(L.ORDER):
        for i, k in enumerate(labels):
            if k[0] == t: groups_idx[i] = ti
    groups = []
    gi_of_theme = {}       # код теми -> її індекс у meta['groups'] (для фільтрації карток)
    for t in L.ORDER:
        ids = [li[k] for k in labels if k[0] == t]
        if ids:
            gi_of_theme[t] = len(groups)
            groups.append([L.THEMES[t], ids, sum(cnt[labels[i]] for i in ids)])
    # law: короткий підпис -> повна назва статті з кодексу. Коротким підписом
    # карта користується в списках, повним — картка проблеми й паспорт SARA,
    # бо лист балансоутримувачу має називати статтю так, як її названо в законі.
    law = {k[1]: PR.nazva(k[1]) for k in labels if PR.nazva(k[1])}
    _no = [k[1] for k in labels if not PR.nazva(k[1])]
    if _no: print(f'   без офіційної назви статті: {len(_no)} — {"; ".join(_no[:3])}')
    meta = dict(courts=[COURTS.get(x, x) for x in ck], cats=[k[1] for k in labels],
                counts=[cnt[k] for k in labels], groups=groups, years=ykeys, law=law)


    # ---- шари контексту: потоки, ризик, чинники (map_layers) ----
    risks, ER, theme_rgrid, pred_theme, FACT = map_layers.build(district, labels)

    # ---- відбір проблем і обрізання до району (map_problems) ----
    P, POP, meta, theme_cnt = map_problems.select(
        P, meta, labels, ck, ykeys, sim_of, gi_of_theme,
        district, risks, ER, FACT, theme_rgrid, pred_theme)

    html = TPL.replace('__POP__', json.dumps(POP, separators=(',', ':'))) \
              .replace('__FACTS__', json.dumps(FACT, ensure_ascii=False, separators=(',', ':'))) \
              .replace('__RISKS__', json.dumps(risks, ensure_ascii=False, separators=(',', ':'))) \
              .replace('__META__', json.dumps(meta, ensure_ascii=False)) \
              .replace('__PTS__', json.dumps(P, ensure_ascii=False, separators=(',', ':')))
    # Крок 5 бере звідси числа районів для плиток — щоб не збирати десять карт
    # заради десяти чисел.
    global LAST_META, LAST_DOCS
    LAST_META = meta
    LAST_DOCS = DOCS

    dst = out or OUT
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)

    # ---- СПРАВИ АДРЕС: окремими файлами по районах ----
    # Разом із витягами обставин це десятки мегабайтів — у сторінку такому не
    # місце. Панель тягне файл свого району тоді, коли її відкривають, і одне
    # посилання лишається одним.
    fdir = os.path.join(os.path.dirname(dst) or '.', 'spravy')
    os.makedirs(fdir, exist_ok=True)
    slugs = meta.get('dslug', [])
    by_d = collections.defaultdict(dict)
    for i, p in enumerate(P):
        di = p[8] if len(p) > 8 else -1
        if i < len(DOCS): by_d[di][i] = DOCS[i]
    tot = 0
    for di, v in by_d.items():
        name = slugs[di] if 0 <= di < len(slugs) else 'inshe'
        fp = os.path.join(fdir, name + '.json')
        json.dump(v, open(fp, 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))
        tot += os.path.getsize(fp)
    print(f'   справи адрес: {len(by_d)} файлів у spravy/ ({tot/1048576:.1f} МБ)')

    open(dst, 'w', encoding='utf-8').write(html)
    print(f'готово: {os.path.basename(dst)} ({os.path.getsize(dst)/1048576:.1f} МБ)')
    return theme_cnt

if __name__ == '__main__':
    main()

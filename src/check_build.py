# -*- coding: utf-8 -*-
"""Самоперевірка збірки карти. Запускати після кожної правки.

Що робить:
  1. зносить __pycache__ і компілює всі файли в src/ — ловить друкарські
     помилки, зіпсовані символи й збірку зі старого кешу;
  2. розпаковує зменшену базу data/events_test.db.gz (22 тисячі подій,
     усі десять районів) — справжня база для цього не потрібна;
  3. збирає дві карти: міську й обрізану до одного району;
  4. витягає з кожної <script> і перевіряє синтаксис через node, якщо він є;
  5. перевіряє, що відомі установи не просочилися на карту;
  6. рахує баланс тегів розмітки;
  6. порівнює контрольні суми з попереднім запуском і каже, чи змінився
     результат.

Порядок роботи з пунктом 6: перед правкою запустіть `python src/check_build.py
--save` — це запам'ятає еталон. Після правки запустіть без ключа. Якщо ви лише
переставляли код, а не міняли поведінку, всі три карти мають лишитися
незмінними. Якщо змінилися — ви бачите, які саме.

Еталон лежить у data/_check_last.json і в репозиторій не потрапляє.
"""
import os, sys, gzip, json, shutil, hashlib, tempfile, subprocess, py_compile, re

SRCD = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SRCD)
DATA = os.path.join(ROOT, 'data')
TESTGZ = os.path.join(DATA, 'events_test.db.gz')
TESTDB = os.path.join(DATA, 'events_test.db')      # data/*.db у .gitignore
STATE = os.path.join(DATA, '_check_last.json')
sys.path.insert(0, SRCD)

VOID = {'meta', 'link', 'br', 'hr', 'img', 'input', 'source',
        'area', 'base', 'col', 'embed', 'track', 'wbr'}

# ---- АДРЕСИ, ЯКИХ НА КАРТІ БУТИ НЕ МАЄ ----
# Це відділи поліції та місця оформлення протоколів. Кожну з них колись уже
# ловили, і кожна колись поверталася — бо ловилися вони правилом, а не
# перевіркою. Тепер повернення видно одразу.
#
# Додавайте сюди щоразу, коли знаходите установу на карті: спершу рядок тут,
# і аж потім правило, яке її ловить.
NE_MAE_BUTY = [
    'вул. Відпочинку, 18',
    'вул. Чорних Запорожців, 20',
    'вул. Святослава Хороброго, 9',
    'вул. С. Хороброго, 9',
    'вул. Бродівська, 79',
    'вул. Радосинська, 140',
]


def drop_cache():
    """Прибрати __pycache__ перед перевіркою.

    Знайдено 3 вересня: збірка взяла старий .pyc і зібрала карту з коду, якого
    вже не було у файлах. Перевірка при цьому казала «чисто». Тому кеш зносимо
    завжди — інакше слово «перевірено» нічого не варте.
    """
    d = os.path.join(SRCD, '__pycache__')
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)


def compile_all():
    bad = []
    for f in sorted(os.listdir(SRCD)):
        if not f.endswith('.py'):
            continue
        try:
            py_compile.compile(os.path.join(SRCD, f), doraise=True)
        except Exception as e:
            bad.append(f'{f}: {e}')
    return bad


def unpack():
    if not os.path.exists(TESTGZ):
        return f'немає {os.path.relpath(TESTGZ, ROOT)}'
    with gzip.open(TESTGZ, 'rb') as g, open(TESTDB, 'wb') as f:
        shutil.copyfileobj(g, f)
    return None


def check_markup(html):
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.st, self.err = [], []

        def handle_starttag(self, t, a):
            if t not in VOID:
                self.st.append(t)

        def handle_endtag(self, t):
            if t in VOID:
                return
            if not self.st:
                self.err.append(f'зайвий </{t}>')
            elif self.st[-1] != t:
                self.err.append(f'очікував </{self.st[-1]}>, отримав </{t}>')
            else:
                self.st.pop()

    p = P()
    p.feed(html)
    return p.err + [f'не закрито <{t}>' for t in p.st]


def check_js(html, tmp):
    m = re.search(r'<script>\n(.*)\n</script>', html, re.S)
    if not m:
        return ['не знайдено <script> у сторінці']
    jsf = os.path.join(tmp, 'x.js')
    with open(jsf, 'w', encoding='utf-8') as f:
        f.write(m.group(1))
    if not shutil.which('node'):
        return []                       # node не встановлено — мовчки пропускаємо
    r = subprocess.run(['node', '--check', jsf], capture_output=True, text=True)
    return [] if r.returncode == 0 else [r.stderr.strip().split('\n')[-1]]


def main(save=False):
    print('1. Компіляція src/')
    drop_cache()
    bad = compile_all()
    if bad:
        for b in bad:
            print('   ПОМИЛКА', b)
        return 1
    print('   усі файли компілюються')

    print('2. Тестова база')
    err = unpack()
    if err:
        print('   ПОМИЛКА', err)
        return 1
    print(f'   {os.path.relpath(TESTDB, ROOT)} розпаковано')

    import step3_map, map_excl
    step3_map.DB = TESTDB
    # Перевірка не має чіпати справжні дані. Раніше вона переписувала
    # data/vykluchennya.txt переліком, порахованим на зменшеній базі, — і цей
    # перелік потрапляв у коміт. Вихідні файли відводимо у тимчасову папку;
    # ваші власні списки (vykluchennya_moyi, vykluchennya_ne) лишаються вхідними.
    tmp = tempfile.mkdtemp(prefix='karta_check_')
    map_excl.EXCL = os.path.join(tmp, 'vykluchennya.txt')
    map_excl.REVIEW = os.path.join(tmp, 'top100.txt')

    CASES = [('міська', dict(district=None)),
             ('районна', dict(district='Деснянський'))]

    now, problems, city_html = {}, [], ''
    try:
        for name, kw in CASES:
            print(f'3. Збірка: {name}')
            dst = os.path.join(tmp, f'{name}.html')
            out = open(os.devnull, 'w')
            keep, sys.stdout = sys.stdout, out
            try:
                step3_map.main(out=dst, **kw)
            finally:
                sys.stdout = keep
                out.close()
            html = open(dst, encoding='utf-8').read()
            if name == 'міська': city_html = html
            now[name] = hashlib.sha256(html.encode('utf-8')).hexdigest()[:16]
            for e in check_markup(html):
                problems.append(f'{name}: розмітка — {e}')
            for e in check_js(html, tmp):
                problems.append(f'{name}: JavaScript — {e}')
            print(f'   {len(html)/1048576:.1f} МБ · {now[name]}')
    finally:
        pass

    print('4. Установи не просочилися на карту')
    # Дві перевірки, бо однієї мало. Перелік виключень — те, що вирішило
    # правило. Підписи точок — те, що врешті побачить людина: одна будівля
    # буває записана і як «9», і як «9А», тож адреса може вилетіти з переліку,
    # а точка лишитися під сусіднім написанням.
    excl_txt = ''
    if os.path.exists(map_excl.EXCL):
        excl_txt = open(map_excl.EXCL, encoding='utf-8').read().lower()
    # Ваш ручний список (vykluchennya_moyi.txt) теж прибирає точки з карти —
    # без нього тут «пропущено» помилково, якщо адреса виключена саме ним,
    # а не автоматикою (знайдено 3 вересня на вул. С. Хороброго, 9).
    if os.path.exists(map_excl.MANUAL):
        excl_txt += '\n' + open(map_excl.MANUAL, encoding='utf-8').read().lower()
    missed = [a for a in NE_MAE_BUTY if a.lower() not in excl_txt]
    leaked = []
    m_ = re.search(r'const M=.*?, P=(\[.*?\]);\n', city_html or '', re.S)
    if m_:
        addrs = {(p or [None, None, ''])[2] for p in json.loads(m_.group(1))}
        leaked = [a for a in NE_MAE_BUTY if a in addrs]
    else:
        print('   не знайшов перелік точок у сторінці')
    for a in missed: print(f'   ПОМИЛКА не потрапила у виключення: {a}')
    for a in leaked: print(f'   ПОМИЛКА лишилася точкою на карті: {a}')
    if not missed and not leaked:
        print(f'   усі {len(NE_MAE_BUTY)} відомих установ виключено й на карті їх немає')
    if missed or leaked:
        return 1

    print('5. Розмітка і JavaScript')
    if problems:
        for p in problems:
            print('   ПОМИЛКА', p)
        return 1
    print('   чисто')

    shutil.rmtree(tmp, ignore_errors=True)

    print('6. Порівняння з попереднім запуском')
    if save:
        json.dump(now, open(STATE, 'w'))
        print('   еталон збережено')
        return 0
    if not os.path.exists(STATE):
        json.dump(now, open(STATE, 'w'))
        print('   еталона не було — збережено поточний результат')
        return 0
    before = json.load(open(STATE))
    same = True
    for name, _ in CASES:
        was, is_ = before.get(name), now[name]
        if was == is_:
            print(f'   {name}: без змін')
        else:
            same = False
            print(f'   {name}: ЗМІНИЛАСЯ  було {was}  стало {is_}')
    json.dump(now, open(STATE, 'w'))
    if same:
        print('\n=== ГОТОВО === результат не змінився')
    else:
        print('\n=== ГОТОВО === результат змінився. Якщо ви лише переставляли\n'
              'код, це помилка. Якщо міняли поведінку — так і має бути.')
    return 0


if __name__ == '__main__':
    sys.exit(main(save='--save' in sys.argv))

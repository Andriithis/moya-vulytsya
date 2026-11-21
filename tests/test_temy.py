"""Дві теми вигляду з перемиканням однією командою (ZAVDANNYA-197, MV-219): spokiyna («Спокійна й чиста», за
замовчуванням) і indygo («Індиго й м'ята»).

Стереже:
* обидві теми збираються; у стилях — змінні, шрифти й власні правила саме обраної теми; іконки й маніфест — її кольорів;
* --tema і MV_TEMA перемикають тему; без них — spokiyna;
* у коді сторінок немає жорстких кольорів поза темою (пошуком: site/sait/*.css|*.js, CSS ігор у картi, генератори сторінок);
* контраст тексту й межі кнопок обох тем — не нижче WCAG AA (текст ≥ 4,5 : 1, межа елемента ≥ 3 : 1), в обох режимах;
* «Спокійна»: найтемніше = найбільше (вершини — того самого тону, лише темніші; у темному режимі — світліші), числа не тонкі;
* виправлення 196 для обох тем: легенда кольору на екрані карти, неповний рік — блідий стовпчик, не пунктир; картка
  маленької соти — не назвою району; підписи районів — шаром над сотами з ореолом.

Запуск: python -m unittest tests/test_temy.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
SITE = KORIN / 'site'
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(SITE))

import zibraty_sait as Z  # noqa: E402
from test_sait import YE_H3, stvoryty_bazu  # noqa: E402

TEMY = ('spokiyna', 'indygo')


def yaskravist(h: str) -> float:
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def kontrast(a: str, b: str) -> float:
    x, y = sorted((yaskravist(a), yaskravist(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def ton(h: str) -> float:
    import colorsys
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)[0] * 360


# Пари «текст / тло» (≥ 4,5 : 1) і «межа елемента / тло» (≥ 3 : 1) — WCAG 2.1 AA, 1.4.3 і 1.4.11.
TEKST = [('ink', 'ground'), ('ink', 'surface'), ('ink-2', 'surface'), ('ink-2', 'ground'), ('muted', 'ground'),
         ('muted', 'surface'), ('accent', 'surface'), ('accent', 'ground'), ('on-accent', 'accent'), ('ink', 'accent-soft'),
         ('ink', 'surface-tint'), ('karta-pidpys', 'karta-tlo'), ('ink-2', 'karta-oreol')]
MEZHA = [('mezha', 'ground'), ('mezha', 'surface')]


class Kontrast(unittest.TestCase):
    def test_aa_obydvi_temy_obydva_rezhymy(self):
        for tema in TEMY:
            for rezhym, z in Z.zminni_temy(tema).items():
                for a, b in TEKST:
                    with self.subTest(tema=tema, rezhym=rezhym, para=(a, b)):
                        self.assertGreaterEqual(kontrast(z[a], z[b]), 4.5, f'{z[a]} на {z[b]}')
                for a, b in MEZHA:
                    with self.subTest(tema=tema, rezhym=rezhym, para=(a, b)):
                        self.assertGreaterEqual(kontrast(z[a], z[b]), 3.0, f'{z[a]} на {z[b]}')

    def test_siryi_tekst_spokiynoi(self):
        """ZVIT-196: сірий «Спокійної» — не світліший за #6B675F (5,1 : 1 на тлі), а не #77736B макета."""
        z = Z.zminni_temy('spokiyna')['svitla']
        self.assertGreaterEqual(kontrast(z['muted'], z['ground']), kontrast('#6B675F', '#F5F3EE') - 0.01)


class Spokiyna(unittest.TestCase):
    def test_naitemnishe_naibilshe(self):
        """Шкала сот і вершини — один тон: світла — від світлого до найтемнішого, темна — навпаки; без «вершин» іншого кольору."""
        k = Z.kolory_tem('spokiyna')
        for rezhym, znak in (('svitla', -1), ('temna', 1)):
            ryad = k[rezhym]['sc'] + k[rezhym]['pk']
            ya = [yaskravist(c) for c in ryad]
            for a, b in zip(ya, ya[1:]):
                self.assertGreater((b - a) * znak, 0, f'{rezhym}: {ryad} — не за порядком')
            t5 = ton(k[rezhym]['sc'][4])
            for c in k[rezhym]['pk'] + k[rezhym]['sc'][1:]:
                rizn = abs((ton(c) - t5 + 180) % 360 - 180)
                self.assertLess(rizn, 25, f'{rezhym}: {c} — інший тон, ніж {k[rezhym]["sc"][4]}')

    def test_chysla_ne_tonki_i_shryfty(self):
        d = Z.dani_temy('spokiyna')
        self.assertGreaterEqual(int(d['zminni']['vaha-chysla']), 400, 'тонкі числа бліднуть на сонці (ZVIT-196)')
        self.assertIn('Source Serif 4', d['zminni']['f-chysla'])
        self.assertEqual({s['simia'] for s in d['shryfty']}, {'Source Sans 3', 'Source Serif 4'})
        for s in d['shryfty']:
            self.assertTrue((SITE / 'sait' / 'shryfty' / s['litsenziia']).is_file())

    def test_knopky_pleski_a_kupivlia_sutsilna(self):
        d, css = Z.dani_temy('spokiyna'), (SITE / 'temy' / 'spokiyna.css').read_text(encoding='utf-8')
        self.assertEqual(d['zminni']['klav-ten'], 'none')
        self.assertGreaterEqual(int(d['zminni']['knopka-holovna-h'].rstrip('px')), 48)
        self.assertIn('.rozdil--kupyty', css, 'блок «купити» праворуч на комп\'ютері («Чітка»)')
        self.assertRegex(css, r'\.tsiny--odna \.knopka--holovna[^{]*\{[^}]*width: 100%', 'на телефоні — на всю ширину')


# Жорсткі кольори в коді сторінок: усе — змінними теми. Дозволено лише чисті білий і чорний як ціль змішування
# (zmishaty(колір, '#FFFFFF', частка) — «світліше/темніше» від кольору теми) і слово white для освітлення 3D.
KOD_STORINOK = [
    *sorted((SITE / 'sait').glob('*.css')), *sorted((SITE / 'sait').glob('*.js')),
    SITE / 'ihry' / 'ihry.css', SITE / 'ihry' / 'kariera' / 'kariera.css', SITE / 'ihry' / 'litopys' / 'litopys.css',
    *[p for p in sorted(SITE.glob('*.py')) if p.name.startswith(('storinky', 'storinka', 'zibraty_sait', 'tsiny', 'zaholovky', 'khostynh'))],
]
HEX6 = re.compile(r'(?<![\w&-])#[0-9A-Fa-f]{6}\b')
HEX3_CSS = re.compile(r'(?:[:,(\s])#[0-9A-Fa-f]{3}\b(?![\w-])')
RGBA = re.compile(r'\brgba?\(\s*\d')
ZMISH = re.compile(r"""zmishaty\([^()]*?['"]#(?:FFFFFF|000000|ffffff|000000)['"]""")


class BezZhorstkykhKoloriv(unittest.TestCase):
    def test_kod_storinok_lyshe_zminni(self):
        for f in KOD_STORINOK:
            for i, ryadok in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
                bez = ZMISH.sub('', ryadok)
                if f.suffix == '.py':      # у Python — лише з HTML/CSS у рядках, не перетворення кольорів
                    bez = re.sub(r"'#000000'|'#FFFFFF'", '', bez)
                znaideno = HEX6.findall(bez) + RGBA.findall(bez)
                if f.suffix == '.css':
                    znaideno += [x for x in HEX3_CSS.findall(bez) if ':' in bez.split(x)[0].rsplit('{', 1)[-1]]
                with self.subTest(f=f.name, ryadok=i):
                    self.assertEqual(znaideno, [], f'{f.relative_to(KORIN)}:{i}: {ryadok.strip()[:160]}')

    def test_tema_ne_v_kodi(self):
        """Шрифтів теми й їхніх @font-face у коді сторінок немає — їх пише збирач із файлу теми."""
        css = re.sub(r'/\*.*?\*/', '', (SITE / 'sait' / 'sait.css').read_text(encoding='utf-8'), flags=re.S)
        self.assertNotIn('@font-face', css)
        self.assertNotRegex(css, r'font-family:\s*(Plex|\'Source)')

    def test_fayly_tem_odnakovi_za_skladom(self):
        kliuchi = None
        for tema in TEMY:
            d = Z.dani_temy(tema)
            for r in ('svitla', 'temna'):
                k = set(d['kolory'][r]) - {'lineStrong', 'bort', 'accentStrong'}
                kliuchi = kliuchi or k
                self.assertEqual(k, kliuchi, f'{tema} ({r}): інший набір кольорів')
            self.assertEqual(set(d['zminni']), set(Z.dani_temy('indygo')['zminni']), tema)
            for r in ('svitla', 'temna'):
                self.assertEqual(set(d['zminni_tem'][r]), set(Z.dani_temy('indygo')['zminni_tem'][r]), f'{tema} {r}')
            self.assertGreaterEqual(len(d['kolory_serii']), 6)


class Peremykannia(unittest.TestCase):
    def test_za_zamovchuvanniam_spokiyna_i_mv_tema(self):
        kod = ('import sys; sys.path.insert(0, sys.argv[1]); import zibraty_sait as Z; '
               'print(Z.vstanovyty_temu(None))')
        env = {k: v for k, v in os.environ.items() if k != 'MV_TEMA'}
        r = subprocess.run([sys.executable, '-c', kod, str(SITE)], capture_output=True, text=True, env=env, check=True)
        self.assertEqual(r.stdout.strip(), 'spokiyna')
        r = subprocess.run([sys.executable, '-c', kod, str(SITE)], capture_output=True, text=True, env={**env, 'MV_TEMA': 'indygo'}, check=True)
        self.assertEqual(r.stdout.strip(), 'indygo')
        with self.assertRaises(SystemExit):
            Z.vstanovyty_temu('nemaie')
        Z.vstanovyty_temu(None)

    def test_parametr_tema(self):
        src = (SITE / 'zibraty_sait.py').read_text(encoding='utf-8')
        self.assertIn("p.add_argument('--tema', choices=TEMY", src)
        self.assertIn('MV_TEMA', (SITE / 'vyklasty.py').read_text(encoding='utf-8'))


@unittest.skipUnless(YE_H3, 'немає h3 — сайт не зібрати')
class ObydviTemyZbyraiutsia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        stvoryty_bazu(tmp / 'events.db')
        cls.saity = {}
        for tema in TEMY:
            Z.zibraty_sait(tmp / 'events.db', tmp / tema, None, KORIN / 'data' / 'borders.json', tema=tema)
            cls.saity[tema] = tmp / tema
        Z.vstanovyty_temu(None)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_zminni_shryfty_i_pravyla_temy(self):
        for tema, sait in self.saity.items():
            css = (sait / 'sait' / 'sait.css').read_text(encoding='utf-8')
            z = Z.zminni_temy(tema)
            self.assertIn(f'--ground:{z["svitla"]["ground"]};', css, tema)
            self.assertIn(f'--ground:{z["temna"]["ground"]};', css, tema)
            for s in Z.dani_temy(tema)['shryfty']:
                self.assertIn(f"font-family: '{s['simia']}'", css, tema)
                for f in Z.fayly_shryftiv(tema):
                    self.assertTrue((sait / 'sait' / 'shryfty' / f).is_file(), f'{tema}: {f}')
            vlasni = Z.dani_temy(tema).get('css')
            if vlasni:
                self.assertIn(f'site/temy/{vlasni}', css)
            for inshyi in set(TEMY) - {tema}:
                self.assertNotIn(f'--ground:{Z.zminni_temy(inshyi)["svitla"]["ground"]};', css, f'{tema}: змінні іншої теми')
            self.assertEqual(len(list((sait / 'karta').glob('zastavka-*.webp'))), 4, f'{tema}: перший екран')

    def test_ikonky_i_manifest_temy(self):
        from PIL import Image
        for tema, sait in self.saity.items():
            k = Z.kolory_tem(tema)['svitla']
            m = json.loads((sait / 'manifest.webmanifest').read_text(encoding='utf-8'))
            self.assertEqual(m['theme_color'], k['ground'], tema)
            for i in m['icons']:
                self.assertTrue((sait / i['src'].lstrip('/')).is_file(), f'{tema}: {i["src"]}')
            with Image.open(sait / 'sait' / 'ikony' / 'ikona-512.png') as im:
                tlo = '#%02X%02X%02X' % im.convert('RGB').getpixel((6, 6))
                znak = '#%02X%02X%02X' % im.convert('RGB').getpixel((256, 150))
            self.assertEqual(tlo, k['ground'], tema)
            self.assertLess(max(abs(int(znak[i:i + 2], 16) - int(k['accent'][i:i + 2], 16)) for i in (1, 3, 5)), 6, tema)
            html = (sait / 'index.html').read_text(encoding='utf-8')
            self.assertIn(f'<meta name="theme-color" content="{k["ground"]}">', html)
            for f in Z.dani_temy(tema)['preload']:
                self.assertIn(f'/sait/shryfty/{f}', html)

    def test_vypravlennia_196(self):
        for tema, sait in self.saity.items():
            holovna = (sait / 'index.html').read_text(encoding='utf-8')
            self.assertIn('id="legenda" class="legenda plashka"', holovna, f'{tema}: легенда кольору на екрані карти')
            css = (sait / 'sait' / 'sait.css').read_text(encoding='utf-8')
            self.assertIn('.rik--nepovnyi .rik__stovpchyk { opacity: .4; }', css)
            self.assertNotRegex(css, r'nepovn[^{]*\{[^}]*dash', 'неповний рік — не пунктир')
            vul = next(p for p in (sait / 'vulytsia').glob('*/index.html') if 'rik--nepovnyi' in p.read_text(encoding='utf-8'))
            self.assertTrue(vul)
        js = (SITE / 'sait' / 'karta.js').read_text(encoding='utf-8')
        self.assertIn("'Ділянка ' + G.pl", js, 'картка соти без вулиці — «Ділянка ≈… км²», не назва району')
        self.assertNotIn("|| rn || 'Київ'", js)
        self.assertIn("id: 'k-rayony-nazvy'", js, 'підписи районів — окремим шаром')
        self.assertIn("'text-halo-color': K.oreol", js)


if __name__ == '__main__':
    unittest.main()

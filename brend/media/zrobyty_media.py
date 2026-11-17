# -*- coding: utf-8 -*-
"""Візуал про публічне місце для медіа (MV-113, ZAVDANNYA-113): числа з dani-edrsr → картинки й слайди.

    python brend/media/zrobyty_media.py <місце>.json <тека media>/<slug> [--adresa-saitu https://…]
    python brend/media/zrobyty_media.py <тека JSON> <тека media>        (усі місця одразу — ZAVDANNYA-124)

Вхід — JSON з `dani-edrsr/src/vizual_mistsia.py` (лише публічні місця, лише агрегати). Вихід у теці місця:
  kartka-1x1.png (1080×1080), kartka-16x9.png (1920×1080) — «цифри + карта» (варіант А з NOVI-LINII.md);
  slaid-1.png … slaid-8.png (1920×1080) і slaidy.pdf — 8 слайдів; vizual.json — ті самі числа з посиланням на сторінку місця.
Збирач сайту (`site/zibraty_sait.py --media <тека media>`) кладе цю теку на сторінку місця й показує блок «Для медіа».
Падає, якщо місце не публічне, текст вилазить за полотно чи трапилось заборонене слово (безпечн-, рейтинг, імена).
Потрібні playwright і Chromium (MV_CHROME — шлях до іншого Chromium), Pillow — для PDF.
"""
import argparse, json, os, re, sys
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parent.parent
sys.path.insert(0, str(KORIN / 'site'))
PUBLICHNI = ('площа', 'вокзал', 'метро', 'ТЦ', 'ринок', 'парк', 'міст', 'пляж', 'острів')   # як dani-edrsr/src/vizual_mistsia.py
ZNIMKY = [('A', '1x1', 'kartka-1x1.png'), ('A', '16x9', 'kartka-16x9.png')] + [('S', n, f'slaid-{n}.png') for n in range(1, 9)]
ZABOR = re.compile(r'безпечн|рейтинг|найгірш|страшн|ОСОБА_|судд', re.I)


def posylannia(adresa_saitu, storinka):
    """«moya-vulytsya.pages.dev/vulytsia/vokzalna-ploshcha/» — як надрукувати на картинці (без https://)"""
    return re.sub(r'^https?://', '', adresa_saitu.rstrip('/')) + storinka


def zrobyty(vkhid, teka, adresa_saitu):
    d = json.loads(Path(vkhid).read_text(encoding='utf-8'))
    if d.get('typ') not in PUBLICHNI:
        raise SystemExit(f'«{d.get("nazva")}»: не публічне місце ({d.get("typ")}) — візуал для медіа лише для публічних місць (MV-113)')
    if not str(d.get('storinka', '')).startswith('/'):
        raise SystemExit(f'«{d.get("nazva")}»: немає сторінки місця на сайті')
    d['posylannia'] = posylannia(adresa_saitu, d['storinka'])
    tekst = json.dumps({k: v for k, v in d.items() if k != 'umovy'}, ensure_ascii=False)
    if ZABOR.search(tekst):
        raise SystemExit(f'«{d["nazva"]}»: заборонене в даних: {ZABOR.search(tekst).group(0)!r}')
    teka = Path(teka); teka.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    pomylky = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=os.environ.get('MV_CHROME') or None)
        s = b.new_page(device_scale_factor=2, viewport={'width': 1000, 'height': 600})
        s.goto((TUT / 'vizual.html').as_uri())
        s.evaluate('document.fonts.ready')
        for v, f, imia in ZNIMKY:
            o = {'v': v, 'f': f} if v != 'S' else {'v': 'S', 'n': f}
            rez = s.evaluate('([d, o]) => pokazaty(d, o)', [d, o])
            s.evaluate('document.fonts.ready')
            s.locator('#p').screenshot(path=str(teka / imia))
            if rez['zle'] or rez['perepovnennia']: pomylky.append((imia, rez))
        b.close()
    if pomylky:
        raise SystemExit(f'«{d["nazva"]}»: {pomylky!r}')
    from PIL import Image
    slaidy = [Image.open(teka / f'slaid-{n}.png').convert('RGB') for n in range(1, 9)]
    slaidy[0].save(teka / 'slaidy.pdf', save_all=True, append_images=slaidy[1:], resolution=144)
    (teka / 'vizual.json').write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    return d


def main(argv=None):
    import zibraty_sait as ZS
    a = argparse.ArgumentParser(description='Візуал про публічне місце для медіа (MV-113)')
    a.add_argument('vkhid', help='<місце>.json або тека з JSON усіх місць (ZAVDANNYA-124: кожна сторінка /mistse/…)')
    a.add_argument('teka', help='тека місця або (для теки JSON) тека media — у ній буде <slug>/ на кожне місце')
    a.add_argument('--adresa-saitu', default=ZS.ADRESA_SAITU)
    k = a.parse_args(argv)
    vkhody = sorted(Path(k.vkhid).glob('*.json')) if Path(k.vkhid).is_dir() else [Path(k.vkhid)]
    for f in vkhody:
        teka = Path(k.teka) / f.stem if Path(k.vkhid).is_dir() else Path(k.teka)
        d = zrobyty(f, teka, k.adresa_saitu)
        print(f'{d["nazva"]}: {len(ZNIMKY)} картинок і slaidy.pdf → {teka}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

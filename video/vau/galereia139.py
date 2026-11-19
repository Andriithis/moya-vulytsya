"""Галерея візуальної лабораторії (ZAVDANNYA-139, п. 6): одна HTML-сторінка з усіма кадрами й кліпами.

    python video/vau/galereia139.py [--vykhid video/vyhid/139] [--kudy video/vyhid/galereia-139]

Бере каталог `video/vyhid/kesh/stsenarii/139-katalog.json` (пише laboratoriia139.py), кадри 1080×1920 з
`<vykhid>/znimky/` (rushii.py --kadry) і кліпи `<vykhid>/<id>.mp4`; кліпи стискає до 540×960 (як дивитиметься телефон
після стиснення TikTok — грубо), кадри — у JPEG. Сторінка відкривається з диска, без сервера й без зовнішніх файлів.
"""
from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parents[1]
sys.path.insert(0, str(TUT))
from rushii import ffmpeg  # noqa: E402

KATALOG = KORIN / 'video' / 'vyhid' / 'kesh' / 'stsenarii' / '139-katalog.json'
ZAPYS = {'kod': 'zapys_saitu', 'id': '139-zapys_saitu-temna', 'tema': 'temna', 'hrupa': 'Справжній сайт',
         'nazva': 'Запис екрана карти сайту (3D)', 'kadr_t': 3.6, 'kadr_svitla': '139-zapys_saitu-svitla',
         'shcho': 'Справжня сторінка /karta/ на весь кадр, увімкнено 3D, камера облітає місто так само, як у кліпах рушія. '
                  'Видно все, що бачить людина на сайті: пошук, кнопки, шкалу часу.',
         'dlia': 'Як це працює, POV: застава завтра, продуктові ролики — коли важливо «це справжній сайт»'}
HRUPY = ['Соти', 'Теми', 'Адреси', 'Не карта', 'Справжній сайт']


def kadr(png: Path, jpg: Path):
    jpg.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(png), '-q:v', '4', str(jpg)], check=True)


def klip(mp4: Path, kudy: Path):
    kudy.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(mp4), '-vf', 'scale=540:960:flags=lanczos', '-c:v', 'libx264',
                    '-preset', 'slow', '-crf', '27', '-maxrate', '1800k', '-bufsize', '3600k', '-pix_fmt', 'yuv420p', '-an',
                    '-movflags', '+faststart', str(kudy)], check=True)


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--vykhid', type=Path, default=KORIN / 'video' / 'vyhid' / '139')
    a.add_argument('--kudy', type=Path, default=KORIN / 'video' / 'vyhid' / 'galereia-139')
    arg = a.parse_args()
    kat = json.loads(KATALOG.read_text(encoding='utf-8'))
    if (arg.vykhid / f"{ZAPYS['id']}.mp4").is_file():
        kat.append(ZAPYS)
    zn = arg.vykhid / 'znimky'
    kartky = {h: [] for h in HRUPY}
    nemaie = []
    for z in kat:
        t = f"{z['kadr_t']:05.2f}"
        fail = []
        for id_ in (z['id'], z.get('kadr_svitla')):
            if not id_:
                continue
            png = zn / f'{id_}-{t}.png'
            if png.is_file():
                kadr(png, arg.kudy / 'kadry' / f'{id_}.jpg')
                fail.append(id_)
            else:
                nemaie.append(png.name)
        mp4 = arg.vykhid / f"{z['id']}.mp4"
        ye_klip = mp4.is_file()
        if ye_klip:
            klip(mp4, arg.kudy / 'klipy' / f"{z['id']}.mp4")
        else:
            nemaie.append(mp4.name)
        e = html.escape
        kadry_html = ''.join(f'<a href="kadry/{f}.jpg"><img src="kadry/{f}.jpg" loading="lazy" alt="кадр {e(z["nazva"])}"></a>' for f in fail)
        video = (f'<video src="klipy/{z["id"]}.mp4" muted loop playsinline autoplay preload="metadata"></video>' if ye_klip else '<div class="nema">кліпу немає</div>')
        tema = {'temna': 'темна', 'svitla': 'світла'}.get(z['tema'], z['tema'])
        kartky[z['hrupa']].append(f'<article id="{z["kod"]}"><h3>{e(z["nazva"])}</h3><div class="media">{video}{kadry_html}</div>'
                                  f'<p>{e(z["shcho"])}</p><p class="dlia"><b>Для роликів:</b> {e(z["dlia"])}</p>'
                                  f'<p class="kod">код <code>{e(z["kod"])}</code> · тема кліпу: {e(tema)}'
                                  f'{" · кадр: темна і світла" if len(fail) > 1 else ""}</p></article>')
    vsogo = sum(len(v) for v in kartky.values())
    zmist = ''.join(f'<h2>{h} <small>{len(v)}</small></h2><section>{"".join(v)}</section>' for h, v in kartky.items() if v)
    storinka = f"""<!DOCTYPE html>
<html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Моя вулиця — лабораторія виглядів роликів (139)</title>
<style>
 body {{ margin: 0; background: #11142A; color: #F0F1FA; font: 16px/1.45 system-ui, sans-serif; }}
 header {{ padding: 24px 20px 8px; max-width: 1400px; margin: 0 auto; }}
 h1 {{ font-size: 26px; margin: 0 0 6px; }} header p {{ color: #A6A9C1; margin: 4px 0; }}
 h2 {{ max-width: 1400px; margin: 34px auto 10px; padding: 0 20px; font-size: 22px; color: #66E6BA; }}
 h2 small {{ color: #A6A9C1; font-weight: 400; }}
 section {{ max-width: 1400px; margin: 0 auto; padding: 0 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 18px; }}
 article {{ background: #1B1F39; border-radius: 16px; padding: 14px; }}
 article h3 {{ margin: 0 0 10px; font-size: 18px; }}
 .media {{ display: flex; gap: 6px; align-items: flex-start; }}
 video {{ width: 160px; aspect-ratio: 9/16; border-radius: 10px; background: #000; }}
 .media img {{ width: 72px; aspect-ratio: 9/16; object-fit: cover; border-radius: 8px; display: block; }}
 .nema {{ width: 160px; aspect-ratio: 9/16; display: grid; place-items: center; color: #A6A9C1; border: 1px dashed #4B506F; border-radius: 10px; }}
 article p {{ margin: 10px 0 0; color: #D1D3E2; }} .dlia {{ color: #F0F1FA; }} .kod {{ color: #A6A9C1; font-size: 13px; }}
 code {{ background: #232849; padding: 1px 5px; border-radius: 5px; }}
 @media (max-width: 600px) {{ video {{ width: 150px; }} .media img {{ width: 64px; }} }}
</style></head><body>
<header><h1>Лабораторія виглядів роликів — {vsogo} виглядів</h1>
<p>Кліп 5 с з рухом камери (540×960) і кадр 1080×1920 (натисніть, щоб відкрити). Дані — пробний випуск 08.11.2026,
 без насильства й чутливих справ, без номерів будинків. Колір — кількість даних або вид події, не «небезпека».</p>
<p>Це зразки вигляду, не готові ролики: без звуку й без кінцевого банера. Нічого не опубліковано.</p></header>
{zmist}
</body></html>
"""
    arg.kudy.mkdir(parents=True, exist_ok=True)
    (arg.kudy / 'index.html').write_text(storinka, encoding='utf-8')
    print(f'{vsogo} виглядів → {arg.kudy / "index.html"}')
    if nemaie:
        print('немає:', ', '.join(nemaie))


if __name__ == '__main__':
    main()

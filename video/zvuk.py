"""Звук роликів «Моєї вулиці» (ZAVDANNYA-94, MV-93): синтезований український голос + тиха власна музика.

Голос вибирає змінна середовища MV_HOLOS (ключі — лише в змінних середовища, ніколи у файлах):

    piper       (за замовчуванням) — безкоштовний, офлайн, на нашому сервері. Модель — MV_PIPER_MODEL
                (за замовчуванням uk_UA-ukrainian_tts-medium, качається з huggingface.co/rhasspy/piper-voices
                у ~/.cache/mv-holosy/), голос — MV_PIPER_HOLOS: tetiana (за замовчуванням) | lada | mykyta.
    azure       — Azure AI Speech: AZURE_SPEECH_KEY, AZURE_SPEECH_REGION (напр. westeurope),
                  MV_AZURE_HOLOS (uk-UA-PolinaNeural | uk-UA-OstapNeural).
    google      — Google Cloud Text-to-Speech: GOOGLE_TTS_KEY (ключ API), MV_GOOGLE_HOLOS (напр. uk-UA-Standard-A).
    elevenlabs  — ElevenLabs: ELEVENLABS_API_KEY, MV_ELEVENLABS_HOLOS (id голосу), модель eleven_multilingual_v2.

Платні голоси не перевірені (ключів немає, ZAVDANNYA-94): код написано за документацією, перший запуск — з ключем
Микити й на 2–3 текстах.

Музика — своя: тихі акорди із синусоїд, згенеровані тут (без чужих прав і без скарг Content ID). Набір петель:
    python video/zvuk.py --muzyka video/muzyka/          # 5 петель по 40 с
Голос для перевірки на слух:
    python video/zvuk.py --holos "Текст" -o proba.wav

Рендер (video/rendery.py --zvuk) бере з кожного відрізка сценарію текст `holos`, синтезує його, ставить на початок
відрізка (коли з'являється картка), під голосом приглушує музику й зводить усе до −16 LUFS (гучність соцмереж);
поруч пише субтитри .srt.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import wave
from pathlib import Path

TUT = Path(__file__).resolve().parent
KESH = Path(os.environ.get('MV_HOLOSY_KESH', Path.home() / '.cache' / 'mv-holosy'))
PIPER_URL = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/uk/uk_UA/'
PIPER_MODELI = {
    'uk_UA-ukrainian_tts-medium': 'ukrainian_tts/medium/uk_UA-ukrainian_tts-medium',
    'uk_UA-lada-x_low': 'lada/x_low/uk_UA-lada-x_low',
}
CHASTOTA = 44100

# ------------------------------------------------------------------ текст для голосу

ODYNYTSI = ['нуль', 'один', 'два', 'три', 'чотири', "п'ять", 'шість', 'сім', 'вісім', "дев'ять", 'десять', 'одинадцять',
            'дванадцять', 'тринадцять', 'чотирнадцять', "п'ятнадцять", 'шістнадцять', 'сімнадцять', 'вісімнадцять',
            "дев'ятнадцять"]
DESIATKY = ['', '', 'двадцять', 'тридцять', 'сорок', "п'ятдесят", 'шістдесят', 'сімдесят', 'вісімдесят', "дев'яносто"]
SOTNI = ['', 'сто', 'двісті', 'триста', 'чотириста', "п'ятсот", 'шістсот', 'сімсот', 'вісімсот', "дев'ятсот"]


def _do_tysiachi(n: int, zhin: bool = False) -> list[str]:
    s = [SOTNI[n // 100]] if n >= 100 else []
    n %= 100
    if n >= 20:
        s.append(DESIATKY[n // 10])
        n %= 10
        if n == 0:
            return s
    if n or not s:
        w = ODYNYTSI[n]
        if zhin and n == 1:
            w = 'одна'
        elif zhin and n == 2:
            w = 'дві'
        s.append(w)
    return s


def chyslo_slovamy(n: int) -> str:
    """Кількісний числівник: 2024 → «дві тисячі двадцять чотири». До 999 999."""
    if n < 0:
        return 'мінус ' + chyslo_slovamy(-n)
    if n < 1000:
        return ' '.join(_do_tysiachi(n))
    t, r = divmod(n, 1000)
    tys = _do_tysiachi(t, zhin=True)
    o = t % 100
    forma = 'тисяч' if 11 <= o <= 19 else {1: 'тисяча', 2: 'тисячі', 3: 'тисячі', 4: 'тисячі'}.get(t % 10, 'тисяч')
    return ' '.join(tys + [forma] + (_do_tysiachi(r) if r else []))


SKOROCHENNIA = [
    (r'\bвул\.\s*', 'вулиця '), (r'\bпросп\.\s*', 'проспект '), (r'\bбульв\.\s*', 'бульвар '), (r'\bпл\.\s*', 'площа '),
    (r'\bпров\.\s*', 'провулок '), (r'\bнаб\.\s*', 'набережна '), (r'\bшосе\b', 'шосе'), (r'\bм\.\s*', 'метро '),
    (r'\bст\.\s*', 'стаття '), (r'\bКУпАП\b', 'Кодексу про адміністративні правопорушення'), (r'\bКК\b', 'Кримінального кодексу'),
    (r'\bЄДРСР\b', 'реєстру судових рішень'), (r'\bДТП\b', 'ДеТеПе'), (r'№\s*', 'номер '), (r'%', ' відсотків'),
    (r'\b1551\b', "п'ятнадцять п'ятдесят один"), (r'\bтис\.', 'тисяч'), (r'\bгрн\b', 'гривень'), (r'\s*·\s*', ', '), (r'\s*—\s*', ' — '),
]


def tekst_dlia_holosu(t: str) -> str:
    """Те, що читає голос: скорочення — словами, числа — словами (кількісні). Роки й порядкові числівники генератор
    пише словами сам («у двадцять п'ятому році»), бо відмінок залежить від речення."""
    t = str(t or '')
    for a, b in SKOROCHENNIA:
        t = re.sub(a, b, t)
    t = re.sub(r'(\d)\s+(\d{3})\b', r'\1\2', t)                 # «1 234» → 1234
    t = re.sub(r'(\d+)[–-](\d+)', lambda m: m.group(1) + ' — ' + m.group(2), t)
    t = re.sub(r'\d+', lambda m: chyslo_slovamy(int(m.group())), t)
    return re.sub(r'\s+', ' ', t).strip()


# ------------------------------------------------------------------ голоси

def _wav_z_pcm(pcm: bytes, chastota: int, kudy: Path) -> Path:
    with wave.open(str(kudy), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(chastota)
        w.writeframes(pcm)
    return kudy


def _zapyt(url: str, dani: bytes, zaholovky: dict) -> bytes:
    r = urllib.request.Request(url, data=dani, headers=zaholovky, method='POST')
    with urllib.request.urlopen(r, timeout=60) as v:
        return v.read()


def piper_model() -> Path:
    nazva = os.environ.get('MV_PIPER_MODEL', 'uk_UA-ukrainian_tts-medium')
    if Path(nazva).exists():
        return Path(nazva)
    KESH.mkdir(parents=True, exist_ok=True)
    f = KESH / f'{nazva}.onnx'
    if not f.exists():
        shliakh = PIPER_MODELI[nazva]
        for kin in ('.onnx', '.onnx.json'):
            urllib.request.urlretrieve(PIPER_URL + shliakh + kin, str(KESH / f'{nazva}{kin}'))
    return f


def holos_piper(tekst: str, kudy: Path) -> Path:
    model = piper_model()
    kfg = json.loads(Path(str(model) + '.json').read_text(encoding='utf-8'))
    mapa = kfg.get('speaker_id_map') or {}
    hol = os.environ.get('MV_PIPER_HOLOS', 'tetiana')   # найрозбірливіша за порівнянням ZAVDANNYA-94
    arg = [sys.executable, '-m', 'piper', '-m', str(model), '-f', str(kudy)]
    if mapa:
        arg += ['-s', str(mapa.get(hol, 0))]
    # Малими літерами: модель uk_UA не має фонем для великих («Неділя» звучало «Аділя», ZAVDANNYA-94 — знайдено
    # розпізнавачем мови); на інтонацію речення це не впливає — розділові знаки лишаються.
    r = subprocess.run(arg, input=tekst.lower().encode('utf-8'), capture_output=True)
    if r.returncode or not kudy.exists():
        raise RuntimeError('Piper: ' + r.stderr.decode('utf-8', 'replace')[-300:])
    return kudy


def holos_azure(tekst: str, kudy: Path) -> Path:
    kl, reg = os.environ['AZURE_SPEECH_KEY'], os.environ.get('AZURE_SPEECH_REGION', 'westeurope')
    hol = os.environ.get('MV_AZURE_HOLOS', 'uk-UA-PolinaNeural')
    ssml = (f"<speak version='1.0' xml:lang='uk-UA'><voice name='{hol}'>"
            + tekst.replace('&', 'і').replace('<', '').replace('>', '') + '</voice></speak>')
    pcm = _zapyt(f'https://{reg}.tts.speech.microsoft.com/cognitiveservices/v1', ssml.encode('utf-8'), {
        'Ocp-Apim-Subscription-Key': kl, 'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': 'riff-24khz-16bit-mono-pcm', 'User-Agent': 'moya-vulytsya-video'})
    kudy.write_bytes(pcm)
    return kudy


def holos_google(tekst: str, kudy: Path) -> Path:
    kl = os.environ['GOOGLE_TTS_KEY']
    hol = os.environ.get('MV_GOOGLE_HOLOS', 'uk-UA-Standard-A')
    tilo = json.dumps({'input': {'text': tekst}, 'voice': {'languageCode': 'uk-UA', 'name': hol},
                       'audioConfig': {'audioEncoding': 'LINEAR16', 'sampleRateHertz': 24000}}).encode('utf-8')
    v = json.loads(_zapyt(f'https://texttospeech.googleapis.com/v1/text:synthesize?key={kl}', tilo,
                          {'Content-Type': 'application/json'}))
    kudy.write_bytes(base64.b64decode(v['audioContent']))   # LINEAR16 повертається вже з заголовком WAV
    return kudy


def holos_elevenlabs(tekst: str, kudy: Path) -> Path:
    kl, hol = os.environ['ELEVENLABS_API_KEY'], os.environ['MV_ELEVENLABS_HOLOS']
    tilo = json.dumps({'text': tekst, 'model_id': os.environ.get('MV_ELEVENLABS_MODEL', 'eleven_multilingual_v2')}).encode('utf-8')
    pcm = _zapyt(f'https://api.elevenlabs.io/v1/text-to-speech/{hol}?output_format=pcm_22050', tilo,
                 {'xi-api-key': kl, 'Content-Type': 'application/json', 'Accept': 'audio/pcm'})
    return _wav_z_pcm(pcm, 22050, kudy)


HOLOSY = {'piper': holos_piper, 'azure': holos_azure, 'google': holos_google, 'elevenlabs': holos_elevenlabs}


def syntez(tekst: str, kudy: Path, rushii: str | None = None) -> Path:
    rushii = rushii or os.environ.get('MV_HOLOS', 'piper')
    if rushii not in HOLOSY:
        raise SystemExit(f'MV_HOLOS={rushii}: невідомий голос; є {", ".join(HOLOSY)}')
    return HOLOSY[rushii](tekst_dlia_holosu(tekst), kudy)


def tryvalist(f: Path) -> float:
    r = subprocess.run([ffmpeg(), '-i', str(f)], capture_output=True, text=True)
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def ffmpeg() -> str:
    f = shutil.which('ffmpeg')
    if not f:
        raise SystemExit('Немає ffmpeg')
    return f


# ------------------------------------------------------------------ музика (своя)

AKORDY = {   # частоти нот (Гц), тихі мажорно-мінорні послідовності; кожна петля — своя
    'spokii': [(220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7), (164.8, 207.7, 246.9)],
    'vechir': [(196.0, 233.1, 293.7), (155.6, 196.0, 233.1), (174.6, 220.0, 261.6), (146.8, 185.0, 220.0)],
    'misto': [(261.6, 329.6, 392.0), (220.0, 277.2, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7)],
    'ranok': [(293.7, 370.0, 440.0), (246.9, 293.7, 370.0), (196.0, 246.9, 293.7), (220.0, 277.2, 329.6)],
    'hra': [(246.9, 293.7, 370.0), (220.0, 261.6, 329.6), (196.0, 246.9, 293.7), (220.0, 277.2, 329.6)],
}


def muzyka(nazva: str, sekund: float, kudy: Path, takt: float = 4.0) -> Path:
    """Петля: акорди із синусоїд (основа + м'яка октава), плавний вступ і згасання кожного акорду, повільна «хвиля»
    гучності й тихий пульс на сильну долю. Рівень −24 dBFS (під голосом ще приглушується)."""
    akordy = AKORDY[nazva]
    n = int(sekund * CHASTOTA)
    zrazky = bytearray()
    for i in range(n):
        t = i / CHASTOTA
        k = int(t // takt) % len(akordy)
        u = (t % takt) / takt
        obvidna = min(1.0, u / 0.25) * min(1.0, (1 - u) / 0.3) ** 0.6
        x = 0.0
        for j, f in enumerate(akordy[k]):
            x += math.sin(2 * math.pi * f * t + j) * (0.55 if j else 0.7) + 0.12 * math.sin(4 * math.pi * f * t)
        x += 0.35 * math.sin(2 * math.pi * akordy[k][0] / 2 * t)                       # бас октавою нижче
        puls = 0.25 * math.exp(-((t % (takt / 4)) / 0.08)) * math.sin(2 * math.pi * akordy[k][2] * 2 * t)
        khvylia = 0.8 + 0.2 * math.sin(2 * math.pi * t / 11)
        v = (x * obvidna * 0.16 + puls * 0.05) * khvylia
        zrazky += struct.pack('<h', int(max(-1, min(1, v)) * 32767 * 0.5))
    return _wav_z_pcm(bytes(zrazky), CHASTOTA, kudy)


# ------------------------------------------------------------------ зведення

def srt_chas(s: float) -> str:
    ms = int(round(s * 1000))
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def zvesty(video: Path, vidrizky: list, kudy: Path, muz: str = 'spokii', rushii: str | None = None) -> dict:
    """video без звуку + голос кожного відрізка + музика → kudy (mp4, AAC) і kudy.srt. Повертає звіт: які репліки
    довелося пришвидшити й наскільки, які не вмістилися."""
    dovzh = tryvalist(video)
    zvit = {'replik': 0, 'pryshvydsheno': [], 'ne_vmistylos': []}
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        vkhody, filtry, myky = ['-i', str(video), '-i', str(muzyka(muz, dovzh + 1, d / 'm.wav'))], [], []
        srt = []
        for i, v in enumerate(vidrizky):
            if not v.get('holos'):
                continue
            f = syntez(v['holos'], d / f'h{i}.wav', rushii)
            l = tryvalist(f)
            pochatok = v['t0'] + min(v.get('vid', 0), 1.2) + 0.15
            mistse = v['t1'] - pochatok - 0.2
            temp = 1.0
            if l > mistse:
                temp = min(1.25, l / max(0.5, mistse))
                zvit['pryshvydsheno'].append((i, round(temp, 2)))
                if l / temp > mistse + 0.3:
                    zvit['ne_vmistylos'].append((i, round(l / temp - mistse, 1)))
            n = len(vkhody) // 2
            vkhody += ['-i', str(f)]
            filtry.append(f'[{n}:a]aresample={CHASTOTA},atempo={temp:.3f},adelay={int(pochatok * 1000)}:all=1,apad[h{n}]')
            myky.append(f'[h{n}]')
            srt.append((pochatok, pochatok + l / temp, v['holos']))
            zvit['replik'] += 1
        if myky:
            filtry.append(''.join(myky) + f'amix=inputs={len(myky)}:normalize=0:duration=longest,volume=1.0[holos]')
            filtry.append('[holos]asplit=2[hm][hs]')
            # музика: тихо, плавний вступ і кінець; під голосом приглушується (стискач від голосу)
            filtry.append(f'[1:a]atrim=0:{dovzh:.2f},afade=t=in:d=1.2,afade=t=out:st={max(0, dovzh - 2):.2f}:d=2,volume=0.55[m0]')
            filtry.append('[m0][hs]sidechaincompress=threshold=0.02:ratio=6:attack=40:release=500[m1]')
            filtry.append(f'[hm][m1]amix=inputs=2:normalize=0:duration=first,atrim=0:{dovzh:.2f},loudnorm=I=-16:TP=-1.5:LRA=11[a]')
        else:
            filtry.append(f'[1:a]atrim=0:{dovzh:.2f},afade=t=in:d=1.2,afade=t=out:st={max(0, dovzh - 2):.2f}:d=2,loudnorm=I=-20[a]')
        r = subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', *vkhody, '-filter_complex', ';'.join(filtry),
                            '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-ar', str(CHASTOTA),
                            '-shortest', '-movflags', '+faststart', str(kudy)], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError('ffmpeg (звук): ' + r.stderr[-500:])
    kudy.with_suffix('.srt').write_text(''.join(f'{i + 1}\n{srt_chas(a)} --> {srt_chas(b)}\n{t}\n\n'
                                                for i, (a, b, t) in enumerate(srt)), encoding='utf-8')
    return zvit


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('--holos', help='текст: синтезувати й записати у -o')
    a.add_argument('--muzyka', type=Path, help='тека: записати 5 петель по 40 с')
    a.add_argument('-o', type=Path, default=Path('holos.wav'))
    arg = a.parse_args()
    if arg.holos:
        print(syntez(arg.holos, arg.o), f'{tryvalist(arg.o):.1f} с')
    if arg.muzyka:
        arg.muzyka.mkdir(parents=True, exist_ok=True)
        for n in AKORDY:
            print(muzyka(n, 40, arg.muzyka / f'{n}.wav'))


if __name__ == '__main__':
    main()

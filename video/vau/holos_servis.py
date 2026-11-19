"""Зовнішній (платний) голос для роликів (ZAVDANNYA-129, MV-151): вибір — змінними середовища, ключ — лише там.

Крок 1 ZAVDANNYA-129 — лише підготовка: поки ключа немає, рушій говорить Piper (як у 127). Коли Андрій обере сервіс:

    MV_HOLOS=elevenlabs  MV_HOLOS_KLUCH=<ключ>  [MV_HOLOS_ID_CH=<голос чоловічий>]  [MV_HOLOS_ID_ZH=<голос жіночий>]
    MV_HOLOS=azure       MV_HOLOS_KLUCH=<ключ>  MV_HOLOS_REHION=westeurope  [MV_HOLOS_ID_CH=uk-UA-OstapNeural] [MV_HOLOS_ID_ZH=uk-UA-PolinaNeural]
    MV_HOLOS=teka        MV_HOLOS_TEKA=<тека з готовими .wav>   — голос, записаний у сервісі вручну: файл <sha1 tekst_dlia_servisu(текст)>.wav
    MV_HOLOS=piper       (або не задано) — безкоштовний офлайн-голос

Ключ ніколи не пишеться у файли, сценарії чи журнал. Готовий голос кешується у video/vyhid/kesh/holos/ (не в git): той самий
текст тим самим голосом вдруге не оплачується. Позначка «Голос згенеровано» (MV-150) лишається для будь-якого сервісу —
її ставить сценарій, а не цей модуль.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import urllib.request
import wave
from pathlib import Path

KESH = Path(__file__).resolve().parents[2] / 'video' / 'vyhid' / 'kesh' / 'holos'
ZHINOCHI = {'tetiana', 'lada'}
TYPOVI = {
    'elevenlabs': {'ch': 'pNInz6obpgDQGcFmaJgB', 'zh': 'XrExE9yKIg1WjnnlVkGX'},   # загальні багатомовні голоси бібліотеки
    'azure': {'ch': 'uk-UA-OstapNeural', 'zh': 'uk-UA-PolinaNeural'},
}


def servis() -> str:
    s = (os.environ.get('MV_HOLOS') or 'piper').strip().lower()
    if s not in ('piper', 'elevenlabs', 'azure', 'teka'):
        raise SystemExit(f'MV_HOLOS={s}: невідомий сервіс голосу (piper, elevenlabs, azure, teka)')
    if s in ('elevenlabs', 'azure') and not os.environ.get('MV_HOLOS_KLUCH'):
        raise SystemExit(f'MV_HOLOS={s}: немає ключа в змінній MV_HOLOS_KLUCH')
    return s


def holos_id(s: str, imia: str) -> str:
    rid = 'zh' if imia in ZHINOCHI else 'ch'
    return os.environ.get('MV_HOLOS_ID_' + rid.upper()) or TYPOVI.get(s, {}).get(rid, imia)


def tekst_dlia_servisu(t: str) -> str:
    """Платні сервіси читають великі літери й розділові знаки; числа — словами (узгодження родів робимо ми), абревіатури — вимовою."""
    from holos_tekst import ABREVIATURY, chyslo_slovamy
    t = t.replace('*', '').replace('\n', ' ').replace('«', '').replace('»', '')
    t = re.sub(r'(\d)[   ](?=\d{3}\b)', r'\1', t)
    t = re.sub(r'\d+', lambda m: chyslo_slovamy(int(m.group())), t)
    for k, v in ABREVIATURY.items():
        t = re.sub(r'(?<!\w)' + k + r'(?!\w)', v, t)
    return re.sub(r'\s+', ' ', t).strip()


def kliuch_keshu(s: str, imia: str, tekst: str, shvydkist: float) -> str:
    return hashlib.sha1(json.dumps([s, holos_id(s, imia), tekst, round(shvydkist, 3)], ensure_ascii=False).encode()).hexdigest()


def _wav_v_masyv(dani: bytes):
    import numpy as np
    with wave.open(io.BytesIO(dani)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    return x, sr


def _pcm_v_wav(pcm: bytes, sr: int) -> bytes:
    b = io.BytesIO()
    with wave.open(b, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm)
    return b.getvalue()


def _elevenlabs(tekst: str, imia: str, shvydkist: float) -> bytes:
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{holos_id("elevenlabs", imia)}?output_format=pcm_44100'
    tilo = {'text': tekst, 'model_id': os.environ.get('MV_HOLOS_MODEL', 'eleven_multilingual_v2'),
            'voice_settings': {'stability': 0.4, 'similarity_boost': 0.75, 'style': 0.35, 'speed': max(0.7, min(1.2, shvydkist))}}
    zap = urllib.request.Request(url, data=json.dumps(tilo).encode(), method='POST',
                                 headers={'xi-api-key': os.environ['MV_HOLOS_KLUCH'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(zap, timeout=60) as v:
        return _pcm_v_wav(v.read(), 44100)


def _azure(tekst: str, imia: str, shvydkist: float) -> bytes:
    from xml.sax.saxutils import escape
    reg = os.environ.get('MV_HOLOS_REHION', 'westeurope')
    tempo = f'{round((shvydkist - 1) * 100):+d}%'
    ssml = (f"<speak version='1.0' xml:lang='uk-UA'><voice name='{holos_id('azure', imia)}'>"
            f"<prosody rate='{tempo}'>{escape(tekst)}</prosody></voice></speak>")
    zap = urllib.request.Request(f'https://{reg}.tts.speech.microsoft.com/cognitiveservices/v1', data=ssml.encode(), method='POST',
                                 headers={'Ocp-Apim-Subscription-Key': os.environ['MV_HOLOS_KLUCH'],
                                          'Content-Type': 'application/ssml+xml',
                                          'X-Microsoft-OutputFormat': 'riff-44100hz-16bit-mono-pcm', 'User-Agent': 'moya-vulytsya-video'})
    with urllib.request.urlopen(zap, timeout=60) as v:
        return v.read()


def _teka(tekst: str, imia: str, shvydkist: float) -> bytes:
    teka = Path(os.environ.get('MV_HOLOS_TEKA', ''))
    f = teka / (hashlib.sha1(tekst.encode()).hexdigest() + '.wav')
    if not f.is_file():
        raise SystemExit(f'MV_HOLOS=teka: немає файлу {f.name} для «{tekst[:50]}» (sha1 tekst_dlia_servisu)')
    return f.read_bytes()


ZAPYTY = {'elevenlabs': _elevenlabs, 'azure': _azure, 'teka': _teka}


def holos(tekst: str, imia: str = 'mykyta', shvydkist: float = 1.0, zapyt=None):
    """→ (масив float −1…1, частота) зовнішнього голосу; кеш на диску. zapyt — підміна мережі (тести)."""
    s = servis()
    t = tekst_dlia_servisu(tekst)
    f = KESH / f'{s}-{kliuch_keshu(s, imia, t, shvydkist)}.wav'
    if f.is_file():
        return _wav_v_masyv(f.read_bytes())
    dani = (zapyt or ZAPYTY[s])(t, imia, shvydkist)
    KESH.mkdir(parents=True, exist_ok=True)
    f.write_bytes(dani)
    return _wav_v_masyv(dani)

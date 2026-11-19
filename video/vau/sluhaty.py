"""Перевірка звуку готового ролика (ZAVDANNYA-127): гучність кожні 0,5 с, піки, тиша, і що каже голос.

    python video/vau/sluhaty.py video/vyhid/<id>.mp4 [--holos] [--stsenarii <сценарій.json>]

--stsenarii (ZAVDANNYA-129, С11): розпізнаний голос порівнюється з текстом сценарію слово в слово; ролик не проходить,
якщо збіг < 80 % або почуто слово, схоже на лайку («пісдесят» замість «шістдесят»). Розпізнавачу дається підказка
«числа словами», інакше він пише цифри й ховає саме ту ваду, яку шукаємо.

Голос розпізнає faster-whisper (модель small, качається з huggingface.co при першому запуску) — так перевіряємо,
що синтезований голос розбірливий і каже саме те, що в сценарії.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rushii import ffmpeg  # noqa: E402


def zvuk(mp4: Path, sr=16000):
    r = subprocess.run([ffmpeg(), '-loglevel', 'error', '-i', str(mp4), '-ac', '1', '-ar', str(sr), '-f', 'wav', '-'],
                       capture_output=True, check=True)
    with wave.open(io.BytesIO(r.stdout)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768, sr


NEBEZPECHNI = re.compile(r'п[іи]с?д[еє]|п[іи]зд|х[уy]й|бля|сук[аи]|[єй]об|їба|мудак|срак', re.I)
PIDKAZKA = 'Усі числа записано словами, без цифр: шістдесят чотири, сімдесят, п’ятдесят, двісті одинадцять тисяч.'


def slova(t: str) -> list[str]:
    from holos_tekst import tekst_dlia_holosu
    return re.findall(r"[а-яєіїґ']+", tekst_dlia_holosu(t))


def pereviryty_holos(segs, S: dict) -> list[str]:
    """С11: що почув розпізнавач ↔ що в сценарії. Повертає зауваження (порожньо — гаразд)."""
    import difflib
    chuty = slova(' '.join(s.text for s in segs))
    treba = slova(' '.join(h['tekst'] for h in (S.get('zvuk') or {}).get('holos', [])))
    z = []
    for s in segs:
        if NEBEZPECHNI.search(s.text):
            z.append(f'схоже на лайку: «{s.text.strip()}» [{s.start:.1f} с]')
    if treba:
        k = difflib.SequenceMatcher(None, treba, chuty).ratio()
        if k < 0.8:
            z.append(f'голос розбірливий лише на {k:.0%} (почуто: «{" ".join(chuty)[:120]}»)')
    return z


def zvit(mp4: Path, holos=False, S: dict | None = None):
    x, sr = zvuk(mp4)
    k = sr // 2
    rms = [20 * np.log10(np.sqrt(np.mean(x[i:i + k] ** 2)) + 1e-9) for i in range(0, len(x), k)]
    pik = 20 * np.log10(np.max(np.abs(x)) + 1e-9)
    tysha = [i * 0.5 for i, r in enumerate(rms) if r < -45]
    smuha = ''.join(' ▁▂▃▄▅▆▇█'[int(np.clip((r + 50) / 50 * 8, 0, 8))] for r in rms)
    print(f'{mp4.name}: {len(x) / sr:.1f} с, пік {pik:.1f} дБ, середнє {np.mean(rms):.1f} дБ')
    print(f'  гучність /0,5 с: {smuha}')
    if tysha:
        print(f'  тиша (< −45 дБ) на: {tysha[:20]}')
    if holos:
        from faster_whisper import WhisperModel
        m = WhisperModel('small', device='cpu', compute_type='int8')
        segs, _ = m.transcribe(x.astype(np.float32), language='uk', vad_filter=True, initial_prompt=PIDKAZKA, temperature=0)
        segs = list(segs)
        for s in segs:
            print(f'  [{s.start:5.1f}–{s.end:5.1f}] {s.text.strip()}')
        if S is not None:
            z = pereviryty_holos(segs, S)
            print('  голос: ' + ('гаразд' if not z else 'ВАДА — ' + '; '.join(z)))
            return z
    return []


if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('mp4', nargs='+', type=Path)
    a.add_argument('--holos', action='store_true')
    a.add_argument('--stsenarii', type=Path, help='сценарій JSON (або тека зі сценаріями <id>.json) — перевірка С11')
    arg = a.parse_args()
    vady = 0
    for f in arg.mp4:
        S = None
        if arg.stsenarii:
            sf = arg.stsenarii / f'{f.stem}.json' if arg.stsenarii.is_dir() else arg.stsenarii
            S = json.loads(sf.read_text(encoding='utf-8'))
        vady += bool(zvit(f, arg.holos or S is not None, S))
    sys.exit(1 if vady else 0)

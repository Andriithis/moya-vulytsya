"""Перевірка звуку готового ролика (ZAVDANNYA-127): гучність кожні 0,5 с, піки, тиша, і що каже голос.

    python video/vau/sluhaty.py video/vyhid/<id>.mp4 [--holos]

Голос розпізнає faster-whisper (модель small, качається з huggingface.co при першому запуску) — так перевіряємо,
що синтезований голос розбірливий і каже саме те, що в сценарії.
"""
from __future__ import annotations

import argparse
import io
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


def zvit(mp4: Path, holos=False):
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
        segs, _ = m.transcribe(x.astype(np.float32), language='uk', vad_filter=True)
        for s in segs:
            print(f'  [{s.start:5.1f}–{s.end:5.1f}] {s.text.strip()}')


if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('mp4', nargs='+', type=Path)
    a.add_argument('--holos', action='store_true')
    arg = a.parse_args()
    for f in arg.mp4:
        zvit(f, arg.holos)

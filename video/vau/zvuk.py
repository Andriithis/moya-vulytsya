"""Звук роликів рушія «Вау» (ZAVDANNYA-127): власна музика, ефекти й голос — без чужих прав.

Усе синтезується тут, з синусоїд, пилок і шуму (numpy): жодного чужого семплу, тож немає скарг Content ID.
Голос — Piper (безкоштовний, офлайн, MIT), модель uk_UA-ukrainian_tts-medium (голоси lada, mykyta, tetiana) з
huggingface.co/rhasspy/piper-voices; шлях — MV_PIPER_MODEL або ~/.cache/mv-holosy/. Платний голос — змінною MV_HOLOS (video/vau/holos_servis.py, ZAVDANNYA-129).

Сценарій: S['zvuk'] = {
    'muzyka': {'styl': 'puls|nich|napruha|hra|epik|lofi', 'bpm': 120, 'drop': 3.0, 'stop': 6.8, 'huchnist': 1.0},
    'efekty': [{'t': 0.4, 'typ': 'pop|klik|tik|vzhukh|rizer|udar|dzvin|spov|druk|svish|bas', 'h': 1.0, 'v': 1.0}],
    'holos':  [{'t': 0.5, 'tekst': '…', 'holos': 'mykyta', 'shvydkist': 1.0}],
}
"""
from __future__ import annotations

import math
import os
import re
import wave
from pathlib import Path

import numpy as np

SR = 44100
MODEL = Path(os.environ.get('MV_PIPER_MODEL', Path.home() / '.cache' / 'mv-holosy' / 'uk_UA-ukrainian_tts-medium.onnx'))
HOLOSY = {'lada': 0, 'mykyta': 1, 'tetiana': 2}


# ------------------------------------------------------------------ основи синтезу

def tt(dur):
    return np.arange(int(dur * SR)) / SR


def sine(f, dur, ph=0.0):
    t = tt(dur)
    if callable(f):
        return np.sin(2 * np.pi * np.cumsum(f(t)) / SR + ph)
    return np.sin(2 * np.pi * f * t + ph)


def saw(f, dur, rng=None):
    t = tt(dur)
    ph = (f * t + (rng.random() if rng is not None else 0)) % 1.0
    return 2 * ph - 1


def shum(n, seed=0):
    return np.random.default_rng(seed).standard_normal(n)


def lp(x, fc):
    """Однополюсний фільтр нижніх частот (fc — число або масив частот у часі)."""
    fc = np.broadcast_to(np.asarray(fc, dtype=float), x.shape)
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    # петля в numpy повільна; для довгих сигналів — блоками з постійним коефіцієнтом
    if np.all(a == a.flat[0]):
        from scipy.signal import lfilter
        return lfilter([1 - a.flat[0]], [1, -a.flat[0]], x)
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def hp(x, fc):
    return x - lp(x, fc)


def bp(x, f1, f2):
    from scipy.signal import butter, sosfilt
    sos = butter(2, [f1, f2], btype='band', fs=SR, output='sos')
    return sosfilt(sos, x)


def lp2(x, fc, q=2):
    from scipy.signal import butter, sosfilt
    sos = butter(q, fc, btype='low', fs=SR, output='sos')
    return sosfilt(sos, x)


def obvidna(n, a=0.005, r=0.1, sustain=None):
    """Проста обвідна: атака a, експоненційне згасання r."""
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / max(r, 1e-4))
    return e


def nota(n):  # MIDI → Гц
    return 440.0 * 2 ** ((n - 69) / 12)


# ------------------------------------------------------------------ ефекти (кожен — коротка функція, детермінована)

def e_pop(h=1.0, seed=0):
    d = 0.16
    f = lambda t: 260 * h + 900 * h * np.exp(-t * 45)
    x = sine(f, d) * obvidna(int(d * SR), 0.002, 0.045)
    x += 0.25 * hp(shum(len(x), seed), 3000) * obvidna(len(x), 0.0005, 0.006)
    return x * 0.9


def e_klik(h=1.0, seed=0):
    d = 0.05
    x = hp(shum(int(d * SR), seed), 1500 * h) * obvidna(int(d * SR), 0.0003, 0.008)
    x += 0.5 * sine(2400 * h, d) * obvidna(int(d * SR), 0.0005, 0.01)
    return x * 0.7


def e_tik(h=1.0, seed=0):
    d = 0.09
    x = (sine(1750 * h, d) + 0.5 * sine(2900 * h, d)) * obvidna(int(d * SR), 0.0005, 0.018)
    return x * 0.55


def e_vzhukh(h=1.0, seed=0, d=0.55):
    n = int(d * SR)
    t = np.arange(n) / SR
    fc = 300 + 5200 * np.sin(np.pi * t / d) ** 2 * h
    x = lp_change(shum(n, seed), fc)
    x *= np.sin(np.pi * t / d) ** 1.5
    return x * 0.8


def lp_change(x, fc, blok=256):
    """Фільтр зі змінною частотою — блоками (швидко й достатньо плавно)."""
    from scipy.signal import butter, sosfilt, sosfilt_zi
    y = np.zeros_like(x)
    zi = None
    for i in range(0, len(x), blok):
        f = float(np.clip(fc[min(i, len(fc) - 1)], 40, SR / 2 - 100))
        sos = butter(2, f, btype='low', fs=SR, output='sos')
        if zi is None:
            zi = sosfilt_zi(sos) * 0
        y[i:i + blok], zi = sosfilt(sos, x[i:i + blok], zi=zi)
    return y


def e_svish(h=1.0, seed=0):
    return e_vzhukh(h * 1.3, seed, 0.28) * 0.8


def e_rizer(h=1.0, seed=0, d=2.0):
    n = int(d * SR)
    t = np.arange(n) / SR
    fc = 200 + 7000 * (t / d) ** 2
    x = lp_change(shum(n, seed), fc) * 0.6
    f = lambda tt_: 110 * h * 2 ** (2.5 * tt_ / d)
    x += 0.25 * np.tanh(2 * np.sin(2 * np.pi * np.cumsum(f(t)) / SR))
    x *= (t / d) ** 2
    return x


def e_udar(h=1.0, seed=0):
    d = 1.6
    n = int(d * SR)
    f = lambda t: 38 * h + 70 * h * np.exp(-t * 18)
    x = sine(f, d) * obvidna(n, 0.002, 0.55) * 1.3
    x += 0.6 * lp2(shum(n, seed), 900) * obvidna(n, 0.001, 0.09)
    x += 0.25 * hp(shum(n, seed + 1), 4000) * obvidna(n, 0.001, 0.25)
    return np.tanh(x * 1.6) * 0.9


def e_bas(h=1.0, seed=0):
    d = 0.9
    f = lambda t: 50 * h + 40 * h * np.exp(-t * 10)
    return np.tanh(1.8 * sine(f, d) * obvidna(int(d * SR), 0.003, 0.3)) * 0.9


def e_dzvin(h=1.0, seed=0):
    d = 1.4
    n = int(d * SR)
    t = np.arange(n) / SR
    f0 = 1046.5 * h
    mod = 2.2 * np.exp(-t * 4) * np.sin(2 * np.pi * f0 * 1.4 * t)
    x = np.sin(2 * np.pi * f0 * t + mod) * obvidna(n, 0.002, 0.45)
    x += 0.3 * np.sin(2 * np.pi * f0 * 2.01 * t) * obvidna(n, 0.002, 0.2)
    return x * 0.5


def e_spov(h=1.0, seed=0):
    """Власний дзвіночок сповіщення: дві ноти вгору (не схожий на звуки телефонів)."""
    a = e_dzvin(h * 0.84, seed)[: int(0.5 * SR)]
    b = e_dzvin(h * 1.26, seed)
    x = np.zeros(int(0.12 * SR) + len(b))
    x[:len(a)] += a
    x[int(0.12 * SR):int(0.12 * SR) + len(b)] += b
    return x * 0.8


def e_druk(h=1.0, seed=0):
    return e_klik(h * 0.8, seed) * 0.6


def e_hlych(h=1.0, seed=0):
    d = 0.3
    n = int(d * SR)
    x = np.sign(np.sin(2 * np.pi * 180 * h * tt(d))) * 0.3 + 0.5 * shum(n, seed)
    x *= (np.random.default_rng(seed).random(n // 400 + 1).repeat(400)[:n] > 0.45)
    return lp2(x, 5000) * obvidna(n, 0.001, 0.12) * 0.6


def e_kasa(h=1.0, seed=0):
    x = e_dzvin(h * 1.5, seed) * 0.7
    k = e_klik(h, seed)
    x[:len(k)] += k
    return x


EFEKTY = {'pop': e_pop, 'klik': e_klik, 'tik': e_tik, 'vzhukh': e_vzhukh, 'svish': e_svish, 'rizer': e_rizer,
          'udar': e_udar, 'bas': e_bas, 'dzvin': e_dzvin, 'spov': e_spov, 'druk': e_druk, 'hlych': e_hlych, 'kasa': e_kasa}


# ------------------------------------------------------------------ музика (власні петлі, акорди — загальні звороти)

STYLI = {
    #        bpm  тональність  акорди (ступені мінору)           що звучить
    'puls':   (122, 57, [0, 8, 3, 10], {'kik', 'het', 'bas', 'pad', 'klep', 'arp'}),
    'nich':   (84, 52, [0, 5, 8, 7], {'pad', 'iskry', 'sub'}),
    'napruha': (100, 50, [0, 0, 1, 0], {'dron', 'tik', 'bas', 'puls'}),
    'hra':    (132, 60, [0, 5, 7, 3], {'kik', 'het', 'arp', 'pad', 'klep'}),
    'epik':   (90, 50, [0, 8, 10, 7], {'tom', 'pad', 'sub', 'dron'}),
    'lofi':   (78, 55, [0, 3, 8, 7], {'kik_m', 'het', 'klavishi', 'sub'}),
}
MINOR = [0, 2, 3, 5, 7, 8, 10]


def akord(korin, stupin):
    """Мінорний лад: акорд на ступені (півтонах від кореня) — тризвук із ладу."""
    base = korin + stupin
    tretia = 3 if stupin in (0, 5, 7) else 4
    if stupin == 1:
        tretia = 3
    return [base, base + tretia, base + 7, base + 12]


def muzyka(styl: str, dur: float, bpm=None, drop=None, stop=None, seed=7):
    bpm0, korin, prohres, sklad = STYLI.get(styl, STYLI['puls'])
    bpm = bpm or bpm0
    rng = np.random.default_rng(seed)
    n = int(dur * SR) + SR
    out = np.zeros(n)
    beat = 60 / bpm
    takt = beat * 4
    pump = np.ones(n)

    def dodaty(x, t0, g=1.0):
        i = int(t0 * SR)
        if i >= n:
            return
        j = min(n, i + len(x))
        out[i:j] += g * x[:j - i]

    tk = 0
    t = 0.0
    while t < dur + takt:
        ak = akord(korin, prohres[tk % len(prohres)])
        pochatok_dropu = drop is not None and t < drop
        if 'pad' in sklad or 'klavishi' in sklad:
            d = takt
            x = np.zeros(int(d * SR))
            for m in ak[:3]:
                for det in (-0.08, 0.0, 0.08):
                    x += saw(nota(m + 12 + det), d, rng) * 0.08
            fc = 900 if styl != 'lofi' else 1400
            x = lp2(x, fc * (0.5 if pochatok_dropu else 1.0))
            e = np.minimum(1, tt(d) / 0.25) * np.minimum(1, (d - tt(d)) / 0.25)
            if 'klavishi' in sklad:
                x = np.zeros(int(d * SR))
                for k_, m in enumerate(ak):
                    tn = k_ * beat * 0.5
                    s = (sine(nota(m + 12), d) + 0.3 * sine(nota(m + 24), d)) * obvidna(int(d * SR), 0.01, 0.9)
                    s = np.roll(s, int(tn * SR)); s[:int(tn * SR)] = 0
                    x += s * 0.12
                e = 1
            dodaty(x * e, t, 0.9)
        if 'dron' in sklad:
            x = (saw(nota(korin - 12), takt, rng) + saw(nota(korin - 12.07), takt, rng)) * 0.12
            dodaty(lp2(x, 300) * 1.2, t)
        if 'sub' in sklad:
            dodaty(sine(nota(ak[0] - 12), takt) * 0.22 * np.minimum(1, tt(takt) / 0.1), t)
        if 'iskry' in sklad:
            for _ in range(3):
                m = korin + 24 + MINOR[rng.integers(0, 7)]
                d = 1.2
                dodaty(sine(nota(m), d) * obvidna(int(d * SR), 0.005, 0.4) * 0.06, t + rng.integers(0, 8) * beat / 2)
        for b in range(8):  # восьмі
            tb = t + b * beat / 2
            if tb > dur + 0.5:
                break
            pered = drop is not None and tb < drop
            if b % 2 == 0 and ('kik' in sklad or 'kik_m' in sklad) and not pered:
                d = 0.32
                f = lambda tt_: 45 + 110 * np.exp(-tt_ * 30)
                k = sine(f, d) * obvidna(int(d * SR), 0.001, 0.12) * (0.85 if 'kik' in sklad else 0.55)
                dodaty(np.tanh(k * 2) * 0.7, tb)
                i = int(tb * SR)
                L = int(0.22 * SR)
                if i + L < n:
                    pump[i:i + L] = np.minimum(pump[i:i + L], 0.45 + 0.55 * (np.arange(L) / L) ** 0.6)
            if 'het' in sklad and not pered and (b % 2 == 1 or styl == 'hra'):
                d = 0.05
                dodaty(hp(shum(int(d * SR), int(tb * 1000)), 7000) * obvidna(int(d * SR), 0.0005, 0.015) * 0.18, tb)
            if 'klep' in sklad and not pered and b in (2, 6):
                d = 0.2
                x = bp(shum(int(d * SR), int(tb * 77)), 900, 4000) * obvidna(int(d * SR), 0.001, 0.05) * 0.5
                dodaty(x, tb)
            if 'tom' in sklad and b in (0, 3, 6) and not pered:
                d = 0.6
                f = lambda tt_: 70 + 60 * np.exp(-tt_ * 12)
                dodaty(np.tanh(sine(f, d) * obvidna(int(d * SR), 0.002, 0.22) * 2) * 0.55, tb)
            if 'bas' in sklad and not (pered and styl != 'napruha'):
                d = beat / 2 * 0.9
                m = ak[0] - 12 if styl != 'napruha' else korin - 12 + (1 if b in (3, 7) else 0)
                x = lp2(saw(nota(m), d, rng) + 0.5 * sine(nota(m), d), 420) * obvidna(int(d * SR), 0.004, 0.18)
                dodaty(x * 0.28, tb)
            if 'tik' in sklad:
                dodaty(e_tik(1.0 if b % 2 == 0 else 0.8) * 0.25, tb)
            if 'puls' in sklad and b % 4 == 0:
                dodaty(e_bas(1.0) * 0.35, tb)
            if 'arp' in sklad and not pered:
                m = ak[[0, 1, 2, 3, 2, 1, 0, 2][b]] + 24
                d = beat / 2
                x = (np.sign(sine(nota(m), d)) * 0.3 + sine(nota(m), d)) * obvidna(int(d * SR), 0.002, 0.07)
                dodaty(lp2(x, 3200) * 0.09, tb)
        t += takt
        tk += 1
    out = out[: int(dur * SR) + SR] * pump[: len(out)]
    if stop is not None:   # обрив: «зупинка плівки» за 0,35 с
        i = int(stop * SR)
        L = int(0.35 * SR)
        if i < len(out):
            seg = out[i:i + L * 2].copy()
            idx = np.cumsum(np.linspace(1, 0.05, L))
            idx = np.clip(idx.astype(int), 0, len(seg) - 1)
            hvist = seg[idx] * np.linspace(1, 0, L)
            out[i:] = 0
            out[i:i + len(hvist)] = hvist
    return out[: int(dur * SR)]


# ------------------------------------------------------------------ голос

from holos_tekst import DOZVOLENI, chyslo_slovamy, tekst_dlia_holosu  # noqa: E402,F401


_PIPER = None


def _piper(tekst: str, imia: str, shvydkist: float):
    global _PIPER
    from piper import PiperVoice, SynthesisConfig
    if _PIPER is None:
        _PIPER = PiperVoice.load(str(MODEL))
    import io
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        _PIPER.synthesize_wav(tekst_dlia_holosu(tekst), w,
                              syn_config=SynthesisConfig(speaker_id=HOLOSY.get(imia, 1), length_scale=1.0 / shvydkist,
                                                         noise_scale=0.6, noise_w_scale=0.7))
    buf.seek(0)
    with wave.open(buf, 'rb') as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768, w.getframerate()


def holos(tekst: str, imia='mykyta', shvydkist=1.0) -> np.ndarray:
    """Голос: Piper або зовнішній сервіс за змінною MV_HOLOS (ZAVDANNYA-129, holos_servis.py); обробка — однакова."""
    import holos_servis
    if holos_servis.servis() == 'piper':
        x, sr = _piper(tekst, imia, shvydkist)
    else:
        x, sr = holos_servis.holos(tekst, imia, shvydkist)
    from math import gcd
    from scipy.signal import resample_poly
    if sr != SR:
        g = gcd(SR, sr)
        x = resample_poly(x, SR // g, sr // g)
    x = hp(x, 90)
    # легка «присутність»: трохи підняти 2–5 кГц і стиснути піки — голос читається поверх музики
    x = x + 0.35 * bp(x, 2000, 5000)
    pik = np.max(np.abs(x)) or 1
    x = np.tanh(1.6 * x / pik) / np.tanh(1.6)
    return x * 0.85


# ------------------------------------------------------------------ зведення

def zibraty(S: dict, kudy: Path) -> dict:
    Z = S.get('zvuk') or {}
    dur = float(S['tryvalist'])
    n = int(dur * SR)
    mus = np.zeros(n)
    sfx = np.zeros(n)
    voc = np.zeros(n)
    m = Z.get('muzyka')
    if m:
        x = muzyka(m.get('styl', 'puls'), dur, m.get('bpm'), m.get('drop'), m.get('stop'), m.get('seed', 7))
        mus[:len(x)] += x[:n] * m.get('huchnist', 1.0)
        if m.get('vid'):
            mus[: int(m['vid'] * SR)] = 0
    for i, e in enumerate(Z.get('efekty', [])):
        f = EFEKTY.get(e['typ'])
        if not f:
            continue
        x = f(e.get('h', 1.0), i)
        j = int(e['t'] * SR)
        if j >= n:
            continue
        if j < 0:                       # ефект, що почався «до нуля», — лише його хвіст
            x, j = x[-j:], 0
            if not len(x):
                continue
        k = min(n, j + len(x))
        sfx[j:k] += x[:k - j] * e.get('v', 1.0)
    srt = []
    for i, h in enumerate(Z.get('holos', [])):
        x = holos(h['tekst'], h.get('holos', 'mykyta'), h.get('shvydkist', 1.0))
        j = int(h['t'] * SR)
        k = min(n, j + len(x))
        voc[j:k] += x[:k - j] * h.get('v', 1.0)
        srt.append((h['t'], h['t'] + len(x) / SR, h['tekst'].replace('*', '')))
    # голос приглушує музику (−10 дБ), плавно
    if np.any(voc):
        env = lp2(np.abs(voc), 6) * 6
        env = np.clip(env / (np.max(env) or 1) * 1.6, 0, 1)
        mus *= 1 - 0.68 * env
    mix = 0.55 * mus + 0.75 * sfx + 1.0 * voc
    pik = np.max(np.abs(mix)) or 1
    mix = np.tanh(1.2 * mix / pik) / np.tanh(1.2) * 0.95
    st = np.stack([mix, mix], 1)
    pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(kudy), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return {'srt': _srt(srt), 'repliky': len(srt), 'holos_kinets': max((b for _, b, _ in srt), default=0)}


def _srt(rows):
    def ts(x):
        h, r = divmod(x, 3600); m, s = divmod(r, 60)
        return f'{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}'
    return '\n'.join(f'{i}\n{ts(a)} --> {ts(b)}\n{t}\n' for i, (a, b, t) in enumerate(rows, 1))


def tryvalist_holosu(tekst, imia='mykyta', shvydkist=1.0) -> float:
    return len(holos(tekst, imia, shvydkist)) / SR

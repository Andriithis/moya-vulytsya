"""Перетворення голосу Андрія (ZAVDANNYA-148, MV-156): запис з телефона → чоловічий або жіночий голос, якого немає в живої людини.

    python video/holos/holos.py pidhotuvaty                          # раз: моделі й два голоси (≈ 2 ГБ, 15–30 хв)
    python video/holos/holos.py peretvoryty <файли або тека> [--holos cholovichyi|zhinochyi|oba] [--rushii knn|openvoice]
                                            [--vykhid video/vyhid/holos] [--teksty teksty.tsv]

Кроки для кожного файлу (m4a, ogg, opus, mp3, wav — усе, що читає ffmpeg):
  1) читання ffmpeg → моно; 2) очищення: зріз гулу нижче 70 Гц, м'яке шумозаглушення (noisereduce), обрізка тиші
  на краях; 3) перетворення голосу (kNN-VC — типово, OpenVoice V2 — запасний); 4) вирівнювання гучності до −16 LUFS, пік
  не вище −1,5 дБ; 5) wav 44,1 кГц 16 біт моно — `<вихід>/<голос>/<ім'я файлу>.wav`.
З `--teksty` (рядки «ім'я_файлу<TAB>текст репліки») готовий голос ще й кладеться як `<вихід>/teka-<голос>/<sha1>.wav` —
рушій роликів бере його без змін у сценарії: `MV_HOLOS=teka MV_HOLOS_TEKA=<вихід>/teka-<голос>` (video/vau/holos_servis.py).

Голоси — суміш десятків дикторів однієї статі з українського набору «Голос Америки» (speech-uk/voice-of-america, CC BY 4.0):
жодної живої людини не імітуємо. Моделі — лише з дозволом на комерційне використання (MIT): kNN-VC (github.com/bshall/knn-vc) і OpenVoice V2
(github.com/myshell-ai/OpenVoice). Дослідження — video/holos/DOSLIDZHENNYA.md. Модель, навчена на некомерційних даних
(Seed-VC), і so-vits-svc сюди не додаються (перевірка — tests/test_holos.py).

Важкі бібліотеки (torch, librosa, …) імпортуються лише в момент роботи: тести перевіряють легку частину без них.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

KORIN = Path(__file__).resolve().parents[2]
MODELI = Path(os.environ.get('MV_HOLOS_MODELI') or Path.home() / '.cache' / 'mv-holos')

# Коди й ваги — закріплені версії (MIT). Інших рушіїв не додавати без перевірки ліцензії ваг і даних навчання.
RUSHII = {
    'knn': {
        'kod': ('https://github.com/bshall/knn-vc', 'c616845c4e309e24d5927f15adbdf277a3d65358'),
        'vagy': ['https://github.com/bshall/knn-vc/releases/download/v0.1/WavLM-Large.pt',
                 'https://github.com/bshall/knn-vc/releases/download/v0.1/prematch_g_02500000.pt'],
        'licenziia': 'MIT',
    },
    'openvoice': {
        'kod': ('https://github.com/myshell-ai/OpenVoice', '74a1d147b17a8c3092dd5430504bd83ef6c7eb23'),
        'vagy': ['hf:myshell-ai/OpenVoiceV2:converter/config.json', 'hf:myshell-ai/OpenVoiceV2:converter/checkpoint.pth'],
        'licenziia': 'MIT',
    },
}
TYPOVYI_RUSHII = 'knn'

# Голоси — суміш десятків дикторів «Голосу Америки» українською (speech-uk/voice-of-america, CC BY 4.0; той самий набір
# у форматі opus — speech-uk/voa-opus). Беремо 4 перші файли набору, перемішуємо (seed 0) і відбираємо шматки 3–15 с без
# латиниці в тексті, з тихим тлом (різниця гучних і тихих кадрів ≥ 25 дБ) і з голосом у ≥ 35 % кадрів. Стать — за висотою
# голосу (медіана основного тону): < 150 Гц — до чоловічого, > 180 Гц — до жіночого, між ними — не беремо. По 12 хв на голос.
# Перетворення бере кожні 20 мс звуку з цієї суміші, тож голос не належить жодній одній людині.
# Англійський набір LibriTTS-R (CC BY 4.0) пробували першим: голос виходив схожішим на вихідний і гірше вимовляв українське
# (README, «Як вибирали»).
NABIR = {'repo': 'speech-uk/voa-opus', 'fayly': ['0.parquet', '1.parquet', '2.parquet', '3.parquet'],
         'licenziia': 'CC BY 4.0',
         'dzherelo': 'Voice of America for Ukrainian, Speech-UK initiative and Yehor Smoliakov, 2025, '
                     'https://huggingface.co/datasets/speech-uk/voice-of-america (doi 10.57967/hf/6430)'}
HOLOSY = {'cholovichyi': (0, 150), 'zhinochyi': (180, 1000)}       # межі медіани основного тону, Гц
HVYLYN_NA_HOLOS = 12
FORMATY = {'.m4a', '.ogg', '.opus', '.mp3', '.wav', '.flac', '.aac', '.amr', '.3gp', '.webm', '.mp4'}
LUFS = -16.0
PIK_DB = -1.5
SR_VYKHID = 44100

# Очищення: гул і «бубніння» нижче 70 Гц геть (ffmpeg), потім м'яке шумозаглушення noisereduce (MIT). Сильніше (ffmpeg afftdn,
# noisereduce 0,8, зріз верху) на тесті псувало голос: схожість з чистим записом падала з 0,80 до 0,55, помилки розпізнавання
# росли — видно в README, «Очищення».
FILTR_OCHYSHCHENNIA = 'highpass=f=70'
SYLA_SHUMOZAHLUSHENNIA = 0.5


# ------------------------------------------------------------------ легка частина (перевіряється в CI без torch)

def imia_vykhodu(vkhid: Path) -> str:
    """'R01 Гачок.m4a' → 'r01-гачок.wav': без пробілів і розширення, малими літерами."""
    s = re.sub(r'[^\w\-]+', '-', vkhid.stem.strip().lower(), flags=re.UNICODE).strip('-')
    return (s or 'zapys') + '.wav'


def zibraty_vkhid(shliakhy: list[str]) -> list[Path]:
    """Файли й теки → відсортований список записів, які читає ffmpeg."""
    vse: list[Path] = []
    for s in shliakhy:
        p = Path(s)
        if p.is_dir():
            vse += sorted(f for f in p.iterdir() if f.suffix.lower() in FORMATY)
        elif p.is_file():
            vse.append(p)
        else:
            raise SystemExit(f'немає файлу або теки: {p}')
    if not vse:
        raise SystemExit('немає жодного запису (m4a, ogg, mp3, wav…)')
    return vse


def chytaty_teksty(f: Path) -> dict[str, str]:
    """teksty.tsv: «ім'я_файлу<TAB>текст». Ім'я — як у запису (з розширенням чи без). Рядки з # — коментарі."""
    t = {}
    for i, riadok in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
        if not riadok.strip() or riadok.lstrip().startswith('#'):
            continue
        if '\t' not in riadok:
            raise SystemExit(f'{f}:{i}: немає табуляції між іменем файлу і текстом')
        imia, tekst = riadok.split('\t', 1)
        t[Path(imia.strip()).stem.lower()] = tekst.strip()
    return t


def imia_teky(tekst: str) -> str:
    """Ім'я файлу, яке шукає рушій роликів у режимі MV_HOLOS=teka (той самий sha1, що в video/vau/holos_servis.py)."""
    sys.path.insert(0, str(KORIN / 'video' / 'vau'))
    from holos_servis import tekst_dlia_servisu
    return hashlib.sha1(tekst_dlia_servisu(tekst).encode()).hexdigest() + '.wav'


def holosy_z_arg(a: str) -> list[str]:
    if a == 'oba':
        return list(HOLOSY)
    if a not in HOLOSY:
        raise SystemExit(f'--holos {a}: є cholovichyi, zhinochyi, oba')
    return [a]


def ffmpeg() -> str:
    f = shutil.which('ffmpeg')
    if f:
        return f
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise SystemExit('немає ffmpeg: встановіть ffmpeg або pip install imageio-ffmpeg')


# ------------------------------------------------------------------ звук

def chytaty(f: Path, sr: int, filtr: str | None = None):
    """Будь-який запис → моно float32 з частотою sr (ffmpeg)."""
    import numpy as np
    kom = [ffmpeg(), '-v', 'error', '-i', str(f), '-ac', '1', '-ar', str(sr)]
    if filtr:
        kom += ['-af', filtr]
    kom += ['-f', 'f32le', '-']
    return np.frombuffer(subprocess.run(kom, check=True, capture_output=True).stdout, dtype=np.float32).copy()


def ochystyty(f: Path, sr: int = 48000):
    """Очищення: ffmpeg (гул) → noisereduce (рівний шум кімнати, вулиці) → обрізка тиші на краях (лишаємо 0,15 с)."""
    import numpy as np
    x = chytaty(f, sr, FILTR_OCHYSHCHENNIA)
    try:
        import noisereduce
        x = noisereduce.reduce_noise(y=x, sr=sr, stationary=True, prop_decrease=SYLA_SHUMOZAHLUSHENNIA).astype(np.float32)
    except ImportError:
        print('  (noisereduce не встановлено — лише ffmpeg)')
    ramka = int(0.02 * sr)
    n = len(x) // ramka
    if n:
        e = np.sqrt((x[: n * ramka].reshape(n, ramka) ** 2).mean(1) + 1e-12)
        porih = max(e.max() * 10 ** (-40 / 20), np.percentile(e, 10) * 3)
        hol = np.nonzero(e > porih)[0]
        if len(hol):
            z = max(0, hol[0] * ramka - int(0.15 * sr))
            k = min(len(x), (hol[-1] + 1) * ramka + int(0.15 * sr))
            x = x[z:k]
    return x, sr


def peresempl(x, sr: int, nove: int):
    if sr == nove:
        return x
    from math import gcd
    from scipy.signal import resample_poly
    g = gcd(sr, nove)
    return resample_poly(x, nove // g, sr // g).astype('float32')


def vyrivniaty(x, sr: int):
    """Гучність −16 LUFS (ITU-R BS.1770, pyloudnorm), потім м'яке обмеження піку до −1,5 дБ."""
    import numpy as np
    import pyloudnorm
    x = x.astype(np.float64)
    if len(x) > sr * 0.5:
        l = pyloudnorm.Meter(sr).integrated_loudness(x)
        if np.isfinite(l):
            x = x * 10 ** ((LUFS - l) / 20)
    pik = 10 ** (PIK_DB / 20)
    nad = np.abs(x) > pik * 0.8
    if nad.any():                        # м'яке коліно: до 80 % піку — без змін, вище — tanh до межі
        p0 = pik * 0.8
        x[nad] = np.sign(x[nad]) * (p0 + (pik - p0) * np.tanh((np.abs(x[nad]) - p0) / (pik - p0)))
    # 15 мс наростання й згасання — без клацань на краях
    f = min(len(x) // 2, int(0.015 * sr))
    if f:
        v = np.linspace(0, 1, f)
        x[:f] *= v
        x[-f:] *= v[::-1]
    return x


def zapysaty(f: Path, x, sr: int):
    import numpy as np
    import soundfile as sf
    f.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(f), np.clip(x, -1, 1), sr, subtype='PCM_16')


# ------------------------------------------------------------------ рушії

def _kod(rushii: str) -> Path:
    url, kom = RUSHII[rushii]['kod']
    d = MODELI / 'kod' / rushii
    if not (d / '.git').is_dir():
        d.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '-q', url, str(d)], check=True)
    subprocess.run(['git', '-C', str(d), 'checkout', '-q', kom], check=True)
    return d


def _vaha(dzherelo: str) -> Path:
    if dzherelo.startswith('hf:'):
        _, repo, imia = dzherelo.split(':', 2)
        from huggingface_hub import hf_hub_download
        return Path(hf_hub_download(repo, imia, local_dir=str(MODELI / 'vagy' / repo.replace('/', '__'))))
    f = MODELI / 'vagy' / dzherelo.rsplit('/', 1)[1]
    if not f.is_file():
        import urllib.request
        f.parent.mkdir(parents=True, exist_ok=True)
        print(f'  завантажую {dzherelo}')
        urllib.request.urlretrieve(dzherelo, f.with_suffix('.chastkovo'))
        f.with_suffix('.chastkovo').rename(f)
    return f


def _potoky():
    import torch
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    return torch


class Knn:
    """kNN-VC: кожен кадр запису (20 мс) замінюється середнім з 4 найближчих кадрів голосу-суміші → у виході немає кадрів
    Андрія, лише чужі. Без навчання; на процесорі."""
    SR = 16000

    def __init__(self):
        torch = _potoky()
        d = _kod('knn')
        sys.path.insert(0, str(d))
        from wavlm.WavLM import WavLM, WavLMConfig
        from hifigan.models import Generator
        from hifigan.utils import AttrDict
        from matcher import KNeighborsVC
        wl, hg = (_vaha(u) for u in RUSHII['knn']['vagy'])
        cp = torch.load(wl, map_location='cpu', weights_only=False)
        wavlm = WavLM(WavLMConfig(cp['cfg']))
        wavlm.load_state_dict(cp['model'])
        wavlm.eval()
        h = AttrDict(json.loads((d / 'hifigan' / 'config_v1_wavlm.json').read_text()))
        gen = Generator(h)
        gen.load_state_dict(torch.load(hg, map_location='cpu', weights_only=False)['generator'])
        gen.eval()
        gen.remove_weight_norm()
        self.torch = torch
        self.vc = KNeighborsVC(wavlm, gen, h, 'cpu')
        self.nabory = {}

    def holos(self, imia: str):
        if imia not in self.nabory:
            f = MODELI / 'holosy' / f'knn-{imia}.pt'
            if not f.is_file():
                raise SystemExit(f'немає голосу {f}: спершу python video/holos/holos.py pidhotuvaty')
            self.nabory[imia] = self.torch.load(f).float()
        return self.nabory[imia]

    def oznaky(self, x):
        """Ознаки WavLM (шар 6) шматками по 20 с: увага WavLM на 5 хв звуку зайняла б десятки ГБ пам'яті."""
        torch = self.torch
        sh = 20 * self.SR
        chastyny = [x[i:i + sh] for i in range(0, len(x), sh)]
        if len(chastyny) > 1 and len(chastyny[-1]) < self.SR:      # хвіст коротший за 1 с — до попереднього шматка
            import numpy as np
            khvist = chastyny.pop()
            chastyny[-1] = np.concatenate([chastyny[-1], khvist])
        with torch.inference_mode():
            return torch.cat([self.vc.get_features(torch.as_tensor(c, dtype=torch.float32)[None]) for c in chastyny])

    def nabir(self, wavs: list[Path]):
        """Ознаки всіх записів голосу-суміші — float16, щоб файл був удвічі меншим."""
        import soundfile as sf
        vse = []
        for w in wavs:
            x, sr = sf.read(str(w), dtype='float32')
            vse.append(self.oznaky(peresempl(x, sr, self.SR)))
        return self.torch.cat(vse).half()

    def peretvoryty(self, x, sr: int, imia: str):
        torch = self.torch
        x = peresempl(x, sr, self.SR)
        q = self.oznaky(x)
        with torch.inference_mode():
            y = self.vc.match(q, self.holos(imia), topk=4, tgt_loudness_db=None)
        return y.cpu().numpy(), self.SR


class OpenVoice:
    """OpenVoice V2: міняє «відбиток тембру» запису на усереднений відбиток п'яти дикторів. Швидкий; ритм і інтонація лишаються."""

    def __init__(self):
        torch = _potoky()
        d = _kod('openvoice')
        sys.path.insert(0, str(d))
        import types
        tekst = types.ModuleType('openvoice.text')        # текстова частина (китайська, англійська) для перетворення не потрібна
        tekst.text_to_sequence = None
        sys.modules['openvoice.text'] = tekst
        from openvoice.api import OpenVoiceBaseClass, ToneColorConverter
        cfg, ckpt = (_vaha(u) for u in RUSHII['openvoice']['vagy'])
        # без водяного знака wavmark: його конструктор у цій версії не приймає enable_watermark, тож збираємо вручну
        self.tc = ToneColorConverter.__new__(ToneColorConverter)
        OpenVoiceBaseClass.__init__(self.tc, str(cfg), device='cpu')
        self.tc.watermark_model = None
        self.tc.version = getattr(self.tc.hps, '_version_', 'v1')
        self.tc.load_ckpt(str(ckpt))
        self.torch = torch
        self.SR = self.tc.hps.data.sampling_rate
        self.vlasnyi = None

    def vidbytok(self, wavs: list[Path]):
        return self.tc.extract_se([str(w) for w in wavs])

    def vidbytok_sumishi(self, f: Path):
        """Відбиток тембру суміші: середнє відбитків шматків по 10 с (увесь файл за раз не влазить у пам'ять)."""
        import tempfile
        import soundfile as sf
        x, sr = sf.read(str(f), dtype='float32')
        with tempfile.TemporaryDirectory() as t:
            fs = []
            for i in range(0, len(x) - sr * 3, sr * 10):
                fs.append(Path(t) / f'{i}.wav')
                sf.write(str(fs[-1]), x[i:i + sr * 10], sr)
            return self.vidbytok(fs)

    def holos(self, imia: str):
        f = MODELI / 'holosy' / f'openvoice-{imia}.pt'
        if not f.is_file():
            raise SystemExit(f'немає голосу {f}: спершу python video/holos/holos.py pidhotuvaty')
        return self.torch.load(f)

    def peretvoryty(self, x, sr: int, imia: str):
        import tempfile
        import soundfile as sf
        x = peresempl(x, sr, self.SR)
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / 'a.wav'
            sf.write(str(f), x, self.SR)
            if self.vlasnyi is None:
                raise RuntimeError('спершу vlasnyi_vidbytok()')
            y = self.tc.convert(str(f), self.vlasnyi, self.holos(imia), tau=0.3)
        return y, self.SR

    def vlasnyi_vidbytok(self, x_list, sr: int):
        """Відбиток голосу Андрія — з усіх записів партії разом (точніше, ніж з одного)."""
        import tempfile
        import soundfile as sf
        with tempfile.TemporaryDirectory() as t:
            fs = []
            for i, x in enumerate(x_list):
                f = Path(t) / f'{i}.wav'
                sf.write(str(f), peresempl(x, sr, self.SR), self.SR)
                fs.append(f)
            self.vlasnyi = self.vidbytok(fs)


KLASY = {'knn': Knn, 'openvoice': OpenVoice}


# ------------------------------------------------------------------ команди

def _vidibraty_sumishi(kudy: Path):
    """Набір → два файли 16 кГц: kudy/cholovichyi.wav і kudy/zhinochyi.wav (по HVYLYN_NA_HOLOS хв). Правила — над NABIR."""
    import random
    import numpy as np
    import soundfile as sf
    import librosa
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download
    riadky = []
    for f in NABIR['fayly']:
        print(f'набір: {NABIR["repo"]}/{f}')
        lok = hf_hub_download(NABIR['repo'], f, repo_type='dataset', local_dir=str(MODELI / 'nabir'))
        riadky += pq.read_table(lok).to_pylist()
    random.Random(0).shuffle(riadky)
    shmatky = {v: [] for v in HOLOSY}
    trv = {v: 0.0 for v in HOLOSY}
    lim = HVYLYN_NA_HOLOS * 60
    for r in riadky:
        if not 3 <= r['duration'] <= 15 or re.search('[a-zA-Z]', r['transcription']):
            continue
        x = np.frombuffer(subprocess.run([ffmpeg(), '-v', 'error', '-i', '-', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                                         input=r['audio']['bytes'], capture_output=True).stdout, dtype=np.float32)
        if len(x) < 32000:
            continue
        kadry = x[: len(x) // 320 * 320].reshape(-1, 320)
        e = 10 * np.log10((kadry ** 2).mean(1) + 1e-10)
        if np.percentile(e, 90) - np.percentile(e, 10) < 25:
            continue
        f0, dzv, _ = librosa.pyin(x, fmin=60, fmax=400, sr=16000, frame_length=1024)
        if np.mean(dzv) < 0.35:
            continue
        m = np.nanmedian(f0)
        v = next((v for v, (n, k) in HOLOSY.items() if n <= m < k), None)
        if v is None or trv[v] >= lim:
            continue
        shmatky[v].append(np.concatenate([x, np.zeros(1600, np.float32)]))
        trv[v] += len(x) / 16000
        if all(t >= lim for t in trv.values()):
            break
    kudy.mkdir(parents=True, exist_ok=True)
    for v, sh in shmatky.items():
        sf.write(str(kudy / f'{v}.wav'), np.concatenate(sh), 16000)
        print(f'  {v}: {len(sh)} шматків, {trv[v] / 60:.1f} хв')
    shutil.rmtree(MODELI / 'nabir', ignore_errors=True)       # ≈ 0,5 ГБ — більше не треба


def pidhotuvaty(rushii: list[str]):
    """Моделі + два голоси-суміші. Повторний запуск нічого не качає вдруге."""
    sumishi = MODELI / 'sumishi'
    if not all((sumishi / f'{v}.wav').is_file() for v in HOLOSY):
        _vidibraty_sumishi(sumishi)
    (MODELI / 'holosy').mkdir(parents=True, exist_ok=True)
    (MODELI / 'holosy' / 'DZHERELA.txt').write_text(
        'Голоси «Моєї вулиці» складено з записів набору ' + NABIR['dzherelo'] + f' ({NABIR["licenziia"]}).\n',
        encoding='utf-8')
    for r in rushii:
        m = None
        for v in HOLOSY:
            f = MODELI / 'holosy' / f'{r}-{v}.pt'
            if f.is_file():
                continue
            m = m or KLASY[r]()
            t0 = time.time()
            import torch
            torch.save(m.nabir([sumishi / f'{v}.wav']) if r == 'knn' else m.vidbytok_sumishi(sumishi / f'{v}.wav'), f)
            print(f'{r}: голос {v} готовий за {time.time() - t0:.0f} с → {f}')
    print('готово:', MODELI)


def peretvoryty(vkhid: list[Path], holosy: list[str], rushii: str, vykhid: Path, teksty: dict[str, str] | None):
    m = KLASY[rushii]()
    chysti = []
    for f in vkhid:
        x, sr = ochystyty(f)
        chysti.append((f, x, sr))
        zapysaty(vykhid / 'chysti' / imia_vykhodu(f), vyrivniaty(x, sr), sr)
    if rushii == 'openvoice':
        m.vlasnyi_vidbytok([x for _, x, _ in chysti], chysti[0][2])
    zvit = []
    for f, x, sr in chysti:
        for v in holosy:
            t0 = time.time()
            y, sry = m.peretvoryty(x, sr, v)
            y = vyrivniaty(peresempl(y, sry, SR_VYKHID), SR_VYKHID)
            kudy = vykhid / v / imia_vykhodu(f)
            zapysaty(kudy, y, SR_VYKHID)
            tryv = len(x) / sr
            zvit.append((f.name, v, tryv, time.time() - t0))
            print(f'{f.name} → {v}: {tryv:.1f} с звуку за {time.time() - t0:.1f} с → {kudy}')
            if teksty is not None:
                t = teksty.get(f.stem.lower())
                if t is None:
                    print(f'  ! немає тексту для {f.stem} у --teksty — для рушія роликів не покладено')
                else:
                    teka = vykhid / f'teka-{v}' / imia_teky(t)
                    teka.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(kudy, teka)
    return zvit


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    k = p.add_subparsers(dest='komanda', required=True)
    a = k.add_parser('pidhotuvaty', help='завантажити моделі й скласти два голоси (раз)')
    a.add_argument('--rushii', default='knn,openvoice')
    b = k.add_parser('peretvoryty', help='записи → голос')
    b.add_argument('vkhid', nargs='+')
    b.add_argument('--holos', default='oba')
    b.add_argument('--rushii', default=TYPOVYI_RUSHII, choices=sorted(RUSHII))
    b.add_argument('--vykhid', default=str(KORIN / 'video' / 'vyhid' / 'holos'))
    b.add_argument('--teksty')
    o = p.parse_args(argv)
    if o.komanda == 'pidhotuvaty':
        rr = [r.strip() for r in o.rushii.split(',') if r.strip()]
        for r in rr:
            if r not in RUSHII:
                raise SystemExit(f'--rushii {r}: є {", ".join(RUSHII)}')
        pidhotuvaty(rr)
    else:
        peretvoryty(zibraty_vkhid(o.vkhid), holosy_z_arg(o.holos), o.rushii, Path(o.vykhid),
                    chytaty_teksty(Path(o.teksty)) if o.teksty else None)


if __name__ == '__main__':
    main()

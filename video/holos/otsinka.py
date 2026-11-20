"""Оцінка перетвореного голосу без людського вуха (ZAVDANNYA-148): чи розбірливо і чи схоже на початковий голос.

    python video/holos/otsinka.py --pochatkovi <теки або файли до> --pisla <тека після> [--teksty teksty.tsv] [--porivniaty <інші голоси>]

Що міряє для кожного файлу «після» (пара «до» — файл з тим самим іменем):
- **схожість голосу** з «до» — косинус відбитків голосу ECAPA (SpeechBrain, модель spkrec-ecapa-voxceleb, Apache-2.0):
  ≈ 1 — та сама людина, нижче ≈ 0,25 — для системи розпізнавання мовця це вже інші люди (поріг моделі на VoxCeleb ≈ 0,25);
- **розбірливість** — частка помилок у літерах (CER) розпізнавання Whisper small (faster-whisper, MIT) проти тексту з
  `--teksty`; 0 — усе розпізнано, 0,1 — кожна десята літера не та;
- **висота голосу** — медіана основного тону, Гц (чоловічий ≈ 85–155, жіночий ≈ 165–255).

Це вимір машиною, не слух: слухати все одно Андрію (і комусь, хто знає його голос).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from holos import chytaty, chytaty_teksty, zibraty_vkhid  # noqa: E402


def cer(a: str, b: str) -> float:
    """Частка помилок у літерах (відстань Левенштейна / довжина еталона), без розділових знаків і регістру."""
    import re
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vau'))
    from holos_tekst import chyslo_slovamy

    def norm(s):                    # «42» → «сорок два»: цифри й слова — одне; різниця роду — одна-дві літери
        s = re.sub(r'\d+', lambda m: chyslo_slovamy(int(m.group())), s.lower().replace('’', "'"))
        return re.sub(r'[^\w ]+', ' ', s).split()
    a, b = ' '.join(norm(a)), ' '.join(norm(b))
    if not a:
        return 0.0 if not b else 1.0
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (ca != cb))
    return d[len(b)] / len(a)


class Mira:
    def __init__(self):
        import os
        from speechbrain.inference.speaker import EncoderClassifier
        kesh = Path(os.environ.get('MV_HOLOS_MODELI') or Path.home() / '.cache' / 'mv-holos') / 'otsinka'
        self.ecapa = EncoderClassifier.from_hparams(source='speechbrain/spkrec-ecapa-voxceleb', savedir=str(kesh / 'ecapa'),
                                                    run_opts={'device': 'cpu'})
        self.asr = None

    def vidbytok(self, f: Path):
        import torch
        x = chytaty(f, 16000)
        with torch.inference_mode():
            e = self.ecapa.encode_batch(torch.from_numpy(x)[None]).squeeze()
        return e / e.norm()

    def skhozhist(self, a: Path, b: Path) -> float:
        return float((self.vidbytok(a) * self.vidbytok(b)).sum())

    def rozpiznaty(self, f: Path) -> str:
        if self.asr is None:
            from faster_whisper import WhisperModel
            self.asr = WhisperModel('small', device='cpu', compute_type='int8')
        sehm, _ = self.asr.transcribe(chytaty(f, 16000), language='uk', beam_size=5)
        return ' '.join(s.text.strip() for s in sehm)

    @staticmethod
    def vysota(f: Path) -> float:
        import librosa
        import numpy as np
        x = chytaty(f, 16000)
        f0, _, _ = librosa.pyin(x, fmin=60, fmax=400, sr=16000)
        return float(np.nanmedian(f0))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--pochatkovi', nargs='+', required=True)
    p.add_argument('--pisla', nargs='+', required=True)
    p.add_argument('--teksty')
    o = p.parse_args(argv)
    do = {f.stem.lower(): f for f in zibraty_vkhid(o.pochatkovi)}
    teksty = chytaty_teksty(Path(o.teksty)) if o.teksty else {}
    m = Mira()
    print('файл | схожість з «до» | помилки в літерах | висота, Гц | розпізнано')
    for f in zibraty_vkhid(o.pisla):
        k = f.stem.lower()
        sk = f'{m.skhozhist(do[k], f):.2f}' if k in do else '—'
        if k in teksty:
            r = m.rozpiznaty(f)
            c = f'{cer(teksty[k], r):.2f}'
        else:
            r, c = '', '—'
        print(f'{f.parent.name}/{f.name} | {sk} | {c} | {m.vysota(f):.0f} | {r}')


if __name__ == '__main__':
    main()

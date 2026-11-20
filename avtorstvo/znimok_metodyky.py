# -*- coding: utf-8 -*-
"""Щомісячний знімок методики бази — для кваліфікованої позначки часу (ZAVDANNYA-158, `docs/METODYKA-BAZY.md`, розд. 8).

Робить один ZIP з правилами й кодом добору обох репозиторіїв на задані коміти, опис поруч і ОДИН хеш (SHA-256), який
Микита підписує своїм КЕП із кваліфікованою позначкою часу (`docs/ZNIMOK-METODYKY.md`).

  python avtorstvo/znimok_metodyky.py                         # знімок HEAD обох репозиторіїв
  python avtorstvo/znimok_metodyky.py --dani ../dani-edrsr --komit-dani origin/main --komit-mv origin/main
  python avtorstvo/znimok_metodyky.py --zhurnal               # ще й дописати рядок у avtorstvo/zhurnal.tsv
  python avtorstvo/znimok_metodyky.py --pereviryty avtorstvo/znimky/metodyka-2026-11-20.sha256

Вихід (типово `avtorstvo/znimky/`, git його не бачить):
  metodyka-<дата>.zip           архів: MANIFEST.tsv + файли з git (теки `moya-vulytsya/…`, `dani-edrsr/…`)
  metodyka-<дата>.MANIFEST.tsv  той самий опис окремо: коміти й дати, кожен файл з SHA-256 і розміром
  metodyka-<дата>.sha256        один рядок «<SHA-256 архіву>  metodyka-<дата>.zip» — його й підписують

Відтворюваність: файли беруться з git (`git ls-tree`/`git cat-file`) на заданий коміт, а не з робочої теки; у ZIP — сталий
порядок, сталі дати й права файлів. Тож з тих самих комітів через рік вийде той самий архів байт у байт, і хеш можна
звірити (`--pereviryty`). Дата в імені файлів — день знімка; у вміст архіву вона не входить.

Архів містить код приватного `dani-edrsr`: не комітити, не публікувати; зберігати у двох місцях поза GitHub.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import subprocess
import sys
import zipfile
from pathlib import Path

KOREN_MV = Path(__file__).resolve().parents[1]
ZHURNAL = KOREN_MV / 'avtorstvo' / 'zhurnal.tsv'
ZHURNAL_POLIA = ['data', 'arkhiv', 'sha256', 'komit_moya_vulytsya', 'komit_dani_edrsr', 'pidpys', 'chas_poznachky']

# Що входить у знімок: правила, журнали рішень, налаштування, схема, код добору й описи замірів.
# Шлях — файл або тека (з «/» в кінці); розширення — лише текстові файли; винятки — сторонні бібліотеки й шрифти.
DANI = {
    'shliakhy': ['SPECYFIKATSIYA.md', 'RISHENNYA.md', 'README.md', 'requirements.txt',
                 'config/', 'db/', 'docs/', 'dovidnyky/', 'src/', 'perevirka/'],
    'vyniatky': ['src/zvit/leaflet/', 'src/zvit/shryfty/'],
}
# perevirka/: лише описи й код замірів (.md, .txt, .py) — без самих вибірок (.jsonl, .csv). Уривки рішень в описах є,
# тому архів лишається приватним (позначку часу ставлять на хеш, сам архів нікуди не викладається).
LYSHE_OPYSY = {'perevirka/': {'.md', '.txt', '.py'}}
MV = {
    'shliakhy': ['AGENTS.md', 'RISHENNYA.md', 'docs/METODYKA-BAZY.md', 'docs/ZNIMOK-METODYKY.md', 'docs/VIDKRYTYI-NABIR.md',
                 'docs/METODYKA-ANALITYKY-ZVITU.md', 'docs/PROBLEMY-YAK-VYZNACHATY.md', 'docs/01-slovnyk.md',
                 'docs/03-dani-i-etyka.md', 'docs/05-model-danykh.md', 'docs/06-metodyka.md', 'avtorstvo/znimok_metodyky.py'],
    'vyniatky': [],
}
TEKSTOVI = {'.md', '.py', '.json', '.csv', '.tsv', '.sql', '.sha256', '.txt', '.js', '.html', '.css', '.yml', '.yaml'}
DATA_ZIP = (1980, 1, 1, 0, 0, 0)  # стала дата файлів в архіві — для відтворюваності


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout


def komit(repo: Path, rev: str) -> tuple[str, str]:
    """(повний хеш, дата коміту ISO) для rev"""
    h, d = git(repo, 'log', '-1', '--format=%H%n%cI', rev).decode().split()
    return h, d


def pidkhodyt(shliakh: str, nabir: dict) -> bool:
    if any(shliakh.startswith(v) for v in nabir['vyniatky']):
        return False
    rozsh = Path(shliakh).suffix.lower()
    for p in nabir['shliakhy']:
        if p.endswith('/') and shliakh.startswith(p):
            dozvoleni = LYSHE_OPYSY.get(p, TEKSTOVI) if nabir is DANI else TEKSTOVI
            return rozsh in dozvoleni
        if shliakh == p:
            return True
    return False


def faily(repo: Path, rev: str, nabir: dict) -> list[tuple[str, bytes]]:
    """[(шлях, вміст)] з git на коміт rev, у сталому порядку"""
    out = []
    for ryadok in git(repo, 'ls-tree', '-r', '-z', '--full-tree', rev).split(b'\0'):
        if not ryadok:
            continue
        meta, shliakh = ryadok.split(b'\t', 1)
        _rezhym, typ, obiekt = meta.decode().split()
        shliakh = shliakh.decode('utf-8')
        if typ != 'blob' or not pidkhodyt(shliakh, nabir):
            continue
        out.append((shliakh, git(repo, 'cat-file', 'blob', obiekt)))
    return sorted(out)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def manifest(komity: dict, vmist: dict) -> bytes:
    """опис знімка: лише з комітів і файлів — без дати знімка, щоб архів відтворювався"""
    r = ['# Знімок методики бази «Моя вулиця» (docs/METODYKA-BAZY.md, розд. 8)',
         '# Відтворити: python avtorstvo/znimok_metodyky.py --komit-mv <коміт> --komit-dani <коміт>']
    for nazva, (h, d) in komity.items():
        r.append(f'# komit\t{nazva}\t{h}\t{d}')
    r.append('repozytorii\tfail\tsha256\tbaitiv')
    for nazva in komity:
        for shliakh, b in vmist[nazva]:
            r.append(f'{nazva}\t{shliakh}\t{sha(b)}\t{len(b)}')
    return ('\n'.join(r) + '\n').encode('utf-8')


def zip_bajty(man: bytes, vmist: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        def dodaty(imia: str, b: bytes):
            zi = zipfile.ZipInfo(imia, DATA_ZIP)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zi.create_system = 3
            z.writestr(zi, b, compresslevel=9)
        dodaty('MANIFEST.tsv', man)
        for nazva, spysok in vmist.items():
            for shliakh, b in spysok:
                dodaty(f'{nazva}/{shliakh}', b)
    return buf.getvalue()


def zibraty(mv: Path, dani: Path, rev_mv: str, rev_dani: str) -> tuple[bytes, bytes, dict]:
    komity = {'moya-vulytsya': komit(mv, rev_mv), 'dani-edrsr': komit(dani, rev_dani)}
    vmist = {'moya-vulytsya': faily(mv, komity['moya-vulytsya'][0], MV),
             'dani-edrsr': faily(dani, komity['dani-edrsr'][0], DANI)}
    for nazva, spysok in vmist.items():
        if not spysok:
            raise SystemExit(f'У {nazva} на коміті {komity[nazva][0][:7]} не знайдено жодного файла методики — не той репозиторій?')
    man = manifest(komity, vmist)
    return zip_bajty(man, vmist), man, komity


def komity_z_manifestu(man: str) -> dict:
    k = {}
    for ryadok in man.splitlines():
        if ryadok.startswith('# komit\t'):
            _, nazva, h, _d = ryadok.split('\t')
            k[nazva] = h
    if set(k) != {'moya-vulytsya', 'dani-edrsr'}:
        raise SystemExit('В описі немає комітів обох репозиторіїв')
    return k


def pereviryty(fail_sha: Path, mv: Path, dani: Path) -> int:
    ryadok = fail_sha.read_text(encoding='utf-8').split()
    ochikuvanyi, imia = ryadok[0].lower(), ryadok[1]
    man_f = fail_sha.with_name(imia.replace('.zip', '.MANIFEST.tsv'))
    if man_f.exists():
        man = man_f.read_text(encoding='utf-8')
    else:  # опису поруч немає — беремо з самого архіву
        with zipfile.ZipFile(fail_sha.with_name(imia)) as z:
            man = z.read('MANIFEST.tsv').decode('utf-8')
    k = komity_z_manifestu(man)
    arkhiv, _man, _k = zibraty(mv, dani, k['moya-vulytsya'], k['dani-edrsr'])
    novyi = sha(arkhiv)
    zip_f = fail_sha.with_name(imia)
    if zip_f.exists() and sha(zip_f.read_bytes()) != ochikuvanyi:
        print(f'НЕ ЗБІГАЄТЬСЯ: збережений архів {zip_f.name} має інший хеш, ніж у {fail_sha.name}')
        return 1
    if novyi != ochikuvanyi:
        print(f'НЕ ЗБІГАЄТЬСЯ: перебудований з комітів архів {novyi}, у файлі {ochikuvanyi}')
        return 1
    print(f'Збігається: {ochikuvanyi} — перебудовано з moya-vulytsya {k["moya-vulytsya"][:7]}, dani-edrsr {k["dani-edrsr"][:7]}')
    return 0


def dopysaty_zhurnal(zhurnal: Path, ryadok: dict) -> None:
    novyi = not zhurnal.exists()
    with zhurnal.open('a', encoding='utf-8', newline='\n') as f:
        if novyi:
            f.write('\t'.join(ZHURNAL_POLIA) + '\n')
        f.write('\t'.join(ryadok.get(p, '') for p in ZHURNAL_POLIA) + '\n')


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description='Знімок методики бази для кваліфікованої позначки часу')
    a.add_argument('--mv', type=Path, default=KOREN_MV, help='клон moya-vulytsya (типово — цей)')
    a.add_argument('--dani', type=Path, default=KOREN_MV.parent / 'dani-edrsr', help='клон dani-edrsr (типово — поруч)')
    a.add_argument('--komit-mv', default='HEAD')
    a.add_argument('--komit-dani', default='HEAD')
    a.add_argument('--vykhid', type=Path, default=KOREN_MV / 'avtorstvo' / 'znimky')
    a.add_argument('--data', default=dt.date.today().isoformat(), help='дата в імені файлів (типово — сьогодні)')
    a.add_argument('--zhurnal', action='store_true', help='дописати рядок у avtorstvo/zhurnal.tsv')
    a.add_argument('--pereviryty', type=Path, help='файл .sha256 знімка: перебудувати архів з комітів і звірити хеш')
    n = a.parse_args(argv)
    for nazva, repo in (('moya-vulytsya', n.mv), ('dani-edrsr', n.dani)):
        if not (repo / '.git').exists():
            print(f'Не знайдено клон {nazva}: {repo} (вкажіть --{"mv" if nazva == "moya-vulytsya" else "dani"})')
            return 2
    if n.pereviryty:
        return pereviryty(n.pereviryty, n.mv, n.dani)
    arkhiv, man, komity = zibraty(n.mv, n.dani, n.komit_mv, n.komit_dani)
    n.vykhid.mkdir(parents=True, exist_ok=True)
    imia = f'metodyka-{n.data}'
    (n.vykhid / f'{imia}.zip').write_bytes(arkhiv)
    (n.vykhid / f'{imia}.MANIFEST.tsv').write_bytes(man)
    h = sha(arkhiv)
    (n.vykhid / f'{imia}.sha256').write_text(f'{h}  {imia}.zip\n', encoding='utf-8')
    failiv = man.count(b'\n') - 5
    print(f'Знімок: {n.vykhid / (imia + ".zip")} ({len(arkhiv) // 1024} КБ, {failiv} файлів)')
    for nazva, (k, d) in komity.items():
        print(f'  {nazva}: {k[:7]} від {d}')
    print(f'SHA-256: {h}')
    print(f'Підписати з позначкою часу: {n.vykhid / (imia + ".sha256")} (docs/ZNIMOK-METODYKY.md)')
    if n.zhurnal:
        dopysaty_zhurnal(ZHURNAL, {'data': n.data, 'arkhiv': f'{imia}.zip', 'sha256': h,
                                   'komit_moya_vulytsya': komity['moya-vulytsya'][0],
                                   'komit_dani_edrsr': komity['dani-edrsr'][0], 'pidpys': '—', 'chas_poznachky': '—'})
        print(f'Рядок дописано: {ZHURNAL}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

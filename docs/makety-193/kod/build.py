import json, os, copy, sys
import styli, storinky as ST, zmist as Z
TUT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(TUT, 'out')
d = Z.D
open(os.path.join(TUT, 'dani.js'), 'w').write('window.DANI=' + json.dumps({k: d[k] for k in ('soty7', 'soty8', 'sota7', 'sota', 'problemy', 'rayony', 'vektory7', 'vektory8')}, ensure_ascii=False) + ';')
tilky = sys.argv[1:] or list(styli.S)
for k in tilky:
    S = dict(styli.S[k]); S['kliuch'] = k
    p = os.path.join(OUT, k); os.makedirs(p, exist_ok=True)
    for tel in (True, False):
        pr = 'tel' if tel else 'pk'
        open(f'{p}/karta-{pr}.html', 'w').write(ST.ekran_karty(S, tel))
        open(f'{p}/budynok-{pr}.html', 'w').write(ST.ekran_budynku(S, tel))
        open(f'{p}/rayon-{pr}.html', 'w').write(ST.ekran_rayonu(S, tel))
    t = S['karta'].get('temna')
    if t:
        S2 = copy.deepcopy(S); S2['tema'] = 'temna'; S2['karta'].update(t)
        open(f'{p}/karta-pk-temna.html', 'w').write(ST.ekran_karty(S2, False))
print('ok', tilky)

import sys, pickle, collections, json, hashlib
sys.path.insert(0, '/home/user/d103/src')
import problemy_varianty as PV, problemy_shi as PS, mech as M
B = pickle.load(open('/home/user/work/baza.pkl','rb')); kand = pickle.load(open('/home/user/work/kand1.pkl','rb'))
S, P = B['S'], B['P']
SK = PV.SkhozhiVikna(B['evs'], S)
ids = {(k['sim'], (k['tochnist'], k['lat'], k['lon'])) for k in kand if k.get('riven') != 'ділянка'}
dil_mista = set()
for k in kand:
    if k.get('riven') == 'ділянка':
        for e in k['s']['evs']: dil_mista.add((k['sim'], e['eid']))
q0 = PV.kv(S); out = []
for (sim, m), xs in P.items():
    if (sim, m) in ids: continue
    u = PV.unikalni(xs, S); qs = [PV.kv(e['data']) for e in u]
    best = 0
    for a in set(qs):
        n = sum(a <= q <= a + 7 for q in qs); best = max(best, n)
    if best < 10: continue
    e0 = max(xs, key=lambda e: (e['nazva'] != '', e['mistse'] == m))
    ok, s = PV.sito_183(xs, S, SK, sim, e0)
    v_dil = sum((sim, e['eid']) in dil_mista for e in xs)
    out.append(dict(sim=sim, m=m, nazva=e0['nazva'], n_vsi=len(u), maks2r=best, ok=ok, p=s.get('p'), och=s.get('ochikuvano'),
                    typ=s.get('typ'), v_dilianku=v_dil, povtor=s.get('povtor')))
print(len(out)); c = collections.Counter((o['sim'], o['ok']) for o in out); print(c.most_common(40))
print(collections.Counter('ділянка' if o['v_dilianku'] else ('ok-but-chutlyvi' if o['ok'] else 'P') for o in out))
pickle.dump(out, open('/home/user/work/propushcheni.pkl','wb'))
for o in sorted(out, key=lambda o: -o['maks2r'])[:25]: print(o['sim'], o['nazva'][:40], o['maks2r'], o['n_vsi'], o['ok'], o['p'] and round(o['p'],3), o['och'], o['typ'], o['v_dilianku'])

# -*- coding: utf-8 -*-
"""ZAVDANNYA-187, п. 1: чутливість сита MV-195 до параметрів (без ШІ). Код dani-edrsr не змінює — підміняє параметри
в пам'яті. Запуск: python chutlyvist.py baza.pkl sprava.pkl out/chutlyvist.json"""
import sys, json, time, pickle, collections
sys.path.insert(0, '/home/user/d103/src')
import problemy_varianty as PV, problemy_shi as PS, mech as M

B = pickle.load(open(sys.argv[1], 'rb')); SPR = pickle.load(open(sys.argv[2], 'rb'))
S, EVS = B['S'], B['evs']
for e in EVS: e['spr'] = SPR.get(e['eid'], '')
VIKNO_ORIG = PV.povtoriuvani_vikna

def vyd(k): return 'ДТП на дорозі' if k['sim'] == 'ДОР_ДТП_дорога' else M.simtheme(k['sim'])

def zapusk(vikno=8, min_pod=5, min_kv=3, r=(40, 60), p=0.05, min_sprav=1, zbir_p=None):
    PV.R_ZLYTTIA, PV.R_ZLYTTIA_DTP = r
    P = PV.pary(EVS) if r != (40, 60) else B['P']
    # різні справи: вікно рахується, лише якщо його події — з ≥ min_sprav різних справ
    orig_sito = PV.sito_183.__wrapped__ if hasattr(PV.sito_183, '__wrapped__') else PV.sito_183
    def sito(xs, S_, SK, sim, e0, budynkiv=1, vikno=vikno, p_mezha=p):
        u = PV.unikalni(xs, S_)
        def pv2(qs, q0, vik=None, *a, **k):
            out = VIKNO_ORIG(qs, q0, vik or vikno, min_pod, min_kv)
            if min_sprav > 1:
                out = [(a_, b_, ix) for a_, b_, ix in out if len({u[i]['spr'] for i in ix}) >= min_sprav]
            if zbir_p is not None:
                for a_, b_, ix in out:
                    _, lam, _ = SK.ochikuvano(sim, e0, a_, b_)
                    zbir_p.append(PV.pois_sf(len(ix), lam * budynkiv))
            return out
        PV.povtoriuvani_vikna = pv2
        try:
            return orig_sito(xs, S_, SK, sim, e0, budynkiv, vikno, p_mezha)
        finally:
            PV.povtoriuvani_vikna = VIKNO_ORIG
    sito.__wrapped__ = orig_sito
    PV.sito_183 = sito
    try:
        z = PV.kandydaty_183(EVS, P, S, lambda *a: None, vikno, p)
    finally:
        PV.sito_183 = orig_sito; PV.R_ZLYTTIA, PV.R_ZLYTTIA_DTP = 40, 60
    kand = PS.bez_chutlyvykh(z['kandydaty'] + z['dilianky'])
    return dict(par=z['par'], povtor=z['povtor'], kandydativ=len(kand), dilianok=len(z['dilianky']),
                za_vydom=dict(collections.Counter(vyd(k) for k in kand))), kand

def bh(ps, q=0.05):
    ps = sorted(ps); m = len(ps); t = 0.0
    for i, x in enumerate(ps, 1):
        if x <= q * i / m: t = x
    return t, m

if __name__ == '__main__':
    rez = {}; KL = {}; KK = {}
    def zap(nazva, **kw):
        t = time.time(); r, kand = zapusk(**kw); r['param'] = {k: v for k, v in kw.items() if k != 'zbir_p'}
        r['sek'] = round(time.time() - t, 1); rez[nazva] = r; KL[nazva] = [(PS.kliuch(k), vyd(k)) for k in kand]; KK[nazva] = kand
        print(nazva, r['kandydativ'], r['za_vydom'], r['sek'], flush=True)
        return kand
    zap('базовий (8 кв., 5 подій, 3 кв., 40/60 м, P 0,05, 1 справа)')
    for v in (6, 12): zap(f'період {v} кв.', vikno=v)
    for n in (4, 6): zap(f'≥ {n} подій', min_pod=n)
    for q in (2, 4): zap(f'≥ {q} квартали', min_kv=q)
    for r in ((40, 40), (60, 60), (100, 100)): zap(f'коло {r[0]}/{r[1]} м (інше/ДТП)', r=r)
    for p in (0.01,): zap(f'P {p}', p=p)
    ps = []; zapusk(p=1.0, zbir_p=ps)
    t, m = bh(ps); rez['_bh'] = dict(testiv=m, porih=t)
    print('BH', m, t, flush=True)
    zap('поправка BH (FDR 5 %)', p=t * 1.0000001)
    for s in (2, 3): zap(f'≥ {s} різні справи', min_sprav=s)
    json.dump(rez, open(sys.argv[3], 'w'), ensure_ascii=False, indent=1)
    pickle.dump(KL, open(sys.argv[3] + '.kliuchi.pkl', 'wb')); pickle.dump(KK, open(sys.argv[3] + '.kand.pkl', 'wb'))

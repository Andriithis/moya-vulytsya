# Скільки кандидатів сита лишиться, якщо події одного місця ближче 30 днів одна до одної (ланцюжком) рахувати як одну
import sys, pickle, datetime as dt, collections
sys.path.insert(0, '/home/user/d103/src')
import problemy_varianty as PV, problemy_shi as PS, mech as M
B = pickle.load(open('/home/user/work/baza.pkl','rb'))
orig = PV.unikalni
def zhaty(xs, S, dni):
    u = orig(xs, S); out = []; last = None
    for e in u:
        d = dt.date.fromisoformat(e['data'])
        if last is not None and (d - last).days <= dni: last = d; continue
        out.append(e); last = d
    return out
for dni in (7, 30):
    PV.unikalni = lambda xs, S, dni=dni: zhaty(xs, S, dni)
    z = PV.kandydaty_183(B['evs'], B['P'], B['S'], lambda *a: None)
    k = PS.bez_chutlyvykh(z['kandydaty'] + z['dilianky'])
    print(dni, len(k), collections.Counter('ДТП на дорозі' if x['sim']=='ДОР_ДТП_дорога' else M.simtheme(x['sim']) for x in k))
PV.unikalni = orig

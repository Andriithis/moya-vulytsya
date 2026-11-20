import sys, pickle, collections, json
sys.path.insert(0, '/home/user/d103/src')
import problemy_varianty as PV, mech as M
B = pickle.load(open('/home/user/work/baza.pkl','rb'))
c = collections.defaultdict(collections.Counter)
for e in B['evs']:
    t = 'ДТП на дорозі' if e['sim']=='ДОР_ДТП_дорога' else M.simtheme(e['sim'])
    c[t][PV.kv(e['data'])] += 1; c['усі'][PV.kv(e['data'])] += 1
qs = [PV.kv(f'{y}-{m:02d}-01') for y in (2024, 2025, 2026) for m in (1, 4, 7, 10)][:-1]
out = {}
for t, x in sorted(c.items()):
    base = sum(x[q] for q in qs[:4]) / 4
    out[t] = {PV.kv_nazva(q): round(x[q] / base, 2) if base else None for q in qs[4:]}
    print(t, out[t])
# річний ряд міста за видами (для тренду)
r = collections.defaultdict(collections.Counter)
for e in B['evs']:
    r[e['sim']][int(e['data'][:4])] += 1
json.dump(dict(povnota=out, riad={k: dict(sorted(v.items())) for k, v in r.items()}), open('/home/user/work/out/povnota.json', 'w'), ensure_ascii=False, indent=1)
for k in ('АЛК_торгівля', 'АЛК_стихторгівля', 'МАЙ_крадіжка', "ДОР_сп'яніння", 'НАР_зберігання', 'ДОР_ДТП_двір', 'ДОР_ДТП_дорога', 'ГП_непокора'):
    print(k, {y: r[k][y] for y in range(2016, 2027)})

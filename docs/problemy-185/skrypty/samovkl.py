# Скільки місць не пройшли надлишок лише тому, що «схожі» включають саме місце (самовключення)
import sys, pickle, collections
sys.path.insert(0, '/home/user/d103/src')
import problemy_varianty as PV, mech as M
B = pickle.load(open('/home/user/work/baza.pkl','rb')); S,P=B['S'],B['P']
SK = PV.SkhozhiVikna(B['evs'], S); q0=PV.kv(S)
# міська середня по типу місця (без клітинки) — запасне очікуване
res=collections.Counter(); prykl=[]
for (sim,m),xs in P.items():
    e0 = max(xs, key=lambda e: (e['nazva'] != '', e['mistse'] == m))
    u=PV.unikalni(xs,S); qs=[PV.kv(e['data']) for e in u]
    vik=PV.povtoriuvani_vikna(qs,q0)
    if not vik: continue
    stare=any(PV.pois_sf(len(ix), SK.ochikuvano(sim,e0,a,b)[1])<0.05 for a,b,ix in vik)
    if stare: res['пройшло і так']+=1; continue
    nove=False; m1=None
    for a,b,ix in vik:
        g=PV.Skhozhi._hrupa(e0)
        n_gr=sum(SK.podii[(sim,)+g][q] for q in range(a,b+1))
        mm=SK.mista.get((M.simtheme(sim),)+g,{}).get(a,0)
        own=len(ix)  # події місця в вікні (≈ його внесок)
        own_all=sum(1 for e in xs if a<=PV.kv(e['data'])<=b)
        if mm<=1: lam=None
        else: lam=(n_gr-own_all)/(mm-1)
        m1=mm
        if lam is not None and PV.pois_sf(len(ix), lam)<0.05: nove=True; break
        if lam is None: res['лише саме місце в групі (m=1)']+=0
    key=('пройшло б без самовключення' if nove else 'не пройшло б і так')+(' · m≤1' if m1<=1 else '')
    res[key]+=1
    if nove: prykl.append((sim,e0['nazva'],len(u)))
print(res); print(collections.Counter(p[0] for p in prykl).most_common())
for p in sorted(prykl,key=lambda p:-p[2])[:15]: print(p)

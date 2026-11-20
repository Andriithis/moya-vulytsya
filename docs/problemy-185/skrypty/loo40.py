import sys, json, pickle, collections
sys.path.insert(0, '/home/user/d103/src')
import problemy_varianty as PV, mech as M
B = pickle.load(open('/home/user/work/baza.pkl','rb')); S,P=B['S'],B['P']
SK = PV.SkhozhiVikna(B['evs'], S); q0=PV.kv(S)
# міська група: той самий тип місця по всьому місту (будинок — усі будинки)
podii_m = collections.defaultdict(collections.Counter); mista_m = collections.defaultdict(lambda: collections.defaultdict(set))
for e in B['evs']:
    if e['data'] > S: continue
    t = PV.Skhozhi._hrupa(e)[0]; q = PV.kv(e['data'])
    podii_m[(e['sim'], t)][q] += 1; mista_m[(M.simtheme(e['sim']), t)][e['mistse']].add(q)
def loo(sim, e0, xs):
    u=PV.unikalni(xs,S); qs=[PV.kv(e['data']) for e in u]; g=PV.Skhozhi._hrupa(e0); best=None
    for a,b,ix in PV.povtoriuvani_vikna(qs,q0):
        n_gr=sum(SK.podii[(sim,)+g][q] for q in range(a,b+1)); mm=SK.mista.get((M.simtheme(sim),)+g,{}).get(a,0)
        own=sum(1 for q in qs if a<=q<=b)
        if mm-1 >= 5: lam=(n_gr-own)/(mm-1); dz='клітинка'
        else:
            t=g[0]; n_c=sum(podii_m[(sim,t)][q] for q in range(a,b+1)); m_c=sum(1 for qq in mista_m[(M.simtheme(sim),t)].values() if any(a<=q<=b for q in qq))
            lam=(n_c-own)/max(m_c-1,1); dz='місто'
        p=PV.pois_sf(len(ix),lam)
        if best is None or p<best[0]: best=(p,round(lam,2),mm,dz,len(ix))
    return best
I=json.load(open('/home/user/work/k185/krytyk.json'))
for i in I:
    if i['grupa']!='не пройшло сито': continue
    o=i['prop']; xs=P[(o['sim'],tuple(o['m']))]; e0=max(xs,key=lambda e:(e['nazva']!='', e['mistse']==tuple(o['m'])))
    p,lam,mm,dz,n=loo(o['sim'],e0,xs); i['loo']=dict(p=p,och=lam,skhozhykh_u_klityntsi=mm,hrupa=dz,n=n)
    print(o['sim'][:16], i['mistse'][:28], 'n',n,'стар.оч',o['och'],'m',mm,'→',dz,'оч',lam,'P',round(p,4), '| К', (i['krytyk'] or {}).get('spravzhnia'), '| А', (i.get('rozbir') or {}).get('spravzhnia'))
json.dump(I, open('/home/user/work/k185/krytyk.json','w'), ensure_ascii=False, indent=1)

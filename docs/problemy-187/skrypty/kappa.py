import json, re, collections, sys, itertools
def kappa(a, b):
    n=len(a); ks=sorted(set(a)|set(b)); po=sum(x==y for x,y in zip(a,b))/n
    ca,cb=collections.Counter(a),collections.Counter(b); pe=sum(ca[k]*cb[k] for k in ks)/n/n
    return po, (po-pe)/(1-pe) if pe<1 else 1.0
norm=lambda r: 'скупчення' if r=='вада' else r
R={n: json.load(open(f'/home/user/work/z187/zghoda-{n}.json'))['vidpovidi'] for n in ('A_sonnet_1','B_sonnet_2','C_opus')}
# прогін 0 — таблиця 183 (рядки «Усі відповіді вибірки»)
t0={}
for l in open('/home/user/d103/perevirka/problemy-183.md'):
    c=[x.strip() for x in l.split('|')]
    if len(c)>8 and c[1] and c[1] not in ('Вид','---') and '/' in c[4]:
        t0.setdefault((c[1].replace(' (дод.)',''), c[2], c[3], c[4]), []).append(c[5].split(' ·')[0])
kal=json.load(open('/home/user/work/k183/problemy-183.json'))['vidpovidi']
kl={x['id']:(x['vyd'], __import__('problemy_183').bez_nomera(x['mistse']) if False else None) for x in kal}
sys.path.insert(0,'/home/user/d103/src'); sys.path.insert(0,'/home/user/d103/perevirka'); import problemy_183 as K
key={x['id']:(x['vyd'], K.bez_nomera(x['mistse']), x['roky'], f"{x['n']} / {x['n_vsi']}") for x in kal}
z0={}
for x in R['A_sonnet_1']:
    v=t0.get(key[x['id']])
    if v and len(v)==1: z0[x['id']]=v[0]
R0=[dict(id=i, rishennia=r) for i,r in z0.items()]
print('збіглось з таблицею 183:', len(z0), 'з', len(R['A_sonnet_1']))
pary=[('A_sonnet_1','B_sonnet_2'),('A_sonnet_1','C_opus'),('B_sonnet_2','C_opus')]
rez={}
for a,b in pary:
    x=[norm(v['rishennia']) for v in R[a]]; y=[norm(v['rishennia']) for v in R[b]]
    po,k=kappa(x,y); rez[f'{a}~{b}']=dict(n=len(x),zbih=round(po,3),kappa=round(k,3),tablytsia=collections.Counter(zip(x,y)).most_common())
    print(a,b,len(x),round(po,3),round(k,3),collections.Counter(zip(x,y)).most_common())
# 183 (прогін 0) проти A і B, C
for b in ('A_sonnet_1','B_sonnet_2','C_opus'):
    d={v['id']:norm(v['rishennia']) for v in R[b]}
    ids=list(z0); x=[norm(z0[i]) for i in ids]; y=[d[i] for i in ids]
    po,k=kappa(x,y); rez[f'183~{b}']=dict(n=len(ids),zbih=round(po,3),kappa=round(k,3),tablytsia=collections.Counter(zip(x,y)).most_common())
    print('183',b,len(ids),round(po,3),round(k,3),collections.Counter(zip(x,y)).most_common())
# за видами: проблема так/ні
for a,b in pary:
    by=collections.defaultdict(lambda:[0,0])
    for u,v in zip(R[a],R[b]):
        by[u['vyd']][0]+=1; by[u['vyd']][1]+= (norm(u['rishennia'])==norm(v['rishennia']))
    print(a,b,{k:f'{v[1]}/{v[0]}' for k,v in by.items()})
    rez[f'{a}~{b}']['za_vydom']={k:f'{v[1]}/{v[0]}' for k,v in by.items()}
# сирі тексти однакові?
same=sum(u['syre']==v['syre'] for u,v in zip(R['A_sonnet_1'],R['B_sonnet_2'])); print('дослівно однакових відповідей A/B', same)
rez['doslivno_A_B']=same
# стійкі «проблеми»: у всіх трьох
st=sum(all(norm(R[n][i]['rishennia'])=='проблема' for n in R) for i in range(len(R['A_sonnet_1'])))
bud=sum(any(norm(R[n][i]['rishennia'])=='проблема' for n in R) for i in range(len(R['A_sonnet_1'])))
print('проблема в усіх трьох', st, 'хоч в одному', bud); rez['problema_usi']=st; rez['problema_khoch_odyn']=bud
json.dump(rez, open('/home/user/work/z187/kappa.json','w'), ensure_ascii=False, indent=1)

import json, collections, pickle, sys
sys.path.insert(0,'/home/user/d103/src'); sys.path.insert(0,'/home/user/d103/perevirka')
import problemy_183 as K
kand=pickle.load(open('/home/user/work/kand1.pkl','rb')); vsi=collections.Counter(K.vyd(k) for k in kand)
R={n: json.load(open(f'/home/user/work/z187/zghoda-{n}.json')) for n in ('A_sonnet_1','B_sonnet_2','C_opus')}
V={n:r['vidpovidi'] for n,r in R.items()}
# 183 (прогін 0)
import re
t0={}
for l in open('/home/user/d103/perevirka/problemy-183.md'):
    c=[x.strip() for x in l.split('|')]
    if len(c)>8 and c[1] and c[1] not in ('Вид','---') and '/' in c[4]: t0.setdefault((c[1].replace(' (дод.)',''),c[2],c[3],c[4]),[]).append(c[5].split(' ·')[0])
kal={x['id']:x for x in json.load(open('/home/user/work/k183/problemy-183.json'))['vidpovidi']}
V['S0_183']=[dict(id=x['id'],vyd=x['vyd'],rishennia=t0[(kal[x['id']]['vyd'],K.bez_nomera(kal[x['id']]['mistse']),kal[x['id']]['roky'],f"{kal[x['id']]['n']} / {kal[x['id']]['n_vsi']}")][0]) for x in V['A_sonnet_1']]
po_v=collections.Counter(x['vyd'] for x in V['A_sonnet_1'])
def ots(flag):
    c=collections.Counter(); 
    for i,x in enumerate(V['A_sonnet_1']):
        if flag(i): c[x['vyd']]+=1
    return round(sum(vsi[t]*c[t]/po_v[t] for t in po_v))
pr=lambda n,i: V[n][i]['rishennia']=='проблема'
out={}
for n in V: out[n]=ots(lambda i,n=n: pr(n,i))
out['Sonnet×2 обидва']=ots(lambda i: pr('A_sonnet_1',i) and pr('B_sonnet_2',i))
out['Sonnet+Opus обидва']=ots(lambda i: pr('A_sonnet_1',i) and pr('C_opus',i))
out['більшість з 3 Sonnet (S0,A,B)']=ots(lambda i: sum(pr(n,i) for n in ('S0_183','A_sonnet_1','B_sonnet_2'))>=2)
out['усі 4']=ots(lambda i: all(pr(n,i) for n in V))
out['хоч один з 4']=ots(lambda i: any(pr(n,i) for n in V))
# друга перевірка — кому: «проблема» або частка ≥ 0,35
dr=sum(1 for x in V['A_sonnet_1'] if x['rishennia']=='проблема' or (x.get('chastka') or 0)>=0.35)
out['частка вибірки на другу перевірку']=round(dr/len(V['A_sonnet_1']),2)
# зважена частка на місто (за видами)
c=collections.Counter(x['vyd'] for x in V['A_sonnet_1'] if x['rishennia']=='проблема' or (x.get('chastka') or 0)>=0.35)
out['запитів на другу перевірку (Київ)']=round(sum(vsi[t]*c[t]/po_v[t] for t in po_v))
print(json.dumps(out,ensure_ascii=False,indent=1))
for n,r in R.items(): print(n, r['stat'])
json.dump(out,open('/home/user/work/z187/otsinky.json','w'),ensure_ascii=False,indent=1)

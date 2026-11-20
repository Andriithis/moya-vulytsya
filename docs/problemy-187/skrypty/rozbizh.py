import json, collections
norm=lambda r: 'скупчення' if r=='вада' else r
R={n: json.load(open(f'/home/user/work/z187/zghoda-{n}.json'))['vidpovidi'] for n in ('A_sonnet_1','B_sonnet_2','C_opus')}
out=[]
for i in range(len(R['A_sonnet_1'])):
    rr={n:R[n][i] for n in R}
    if len({norm(v['rishennia']) for v in rr.values()})>1:
        a=rr['A_sonnet_1']
        out.append(dict(vyd=a['vyd'], mistse=a['mistse'], n=a['n'], **{n:dict(r=v['rishennia'], ch=v['chastka'], nz=(v['shi'] or v['spilne'] or '')[:150], zn=(v['znizheno'] or '')[:120], vady=v['vady']) for n,v in rr.items()}))
print(len(out))
for o in out:
    print(f"\n## {o['vyd']} | {o['mistse']} | n={o['n']}")
    for n in R: print('  ',n, o[n]['r'], o[n]['ch'], '|', o[n]['nz'], '|', o[n]['zn'], o[n]['vady'] or '')
json.dump(out, open('/home/user/work/z187/rozbizhnosti.json','w'), ensure_ascii=False, indent=1)

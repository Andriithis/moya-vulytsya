import json, collections, math
I = json.load(open('/home/user/work/k185/krytyk.json'))
def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z*z/n; c = p + z*z/(2*n); r = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return round((c - r)/d, 3), round((c + r)/d, 3)
for g in ('проблема', 'скупчення', 'не пройшло сито'):
    xs = [i for i in I if i['grupa'] == g]
    kr = collections.Counter((i['krytyk'] or {}).get('spravzhnia') for i in xs)
    fin = collections.Counter()
    for i in xs:
        if i['zgoda']: s = 'так' if g == 'проблема' else 'ні'
        else: s = (i.get('rozbir') or {}).get('spravzhnia')
        i['pidsumok'] = s; fin[s] += 1
    print(g, len(xs), 'критик:', dict(kr), 'підсумок після розбору:', dict(fin))
    pr = collections.Counter((i.get('rozbir') or {}).get('pravyi') for i in xs if not i['zgoda'])
    print('   хто правий у спірних:', dict(pr))
    print('   причини:', collections.Counter((i.get('rozbir') or {}).get('prychyna') for i in xs if not i['zgoda'] and (i.get('rozbir') or {}).get('pravyi') != 'метод').most_common())
    print('   за видами (так/усіх):', {v: f"{sum(i['pidsumok']=='так' for i in xs if i['vyd']==v)}/{sum(1 for i in xs if i['vyd']==v)}" for v in sorted({i['vyd'] for i in xs})})
pp = [i for i in I if i['grupa'] == 'проблема']; k = sum(i['pidsumok'] == 'так' for i in pp)
print('точність', k, len(pp), wilson(k, len(pp)))
for g in ('скупчення', 'не пройшло сито'):
    xs = [i for i in I if i['grupa'] == g]; k = sum(i['pidsumok'] == 'так' for i in xs); print('пропущено', g, k, len(xs), wilson(k, len(xs)))
oz = collections.Counter(k for i in I for k, v in ((i['krytyk'] or {}).get('oznaky') or {}).items() if v)
print('ознаки критика', oz)
json.dump(I, open('/home/user/work/k185/krytyk.json', 'w'), ensure_ascii=False, indent=1)

import sys, pickle, collections, re
sys.path.insert(0, '/home/user/d103/src')
import problemy_varianty as PV
kand = pickle.load(open('/home/user/work/kand1.pkl','rb'))
po = collections.defaultdict(list)
for k in kand:
    if k.get('riven') != 'ділянка': po[k['sim']].append(k)
blyz = []; c = collections.Counter()
for sim, ks in po.items():
    for i, a in enumerate(ks):
        for b in ks[i+1:]:
            d = PV.vidstan((a['lat'], a['lon']), (b['lat'], b['lon']))
            if d < 150:
                same = re.sub(r',.*', '', a['mistse']) == re.sub(r',.*', '', b['mistse'])
                plo = bool(re.search(r'площ|перехрест|ст\. м', a['mistse'] + b['mistse']))
                c[('<150 м', 'одна назва' if same else 'різні назви', 'площа/перехрестя/метро' if plo else 'будинки')] += 1
                if plo and len(blyz) < 12: blyz.append((sim, a['mistse'], b['mistse'], round(d)))
print(sum(len(v) for v in po.values()), c)
for x in blyz: print(x)

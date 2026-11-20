# ZAVDANNYA-187 п.1: оцінка проблем для кожного варіанта сита. Суворіші варіанти — частка «проблем» серед кандидатів
# вибірки 183 (повтор, Sonnet), що лишаються у варіанті; м'якші — плюс частка серед доданих кандидатів (вибірка, Sonnet).
import sys, os, json, pickle, collections, hashlib
sys.path.insert(0, '/home/user/d103/src'); sys.path.insert(0, '/home/user/d103/perevirka')
import problemy_shi as PS, problemy_183 as K
KL = pickle.load(open('/home/user/work/out/chutlyvist.json.kliuchi.pkl', 'rb'))
KK = pickle.load(open('/home/user/work/out/chutlyvist.json.kand.pkl', 'rb'))
rez = json.load(open('/home/user/work/out/chutlyvist.json'))
kal = json.load(open('/home/user/work/k183/problemy-183.json'))
vyb = {x['id']: x for x in kal['vidpovidi'] if not x.get('dodatkovyi')}
BAZ = 'базовий (8 кв., 5 подій, 3 кв., 40/60 м, P 0,05, 1 справа)'
baza = {k for k, _ in KL[BAZ]}
h = lambda s: hashlib.sha256(s.encode()).hexdigest()
instr = open(PS.INSTRUKTSIIA, encoding='utf-8').read()
vk = PS.Vyklyky('/home/user/work/k183/kesh', 8, lambda *x: print(*x, flush=True))
out = {}
for nazva, kl in KL.items():
    ks = {k for k, _ in kl}; po_v = collections.Counter(v for _, v in kl)
    if not (ks & baza) or len(ks & baza) < 0.5 * len(baza):
        out[nazva] = None; continue
    # частка серед вибірки, що лишилась у варіанті
    sh = collections.defaultdict(lambda: [0, 0])
    for i, x in vyb.items():
        if i in ks: sh[x['vyd']][0] += 1; sh[x['vyd']][1] += x['rishennia'] == 'проблема'
    vsi_p = sum(v[1] for v in sh.values()) / max(sum(v[0] for v in sh.values()), 1)
    dod = [k for k in KK[nazva] if PS.kliuch(k) not in baza]
    zal = sum(po_v[t] * (sh[t][1] / sh[t][0] if sh[t][0] else vsi_p) for t in po_v if True) - \
          sum((sh[K.vyd(k)][1] / sh[K.vyd(k)][0] if sh[K.vyd(k)][0] else vsi_p) for k in dod)
    marzha = None
    if len(dod) >= 50 and len(ks & baza) > 0.9 * len(baza):
        # вибірка доданих: 30 пропорційно за видами, сталий вибір
        po = collections.defaultdict(list)
        for k in dod: po[K.vyd(k)].append(k)
        for v in po.values(): v.sort(key=lambda k: h(PS.kliuch(k)))
        kv = {t: max(1, round(30 * len(v) / len(dod))) for t, v in po.items()}
        vb = [k for t, v in po.items() for k in v[:kv[t]]]
        for k in vb: k['zriz'] = '2026-11-10'
        zz = [PS.zapyt(k, instr) for k in vb]
        tt = vk('sonnet', [q['tekst'] for q in zz], f'додані: {nazva}')
        rr = []
        for k, q, t in zip(vb, zz, tt):
            v, vady = PS.pereviryty(t, q); rr.append('вада' if vady else (v or {}).get('rishennia'))
        c = collections.Counter(rr); m = len(rr)
        marzha = dict(dodano=len(dod), vybirka=m, problem=c['проблема'], chastka=round(c['проблема'] / m, 3))
        dod_est = len(dod) * c['проблема'] / m
    else:
        dod_est = sum((sh[K.vyd(k)][1] / sh[K.vyd(k)][0] if sh[K.vyd(k)][0] else vsi_p) for k in dod)
    out[nazva] = dict(kandydativ=len(ks), spilnykh_z_bazovym=len(ks & baza), dodano=len(dod), vybirky_u_varianti=sum(v[0] for v in sh.values()),
                      problem_otsinka=round(zal + dod_est), marzha=marzha)
    print(nazva, out[nazva], flush=True)
json.dump(out, open('/home/user/work/out/marzha.json', 'w'), ensure_ascii=False, indent=1)

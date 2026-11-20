import sys, time, pickle, json, hashlib
sys.path.insert(0, '/home/user/d103/src')
import problemy_varianty as PV, problemy_shi as PS
B = pickle.load(open('/home/user/work/baza.pkl','rb'))
t=time.time()
z = PV.kandydaty_183(B['evs'], B['P'], B['S'])
kand = sorted(PS.bez_chutlyvykh(z['kandydaty'] + z['dilianky']), key=lambda k: (-k['n'], PS.kliuch(k)))
for k in kand: k['zriz']=B['S']
print(len(kand), time.time()-t)
h = hashlib.sha256(json.dumps([(PS.kliuch(k), k['n'], k['roky_tekst'], [e['eid'] for e in k['s']['evs']]) for k in kand]).encode()).hexdigest()
print('hash', h)
pickle.dump(kand, open(sys.argv[1],'wb'))

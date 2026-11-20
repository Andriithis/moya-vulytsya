import sys, os, time, pickle, sqlite3
sys.path.insert(0, '/home/user/d103/src')
import problemy_varianty as PV
t=time.time()
con = sqlite3.connect('file:/home/user/data/events.db?mode=ro', uri=True)
S = PV.zriz(con); evs = PV.podii(con); con.close()
print('zriz', S, 'podii', len(evs), time.time()-t, flush=True)
P = PV.pary(evs)
print('par', len(P), time.time()-t, flush=True)
pickle.dump(dict(S=S, evs=evs, P=P), open('/home/user/work/baza.pkl','wb'))
print('ok', time.time()-t)

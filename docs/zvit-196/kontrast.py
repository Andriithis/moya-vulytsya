# Контраст кольорів 9 виглядів ZAVDANNYA-196 за формулою WCAG 2.1 (кольори — з docs/makety-193/kod/styli.py).
import sys,re
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'makety-193', 'kod'))
from styli import S
def lum(h):
    h=h.lstrip('#'); 
    if len(h)==3: h=''.join(c*2 for c in h)
    c=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    c=[x/12.92 if x<=0.03928 else ((x+0.055)/1.055)**2.4 for x in c]
    return .2126*c[0]+.7152*c[1]+.0722*c[2]
def cr(a,b):
    la,lb=sorted([lum(a),lum(b)],reverse=True); return (la+.05)/(lb+.05)
def vars_(css,sel):
    m=re.search(re.escape(sel)+r'\{([^}]*)\}',css); d={}
    if m:
        for k,v in re.findall(r'--([\w-]+):(#[0-9A-Fa-f]{3,6})',m.group(1)): d[k]=v
    return d
print('стиль | ink/tlo | ink/surface | ink-2/tlo | muted/tlo | muted/surface | akcent/tlo | на-акценті/akcent | pidpys/карта | сота1/карта | сота5/карта')
for k,s in S.items():
    v=vars_(s['css'],':root'); kt=s['karta']['pidkladka']['tlo']; r=s['karta']['ramp']
    ink=v.get('ink'); 
    row=[cr(ink,v['tlo']),cr(ink,v['surface']),cr(v.get('ink-2',ink),v['tlo']),cr(v['muted'],v['tlo']),cr(v['muted'],v['surface']),cr(v['akcent'],v['tlo']),cr(v.get('na-akcenti','#FFFFFF'),v['akcent']),cr(v['pidpys'],kt),cr(r[0],kt),cr(r[-1],kt)]
    print(k,'|',' | '.join(f'{x:.1f}' for x in row))
    if 'ink-strong' in v: print('   ink-strong/tlo',round(cr(v['ink-strong'],v['tlo']),1))
print()
# штрихи «Вектора · ночі» до тла карти
print('vektor-nich hatch/tlo', round(cr('#86837D','#121212'),1), 'hatchPik/tlo', round(cr('#EEEBE4','#121212'),1))
print('smila zhovta/chorna', round(cr('#FFD60A','#0A0A0A'),1))
print('chitka kobalt/sota4', round(cr('#1F4DFF','#4B4B46'),1))
print('nynishniy mint/sc4', round(cr('#31B88D','#4549A3'),1))

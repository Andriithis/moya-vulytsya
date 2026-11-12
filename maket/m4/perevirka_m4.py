"""Вимірювання для чек-листа (docs/DOSLIDZHENNIA-VYHLIADU.md, 37 пунктів) у справжньому браузері.

Запуск (сервер макета на 8740): python maket/m4/perevirka_m4.py
Друкує JSON: розміри цілей дотику, найменший шрифт, контраст тексту, час першого кадру, влучання кліку в 3D.
Браузер — Edge без вікна з програмним WebGL, тож час — оцінка зверху, не справжній телефон.
"""
from __future__ import annotations

import json
import random

from playwright.sync_api import sync_playwright

ADRESA = 'http://127.0.0.1:8740/m4/'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
ARGUMENTY = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']

JS_MIRKY = r"""() => {
 const lum = c => { const m = c.match(/[\d.]+/g).map(Number); const v = m.slice(0,3).map(x => { x/=255; return x<=.04045? x/12.92 : ((x+.055)/1.055)**2.4 });
   return .2126*v[0] + .7152*v[1] + .0722*v[2] };
 const tlo = el => { while (el) { const b = getComputedStyle(el).backgroundColor; const a = (b.match(/[\d.]+/g)||[]).map(Number);
   if (a.length===3 || (a.length===4 && a[3]>.9)) return b; el = el.parentElement } return getComputedStyle(document.body).backgroundColor };
 const vydymi = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none' };
 const tsili = [...document.querySelectorAll('button, input, a, [role=option]')].filter(vydymi).filter(e=>!e.closest('.maplibregl-ctrl-attrib-inner'));
 const male = tsili.map(e => { const r = e.getBoundingClientRect(); return {t:(e.getAttribute('aria-label')||e.textContent||e.id).trim().slice(0,24), w:Math.round(r.width), h:Math.round(r.height)} })
   .filter(x => x.w<44 || x.h<44);
 // найменший проміжок між сусідніми цілями
 let promizhok = 1e9;
 const rs = tsili.map(e => e.getBoundingClientRect());
 for (let i=0;i<rs.length;i++) for (let j=i+1;j<rs.length;j++) { const a=rs[i], b=rs[j];
   const dx = Math.max(0, Math.max(a.left,b.left) - Math.min(a.right,b.right)), dy = Math.max(0, Math.max(a.top,b.top) - Math.min(a.bottom,b.bottom));
   const d = Math.max(dx,dy); if (dx===0 && dy===0) continue; if ((dx===0||dy===0) && d<promizhok) promizhok = d }
 const teksty = [...document.querySelectorAll('body *')].filter(e => vydymi(e) && [...e.childNodes].some(n => n.nodeType===3 && n.textContent.trim()) && !e.closest('#map'));
 let minShryft = 99, minEl = '', minKontrast = 99, minKEl = '';
 for (const e of teksty) { const s = getComputedStyle(e), f = parseFloat(s.fontSize); if (f<minShryft) { minShryft=f; minEl=e.textContent.trim().slice(0,30) }
   const L1 = lum(s.color), L2 = lum(tlo(e)), k = (Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05);
   const velykyi = f>=24 || (f>=18.5 && +s.fontWeight>=700); const k2 = velykyi ? k*4.5/3 : k;
   if (k2<minKontrast) { minKontrast=k2; minKEl=e.textContent.trim().slice(0,30)+' '+k.toFixed(2) } }
 const p = document.getElementById('poshuk'), ps = getComputedStyle(p);
 return {male, promizhok, minShryft, minEl, minKontrast:+minKontrast.toFixed(2), minKEl,
   poshuk:{shryft:parseFloat(ps.fontSize), vysota:Math.round(document.getElementById('verkh').getBoundingClientRect().height)},
   viewport: document.querySelector('meta[name=viewport]').content,
   transitionAll: [...document.styleSheets].some(ss => { try { return [...ss.cssRules].some(r => /transition:\s*all/.test(r.cssText)) } catch(e){ return false } }) }
}"""


def main() -> None:
    rez = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=EDGE, args=ARGUMENTY)
        for v in 'abv':
            for ekran, (w, h) in {'pk': (1440, 900), 'telefon': (390, 844)}.items():
                k = b.new_context(viewport={'width': w, 'height': h}, is_mobile=ekran == 'telefon', has_touch=ekran == 'telefon')
                s = k.new_page()
                s.goto(f'{ADRESA}?v={v}')
                # перший кадр: від початку навігації до першого малювання карти
                s.wait_for_function('window.MAKET && MAKET.map && MAKET.map.loaded()', timeout=60000)
                persh = s.evaluate('performance.now()')
                s.wait_for_function('MAKET.stan.vyrosly', timeout=60000)
                ris = s.evaluate('performance.now()')
                mirky = s.evaluate(JS_MIRKY)
                # сота на першому екрані: діаметр 330 м у пікселях
                d_px = s.evaluate("""(()=>{const m=MAKET.map,c=m.getCenter(),a=m.project(c),b=m.project([c.lng+660/(111320*Math.cos(c.lat*Math.PI/180)),c.lat]);return Math.round(b.x-a.x)})()""")
                # пошук: підказки
                pidk = s.evaluate("MAKET.poshuk('Хрещ')")
                # Клік у 3D: на Подолі, 40 випадкових сот під камерою — чи відкриває картку саме тієї соти
                vluch = None
                if v != 'a' or True:
                    s.goto(f'{ADRESA}?v={v}#13.2/50.4655/30.5155/0/{0 if v=="a" else 50}')
                    s.wait_for_function('window.MAKET && MAKET.map && MAKET.map.loaded() && MAKET.stan.vyrosly', timeout=60000)
                    s.wait_for_timeout(800)
                    if v == 'a':
                        s.click('#f3d')
                        s.wait_for_timeout(1500)
                    tochky = s.evaluate("""(()=>{const m=MAKET.map,G=MAKET.HEXG[1],out=[],W=innerWidth,H=innerHeight;
                      for(const b of MAKET.HEXB.S.values()){if(!b.nf) continue; const ll=[b.cx/(111320*Math.cos(50.45*Math.PI/180)),b.cy/111320];
                       const p=m.project(ll); if(p.x>60&&p.x<W-60&&p.y>200&&p.y<H-60) out.push({k:b.k,x:p.x,y:p.y})} return out})()""")
                    random.seed(28)
                    vybir = random.sample(tochky, min(40, len(tochky)))
                    ok = pered = hub = 0
                    for t in vybir:
                        # клік у центр основи соти: має відкритись ця сота або стовпчик, що стоїть перед нею (ближче до камери)
                        r = s.evaluate("""(t=>{const h=MAKET.vluchannya({x:t.x,y:t.y},false); if(!h) return null;
                           const m=MAKET.map,p=m.project([h.b.cx/(111320*Math.cos(50.45*Math.PI/180)),h.b.cy/111320]); return {k:h.b.k,y:p.y}})""", t)
                        if r is None:
                            hub += 1
                        elif r['k'] == t['k']:
                            ok += 1
                        elif r['y'] > t['y']:
                            pered += 1
                        else:
                            hub += 1
                    vluch = {'sprob': len(vybir), 'tochno': ok, 'stovpchyk_pered_neyu': pered, 'zahubleno': hub}
                rez[f'{v}-{ekran}'] = {'pershyi_kadr_ms': round(persh), 'vyrosly_ms': round(ris), 'sota_330_px': d_px,
                                       'pidkazky': pidk, 'klik_3d_po_osnovi': vluch, **mirky}
                k.close()
        b.close()
    print(json.dumps(rez, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()

import sys, json, pickle, collections, re
sys.path.insert(0, '/home/user/d103/src')
import problemy_varianty as PV, problemy_shi as PS, mech as M
I=json.load(open('/home/user/work/k185/krytyk.json'))
# ознаки критика з рішенням методу
for f in ('odna_seriia','reid','ustanova','ne_tut','mezhi','fon_mista'):
    xs=[i for i in I if ((i['krytyk'] or {}).get('oznaky') or {}).get(f)]
    print(f, len(xs), [(i['grupa'], i['sim'], i['mistse'][:30], (i['krytyk'] or {}).get('spravzhnia')) for i in xs][:8])
print('рейд (≥2 події в одну дату):', [(i['grupa'], i['mistse'], i['oz']['maks_data']) for i in I if i['oz']['maks_data']>1])
print('одна справа ≥2:', [(i['grupa'], i['mistse'], i['oz']['maks_sprava']) for i in I if i['oz']['maks_sprava']>1])
# статус проблем і тренд міста
for i in I:
    if i['grupa']!='проблема': continue
    st=(i['metod'].get('stan') or {})
    if st.get('status')=='згасла' and (i['oz']['misto_teper_do_piku'] or 9)<0.6: print('згасла при падінні міста', i['sim'], i['mistse'], st.get('roky_tekst'), i['oz']['misto_teper_do_piku'])
st=collections.Counter((i['metod'].get('stan') or {}).get('status') for i in I if i['grupa']=='проблема'); print(st)
# свіжість: «згасла», остання подія картини — в останні 3 роки до зрізу
for i in I:
    if i['grupa']=='проблема' and (i['metod'].get('stan') or {}).get('status')=='згасла' and i['oz']['ostannia']>='2023-11':
        print('згасла, але остання подія свіжа', i['sim'], i['mistse'], i['metod']['stan'].get('roky_tekst'), i['oz']['ostannia'])

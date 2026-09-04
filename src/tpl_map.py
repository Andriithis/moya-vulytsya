# -*- coding: utf-8 -*-
"""Карта й шари: перша половина клієнтського JavaScript.

Тут: підстановка даних (__META__, __PTS__, __RISKS__, __POP__, __FACTS__),
створення карти Leaflet, підкладка й шари — населення, потоки, ризики,
чинники середовища, теплова карта — і підсвітка «що поруч».

Функції: $ify, showNear, showAllNear, drawFacts, riskPopup, drawRisks.
Друга половина (бічна панель, спливні вікна, картка проблеми) — у tpl_popup.
"""
JS_MAP = r"""const M=__META__, P=__PTS__;
// 8 кольорів — по одному на кожну тему з labels.ORDER (ГП..ДОМ). Було 7 на 8
// тем: домашнє насильство (індекс 7) отримувало через %7 той самий колір,
// що й громадський порядок (індекс 0) — на карті їх було не відрізнити.
const PALA=['#e0533d','#e8a33d','#8b5cf6','#ef4444','#3b82f6','#22c55e','#14b8a6','#ec4899'];
const CATTH={};M.groups.forEach((g,gi)=>g[1].forEach(i=>CATTH[i]=gi));
// Повна назва статті з кодексу за коротким підписом (src/pravo.py).
// Порожньо, якщо назви немає: приблизна назва в листі гірша за її відсутність.
const LAW=s=>(M.law&&M.law[s])||'';
const R=__RISKS__, POP=__POP__, F=__FACTS__;
// Справи адрес для правої панелі лежать у файлах spravy/<район>.json поруч
// зі сторінкою. Панель тягне свій файл тоді, коли її відкривають уперше.
const DOCCACHE={};
// Потоки приїжджають стисло: геометрія кожного відрізка лежить один раз у
// R.geo, а шари несуть тільки номер відрізка й число. Розгортаємо тут-таки,
// щоб решта коду працювала як раніше.
if(R.geo) Object.values(R.lines||{}).forEach(v=>{
 if(v.g) v.items=v.items.map(x=>[R.geo[x[0]][0], R.geo[x[0]][1], x[1]]);
});
const map=L.map('map',{preferCanvas:true}).setView(M.center||[50.45,30.52],M.only?13:11);
map.createPane('popPane'); map.getPane('popPane').style.zIndex=350;
map.createPane('maskPane'); map.getPane('maskPane').style.zIndex=345;
if(M.bounds){
 const b=L.latLngBounds(M.bounds);
 map.fitBounds(b,{padding:[24,24]});
 // за межі району не випускаємо: запас ~10% від розміру району
 const dy=(M.bounds[1][0]-M.bounds[0][0])*0.10, dx=(M.bounds[1][1]-M.bounds[0][1])*0.10;
 const lim=L.latLngBounds([M.bounds[0][0]-dy,M.bounds[0][1]-dx],
                          [M.bounds[1][0]+dy,M.bounds[1][1]+dx]);
 map.setMaxBounds(lim);
 map.setMinZoom(map.getBoundsZoom(lim));
}
// Зовнішня рамка затемнення. Раніше тут стояв нерухомий прямокутник на весь
// світ (довготи -360..360). Полотно Leaflet обрізає такий багатокутник, і на
// широкому екрані ліворуч та вгорі лишалася незатемнена смуга — видно на
// живому сайті. Тепер рамка будується від поточного вигляду з добрим запасом
// і перебудовується під час руху карти.
function maskRing(){
 const b=map.getBounds().pad(2.5);
 return [[b.getSouth(),b.getWest()],[b.getSouth(),b.getEast()],
         [b.getNorth(),b.getEast()],[b.getNorth(),b.getWest()]];
}
if(M.border){
 let mk=L.polygon([maskRing(),M.border],{pane:'maskPane',color:'#0f1117',weight:0,
   fillColor:'#0f1117',fillOpacity:.82,interactive:false}).addTo(map);
 map.on('moveend zoomend',()=>mk.setLatLngs([maskRing(),M.border]));
 L.polygon(M.border,{color:'#6b7890',weight:1.8,opacity:.9,
   fill:false,dashArray:'6,5',interactive:false}).addTo(map);
}
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
{attribution:'&copy; OpenStreetMap',maxZoom:19}).addTo(map);
let layer=L.layerGroup().addTo(map),heat=null,heatOn=false;
const rlayer=L.layerGroup().addTo(map);
const poplayer=L.layerGroup();          // фон під усім іншим
const flayer=L.layerGroup().addTo(map); // чинники середовища за чекбоксами
const hlayer=L.layerGroup().addTo(map); // підсвітка «чинники поруч» для конкретного місця
// ---- РАЙОНИ В МЕЖАХ ОДНОГО ФАЙЛУ ----
// Міська карта несе межі всіх десяти районів і їхні власні переліки проблем.
// Клік по району не веде на інший файл: карта під'їжджає, затемнює решту
// міста й перемикає панель. Фільтри при цьому лишаються — раніше вони гинули
// разом із перезавантаженням сторінки.
const DN=M.dnames||[], DBORD=M.borders||[], DSLUG=M.dslug||[];
let CURD=-1;                       // -1 = все місто, інакше індекс району
// Клік по вікні проблеми, коли воно відкрите, мав закривати саме вікно — а
// закривав вікно (стандартна поведінка Leaflet) І одночасно відкривав район,
// бо межі району клікабельні майже по всій площі міста. Перший клік «повз»
// відкрите вікно тепер лише закриває його; район відкриє вже наступний клік.
let popupWasOpen=false;
map.on('preclick',()=>{popupWasOpen=!!map._popup});
let dmask=null;
const dlayer=L.layerGroup().addTo(map);
const dshapes=[];
const CITY={c:M.center||[50.45,30.52], z:11};
const dBounds=i=>L.latLngBounds(DBORD[i]);
if(DN.length&&!M.only) DN.forEach((nm,i)=>{
 const pg=L.polygon(DBORD[i],{color:'#9fb0c9',weight:1.8,opacity:.85,dashArray:'7,5',
   fillColor:'#8ea0bd',fillOpacity:.05});
 const np=(M.dprob||[])[i]||0;
 pg.bindTooltip(`<b>${nm}</b><span>`+(np?`${np} проблем · `:'')+`натисніть, щоб відкрити</span>`,
   {className:'rt',sticky:true});
 pg.on('mouseover',()=>{if(CURD<0)pg.setStyle({fillOpacity:.13,opacity:.9})});
 pg.on('mouseout', ()=>{if(CURD<0)pg.setStyle({fillOpacity:.04,opacity:.45})});
 pg.on('click',    ()=>{if(popupWasOpen){popupWasOpen=false;return}if(CURD<0)enterDistrict(i)});
 pg.addTo(dlayer); dshapes.push(pg);
});
// Межі решти районів у вибраному районі гасимо, а не ховаємо: під затемненням
// вони все одно не читаються, зате перемикання лишається однією дією.
function paintScope(){
 dshapes.forEach((pg,i)=>pg.setStyle(CURD<0
   ? {opacity:.85,fillOpacity:.05,dashArray:'7,5'}
   : {opacity:i===CURD?1:0,fillOpacity:0,dashArray:null}));
 if(dmask){map.removeLayer(dmask);dmask=null}
 if(CURD>=0){
  dmask=L.polygon([maskRing(),DBORD[CURD]],{pane:'maskPane',color:'#0f1117',weight:0,
    fillColor:'#0f1117',fillOpacity:.78,interactive:false}).addTo(map);
 }
}
// рамка затемнення має встигати за картою, інакше при від'їзді з'являються
// незатемнені краї
map.on('moveend zoomend',()=>{if(dmask)dmask.setLatLngs([maskRing(),DBORD[CURD]])});
function enterDistrict(i,fly){
 if(!(i>=0&&i<DN.length)) return;
 CURD=i; paintScope();
 if(fly===false) map.fitBounds(dBounds(i),{padding:[28,28]});
 else map.flyToBounds(dBounds(i),{padding:[28,28],duration:1.15,easeLinearity:.22});
 if(location.hash.slice(1)!==DSLUG[i]) history.replaceState(null,'','#'+DSLUG[i]);
 onScopeChange();
}
function exitDistrict(){
 CURD=-1; paintScope();
 map.flyTo(CITY.c,CITY.z,{duration:1.0});
 history.replaceState(null,'',location.pathname+location.search);
 onScopeChange();
}
window.addEventListener('hashchange',()=>{
 const i=DSLUG.indexOf(decodeURIComponent(location.hash.slice(1)).toLowerCase());
 if(i>=0){if(i!==CURD)enterDistrict(i)} else if(CURD>=0)exitDistrict();
});
const FCOL=['#f59e0b','#38bdf8','#a3a3a3'];   // притягують / збирають людей / стан
const FZOOM=14;                               // ближче за цей масштаб — показуємо позначки
const RCOL={metro:'#38bdf8',busstop:'#7dd3fc',
 flow_school:'#fbbf24',flow_transit:'#38bdf8',flow_shop:'#f472b6'};
// ризик успадковує колір своєї теми — той самий, що в подіях
Object.keys(R.lines||{}).forEach(k=>{if(k.startsWith('risk_'))RCOL[k]=PALA[(R.lines[k].theme||0)%PALA.length]});;
if(M.skew) $ify('#skew', `<div class="skew">${M.skew}</div>`);
function $ify(sel,html){const el=document.querySelector(sel);if(el)el.innerHTML=html}
{
 // --- прогноз ризику ---
 let rh='';
 const rkeys=Object.keys(R.lines||{}).filter(k=>k.startsWith('risk_'))
   .sort((a,b)=>R.lines[b].hit-R.lines[a].hit);
 // Один рядок панелі. Ключ — тема ('risk_ДОР') або механізм ('risk_ДОР_ДТП').
 const rrow=k=>{const v=R.lines[k],c=RCOL[k];
  if(v.nodata){
   // тема є в списку правопорушень, але подій замало на навчання моделі
   return `<div class="rw nod" style="border-left-color:#3a4256">
    <label class="rl"><input type="checkbox" disabled>
     <span class="sw" style="background:#3a4256"></span>
     <span class="nm">${v.title}</span>
     <span class="acc">—</span></label>
    <div class="why">замало подій для навчання моделі</div></div>`}
  return `<div class="rw" style="border-left-color:${c}">
   <label class="rl"><input type="checkbox" data-r="${k}">
    <span class="sw" style="background:${c}"></span>
    <span class="nm">${v.title}</span>
    <span class="acc">${v.hit}%</span></label>
   ${v.why?`<div class="why">${v.why}</div>`:''}</div>`};
 // Механізмів більше, ніж тем, тож панель згорнута: тема -> її механізми.
 const grp={};
 rkeys.forEach(k=>{const g=R.lines[k].group||R.lines[k].title;(grp[g]=grp[g]||[]).push(k)});
 Object.keys(grp).sort((a,b)=>
   Math.min(...grp[a].map(k=>R.lines[k].theme|0))-Math.min(...grp[b].map(k=>R.lines[k].theme|0))
 ).forEach(g=>{
  const ks=grp[g].sort((a,b)=>
    ((R.lines[a].kind==='theme')?0:1)-((R.lines[b].kind==='theme')?0:1)
    ||R.lines[b].hit-R.lines[a].hit);
  if(ks.length<2){rh+=rrow(ks[0]);return}
  rh+=`<details class="rg"><summary><span class="gn">${g}</span>
   <span class="gc">${ks.length}</span></summary>${ks.map(rrow).join('')}</details>`});
 if(rkeys.length) rh+=`<div class="lgd" style="color:${RCOL[rkeys[0]]}"><span>менший</span><i></i><span>більший</span></div>`;
 $ify('#frisk',rh);

 // --- контекст ---
 let ch='';
 if(POP.length) ch+=`<label><input type="checkbox" data-r="pop">
   <span class="sw" style="background:#3b4a63"></span><span>Щільність населення</span>
   <span class="n">${POP.length.toLocaleString('uk')}</span></label>`;
 ['flow_school','flow_transit','flow_shop'].forEach(k=>{const v=R.lines&&R.lines[k];if(!v)return;
  ch+=`<label><input type="checkbox" data-r="${k}">
   <span class="sw" style="background:${RCOL[k]}"></span><span>${v.title}</span>
   <span class="n">${v.items.length.toLocaleString('uk')}</span></label>`});
 $ify('#fctx',ch);

 // --- середовище: чинники, згруповані за роллю ---
 let ff='';
 (F.cats||[]).forEach((c,ci)=>c._i=ci);
 (F.groups||[]).forEach((gn,gi)=>{
  const inG=(F.cats||[]).filter(c=>c.g===gi&&c.pts.length);
  if(!inG.length) return;
  ff+=`<div class="fgh">${gn}</div>`;
  inG.forEach(c=>{ff+=`<label><input type="checkbox" data-f="${c._i}">
    <span class="sw" style="background:${FCOL[gi]}"></span><span>${c.n}</span>
    <span class="n">${c.pts.length.toLocaleString('uk')}</span></label>`});
 });
 $ify('#ffact',ff||'<div class="sub">шар чинників недоступний</div>');
 $ify('#fhint','Об’єкти, які модель рахує як чинники ризику. З’являються від масштабу '+
   FZOOM+' — інакше карта нечитабельна.'+
   ' У картці проблеми та у вікні ризикованої вулиці є кнопка «Показати чинники '+
   'поруч» — вона підсвічує саме ті об’єкти, що дали цьому місцю ризик. '+
   'Кнопка «Що поруч» у вікні будь-якої адреси показує все в радіусі 250 м, '+
   'без підказки моделі: які з цих об’єктів справді пояснюють скупчення — '+
   'визначаєте ви.');
}
// підсвічує об'єкти, які модель порахувала для конкретної точки, з колами радіусів
function showNear(la,lo,factors){
 hlayer.clearLayers();
 if(!(F.cats||[]).length||!factors||!factors.length) return 0;
 const need={};
 factors.forEach(f=>String(f[0]).split(' × ').forEach(part=>{
  const m=part.match(/^(.+)_(\d+)м$/);
  if(m) need[m[1]]=Math.max(need[m[1]]||0,+m[2]);
 }));
 const my=111320, mx=111320*Math.cos(la*Math.PI/180);
 const rads=new Set(); let shown=0;
 Object.keys(need).forEach(base=>{
  const c=F.cats.find(x=>x.b===base); if(!c) return;
  const rad=need[base]; rads.add(rad);
  c.pts.forEach(p=>{
   const d=Math.hypot((p[0]-la)*my,(p[1]-lo)*mx);
   if(d>rad) return;
   shown++;
   L.circleMarker(p,{radius:6,weight:2,color:'#fbbf24',
     fillColor:FCOL[c.g],fillOpacity:.95})
    .bindTooltip(`${c.n} — ${Math.round(d)} м`,{className:'rt'}).addTo(hlayer)});
 });
 rads.forEach(r=>L.circle([la,lo],{radius:r,color:'#fbbf24',weight:1,opacity:.45,
   fill:false,dashArray:'4,4',interactive:false}).addTo(hlayer));
 L.circleMarker([la,lo],{radius:5,weight:2,color:'#fbbf24',
   fillColor:'#fbbf24',fillOpacity:1,interactive:false}).addTo(hlayer);
 return shown;
}
// те саме, але БЕЗ підказки моделі: просто все, що є довкола в заданому радіусі.
// Для слухачів — це спостереження, а не готова відповідь: які саме з цих об'єктів
// пояснюють скупчення, вони мають визначити самі.
function showAllNear(la,lo,rad){
 hlayer.clearLayers();
 if(!(F.cats||[]).length) return 0;
 const my=111320, mx=111320*Math.cos(la*Math.PI/180);
 let shown=0;
 F.cats.forEach(c=>c.pts.forEach(p=>{
  const d=Math.hypot((p[0]-la)*my,(p[1]-lo)*mx);
  if(d>rad) return;
  shown++;
  L.circleMarker(p,{radius:6,weight:2,color:'#fbbf24',
    fillColor:FCOL[c.g],fillOpacity:.95})
   .bindTooltip(`${c.n} — ${Math.round(d)} м`,{className:'rt'}).addTo(hlayer)}));
 L.circle([la,lo],{radius:rad,color:'#fbbf24',weight:1,opacity:.45,
   fill:false,dashArray:'4,4',interactive:false}).addTo(hlayer);
 L.circleMarker([la,lo],{radius:5,weight:2,color:'#fbbf24',
   fillColor:'#fbbf24',fillOpacity:1,interactive:false}).addTo(hlayer);
 return shown;
}
function drawFacts(){
 flayer.clearLayers();
 const zo=map.getZoom()<FZOOM;
 const el=document.querySelector('#fzoom');
 const on=[...document.querySelectorAll('[data-f]')].some(x=>x.checked);
 if(el) el.textContent = (zo&&on) ? 'Наблизьте карту, щоб побачити позначки' : '';
 if(zo) return;
 const b=map.getBounds();
 document.querySelectorAll('[data-f]').forEach(cb=>{
  if(!cb.checked) return;
  const c=F.cats[+cb.dataset.f]; if(!c) return;
  const col=FCOL[c.g];
  c.pts.forEach(p=>{
   if(!b.contains(p)) return;
   L.circleMarker(p,{radius:4,weight:1,color:'#0f1117',fillColor:col,fillOpacity:.9})
    .bindTooltip(c.n,{className:'rt'}).addTo(flayer)});
 });
}
function riskPopup(k,it){
 const v=R.lines[k];
 let h=`<div class="rpop"><b>${it[1]}</b><span class="sub">${v.title} — верхні ${101-it[2]}% за ризиком</span>`;
 if(v.method) h+=`<div class="rmeth">${v.method}</div>`;
 if(v.factors&&v.factors.length){
  h+='<table>'+v.factors.map(f=>`<tr><td>${f[0]}</td><td>+${f[1]}</td></tr>`).join('')+'</table>';
 }
 // відсилка на документ дослідження. Викладачеві — одразу на рядок цієї вулиці
 // (?st= підсвічує його й прокручує туди), слухачеві — на методику теми:
 // поіменного переліку в його версії документа немає.
 const an=v.slug?('#t-'+v.slug):'';
 h+=`<a class="rdoc" href="doslidzhennya.html${(it[1]&&it[1]!=='без назви')?('?st='+encodeURIComponent(it[1])):''}${an}" target="_blank" rel="noopener">Розбір вулиці в дослідженні ↗</a>`;
 h+='</div>';
 return h;
}
function drawRisks(){
 rlayer.clearLayers();
 const pc=document.querySelector('[data-r="pop"]');
 if(pc&&pc.checked){
  if(!map.hasLayer(poplayer)){
   if(!poplayer.getLayers().length){
    const mx=Math.max(...POP.map(p=>p[2]));
    POP.forEach(p=>L.circleMarker([p[0],p[1]],{pane:'popPane',
      radius:5+16*Math.sqrt(p[2]/mx),weight:0,fillColor:'#4b6fa8',
      fillOpacity:.10+.28*Math.sqrt(p[2]/mx)})
      .bindTooltip(`${p[2].toLocaleString('uk')} осіб`,{className:'rt',sticky:true})
      .addTo(poplayer));
   }
   poplayer.addTo(map); poplayer.bringToBack();
  }
 } else map.removeLayer(poplayer);

 document.querySelectorAll('[data-r]').forEach(cb=>{
  if(!cb.checked||cb.dataset.r==='pop') return;
  const k=cb.dataset.r, col=RCOL[k];
  if(!(R.lines&&R.lines[k])) return;
  const isRisk=k.startsWith('risk_'), v=R.lines[k];
  if(isRisk){
   // п.7.5: без теплового світіння (блокувало кліки) — самі лінії, товщі й клікабельні
   v.items.forEach(it=>
     L.polyline(it[0],{color:col,weight:Math.max(2,1.5+it[2]/16),
       opacity:Math.max(.35,.85*it[2]/100)})
      .bindTooltip(`<b>${it[1]}</b><span>${v.title} — верхні ${101-it[2]}% за ризиком, клікніть для деталей</span>`,
        {className:'rt',sticky:true})
      .on('click',ev=>{
        const w=document.createElement('div'); w.innerHTML=riskPopup(k,it);
        if(v.factors&&v.factors.length&&(F.cats||[]).length){
         const bt=document.createElement('button'); bt.className='pbtn2';
         bt.textContent='Показати чинники поруч';
         bt.onclick=()=>{const q=showNear(ev.latlng.lat,ev.latlng.lng,v.factors);
           bt.textContent=q?`Підсвічено об’єктів: ${q}`:'Поруч нічого з чинників немає'};
         w.appendChild(bt);
        } else if((F.cats||[]).length){
         // моделі для цієї вулиці немає — показуємо просто околиці, без підказки
         const bt=document.createElement('button'); bt.className='pbtn2';
         bt.textContent='Що поруч (250 м)';
         bt.onclick=()=>{const q=showAllNear(ev.latlng.lat,ev.latlng.lng,250);
           bt.textContent=q?`Показано об’єктів: ${q}`:'Поруч нічого не знайдено'};
         w.appendChild(bt);
        }
        L.popup({maxWidth:320}).setLatLng(ev.latlng).setContent(w).openOn(map)})
      .addTo(rlayer));
  } else {
   const mxf=Math.max(...v.items.map(x=>x[2]))||1;
   v.items.forEach(it=>
    L.polyline(it[0],{color:col,weight:Math.max(1.5,1+5*Math.sqrt(it[2]/mxf)),
      opacity:Math.max(.25,.75*Math.sqrt(it[2]/mxf))})
     .bindTooltip(`<b>${it[1]||'без назви'}</b><span>${v.title} — ~${it[2].toLocaleString('uk')} осіб</span>`+
       (v.when?`<span>${v.when}</span>`:''),{className:'rt',sticky:true}).addTo(rlayer));
  }
 });
}"""

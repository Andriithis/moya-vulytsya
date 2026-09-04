# -*- coding: utf-8 -*-
"""Бічна панель і спливні вікна: друга половина клієнтського JavaScript.

Тут: побудова прапорців і кнопок панелі, паспорт проблеми за SARA
(buildPassport, downloadPassport) і головна функція draw() — вона малює
позначки подій і збирає вміст спливних вікон, зокрема картку проблеми.

Правка картки проблеми чіпає лише цей файл.
Карта, шари й підсвітка — у tpl_map.
"""
JS_POPUP = r"""const $=s=>document.querySelector(s);
if(M.only){$('#subt').textContent=M.only+' район · за даними ЄДРСР';
 $('#backl').innerHTML='<a href="index.html" style="color:#e0533d;font-size:12px;text-decoration:none">← всі райони</a>';}
$('#fc').innerHTML=M.courts.map((n,i)=>`<label><input type="checkbox" data-c="${i}" checked>${n}</label>`).join('');
// На карті одного району перелік з усіх десяти районів безглуздий. Ховаємо
// саму рамку, а прапорці лишаємо в розмітці — на них спирається фільтр draw().
if(M.only){const w_=$('#fcw'); if(w_) w_.style.display='none';}
$('#fy').innerHTML=M.years.map((n,i)=>`<label><input type="checkbox" data-y="${i}" checked>${n}</label>`).join('');
const fmt=n=>n.toLocaleString('uk');
$('#fa').innerHTML=M.groups.map((g,gi)=>`<div class="gr" data-g="${gi}">
<div class="gh"><span class="ar">&#9656;</span><input type="checkbox" class="gt" data-gt="${gi}" checked>
<span class="nm">${g[0]}</span><span class="n">${fmt(g[2])}</span></div>
<div class="gb">`+g[1].map(i=>`<label><input type="checkbox" data-a="${i}" checked>
<span>${M.cats[i]}</span><span class="n">${fmt(M.counts[i])}</span></label>`).join('')+
`</div></div>`).join('');
document.querySelectorAll('.gh').forEach(el=>el.onclick=e=>{
 if(e.target.tagName==='INPUT')return; el.parentElement.classList.toggle('open')});
document.querySelectorAll('.gt').forEach(el=>el.onchange=()=>{
 M.groups[+el.dataset.gt][1].forEach(i=>{const b=document.querySelector(`[data-a="${i}"]`);if(b)b.checked=el.checked});
 draw()});
function syncThemes(){document.querySelectorAll('.gt').forEach(el=>{
 const ids=M.groups[+el.dataset.gt][1], on=ids.filter(i=>document.querySelector(`[data-a="${i}"]`).checked).length;
 el.checked=on>0; el.indeterminate=on>0&&on<ids.length})}
const PERIODS=[['Ранок','6–11',[6,7,8,9,10,11]],['День','12–17',[12,13,14,15,16,17]],
 ['Вечір','18–23',[18,19,20,21,22,23]],['Ніч','0–5',[0,1,2,3,4,5]]];
// Документи кроку 6. Версія одна, тож посилання однакові для всіх.
$ify('#docs',
 '<a href="doslidzhennya.html" target="_blank" rel="noopener">Дослідження ризиків ↗</a>'+
 '<a href="rezyume.html" target="_blank" rel="noopener">Резюме на одну сторінку ↗</a>'+
 '<a href="analiz.html" target="_blank" rel="noopener">Аналіз поточного стану ↗</a>');
// п.7.7: замість чотирьох кнопок категорій — лише "Усі" й "Тільки проблеми"
const CATS=[['Усі','подій ≥1','cA',-1],
            ['Тільки проблеми',`з відібраних ${M.n_problems||50}`,'c2',2]];
const cb_=$('#fcat');
CATS.forEach((c,i)=>{const sp=document.createElement('span');
 sp.className=c[2]+(i===0?' on':'');sp.innerHTML=`${c[0]}<i>${c[1]}</i>`;sp.dataset.c=c[3];cb_.appendChild(sp)});
cb_.onclick=e=>{const t=e.target.closest('[data-c]');if(!t)return;
 [...cb_.children].forEach(x=>x.classList.remove('on'));t.classList.add('on');draw()};
const CATNAME={2:['Проблема','#f87171','у кураторському списку'],0:null};
const hb=$('#hr');
PERIODS.forEach((p,i)=>{const s=document.createElement('span');
 s.innerHTML=`${p[0]}<i>${p[1]}</i>`;s.dataset.p=i;hb.appendChild(s)});
hb.onclick=e=>{const t=e.target.closest('[data-p]');if(t){t.classList.toggle('on');draw()}};
const sel=a=>new Set([...document.querySelectorAll(`[data-${a}]`)].filter(x=>x.checked).map(x=>+x.dataset[a]));
// ---- ПРАВА ПАНЕЛЬ: усі рішення адреси ----
// Витяг обставин і посилання на папери лежать окремо від сторінки: на сайті
// це файл spravy/<район>.json, який тягнемо, коли панель відкривають уперше.
// У сторінці, відкритій з диска, DOCS уже вкладено — тоді нічого не тягнемо.
const esc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>
 ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const REESTR='https://od.reyestr.court.gov.ua/files/';
const docUrl=h=>REESTR+h.slice(0,2)+'/'+h.slice(2)+'.rtf';
function docsFor(i){
 const sl=(M.dslug||[])[(P[i]||[])[8]]||'inshe';
 if(!DOCCACHE[sl]) DOCCACHE[sl]=fetch('spravy/'+sl+'.json')
   .then(r=>r.ok?r.json():{}).catch(()=>null);
 return DOCCACHE[sl].then(o=>o?(o[i]||[]):null);
}
function closePanel(){$('#pan').classList.remove('on')}
function openPanel(i){
 const p=P[i]; if(!p) return;
 $('#pan').classList.add('on');
 $('#panh').innerHTML='<button id="panx" title="Закрити">&times;</button>'+
  `<div class="pa">${esc(p[2]||'адреса не визначена')}</div>`+
  '<div class="ps">завантажую…</div>';
 $('#panx').onclick=closePanel;
 $('#panb').innerHTML='';
 docsFor(i).then(cs=>{
  if(cs===null){
   $('#panh').querySelector('.ps').textContent='перелік рішень недоступний';
   $('#panb').innerHTML='<div class="sub">Карту відкрито як файл із диска, а '+
     'перелік рішень лежить окремим файлом поруч — браузер такому файлу читати '+
     'сусідів не дозволяє. Відкрийте карту з сайту або запустіть '+
     '<b>PODYVYTYSYA.bat</b>.</div>';
   return;
  }
  // панель слухається тих самих фільтрів, що й карта: інакше в ній були б
  // рішення, яких на карті зараз не видно
  const A=sel('a'), Y=new Set([...sel('y')].map(k=>M.years[k]));
  const H=new Set(); hb.querySelectorAll('.on').forEach(x=>
    PERIODS[+x.dataset.p][2].forEach(h=>H.add(h)));
  const vis=cs.filter(c=>A.has(c[0])
    && (Y.has((c[1]||'').slice(0,4))||Y.has('раніше'))
    && (!H.size||H.has(c[2])));
  $('#panh').querySelector('.ps').textContent =
    vis.length===cs.length ? `${cs.length} ${cs.length===1?'справа':'справ'}`
    : `${vis.length} з ${cs.length} справ за поточним фільтром`;
  $('#panb').innerHTML = vis.length ? vis.map(c=>{
   // повну назву статті тут не повторюємо на кожному рядку — вона є в картці
   // проблеми й у підказці таблиці; тут важать дата, стаття й обставини
   return '<div class="cs">'+
    `<div class="cd" title="${esc(LAW(M.cats[c[0]]))}"><b>${esc(c[1]||'')}</b>${c[2]>=0?' · '+String(c[2]).padStart(2,'0')+':00':''} · ${esc(M.cats[c[0]])}</div>`+
    (c[3]?`<div class="cn">справа ${esc(c[3])}</div>`:'')+
    (c[5]?`<div class="cx">${esc(c[5])}</div>`:'')+
    ((c[4]||[]).length?'<div class="cl">'+c[4].map((h,k)=>
      `<a href="${docUrl(h)}" target="_blank" rel="noopener">${(c[4].length>1?'рішення '+(k+1):'відкрити рішення')}</a>`).join('')+'</div>':'')+
    '</div>';
  }).join('') : '<div class="sub">За поточним фільтром рішень немає.</div>';
 });
}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closePanel()});
// Що доречно для поточного вигляду. У місті — міський перелік проблем,
// у районі — перелік цього району. Район точки порахований у Python (p[8]),
// тому перемикання коштує одного порівняння чисел, а не геометрії.
const probsOf=p=>{const a=p[7]||[];
 return CURD<0?a.filter(q=>q.city):a.filter(q=>q.d===CURD&&q.loc)};
const inScope=p=>CURD<0||p[8]===CURD;
// Лічильники бічної панелі рахуються з того, що справді видно: у районі
// стояли б міські числа, а це та сама помилка, що вже виправлялася раніше.
function recount(){
 const c=new Array(M.cats.length).fill(0);
 for(const p of P){if(!inScope(p))continue;for(const e of p[4])c[e[1]]++}
 return c;
}
// Перелік районів у панелі. У щільному центрі клікнути по багатокутнику майже
// неможливо — його закривають позначки подій, тому головний шлях у район саме
// тут, а клік по карті лишається зручним доповненням.
if(DN.length&&!M.only){
 const dev=(M.dtheme||[]).map(o=>Object.values(o||{}).reduce((a,b)=>a+b,0));
 $('#fd').innerHTML=DN.map((n,i)=>{
  const np=(M.dprob||[])[i]||0;
  const sub=np?`${np} ${np===1?'проблема':'проблем'}`:(dev[i]?fmt(dev[i])+' подій':'');
  return `<span data-d="${i}">${n}<i>${sub}</i></span>`}).join('');
 $('#fd').onclick=e=>{const t=e.target.closest('[data-d]'); if(!t)return;
  const i=+t.dataset.d; if(i===CURD) exitDistrict(); else enterDistrict(i)};
}else{const w=$('#fdw'); if(w) w.style.display='none'}
function paintDistrictList(){
 document.querySelectorAll('#fd [data-d]').forEach(el=>
  el.classList.toggle('on', +el.dataset.d===CURD));
}
function onScopeChange(){
 if(M.only){draw();return}                    // окремий файл району — перемикати нічого
 paintDistrictList();
 const c=recount();
 document.querySelectorAll('[data-a]').forEach(inp=>{
  const n=inp.parentElement.querySelector('.n'); if(n)n.textContent=fmt(c[+inp.dataset.a])});
 document.querySelectorAll('.gt').forEach(inp=>{
  const g=M.groups[+inp.dataset.gt], n=inp.parentElement.querySelector('.n');
  if(n)n.textContent=fmt(g[1].reduce((a,i)=>a+c[i],0))});
 // Перелік районів за судом усередині району зайвий — як і в окремих файлах.
 {const w=$('#fcw'); if(w) w.style.display=CURD<0?'':'none';}
 if(CURD<0){
  $('#subt').textContent='за даними ЄДРСР · місто Київ';
  $('#backl').innerHTML='';
  $ify('#skew',M.skew?`<div class="skew">${M.skew}</div>`:'');
 }else{
  $('#subt').textContent=DN[CURD]+' район';
  $('#backl').innerHTML='<a href="#" class="upl">← усе місто</a>';
  $('#backl').querySelector('.upl').onclick=e=>{e.preventDefault();exitDistrict()};
  $ify('#skew',(M.dskew||[])[CURD]?`<div class="skew">${M.dskew[CURD]}</div>`:'');
 }
 const c2=cb_.querySelector('.c2');
 if(c2)c2.querySelector('i').textContent=CURD<0
   ?`з відібраних ${M.n_problems}`:`${(M.dprob||[])[CURD]||0} у цьому районі`;
 draw();
}
function buildPassport(p,pr){
 const today=new Date().toISOString().slice(0,10);
 let t=`# Паспорт проблеми (SARA)\n\n`;
 t+=`**Адреса:** ${p[2]||'не визначена'}\n`;
 t+=`**Механізм:** ${pr.mech}\n**Дата формування:** ${today}\n\n`;
 t+=`## Scanning\n\n`;
 t+=`- Подій за напрямком: **${pr.n}** (усього на адресі — ${pr.core_n})\n`;
 t+=`- Роки повторення: ${pr.years.join(', ')}\n`;
 t+=`- Склад:\n`+pr.arts.map(a=>{const ln=LAW(a[0]);
   return `    - ${a[0]} — ${a[1]}`+(ln?`\n      ${ln}`:'')}).join('\n')+`\n\n`;
 t+=`## Analysis\n\n`;
 if(pr.analysis){
  t+=`Адреса потрапляє у верхні ${100-pr.analysis.pc}% вулиць за прогнозом моделі для цієї теми `+
     `(влучність моделі ${pr.analysis.hit}%, навчання на ${pr.analysis.train}, перевірка на ${pr.analysis.test} подіях).\n\n`;
  t+=`Чинники середовища:\n`+pr.analysis.factors.map(f=>`- ${f[0]} (вага ${f[1]})`).join('\n')+`\n\n`;
 } else {
  t+=`Модель не пояснює це скупчення умовами середовища — причину треба встановити на місці `+
     `(польовий підрахунок, опитування, огляд).\n\n`;
 }
 t+=`**Гіпотеза причини (заповнити на місці):**\n\n_____\n\n`;
 t+=`## Response\n\n**Тип втручання:** _____\n**Адресат:** _____\n**Горизонт:** _____\n\n`;
 t+=`## Assessment\n\n**Критерій спростування (як дізнатись, що не спрацювало):** _____\n\n`;
 t+=`**Дата повторної перевірки:** _____\n`;
 return t;
}
function downloadPassport(p,pr){
 const txt=buildPassport(p,pr);
 const blob=new Blob([txt],{type:'text/markdown;charset=utf-8'});
 const a=document.createElement('a');
 a.href=URL.createObjectURL(blob);
 a.download='pasport_'+(p[2]||'problema').replace(/[^a-zA-Zа-яА-ЯіїєІЇЄ0-9]+/g,'_').slice(0,60)+'.md';
 document.body.appendChild(a);a.click();document.body.removeChild(a);
}
window.__downloadPassport=downloadPassport;
function draw(){
 syncThemes();
 const C=sel('c'),A=sel('a'),Y=sel('y');
 // які теми зараз видимі за фільтром статей — картки проблем ховаються разом з ними,
 // інакше при фільтрі «Насильство» знизу висіла картка про ДТП
 const GVIS=new Set();M.groups.forEach((g,gi)=>{if(g[1].some(i=>A.has(i)))GVIS.add(gi)});
 const CF=+(cb_.querySelector('.on')||{dataset:{c:-1}}).dataset.c;
 const H=new Set();
 hb.querySelectorAll('.on').forEach(x=>PERIODS[+x.dataset.p][2].forEach(h=>H.add(h)));
 let tot=0;const vis=[];
 for(const p of P){
  if(!inScope(p)) continue;
  if(CF>=0&&!probsOf(p).length) continue;
  let n=0,th=null;
  for(const e of p[4]) if(C.has(e[0])&&A.has(e[1])&&Y.has(e[2])&&(!H.size||H.has(e[3]))){n++;if(th===null)th=CATTH[e[1]]}
  if(n){tot+=n;vis.push([p,n,th])}}
 vis.sort((a,b)=>b[1]-a[1]);
 // «Топ адрес за фільтром» слухається саме фільтра, а не переліку проблем:
 // увімкнено «Тільки проблеми» — тут проблеми, вимкнено — найгарячіші адреси
 // взагалі. Слухачеві потрібне саме друге, щоб шукати скупчення самому.
 const rank=vis.filter(v=>v[0][3]);
 $('#cnt').textContent=tot.toLocaleString('uk');
 $('#cntl').textContent=`подій на ${vis.length.toLocaleString('uk')} адресах`;
 {let q=0;P.forEach(p=>{if(inScope(p)&&probsOf(p).length)q++});
  $('#cathint').innerHTML=q?`У поточних межах: <b style="color:#f87171">${q.toLocaleString('uk')}</b> проблем.`:'';}
 $('#top').innerHTML=rank.slice(0,15).map((v,i)=>
  `<div data-i="${i}"><span>${v[0][2]}</span><b>${v[1]}</b></div>`).join('')||'<div class="sub">нема даних</div>';
 [...$('#top').children].forEach((el,i)=>el.onclick=()=>{const v=rank[i];map.setView([v[0][0],v[0][1]],17);
  setTimeout(()=>{let best=null,bd=1e9;layer.eachLayer(l=>{const ll=l.getLatLng();
   const d=Math.abs(ll.lat-v[0][0])+Math.abs(ll.lng-v[0][1]);if(d<bd){bd=d;best=l}});
   if(best&&bd<1e-4)best.openPopup()},350)});
 layer.clearLayers();if(heat){map.removeLayer(heat);heat=null}
 if(heatOn){heat=L.heatLayer(vis.flatMap(v=>Array(Math.min(v[1],20)).fill([v[0][0],v[0][1],1])),
  {radius:18,blur:24,maxZoom:16}).addTo(map);return}
 const mx=vis.length?vis[0][1]:1;
 for(const [p,n,th] of vis){
  const r=Math.max(3.2,Math.min(19,3.2+8.5*Math.sqrt(n/Math.max(mx,1))*2));
  L.circleMarker([p[0],p[1]],{radius:r,weight:p[3]?.8:0,color:'#0f1117',
   fillColor:p[3]?(PALA[th%PALA.length]):'#5f6878',fillOpacity:p[3]?.72:.35})
  .bindPopup(()=>{
   const ev=p[4].filter(e=>C.has(e[0])&&A.has(e[1])&&Y.has(e[2])&&(!H.size||H.has(e[3])));
   const bc={},hh=new Array(24).fill(0);let nk=0;
   ev.forEach(e=>{bc[e[1]]=(bc[e[1]]||0)+1;if(e[3]>=0){hh[e[3]]++;nk++}});
   const rows=Object.entries(bc).sort((a,b)=>b[1]-a[1]);
   const mxh=Math.max(...hh,1);
   let bars='';
   if(nk>=8){bars='<div class="hg">'+hh.map((v,i)=>
     `<i style="height:${Math.max(2,Math.round(22*v/mxh))}px" title="${i}:00 — ${v}"></i>`).join('')+
     '</div><div class="hx"><span>0</span><span>6</span><span>12</span><span>18</span><span>23</span></div>';}
   const night=hh.slice(20).concat(hh.slice(0,4)).reduce((a,b)=>a+b,0);
   const hint = nk>=8 ? `<div class="hn">${Math.round(100*night/nk)}% подій припадає на 20:00–04:00</div>` : '';
   // ---- КАРТКИ ПРОБЛЕМ (п.7.4): по одній на кожен відібраний напрямок адреси ----
   let pblock='';
   const allp=probsOf(p);
   const probs=allp.filter(pr=>pr.thi===undefined||pr.thi<0||GVIS.has(pr.thi));
   const hidden=allp.length-probs.length;
   if(!probs.length&&hidden)
    pblock=`<div class="hn">Ця адреса — у списку проблем, але за іншим напрямком `+
     `(${allp.map(x=>x.theme).join(', ')}). Увімкніть відповідні правопорушення, щоб побачити картку.</div>`;
   if(probs.length){
    pblock=probs.map((pr,pi)=>{
     let h=`<div class="pcard"><div class="ph">Проблема · ${pr.theme}</div>`;
     h+=`<div class="pt">${pr.mech}</div>`;
     // Статті названо і коротко, і юридично точно: лист балансоутримувачу
     // пишеться повною назвою з кодексу, інакше він не має ваги.
     h+=`<div class="pm"><b>Правопорушення:</b></div><ul class="art">`+
        pr.arts.map(a=>{const ln=LAW(a[0]);
         return `<li><span class="sh">${a[0]} — <b>${a[1]}</b></span>`+
                (ln?`<span class="ln">${ln}</span>`:'')+`</li>`}).join('')+`</ul>`;
     h+=`<div class="pm"><b>Чому проблема:</b> ${pr.n} однорідних подій за ${pr.years.length} `+
        `${pr.years.length===1?'рік':'роки'} (${pr.years.join(', ')}), `+
        `${Math.round(100*pr.n/Math.max(pr.core_n,1))}% усіх подій адреси цього роду.</div>`;
     if(pr.analysis){
      h+=`<div class="why"><b>Аналіз:</b> адреса — у верхніх ${100-pr.analysis.pc}% вулиць за `+
         `прогнозом моделі (${pr.theme.toLowerCase()}), влучність ${pr.analysis.hit}%. `+
         `Чинники: `+pr.analysis.factors.slice(0,5).map(f=>f[0]).join(', ')+`.</div>`;
     } else {
      h+=`<div class="why"><b>Аналіз:</b> модель не пояснює — причина встановлюється на місці.</div>`;
     }
     if(pr.analysis&&pr.analysis.factors&&pr.analysis.factors.length&&(F.cats||[]).length)
      h+=`<button class="pbtn2" data-nf="${pi}">Показати чинники поруч</button>`;
     h+=`<button class="pbtn" data-pp="${pi}">Взяти в роботу — паспорт SARA</button></div>`;
     return h;
    }).join('');
    if(probs.length>1) pblock+='<div class="hn" style="margin-top:4px">Кілька напрямків на адресі — кілька окремих проблем із різними причинами.</div>';
   }
   // Кнопка потрібна в КОЖНІЙ адресі, не лише у відібраних проблемах — це
   // основний хід слухача: побачив скупчення -> подивився, що довкола ->
   // висунув гіпотезу. Кнопка нічого не підказує, лише показує околиці.
   if((F.cats||[]).length)
    pblock+='<button class="pbtn2" data-na="1">Що поруч (250 м)</button>';
   const ncase=typeof p[5]==='number'?p[5]:(p[5]||[]).length;
   const cinf=probs.length?CATNAME[2]:null;
   const html=`<div class="lp">
   ${cinf?`<span class="cbadge" style="background:${cinf[1]}22;color:${cinf[1]}">${cinf[0]}</span>`:''}
   <b>${p[2]||'адреса не визначена'}</b>
   <div class="tt">${n} ${n%10===1&&n%100!==11?'подія':'подій'} за поточним фільтром</div>
   <table class="bd">`+rows.map(([i,c])=>
     `<tr><td title="${LAW(M.cats[i])}">${M.cats[i]}</td><td><b>${c}</b></td></tr>`).join('')+`</table>
   ${bars}${hint}${pblock}
   <button class="pbtn2" data-all="1">Усі рішення (${ncase})</button>
   </div>`;
   const wrap=document.createElement('div');wrap.innerHTML=html;
   wrap.querySelectorAll('[data-pp]').forEach(b=>b.onclick=()=>downloadPassport(p,probs[+b.dataset.pp]));
   wrap.querySelectorAll('[data-nf]').forEach(b=>b.onclick=()=>{
    const q=showNear(p[0],p[1],probs[+b.dataset.nf].analysis.factors);
    b.textContent=q?`Підсвічено об’єктів: ${q}`:'Поруч нічого з чинників немає'});
   wrap.querySelectorAll('[data-all]').forEach(b=>b.onclick=()=>openPanel(P.indexOf(p)));
   wrap.querySelectorAll('[data-na]').forEach(b=>b.onclick=()=>{
    const q=showAllNear(p[0],p[1],250);
    b.textContent=q?`Показано об’єктів: ${q}`:'Поруч нічого не знайдено'});
   return wrap},{maxWidth:360,autoPanPaddingTopLeft:[14,14],autoPanPaddingBottomRight:[14,14]}).addTo(layer)}
}
$('#heat').onclick=e=>{heatOn=!heatOn;e.target.classList.toggle('act');e.target.textContent=heatOn?'Показати точки':'Теплова карта';draw()};
$('#reset').onclick=()=>{document.querySelectorAll('#side input:not([data-r]):not([data-f])').forEach(x=>x.checked=true);
 hb.querySelectorAll('.on').forEach(x=>x.classList.remove('on'));draw()};
$('#none').onclick=()=>{document.querySelectorAll('[data-a]').forEach(x=>x.checked=false);draw()};
$('#all').onclick=()=>{document.querySelectorAll('[data-a]').forEach(x=>x.checked=true);draw()};
document.querySelectorAll('#side input:not([data-r]):not([data-f])').forEach(x=>x.addEventListener('change',draw));
document.querySelectorAll('[data-r]').forEach(x=>x.addEventListener('change',drawRisks));
document.querySelectorAll('[data-f]').forEach(x=>x.addEventListener('change',drawFacts));
map.on('zoomend moveend',drawFacts);
{const fc=$('#fclear'); if(fc) fc.onclick=()=>hlayer.clearLayers();}
// Підсвітка «Що поруч» знімається кліком по вільному місцю карти.
// Ловимо саме popupclose, а не click: клік по позначці в Leaflet теж
// доходить до карти, і по кліку підсвітка гасла б одразу після появи.
// Закриття вікна — це і є «користувач пішов з цього місця».
map.on('popupclose',()=>hlayer.clearLayers());
draw();drawRisks();drawFacts();
// Посилання виду kyiv.html#desna відкриває одразу потрібний район:
// викладач може дати групі адресу конкретного району, а не «знайдіть самі».
{const i=DSLUG.indexOf(decodeURIComponent(location.hash.slice(1)).toLowerCase());
 if(i>=0) enterDistrict(i,false); else if(DN.length&&!M.only) paintDistrictList();}"""

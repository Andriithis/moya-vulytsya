# -*- coding: utf-8 -*-
"""Шапка сторінки й усі стилі карти.

Тут: <!DOCTYPE>, <head>, підключення Leaflet і <style> цілком.
Кольори, розміри бічної панелі, вигляд спливних вікон — усе змінюється тут.
Жодного тексту й жодної логіки: підписи — у tpl_body, поведінка — у tpl_map
і tpl_popup.
"""
HEAD = r"""<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Карта правопорушень Києва</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>
*{box-sizing:border-box}html,body{margin:0;height:100%;font:13.5px/1.45 system-ui,sans-serif;background:#0f1117;color:#e8eaf0}
#wrap{display:flex;height:100%}
#side{width:330px;flex:0 0 330px;overflow-y:auto;padding:14px;background:#161922;border-right:1px solid #252a37}
#map{flex:1}h1{font-size:15px;margin:0 0 2px}.sub{color:#79839a;font-size:11.5px}
#cnt{font-size:26px;font-weight:600;margin:12px 0 0;letter-spacing:-.02em}
fieldset{border:0;border-top:1px solid #252a37;padding:11px 0 3px;margin:10px 0 0}
legend{font-size:10.5px;text-transform:uppercase;letter-spacing:.09em;color:#79839a}
label{display:flex;gap:7px;align-items:flex-start;padding:2.5px 0;cursor:pointer}
input[type=checkbox]{accent-color:#e0533d;width:14px;height:14px;margin-top:2px;flex:0 0 auto}
button{width:100%;padding:8px;background:#1f2432;color:#e8eaf0;border:1px solid #303747;border-radius:6px;font:inherit;cursor:pointer;margin-top:7px}
button:hover{background:#28303f}button.act{background:#e0533d;border-color:#e0533d;color:#fff}
.th{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:#5f6878;margin:9px 0 2px}
#hr{display:grid;grid-template-columns:1fr 1fr;gap:5px}
#hr span{padding:7px 4px;background:#1f2432;border-radius:6px;font-size:12px;cursor:pointer;
 user-select:none;text-align:center;line-height:1.15;transition:background .12s}
#hr span:hover{background:#28303f}
#hr span i{display:block;font-style:normal;font-size:10px;color:#6d7789;margin-top:1px}
#hr span.on{background:#e0533d;color:#fff}#hr span.on i{color:#ffd9d0}
#top{margin-top:6px}
#top div{display:flex;justify-content:space-between;gap:8px;padding:5px 7px;background:#1c212c;border-radius:5px;margin-bottom:3px;cursor:pointer;font-size:12.5px}
#top div:hover{background:#252c3a}#top b{color:#e0533d;flex:0 0 auto}
.gr{margin-bottom:2px}
.gh{display:flex;align-items:center;gap:7px;padding:5px 6px;background:#1c212c;border-radius:5px;cursor:pointer;user-select:none}
.gh:hover{background:#232a37}.gh .nm{flex:1;font-size:12.5px}
.gh .n{color:#79839a;font-size:11px}.gh .ar{color:#5f6878;font-size:10px;width:9px}
.gb{display:none;padding:4px 0 6px 22px}.gr.open .gb{display:block}
.gr.open .ar{transform:rotate(90deg)}.ar{display:inline-block;transition:transform .12s}
.gb label{font-size:12px;color:#c4cbd8}.gb .n{color:#5f6878;font-size:10.5px;margin-left:auto;flex:0 0 auto}
.hint{font-size:11px;color:#5f6878;margin-top:7px;line-height:1.4}
#backl a{color:#e0533d;font-size:12px;text-decoration:none;display:inline-block;margin-top:2px}
#pan{position:absolute;top:0;right:0;bottom:0;width:380px;max-width:34vw;z-index:1200;
 background:#161922;border-left:1px solid #252a37;display:flex;flex-direction:column;
 transform:translateX(100%);transition:transform .22s ease;box-shadow:-14px 0 34px #0006}
#pan.on{transform:none}
#panh{padding:13px 14px 10px;border-bottom:1px solid #252a37;position:relative;flex:0 0 auto}
#panh .pa{font-size:14.5px;font-weight:600;padding-right:26px;line-height:1.25}
#panh .ps{font-size:11.5px;color:#79839a;margin-top:3px}
#panx{position:absolute;top:9px;right:10px;width:24px;height:24px;padding:0;margin:0;
 background:#1f2432;border:1px solid #303747;border-radius:6px;color:#9aa4b6;
 font-size:15px;line-height:1;cursor:pointer}
#panx:hover{background:#28303f;color:#e8eaf0}
#panb{flex:1;overflow-y:auto;padding:10px 14px 22px}
.cs{border-top:1px solid #232838;padding:9px 0}
.cs:first-child{border-top:0}
.cd{font-size:12.5px;color:#c4cbd8}
.cd b{color:#e8eaf0;font-weight:600}
.cn{font-size:11px;color:#5f6878;margin-top:1px}
.cx{font-size:12px;color:#9aa4b6;line-height:1.45;margin-top:5px}
.cl{margin-top:5px;display:flex;flex-wrap:wrap;gap:6px}
.cl a{font-size:11px;color:#e0533d;text-decoration:none;border:1px solid #3a2a26;
 border-radius:5px;padding:2px 7px}
.cl a:hover{background:#2a1e1b}
#panb .sub{font-size:12px;color:#5f6878;padding:8px 0}
@media(max-width:900px){#pan{width:100%;max-width:100%}}
#fd{display:grid;grid-template-columns:1fr 1fr;gap:5px}
#fd span{padding:6px 5px;background:#1f2432;border-radius:6px;font-size:11.5px;cursor:pointer;
 user-select:none;text-align:center;line-height:1.15;transition:background .12s}
#fd span:hover{background:#28303f}
#fd span i{display:block;font-style:normal;font-size:10px;color:#6d7789;margin-top:1px}
#fd span.on{background:#e0533d;color:#fff}#fd span.on i{color:#ffd9d0}
#backl a:hover{text-decoration:underline}
#fr label,#frisk label,#fctx label{font-size:12px}
#fr .n,#frisk .n,#fctx .n{color:#5f6878;font-size:10.5px;margin-left:auto;flex:0 0 auto}
#fr .sw,#frisk .sw,#fctx .sw{width:9px;height:9px;border-radius:2px;flex:0 0 auto}
#fcat{display:grid;grid-template-columns:1fr 1fr;gap:5px}
#fcat span{padding:7px 5px;background:#1f2432;border-radius:6px;font-size:12px;cursor:pointer;
 user-select:none;text-align:center;line-height:1.15;transition:background .12s;position:relative}
#fcat span:hover{background:#28303f}
#fcat span i{display:block;font-style:normal;font-size:10px;color:#6d7789;margin-top:1px}
#fcat span.on{background:#2b3243;box-shadow:inset 0 0 0 1.5px currentColor}
#fcat span.c2{color:#f87171}#fcat span.cA{color:#a8b2c4}
.skew{font-size:11.5px;color:#c4cbd8;background:#1c2230;border-left:3px solid #e0533d;
 border-radius:5px;padding:7px 9px;margin-top:9px;line-height:1.4}
.env{margin:8px 0 0}
.env .eh{font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:#8b95a8;margin-bottom:4px}
.dirs{margin:7px 0}.dirs .row{display:flex;gap:7px;align-items:center;font-size:11.5px;margin-bottom:3px}
.dirs .bar2{flex:1;height:4px;background:#232838;border-radius:2px;overflow:hidden}
.dirs .bar2 i{display:block;height:100%;background:#e0533d}
.miss{font-size:11px;color:#8b95a8;background:#1a2030;border-left:2px solid #3b82f6;
 padding:5px 8px;border-radius:4px;margin-top:7px}
.cbadge{display:inline-block;padding:1px 7px;border-radius:99px;font-size:10.5px;
 text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}
#fr .rh{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:#5f6878;margin:9px 0 2px}
/* ---- прогноз ризику ---- */
#frisk .rw{margin-bottom:5px;border-radius:6px;background:#1a1f2a;padding:6px 8px;
  border-left:3px solid transparent;transition:background .12s}
#frisk .rw:hover{background:#212836}
#frisk .rl{display:flex;align-items:center;gap:7px;cursor:pointer}
#frisk .nm{flex:1;font-size:12.5px;line-height:1.2}
#frisk .acc{font-size:10px;color:#7c8698;padding:1px 5px;border:1px solid #333c4d;border-radius:99px}
#frisk .why{font-size:10.5px;color:#6d7789;margin:3px 0 0 22px;line-height:1.35}
#frisk .rw.nod{opacity:.5}#frisk .rw.nod .rl{cursor:default}
#frisk .rg{margin-bottom:6px;border-radius:6px;background:#151a24;border:1px solid #222836}
#frisk .rg>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:7px;
 padding:6px 9px;font-size:12px;color:#c4cbd8;user-select:none}
#frisk .rg>summary::-webkit-details-marker{display:none}
#frisk .rg>summary::before{content:'\25B8';color:#5f6878;font-size:9px;transition:.15s}
#frisk .rg[open]>summary::before{transform:rotate(90deg)}
#frisk .rg>summary .gn{flex:1;font-weight:500}
#frisk .rg>summary .gc{font-size:10px;color:#6d7789;padding:1px 6px;border:1px solid #2b3242;border-radius:99px}
#frisk .rg .rw{margin:0 6px 5px}#frisk .rg .rw:first-of-type{margin-top:2px}
.lgd{display:flex;align-items:center;gap:6px;font-size:10px;color:#5f6878;margin-top:8px}
.lgd i{height:3px;flex:1;border-radius:2px;background:linear-gradient(90deg,#5f6878 0%,currentColor 100%)}
/* Підкладка — звичайні плитки OpenStreetMap, темними їх робить цей фільтр.
   CARTO з 2026 року вимагає ключ і малює поверх карти напис API KEY REQUIRED,
   а ключ означав би реєстрацію, ліміти й ще одну залежність. Фільтр
   накладається ЛИШЕ на шар плиток, тож точки й лінії лишаються своїх кольорів. */
.leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.93) contrast(.92) saturate(.65)}
.leaflet-popup-content-wrapper{background:#161922;color:#e8eaf0;border-radius:8px}
.leaflet-popup-tip{background:#161922}
.leaflet-tooltip.rt{background:#161922;border:1px solid #2c3444;color:#e8eaf0;
  font:12px system-ui;border-radius:6px;box-shadow:0 4px 16px rgba(0,0,0,.5);padding:6px 9px}
.leaflet-tooltip.rt:before{display:none}
.leaflet-tooltip.rt b{display:block;margin-bottom:2px}
.leaflet-tooltip.rt span{color:#8b95a8;font-size:11px}
/* висота в частках екрана, інакше висока картка вилазить за верх вікна */
.lp{font-size:12.5px;max-height:min(420px,58vh);overflow-y:auto;overscroll-behavior:contain}
.lp b{display:block;margin-bottom:5px;font-size:13px}
.lp a{color:#c94a34;text-decoration:none}.lp a:hover{text-decoration:underline}
.lp li{margin-bottom:4px;font-size:11.5px}.lp ul{padding-left:15px;margin:3px 0}
.lp .tt{color:#79839a;font-size:11.5px;margin-bottom:7px}
.bd{width:100%;border-collapse:collapse;margin-bottom:8px}
.bd td{padding:2px 0;font-size:12px;vertical-align:top}
.bd td:last-child{text-align:right;padding-left:10px;color:#e0533d;width:44px}
.hg{display:flex;align-items:flex-end;gap:1px;height:24px;margin:2px 0 1px}
.hg i{flex:1;background:#e0533d;opacity:.8;border-radius:1px 1px 0 0}
.hx{display:flex;justify-content:space-between;font-size:9.5px;color:#5f6878;margin-bottom:5px}
.hn{font-size:11px;color:#c4cbd8;background:#232a37;padding:4px 7px;border-radius:4px;margin-bottom:7px}
.pcard{background:#1c2230;border-left:3px solid #f87171;border-radius:5px;padding:8px 9px;margin:8px 0}
.pcard .ph{font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:#8b95a8;margin-bottom:3px}
.pcard .pt{font-size:13px;font-weight:600;margin-bottom:5px;line-height:1.25}
.pcard .pm{font-size:11.5px;color:#c4cbd8;margin-bottom:2px}
.pcard .pm b{color:#e8eaf0}
.pcard .art{margin:3px 0 5px}
.pcard .art li{list-style:none;margin-bottom:4px}
.pcard .art .sh{font-size:11.5px;color:#e8eaf0}
.pcard .art .ln{display:block;font-size:10.5px;color:#8b95a8;line-height:1.35;margin-top:1px}
.pcard .pf{font-size:10.5px;color:#6d7789;margin-top:4px;line-height:1.4}
.pcard .why{font-size:11px;color:#c4cbd8;background:#161c28;border-radius:4px;padding:6px 8px;margin-top:5px}
.pbtn{width:100%;padding:7px;background:#e0533d;color:#fff;border:0;border-radius:6px;
 font:inherit;font-size:12px;cursor:pointer;margin-top:7px}
.pbtn:hover{background:#c94a34}
/* ---- шар чинників середовища ---- */
.fgh{font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:#8b95a8;margin:9px 0 2px}
#ffact label{font-size:12px}
#ffact .n{color:#5f6878;font-size:10.5px;margin-left:auto;flex:0 0 auto}
#ffact .sw{width:9px;height:9px;border-radius:99px;flex:0 0 auto;margin-top:3px}
.pbtn2{width:100%;padding:6px;background:#2b3243;color:#e8eaf0;border:1px solid #3a4256;
 border-radius:6px;font:inherit;font-size:11.5px;cursor:pointer;margin-top:5px}
.pbtn2:hover{background:#343d52}
.ex{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:#5f6878;margin-top:6px}
.rpop b{display:block;margin-bottom:4px;font-size:13px}
.rpop .rmeth{font-size:11px;color:#8b95a8;margin:6px 0;line-height:1.4}
.rpop table{width:100%;border-collapse:collapse;margin-top:4px}
.rpop td{padding:1.5px 0;font-size:11px}
.rpop td:last-child{text-align:right;color:#e0533d}
.rpop .rdoc{display:block;margin-top:8px;font-size:11.5px;color:#7cb2ff;text-decoration:none}
.rpop .rdoc:hover{text-decoration:underline}
#docs a{display:block;font-size:12.5px;color:#7cb2ff;text-decoration:none;padding:3px 0}
#docs a:hover{text-decoration:underline}
@media(max-width:760px){#wrap{flex-direction:column}#side{width:100%;flex:0 0 auto;max-height:50%}}
</style></head>"""

# -*- coding: utf-8 -*-
"""Розмітка бічної панелі.

Порожні гнізда (<div id="...">), які наповнює JavaScript, і нерухомі підписи —
заголовки рамок та пояснення під ними. Змінювати тут — коли треба переставити
блоки панелі, перейменувати рамку або поправити пояснювальний текст.
"""
BODY = r"""<body><div id="wrap"><div id="side">
<h1>Карта правопорушень</h1><div class="sub" id="subt">за даними ЄДРСР · місто Київ</div>
<div id="backl"></div>
<div id="skew"></div>
<div id="cnt">0</div><div class="sub" id="cntl"></div>
<fieldset id="fdw"><legend>Район міста</legend><div id="fd"></div>
<div class="hint">Натисніть район — карта під'їде до нього й покаже його власний перелік проблем. По межах на карті теж можна клікати, але в щільному центрі їх закривають позначки подій.</div></fieldset>
<button id="heat">Теплова карта</button><button id="reset">Скинути фільтри</button>
<fieldset><legend>Що показувати</legend><div id="fcat"></div>
<div class="hint" id="cathint"></div></fieldset>
<fieldset><legend>Топ адрес за фільтром</legend><div id="top"></div></fieldset>
<fieldset id="fcw"><legend>Район</legend><div id="fc"></div></fieldset>
<fieldset><legend>Правопорушення</legend>
<div style="display:flex;gap:6px"><button id="none" style="margin:0 0 8px">Зняти всі</button>
<button id="all" style="margin:0 0 8px">Обрати всі</button></div><div id="fa"></div></fieldset>
<fieldset><legend>Прогноз ризику</legend><div id="frisk"></div>
<div class="hint">Модель оцінює <b>кожну вулицю</b> за умовами середовища, незалежно від того, чи були там події. Клікніть на вулицю — розбір чинників і методики відкриється в спливному вікні. У кружечку — влучність: яка частка подій наступних років припала на верхні 10% відібраних вулиць.</div>
</fieldset>
<fieldset><legend>Документи</legend><div id="docs"></div>
<div class="hint">Збираються автоматично з тих самих даних, що й карта.</div></fieldset>
<fieldset><legend>Середовище</legend><div id="ffact"></div>
<div class="hint" id="fzoom"></div>
<button id="fclear">Прибрати підсвітку</button>
<div class="hint" id="fhint"></div></fieldset>
<fieldset><legend>Контекст</legend><div id="fctx"></div>
<div class="hint">Населення — фон під картою, за даними Kontur (комірки 400 м). Потоки — модельовані пішохідні маршрути від житла до цілей, з урахуванням населення. Товщина = кількість людей.</div></fieldset>
<fieldset><legend>Рік</legend><div id="fy"></div></fieldset>
<fieldset><legend>Час доби</legend><div id="hr"></div>
<div class="hint">Порожній вибір = усі. Розмір кола = кількість подій за адресою. Сірі кола — прив'язка лише до вулиці, без номера будинку.</div></fieldset>
</div><div id="map"></div>
<div id="pan"><div id="panh"></div><div id="panb"></div></div></div>"""

# -*- coding: utf-8 -*-
"""HTML-шаблон карти. Збирається з чотирьох частин.

    tpl_style   шапка сторінки і стилі
    tpl_body    розмітка бічної панелі
    tpl_map     карта, шари, підсвітка «що поруч»
    tpl_popup   панель, паспорт SARA, картка проблеми (draw)

Плейсхолдери __META__, __PTS__, __RISKS__, __POP__, __FACTS__ підставляє
step3_map.main(). Тут немає жодного обчислення — тільки те, що бачить
і натискає користувач.

Розділено 2 вересня 2026: правка в одній частині більше не пересилає
весь шаблон цілком.
"""
from tpl_style import HEAD
from tpl_body import BODY
from tpl_map import JS_MAP
from tpl_popup import JS_POPUP

TPL = HEAD + BODY + '\n<script>\n' + JS_MAP + '\n' + JS_POPUP + '\n</script></body></html>'

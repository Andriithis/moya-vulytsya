# -*- coding: utf-8 -*-
"""«Кваліфікуй: кар'єра» (ZAVDANNYA-146, прототип): навчальні справи з випуску events-<дата>.db і текстів рішень.

  python site/ihry/kariera/kariera.py --baza events-<дата>.db --teksty <тека з *.jsonl.xz Release teksty> \
      [--vykhid site/ihry/kariera/kariera.json] [--na-chastynu 40]

Що робить:
1. Справа — подія випуску з фабулою (так, як її взяв конвеєр з рішення), одна подія на рішення.
2. Правильна відповідь — **з резолютивної частини того самого рішення** («визнати винним … передбаченого ч. N ст. X …»):
   кодекс, стаття, частина. Лише одна кваліфікація в реченні про вину і та сама стаття, що в події; інакше справа не йде
   (кілька статей, замах, співучасть — для гри неоднозначно).
3. Пояснення — речення самого суду з тексту рішення з тією самою кваліфікацією (найкраще — з «тобто …»); нічого від себе.
4. Знеособлення фабули: статті й кодекси приховано (щоб не підказати відповідь), «ОСОБА_1» → «Особа А», номери машин і
   «ІНФОРМАЦІЯ_N» прибрано, номери будинків прибрано — лише назва вулиці (MV-25: гра безкоштовна).
4а. ZAVDANNYA-176 (за ZVIT-168): фабула — **цілими реченнями** (S-П.1): у випуску вона обрізана, тож її знаходимо в тексті
   рішення й дочитуємо до кінця речення; не знайшли й не закінчена — справа не йде. Ім'я людини не показуємо ніде: речення
   з прізвищем та ініціалами (суддя, поліцейський, адвокат) і процесуальні речення про суддю — геть (як
   `dani-edrsr/src/pokaz_fabuly.py`, `IMENA`); «ОСОБА_N» після ролі («водій», «потерпілий») — лише роль, як у колоді; номери
   протоколів і квартир — геть; не Київ (інше місто, автодорога з кілометром) — справа не йде. **Ознака частини — в умові**:
   якщо суд пояснює частину обставиною (повторно, групою, у великому розмірі, проникнення, воєнний стан, наслідки…), ця
   обставина мусить бути у фабулі, інакше справу не беремо (`OZNAKY`). Після збору — `perevirka()`: щось лишилось
   (ім'я, «кв. N», номер протоколу, мітка реєстру, обірване речення) — збірка падає (`main`, і сайт — `zibraty_sait.py`).
5. Поза грою (MV-69, MV-165): статеві, щодо дітей, домашнє насильство (`dani-edrsr/src/chutlyvi.py`) і будь-яка фабула,
   де згадано неповнолітніх чи малолітніх.
6. Складність — за частотою статті у випуску (часті — на перших рівнях), частина, рідша за 15 % у своїй статті, — +1.
7. Скасоване чи змінене в апеляції або касації (MV-17, ZAVDANNYA-152) — поза грою: гра показує, як кваліфікував суд, а
   кваліфікація такого рішення вже не діє. Позначка — таблиця `skasuvannia` випуску (S-Т.6, `dani-edrsr/src/skasuvannia.py`):
   поза грою наслідки з `SKASOVANO_NASLIDKY` («без змін» і «не розпізнано» — лишаються: саме подання апеляції подію не
   скасовує). Видалене за зверненням (`withdrawal`) — теж поза грою. Немає таблиці у випуску (пробний 08.11 — стара
   схема) — відсіву немає, і збирач каже про це вголос.

Фабули — з випуску, тож файл даних у git не кладемо (`.gitignore`), як `litopys.json`.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import json
import lzma
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

TUT = Path(__file__).resolve().parent
KVAL_ZACHATOK = TUT.parent / 'kvalifikuy.json'

# Поза грою: статеві, щодо дітей, домашнє насильство (як dani-edrsr/src/chutlyvi.py: STATTI і DOMASHNIE).
POZA = re.compile(r'ст\.173-2 КУпАП|ст\.173-8 КУпАП|ст\.126-1 КК|ст\.15[2-6] КК|ст\.117 КК|ст\.166 КК|ст\.180 КУпАП|'
                  r'ст\.180-1 КУпАП|ст\.184 КУпАП|ст\.303 КК|ст\.390-1 КК|ст\.13[5-7] КК|ст\.150 КК|ст\.164 КК|'
                  r'ст\.30[14]|ст\.301-1 КК')
SHAPKA = re.compile(r'провадження\s*№|об.єднан|В\s*С\s*Т\s*А\s*Н\s*О\s*В\s*И|зареєстрован|проживаю|уродже|громадян\w+\s+України|не\s+працю')
DITY = re.compile(r'неповнолітн|малолітн|дитин|дітей|дітьми|школяр|учн[яіею]', re.I)

KODEKS = r'(КК|КУпАП|КпАП|КУАП|Кодексу\s+України\s+про\s+адміністративні\s+правопорушення|Кримінального\s+кодексу)'
KVAL = re.compile(r'(?:ч(?:\.|астин\w*)\s*(\d+)\s*)?ст(?:\.|атт\w+)\s*(\d+(?:\s*[-–]\s*\d+)?)\s*,?\s*' + KODEKS)
REZOL = re.compile(r'П\s*О\s*С\s*Т\s*А\s*Н\s*О\s*В\s*И\s*[ВЛ]|У\s*Х\s*В\s*А\s*Л\s*И\s*[ВЛ]|В\s*И\s*Р\s*І\s*Ш\s*И\s*[ВЛ]')
VYNA = re.compile(r'винн|винуват')

# Приховати статті у фабулі (будь-яке «ч. N ст. X …» чи «ст. X»), щоб текст не підказав відповідь.
STATTIA_U_TEKSTI = re.compile(
    r'(?:частин\w+\s+(?:перш|друг|трет|четверт|п.ят|шост|сьом|восьм)\w*\s+)?'
    r'(?:ч(?:\.|астин\w*)\s*\d+\s*,?\s*)?(?:ст\.|статт\w+)\s*\d+(?:\s*[-–]\s*\d+)?(?:\s*,\s*\d+(?:[-–]\d+)?)*'
    r'(?:\s*(?:ч\.?|частин\w*)\s*\d+)?(?:\s*' + KODEKS + r'(?:\s+України)?)?')
ZAIVE_RECHENNIA = re.compile(r'[,;]?\s*(?:що\s+утворює|чим\s+(?:вчинил?[аи]?|скоїл?[аи]?|здійснил?[аи]?)|тобто\s+(?:вчинив|скоїв)|'
                             r'відповідальність\s+за\s+що|за\s+що\s+відповідальність|за\s+що\s+передбачена|які\s+(?:передбачені|кваліфіковано))[^.]*'
                             r'\[\s*стаття\s*\][^.]*', re.I)
VULYTSIA = re.compile(
    r'((?:вул\.|вул\b|пр\.|бул\.|вулиц\w+|просп\.*|пр-т|пр-кт|проспект\w*|бульв\.|бульвар\w*|б-р|пров\.|провулк\w*|пл\.|площ\w+|наб\.|'
    r'набережн\w+|шосе|узвіз\w*|дорог\w+|алея|алеї|майдан\w*)\s*[^,;\d]{2,45}?)\s*,?\s*(?:буд(?:инок|инку)?\.?\s*)?№?\s*\d+[а-яА-ЯіїєґІЇЄҐ]?'
    r'(?:\s*[-/]\s*[\dа-яА-ЯіІ]+)?(?:\s*,?\s*(?:кв\.|квартир\w+|під\'?їзд\w*)\s*№?\s*\d+)?')
# Номер будинку, який не зміг прибрати VULYTSIA (назва з цифрою: «вул. 21-ша Садова, 49») — така справа не йде.
ZALYSHOK_NOMERA = re.compile(r'(?:вул|просп|бул|пров|пл)\.?\s[^,.;]{0,35},\s*\d')
# «…, чим вчинила правопорушення, передбачене [стаття]» — кваліфікація в кінці опису, без неї речення ціле (ZAVDANNYA-176)
ZAIVE_KVAL = re.compile(r'[,;]?\s*(?:чим\s+|тим\s+самим\s+|і\s+|та\s+|й\s+)?(?:вчинив|вчинил[аио]|учинив|учинил[аио]|скоїв|скоїл[аи]|вчинивши|скоївши|вчинено|здійснив|здійснил[аи])\s+'
                        r'(?:адміністративне\s+|кримінальне\s+)?(?:правопорушення|порушення|злочин|проступок)\s*,?\s*(?:що\s+|яке\s+)?'
                        r'(?:передбачен\w+|відповідальність\s+за\s+як\w+\s+передбачен\w+)\s*\[\s*стаття\s*\](?:\s*\(\s*далі[^)]{0,30}\))?|'
                        r'(?<=[.!?])\s*Відповідальність\s+за\s+[^.]{0,80}?передбачен\w+\s*\[\s*стаття\s*\][^.]{0,40}\.', re.I)
# Процесуальне речення після опису («Особа А свою вину визнав», «В судове засідання не з'явився») — опис закінчився.
KHVIST_PROTSES = re.compile(r'(?<=[.!?])\s+(?:Особа\s+[А-ЯІЇЄҐ]\s+|Обвинувачен\w+\s+|Правопорушни\w+\s+)?(?:(?:свою\s+)?(?:вину|винуватість)\s|'
                            r'(?:в|у|на)\s+судове\s+засідання|(?:в|у)\s+судовому\s+засіданні|про\s+(?:час\s+і\s+)?місце|Вивчивши|Дослідивши|'
                            r'Заслухавши|Вислухавши|Суд\s|Суддя\s|Таким\s+чином|Враховуючи|Згідно\s+з?\s*(?:протокол|ст\.))', re.I)
BUKVY = 'АБВГДЕЄЖЗИКЛМНОПРСТУФХЦЧШЩ'
# Наслідки апеляції чи касації (dani-edrsr/src/skasuvannia.py, NASLIDKY), з якими рішення в гру не йде: скасовано (закрито,
# виправдано, новий розгляд, апеляційний вирок) чи змінено — покарання або кваліфікацію; з тексту наслідку не видно, що саме.
SKASOVANO_NASLIDKY = ('zakryto', 'vypravdano', 'novyi_rozghliad', 'apeliatsiinyi_vyrok', 'zmina')

# ---------- ZAVDANNYA-176: знеособлення й цілі речення ----------
# Прізвище з ініціалами («Діденком Т.М.», «І.І. Коваленко») і процесуальні речення про суддю — рівно як
# dani-edrsr/src/pokaz_fabuly.py (IMENA, PROTSES_SUDDI; тест порівнює, якщо поруч лежить dani-edrsr).
IMENA = re.compile(r"[А-ЯІЇЄҐ][а-яіїєґʼ'’`]+\s+[А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ](?:\.|(?![\wʼ'’`]))|(?<![А-ЯІЇЄҐа-яіїєґ])[А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ][а-яіїєґ]+")
PROTSES_SUDDI = re.compile(r'розподіл\w*\s+судов\w*\s+справ|між\s+суддями|визначено\s+суддю|колегі\w+\s+судд|'
                           r'передан\w*\s+(?:для\s+розгляду\s+)?судд|у\s+складі\s+(?:головуюч|судд)|головуюч\w*\s+судд|'
                           r'описк\w*\s+(?:у|в)\s+постанов\w*\s+судд', re.I)
# Ім'я поліцейського при званні чи службі без другого ініціала: «інспектора УПП Красьохи Є.», «л-т поліції І. Михайлюк».
PIB_SLUZHBA = re.compile(
    r"(?:поліц\w*|інспектор\w*|сержант\w*|лейтенант\w*|капітан\w*|майор\w*|полковник\w*|л-т\.?|капрал\w*|УПП|патрульн\w*)"
    r"(?:\s+[^\s.;,]+){0,4}?\s+(?:(?:[А-ЯІЇЄҐ]\.\s*){1,2}[А-ЯІЇЄҐ][а-яіїєґ'’`]+|[А-ЯІЇЄҐ][а-яіїєґ'’`]+\s+(?:[А-ЯІЇЄҐ]\.\s*){1,2})")
# межа речення: не на ініціалі й не на скороченні («вул.», «буд.», «д.н.з.», «год.», «ч. 2»)
SKOROCHENNIA = r'(?<!\W\w\.)(?<!^\w\.)(?<!вул\.)(?<!буд\.)(?<!обл\.)(?<!просп\.)(?<!пров\.)(?<!грн\.)(?<!год\.)(?<!хв\.)(?<!бульв\.)(?<!див\.)(?<!кв\.)(?<!ст\.)(?<!пл\.)(?<!наб\.)(?<!р\.)(?<!км\.)(?<!тис\.)(?<!коп\.)'
RECHENNIA = re.compile(r'(?<=[.!?…])' + SKOROCHENNIA + r'\s+(?=[А-ЯІЇЄҐA-Z«"])')
KINETS_RECHENNIA = re.compile(r'[.!?…]' + SKOROCHENNIA.replace('(?<!^\\w\\.)', '') + r'(?=\s+[А-ЯІЇЄҐA-Z«"]|\s*$)')
# Повне ПІБ («старшим лейтенантом поліції Пальчиком Ігорем Віталійовичем») — речення геть, як з ініціалами.
PIB_POVNE = re.compile(r"[А-ЯІЇЄҐ][а-яіїєґʼ'’`-]+\s+[А-ЯІЇЄҐ][а-яіїєґʼ'’`]+\s+[А-ЯІЇЄҐ][а-яіїєґʼ'’`]+(?:ович|йович|евич|івн|ївн|овн)\w*")
# Зачин і рамка протоколу на початку фабули (скорочено з pokaz_fabuly.ZACHYN і RAMKA): опис — з самої події.
ZACHYN = re.compile(r'^\s*(?:\d+\.\s*)?(?:(?:Судом|Суддею)\s+(?:визнано\s+)?(?:доведеним|встановленим|встановлено|встановив)\s*,?\s*(?:що\s*,?\s*)?|'
                    r'(?:Досудовим\s+розслідуванням|В\s+ході\s+досудового\s+розслідування)\s+встановлено\s*,?\s*(?:що\s*,?\s*)?|'
                    r'(?:Із|З)\s+наявного\s+в\s+матеріалах\s+справи\s+протокол\w*[^,]{0,120},\s*(?:що\s*,?\s*)?|'
                    r'(?:Відповідно\s+до|Згідно(?:\s+(?:з|із))?|Виходячи\s+з)\s+(?:даних\s+|складеного\s+)?(?:з\s+)?(?:дани(?:х|ми)\s+)?протокол\w*'
                    r'(?:[^.,]|\.(?=\d)|,\s*(?=від\s))*?,(?!\s*від\s)\s*(?:(?:складеного|відносно)[^,:«]{0,160}[,:«]\s*«?\s*)?|'
                    r'До\s+\w+(?:\s+\w+){0,6}\s+суду[^.]{0,200}?надійшо?в?л?\w*\s+(?:протокол|матеріал)\w*(?:[^.]|\.(?=\d)){0,250}?'
                    r'(?:згідно\s+(?:з\s+)?як\w+|відповідно\s+до\s+як\w+|в\s+якому\s+зазначено|з\s+якого\s+вбачається)\s*,?\s*(?:що\s*,?\s*)?|'
                    r'(?:З|Із)\s+протокол\w*(?:[^.]|\.(?=\d)){0,200}?вбачається\s*,?\s*що\s*,?\s*)', re.I)
RAMKA = re.compile(r'^.{0,500}?(?:У\s+фабулі\s+(?:зазначеного\s+|даного\s+|вказаного\s+)?протоколу\s+(?:вказано|зазначено)|'
                   r'протокол\w*[^.]{0,150}?вбачається)\s*,?\s*(?:про\s+те\s*,?\s*)?що\s*,?\s*', re.I)
# Номер протоколу чи постанови: «серії ЕПР1 № 470986», «серія ААД №728948», «№3511190» (ключ до справи поза реєстром).
PROTOKOL = re.compile(r'\s*,?\s*(?:(?:серії|серія|сер\.)\s*:?\s*(?:[A-ZА-ЯІЇЄҐ]{1,4}\s*\d*\s*(?:№\s*)?\d*|…)(?![\wа-яіїєґ])|'
                      r'№\s*(?:(?:[\w/-]|\.(?=\w))*\d{4,}(?:[\w/-]|\.(?=\w))*(?:\s*-\s*[A-ZА-ЯІЇЄҐ\d]+)?|…))')
# Номер авто разом із назвою знака (скорочено з pokaz_fabuly.NOMER_AVTO): «д.н.з. НОМЕР_1», «номерний знак НОМЕР_2»
NOMER_AVTO = re.compile(r',?\s*\(?\s*(?:(?:державн\w*\s+)?(?:реєстраційн\w*\s+)?(?:номерн\w*\s+)?(?:знак\w*|номер\w*)|держномер\w*|'
                        r'д\.?\s?н\.?\s?з\.?|н\.\s?з\.?|н/з|д/н(?:/з)?|днз)\s*:?\s*[«"]?\s*НОМЕР_\d+\s*[»"]?\s*\)?', re.I)
KVARTYRA = re.compile(r'(?<![\w-])(кв\.|квартир\w*)\s*№?\s*\d+[а-яА-ЯіІ]?(?:\s*[/,-]\s*\d+)*', re.I)
# «водій ОСОБА_1» → «водій» (як у колоді: роль уже каже, хто це)
ROLI = (r'водій|водійка|водія|водієві|водієм|пасажир\w*|пішохід|пішохода|пішоходу|потерпіл\w+|обвинувачен\w+|правопорушни\w+|'
        r'підсудн\w+|засуджен\w+|власник\w*|власниц\w+|продав\w+|покуп\w+|охоронц?\w*|працівник\w*|громадян\w+|гр\.|'
        r'співмешкан\w+|знайом\w+|сусід\w*|касир\w*|адміністратор\w*|керівник\w*|директор\w*|чоловік\w*|жінк\w+|особ[аиуіою]')
ROL_OSOBA = re.compile(r'\b(' + ROLI + r')\s+ОСОБА_\d+\b', re.I)
# Не Київ: інше місто чи автодорога з кілометром («м. Стрий, автомобільна дорога Київ-Чоп, 548 км»).
NE_KYIV = re.compile(r'\b(?:м\.|місті|міста|смт\.?|с\.|селі|села)\s*(?:Стри\w*|Житомир\w*|Сум\w*|Львов\w*|Львів\w*|Харків\w*|Харков\w*|Одес\w*|Дніпр\w*|Полтав\w*|'
                     r'Чернігов\w*|Чернігів\w*|Черкас\w*|Вінниц\w*|Рівн\w*|Луцьк\w*|Тернопол\w*|Тернопіл\w*|Ужгород\w*|Хмельниц\w*|Кропивниц\w*|Миколаєв\w*|'
                     r'Миколаїв\w*|Херсон\w*|Запоріж\w*|Чернівц\w*|Івано-Франків\w*|Біл\w+\s+Церкв\w*|Бровар\w*|Борисп\w*|Ірпін\w*|Буч\w*|Вишгород\w*|'
                     r'Обухов\w*|Обухів\w*|Фастов\w*|Фастів\w*|Василь\w*|Вишнев\w*|Боярк\w*|Українк\w*|Славутич\w*|Кривого\s+Рогу|Кривий\s+Ріг)|'
                     r'автодоро\w+|автомобільн\w+\s+дорог\w+|\d+\s*км\b(?!\s*/)|\b(?!Київськ)(?:\w+ськ|\w+цьк)\w*\s+област\w+', re.I)
POCHATOK_NE_PODIIA = re.compile(r'^(?:Складен|Відносно|Від\s|До\s.{0,80}?суд|Протокол|Згідно|Відповідно|Виходячи|Із\s+наявн|З\s+наявн)|^(?:В|У)\s+подальшому|^\W*(?:що\s+)?підтверджу|^(?:Крім\s+того|Також|Окрім\s+того|Вина|Винуватість|Доказ)', re.I)
# Ознаки частини (кваліфікуючі обставини). Якщо суд у поясненні назвав обставину — вона мусить бути у фабулі.
OZNAKY = {
    'повторно': (r'повторн|вдруге|протягом\s+року\s+після|раніше\s+(?:вже\s+)?(?:засуджен|судим|притягувал|вчиня|був\s+притягнут)|судимість|'
                 r'не\s+знят\w+\s+(?:і\s+не\s+погашен\w+\s+)?судимост'),
    'групою': r'груп\w+\s+осіб|попередн\w+\s+змов|організован\w+\s+груп',
    'проникнення': r'проникн|приміщенн|сховищ|житл',
    'воєнний стан': r'воєнн\w+\s+стан',
    'розмір': (r'(?:велик|особливо\s+велик|значн|невелик)\w*\s+(?:розмір|шкод|кількост)|мас[аиоуі]\w*\s|масою|вагою|\d\s*(?:г|гр|грам\w*|мг)\b|'
               r'\d[\d\s]*(?:,\d+)?\s*грн|вартіст'),
    'наслідки': r'смерт|загибел|загину|помер|тяжк\w+\s+тілесн|середньої\s+тяжкості|тілесн\w+\s+ушкоджен|травм',
    'зброя': r'зброї|зброєю|зброя|ніж|ножем|пістолет|предмет\w*,?\s+(?:заздалегідь\s+)?(?:пристосован|що\s+використову)',
    'замах': r'замах|не\s+довів|не\s+зміг\s+(?:довести|розпорядит)|затриман\w+\s+(?:на\s+місці|працівник|охорон)|не\s+маючи\s+можливості',
    'без права': r'позбавлен\w*\s+права|не\s+має\s+права\s+керування|не\s+маючи\s+права|без\s+права\s+керування|посвідчен\w+\s+водія',
    'аварійна обстановка': r'аварійн\w+\s+(?:обстановк|ситуаці)|створив\w*\s+(?:перешкоду|небезпеку)',
    'неодноразово': r'неодноразов|систематичн',
}
OZNAKY_RX = {k: re.compile(v, re.I) for k, v in OZNAKY.items()}
# Що не має лишитись у справі для показу (перевірка після збору; знайдено — збірка падає).
ZALYSHOK_NE_MOZHNA = re.compile(r'ОСОБА_|АДРЕСА_|НОМЕР_|ІНФОРМАЦІЯ_|' + KVARTYRA.pattern + r'|(?:серії|серія)\s*[A-ZА-ЯІЇЄҐ]{1,4}\s*\d?\s*№?\s*\d{3,}|№\s*\d{5,}', re.I)


def oznaky(t: str) -> set:
    return {k for k, rx in OZNAKY_RX.items() if rx.search(t or '')}


def bez_imen(t: str) -> str:
    """Прибрати речення з прізвищем та ініціалами чи процесуальне речення про суддю (як pokaz_fabuly.bez_imen)."""
    if not (IMENA.search(t) or PROTSES_SUDDI.search(t) or PIB_SLUZHBA.search(t) or PIB_POVNE.search(t)):
        return t
    return ' '.join(r for r in RECHENNIA.split(t)
                    if not (IMENA.search(r) or PROTSES_SUDDI.search(r) or PIB_SLUZHBA.search(r) or PIB_POVNE.search(r))).strip()


def tsili_rechennia(fab: str, tekst: str, stelia: int = 900) -> str:
    """Фабула випуску (обрізана конвеєром) → та сама фабула з тексту рішення до кінця речення. '' — не вийшло:
    фабули в тексті немає й сама вона не закінчується реченням, або речення задовге."""
    f = re.sub(r'\s+', ' ', fab or '').strip()
    t = re.sub(r'\s+', ' ', tekst or '')
    p = t.find(f[:60]) if len(f) >= 60 else -1
    if p >= 0:
        kinets = p + len(f)
        if t[p:kinets] != f:                                    # фабула в тексті інакша (злиті рядки) — шукаємо кінець по суті
            kinets = p + len(f) - 1
        m = KINETS_RECHENNIA.search(t, max(p, kinets - 1))
        if m and m.end() - p <= stelia:
            return t[p:m.end()].strip()
        # речення задовге — беремо лише цілі речення, що вміщаються
        chast = t[p:p + stelia]
        ostannie = [x.end() for x in KINETS_RECHENNIA.finditer(chast)]
        return chast[:ostannie[-1]].strip() if ostannie and ostannie[-1] >= 120 else ''
    if KINETS_RECHENNIA.search(f[-2:] if f else '') or (f and f[-1] in '.!?…'):
        return f
    return ''


def obrizaty_do_rechennia(t: str) -> str:
    """Після чистки (вирізано речення з іменами, хвости) текст має закінчуватися реченням: інакше — до останнього цілого."""
    t = t.strip(' ,;:')
    if not t:
        return ''
    if t[-1] in '.!?…»")':
        return t
    kintsi = [m.end() for m in KINETS_RECHENNIA.finditer(t)]
    if kintsi and kintsi[-1] >= 120:
        return t[:kintsi[-1]].strip()
    return t + '.' if re.search(r'[\w)»"]$', t) and len(t) >= 120 and not ZAIVE_KINETS.search(t) else ''


# Кінець, яким речення не закінчується по суті (обірване на сполучнику чи прийменнику)
ZAIVE_KINETS = re.compile(r'\s(?:і|й|та|а|але|що|як|який|яка|які|чим|у|в|на|з|із|до|по|від|за|для|при|біля|після|під|над)$', re.I)


def perevirka(dani: dict) -> list:
    """Що лишилось недозволене в справах для показу: [(doc, поле, уривок)]. Порожньо — можна публікувати."""
    pole = dani['pole']
    i_doc, i_fab, i_ch = pole.index('doc'), pole.index('fabula'), pole.index('chomu')
    bidy = []
    for s in dani['spravy']:
        for nazva, i in (('fabula', i_fab), ('chomu', i_ch)):
            t = s[i] or ''
            bez_osib = re.sub(r'Особ[аиуіою] [А-ЯІЇЄҐ]\b', 'особа', t)    # «Особа В. З метою» — не ініціал
            m = (ZALYSHOK_NE_MOZHNA.search(t) or IMENA.search(bez_osib) or PROTSES_SUDDI.search(t) or PIB_SLUZHBA.search(bez_osib)
                 or PIB_POVNE.search(t))
            if m:
                bidy.append((s[i_doc], nazva, m.group(0)))
            elif nazva == 'fabula' and t and t[-1] not in '.!?…»")':
                bidy.append((s[i_doc], nazva, 'обірване речення: …' + t[-40:]))
    return bidy



def kod_kodeksu(s: str) -> str:
    return 'КК' if s.startswith(('КК', 'Кримін')) else 'КУпАП'


def kliuch(kodeks: str, nomer: str) -> str:
    return f"{kodeks} {re.sub(r'\s*[-–]\s*', '-', nomer)}"


SLOVA_CHASTYN = {'перш': '1', 'друг': '2', 'трет': '3', 'четверт': '4', 'п': '5', 'шост': '6', 'сьом': '7'}
CHASTYNA_SLOVOM = re.compile(r'частин\w*\s+(перш|друг|трет|четверт|п.ят|шост|сьом)\w*\s+(?=ст)', re.I)


def chastyny_tsyframy(t: str) -> str:
    """«частиною першою статті 130» → «ч. 1 статті 130»: суди пишуть частину й словами."""
    def tsyfra(m):
        slovo = m.group(1).lower()
        return 'ч. ' + SLOVA_CHASTYN['п' if slovo.startswith('п') else slovo] + ' '
    return CHASTYNA_SLOVOM.sub(tsyfra, t)


def znaity_kvalifikatsiiu(tekst: str):
    """(ключ статті, частина або '') з речення про вину в резолютивній частині; None — якщо не одна кваліфікація."""
    tekst = chastyny_tsyframy(tekst)
    m = list(REZOL.finditer(tekst))
    if not m:
        return None
    rez = tekst[m[-1].end():m[-1].end() + 2500]
    # речення — до крапки перед великою літерою (не перед цифрою: «ч. 2 ст. 130» — одне речення)
    for rech in re.split(r'(?<=[.;])\s+(?=[А-ЯІЇЄҐ])', rez):
        if not VYNA.search(rech):
            continue
        # лише до «та призначити / накласти»: далі — покарання (там бувають інші статті: 75, 71 КК тощо)
        rech = re.split(r'\s(?:та|і|й)?\s*(?:призначити|накласти|застосувати|піддати|звільнити)', rech)[0]
        kv = {(kliuch(kod_kodeksu(k), n), ch or '') for ch, n, k in KVAL.findall(rech)}
        # «ст. 124, ч. 2 ст. 130 КУпАП», «ст.ст. 124, 130» — кодекс названо раз на кілька статей: теж неоднозначно
        nomery = set(re.findall(r'ст(?:\.|атт\w+)\s*(\d+(?:-\d+)?)', rech))
        if kv and (len(nomery) > 1 or re.search(r'ст\.\s*ст\.|статтями', rech)):
            return None
        if kv:
            return next(iter(kv)) if len(kv) == 1 else None
    return None


def inshi_statti(tekst: str, kl: str, vidomi) -> bool:
    """Чи судить рішення ще за іншою статтею (об'єднані справи: фабула про одне, кваліфікація про інше)."""
    tekst = chastyny_tsyframy(tekst)
    m = list(REZOL.finditer(tekst))
    do = re.sub(r'\s+', ' ', tekst[:m[-1].start()] if m else tekst)
    for rech in re.split(r'(?<=[.!?])\s+(?=[А-ЯІЇЄҐ])', do):
        if not re.search(r'передбачен|кваліфік|склад', rech):
            continue
        for ch, n, k in KVAL.findall(rech):
            inshyi = kliuch(kod_kodeksu(k), n)
            if inshyi != kl and inshyi in vidomi:
                return True
    return False


def poiasnennia(tekst: str, kl: str, chastyna: str) -> str:
    """Речення суду (до резолютивної частини), де названо ту саму кваліфікацію; найкраще — з «тобто»."""
    tekst = chastyny_tsyframy(tekst)
    m = list(REZOL.finditer(tekst))
    do = tekst[:m[-1].start()] if m else tekst
    nomer = kl.split(' ', 1)[1]
    kandydaty = []
    for rech in re.split(r'(?<=[.!?])\s+(?=[А-ЯІЇЄҐ])', re.sub(r'\s+', ' ', do)):
        for ch, n, _ in KVAL.findall(rech):
            if re.sub(r'\s*[-–]\s*', '-', n) == nomer and (ch or '') == chastyna \
                    and not re.search(r'покаран|санкці|стягнен|призначи|звільни|строк', rech):
                if not re.search(r'кваліфік|доведен|склад\w*\s+(?:адміністративн|кримінальн|правопоруш)|винн|винуват', rech):
                    continue   # речення про наказ, протокол чи процедуру — не пояснення кваліфікації
                bal = (2 if re.search(r'тобто|а\s+саме', rech) else 0) + (1 if re.search(r'кваліфік', rech) else 0)
                kandydaty.append((bal, -abs(len(rech) - 250), rech.strip()))
                break
    if not kandydaty:
        return ''
    rech = max(kandydaty)[2]
    return znejosobyty(rech, prykhovaty_statti=False)[:450]


def znejosobyty(t: str, prykhovaty_statti: bool = True) -> str:
    t = re.sub(r'\s+', ' ', t.replace('\\~', ' ')).strip()
    t = re.sub(r'(?<=[а-яіїєґА-ЯІЇЄҐ])[?`\'](?=[а-яіїєґ])', '\u2019', t)   # «здоров?я», «сп`яніння» → апостроф
    if prykhovaty_statti:                       # фабула: без зачину й рамки протоколу — з самої події
        t = ZACHYN.sub('', t, count=1)
        t = RAMKA.sub('', t, count=1)
        t = t[:1].upper() + t[1:]

    def osoba(m):
        # за номером, а не за порядком появи: та сама людина — та сама буква і у фабулі, і в поясненні суду
        return f'Особа {BUKVY[(int(m.group(1)) - 1) % len(BUKVY)]}'
    t = bez_imen(t)
    # роль + мітка → роль («водій ОСОБА_2» → «водій»); «гр. ОСОБА_1» → «Особа А» (громадянин — не роль)
    t = re.sub(r'(?:гр\.|громадян\w*)\s+(?=ОСОБА_)', '', t, flags=re.I)
    t = ROL_OSOBA.sub(lambda m: m.group(1), t)
    t = re.sub(r'ОСОБА_(\d+)', osoba, t)
    t = PROTOKOL.sub('', t)
    t = KVARTYRA.sub(lambda m: '' if m.group(1).lower() == 'кв.' else m.group(1), t)
    t = re.sub(r'\s*,?\s*ІНФОРМАЦІЯ_\d+\s*,?', ',', t)
    t = NOMER_AVTO.sub('', t)
    t = re.sub(r'НОМЕР_\d+|АДРЕСА_\d+', '…', t)
    t = VULYTSIA.sub(r'\1', t)
    t = re.sub(r'(будин\w+|буд\.)\s*№?\s*\d+[^\s,.;]*', r'\1', t)
    t = re.sub(r'(будин\w+)\s+буд\.?(?=\s)', r'\1', t)
    t = re.sub(r'(?<![\w.])буд\.(\.?)(?!\s*\d)', r'будинку\1', t)   # «буд. №5. Після» → «будинку. Після»: крапка речення лишається      # «біля буд. по вул.» → «біля будинку по вул.»
    if prykhovaty_statti:
        t = STATTIA_U_TEKSTI.sub('[стаття]', t)
        t = ZAIVE_RECHENNIA.sub('', t)
        t = ZAIVE_KVAL.sub('', t)
        t = re.sub(r'про\s+адміністративн\w+\s+правопорушенн\w+', '', t)
        t = re.sub(r'(?:адміністративн|кримінальн)\w+\s+(правопорушенн\w*|проступ\w*)', r'\1', t)
        t = re.sub(r'\b(КУпАП|КпАП|КК України)\b', '', t)
    t = re.sub(r'\s+([,.;:])', r'\1', t)
    t = re.sub(r',\s*,', ',', t)
    t = re.sub(r'\s{2,}', ' ', t).strip(' ,')
    return t


def poza_skasovani(con) -> tuple[set, str]:
    """-> (doc_id, які не йдуть у гру; пояснення для журналу). Скасовані/змінені вищим судом і видалені за зверненням."""
    tabl = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    poza, slova = set(), []
    if 'skasuvannia' in tabl:
        q = ','.join('?' * len(SKASOVANO_NASLIDKY))
        poza |= {d for (d,) in con.execute(f'SELECT doc_id FROM skasuvannia WHERE naslidok IN ({q})', SKASOVANO_NASLIDKY)}
        slova.append(f'скасованих чи змінених вищим судом: {len(poza)}')
    else:
        slova.append('у випуску немає таблиці skasuvannia — скасовані в апеляції не відсіяно')
    if 'withdrawal' in tabl:
        vz = {d for (d,) in con.execute('SELECT doc_id FROM withdrawal')}
        slova.append(f'видалених за зверненням: {len(vz)}')
        poza |= vz
    return poza, '; '.join(slova)


def zibraty(baza: Path, teksty: list[Path], na_chastynu: int = 60, log=print) -> dict:
    con = sqlite3.connect(f'file:{baza}?mode=ro', uri=True)
    vypusk = con.execute('SELECT versiia FROM release').fetchone()[0]
    poza, pro_poza = poza_skasovani(con)
    log(pro_poza)
    epizodiv = Counter(d for (d,) in con.execute('SELECT doc_id FROM event'))
    nazvy: dict[str, str] = {}
    chastota: Counter = Counter()
    podii = {}
    for doc, st, fab, vyd, data, url in con.execute(
            'SELECT e.doc_id, e.stattia, e.fabula, e.vyd, d.data_rishennia, d.url FROM event e JOIN document d USING(doc_id) '
            'WHERE e.chutlyva = 0 AND e.fabula IS NOT NULL AND e.stattia IS NOT NULL'):
        m = re.match(r'ст\.(\S+) (КК|КУпАП)(?: · (.+))?', st)
        if not m or POZA.search(st):
            continue
        k = f'{m.group(2)} {m.group(1)}'
        chastota[k] += 1
        nazvy.setdefault(k, m.group(3) or '')
        if epizodiv[doc] == 1 and not DITY.search(fab) and doc not in poza:
            podii[doc] = (k, fab, vyd, data, url)
    zibrano = defaultdict(list)
    vidkynuto: Counter = Counter()
    for f in teksty:
        with lzma.open(f, 'rt', encoding='utf-8') as fh:
            for ryadok in fh:
                doc = ryadok[12:ryadok.find('"', 12)] if ryadok.startswith('{"doc_id": "') else json.loads(ryadok)['doc_id']
                if doc not in podii:
                    continue
                z = json.loads(ryadok)
                k, fab, vyd, data, url = podii.pop(doc)   # те саме рішення буває в кількох файлах — беремо раз
                kv = znaity_kvalifikatsiiu(z.get('tekst') or '')
                if not kv or kv[0] != k or inshi_statti(z['tekst'], k, chastota):
                    continue
                tsila = tsili_rechennia(fab, z['tekst'])
                if not tsila or NE_KYIV.search(tsila):
                    vidkynuto['не цілим реченням' if not tsila else 'не Київ'] += 1
                    continue
                fabula = znejosobyty(tsila)
                kh = KHVIST_PROTSES.search(fabula, 100)
                fabula = obrizaty_do_rechennia(fabula[:kh.start()] if kh else fabula)
                if not 120 <= len(fabula) <= 900 or 'ОСОБА_' in fabula or SHAPKA.search(fabula) \
                        or ZALYSHOK_NOMERA.search(fabula) or POCHATOK_NE_PODIIA.search(fabula):
                    vidkynuto['шапка, довжина чи початок не з події'] += 1
                    continue
                chomu = poiasnennia(z['tekst'], k, kv[1])
                # ознака частини — в умові: що суд назвав у поясненні, мусить бути у фабулі (ZAVDANNYA-176)
                treba = oznaky(chomu) if chomu else set()
                if treba - oznaky(fabula) or (not chomu and kv[1] not in ('', '1') and not oznaky(fabula)):
                    vidkynuto['ознаки частини немає в умові'] += 1
                    continue
                zibrano[(k, kv[1])].append({'doc': doc, 'fabula': fabula, 'chomu': chomu, 'url': url,
                                            'data': data, 'vyd': vyd})
    # Частини, які справді є: для статей зачатку — його перелік (у ст. 173 КУпАП частин немає, хоч суди й пишуть «ч. 1»);
    # для решти — частина щонайменше в 3 справах і 1 % справ статті. Справа з іншою частиною не йде.
    zachatok = json.loads(KVAL_ZACHATOK.read_text(encoding='utf-8'))['statti'] if KVAL_ZACHATOK.exists() else {}
    vsogo_st = Counter()
    for (k, ch), sp in zibrano.items():
        vsogo_st[k] += len(sp)
    chysti = defaultdict(list)
    for (k, ch), sp in zibrano.items():
        if k in zachatok:
            dozv = zachatok[k].get('chastyny') or []
            if not dozv:
                ch = ''
            elif ch and ch not in dozv:
                continue
        elif ch and (len(sp) < 3 or len(sp) < 0.01 * vsogo_st[k]):
            continue
        chysti[(k, ch)] += sp
    zibrano = chysti
    # Добір: на кожну пару «стаття + частина» — до na_chastynu справ, спершу з поясненням суду; порядок — сталий (хеш).
    spravy = []
    chastyny = defaultdict(Counter)
    for (k, ch), sp in zibrano.items():
        chastyny[k][ch] += len(sp)
        sp.sort(key=lambda s: (not s['chomu'], hashlib.sha1(s['doc'].encode()).hexdigest()))
        spravy += [dict(s, stattia=k, chastyna=ch) for s in sp[:na_chastynu]]
    poriadok = [k for k, _ in chastota.most_common() if k in chastyny]
    statti = {}
    for i, k in enumerate(poriadok):
        riven = 1 if i < 4 else 2 if i < 10 else 3 if i < 20 else 4
        vsi_ch = sorted((set(chastyny[k]) | set((zachatok.get(k) or {}).get('chastyny') or [])) - {''}, key=int)
        statti[k] = {'nazva': (zachatok.get(k) or {}).get('nazva') or nazvy[k], 'korotko': nazvy[k],
                     'kodeks': k.split(' ')[0], 'n': chastota[k], 'riven': riven,
                     'chastyny': vsi_ch, 'chastky': {c or '—': n for c, n in chastyny[k].most_common()}}
    vykhid = []
    for s in sorted(spravy, key=lambda s: hashlib.sha1(s['doc'].encode()).hexdigest()):
        st = statti[s['stattia']]
        vsogo = sum(chastyny[s['stattia']].values())
        ridka = s['chastyna'] and chastyny[s['stattia']][s['chastyna']] / vsogo < 0.15
        vykhid.append([s['doc'], s['stattia'], s['chastyna'], s['fabula'], s['chomu'], s['url'], s['data'],
                       min(5, st['riven'] + (1 if ridka else 0)), s['vyd']])
    log('не взято: ' + (', '.join(f'{k} — {v}' for k, v in vidkynuto.most_common()) or 'нічого'))
    return {'versiia': 1, 'vypusk': vypusk, 'skasovani': pro_poza, 'zibrano': datetime.date.today().isoformat(),
            'pole': ['doc', 'stattia', 'chastyna', 'fabula', 'chomu', 'url', 'data', 'skladnist', 'vyd'],
            'statti': statti, 'spravy': vykhid}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--baza', required=True, type=Path)
    p.add_argument('--teksty', required=True, type=Path, help='тека з *.jsonl.xz (Release teksty)')
    p.add_argument('--vykhid', type=Path, default=TUT / 'kariera.json')
    p.add_argument('--na-chastynu', type=int, default=60)
    a = p.parse_args()
    d = zibraty(a.baza, sorted(Path(x) for x in glob.glob(str(a.teksty / '*.jsonl.xz'))), a.na_chastynu)
    bidy = perevirka(d)
    if bidy:
        raise SystemExit(f'Справи не годяться для показу ({len(bidy)}), файл не записано: ' +
                         '; '.join(f'{doc} {pole}: «{u}»' for doc, pole, u in bidy[:10]))
    a.vykhid.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f"справ: {len(d['spravy'])}, статей: {len(d['statti'])} → {a.vykhid}")


if __name__ == '__main__':
    main()

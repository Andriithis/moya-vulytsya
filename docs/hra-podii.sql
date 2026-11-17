-- Події ігор «Вгадай, де це було» (ZAVDANNYA-07) і «Вулиця дня» (ZAVDANNYA-114) в лічильнику заглушки.
-- Виконати в сховищі ПІСЛЯ docs/zahlushka-skhema.sql — дописує десять назв подій
-- до дозволеного переліку таблиці podiya. Нових стовпців немає: лише назва події і канал,
-- без кукі, ідентифікаторів і адрес сторінок (як для чотирьох чисел).
--
--   hra_start        — почали раунд з 10 подій або «подію дня»
--   hra_vidpovid     — відповіли на одну подію
--   hra_kinets       — дограли раунд до кінця
--   hra_podilytysia  — натиснули «Поділитися»
--   den_zihrano      — зіграли «подію дня» (раз на добу на пристрої)
--
-- Друга гра «Вулиця дня» (MV-126, ZAVDANNYA-114) — ще п'ять назв:
--   vd_start         — зробили першу спробу дня
--   vd_kinets        — розгадали або вичерпали 7 спроб
--   vd_storinka      — з кінця гри перейшли на сторінку загаданої вулиці
--   vd_pidpyska      — натиснули «А що на вашій вулиці?» (підписка «Мій район»)
--   vd_podilytysia   — натиснули «Поділитися»

alter table public.podiya drop constraint if exists podiya_nazva_check;
alter table public.podiya add constraint podiya_nazva_check check (nazva in (
  'pryishly', 'adresa', 'peredzamovyty', 'kontakt',
  'hra_start', 'hra_vidpovid', 'hra_kinets', 'hra_podilytysia', 'den_zihrano',
  'vd_start', 'vd_kinets', 'vd_storinka', 'vd_pidpyska', 'vd_podilytysia'
));

-- Скільки грають, за тижнями і каналами (поруч із чотирма числами).
-- select date_trunc('week', chas) as tyzhden, kanal,
--        count(*) filter (where nazva = 'hra_start')       as pochaly,
--        count(*) filter (where nazva = 'hra_kinets')      as doigraly,
--        count(*) filter (where nazva = 'den_zihrano')     as podiya_dnya,
--        count(*) filter (where nazva = 'hra_podilytysia') as podilylysia
-- from public.podiya group by 1, 2 order by 1 desc, 2;

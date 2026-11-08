-- Події гри «Вгадай, де це було» в лічильнику заглушки (ZAVDANNYA-07).
-- Виконати в сховищі ПІСЛЯ docs/zahlushka-skhema.sql — дописує п'ять назв подій
-- до дозволеного переліку таблиці podiya. Нових стовпців немає: лише назва події і канал,
-- без кукі, ідентифікаторів і адрес сторінок (як для чотирьох чисел).
--
--   hra_start        — почали раунд з 10 подій або «подію дня»
--   hra_vidpovid     — відповіли на одну подію
--   hra_kinets       — дограли раунд до кінця
--   hra_podilytysia  — натиснули «Поділитися»
--   den_zihrano      — зіграли «подію дня» (раз на добу на пристрої)

alter table public.podiya drop constraint if exists podiya_nazva_check;
alter table public.podiya add constraint podiya_nazva_check check (nazva in (
  'pryishly', 'adresa', 'peredzamovyty', 'kontakt',
  'hra_start', 'hra_vidpovid', 'hra_kinets', 'hra_podilytysia', 'den_zihrano'
));

-- Скільки грають, за тижнями і каналами (поруч із чотирма числами).
-- select date_trunc('week', chas) as tyzhden, kanal,
--        count(*) filter (where nazva = 'hra_start')       as pochaly,
--        count(*) filter (where nazva = 'hra_kinets')      as doigraly,
--        count(*) filter (where nazva = 'den_zihrano')     as podiya_dnya,
--        count(*) filter (where nazva = 'hra_podilytysia') as podilylysia
-- from public.podiya group by 1, 2 order by 1 desc, 2;

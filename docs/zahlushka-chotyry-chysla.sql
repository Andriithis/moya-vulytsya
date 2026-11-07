-- Чотири числа заглушки (MV-5, MV-9) за тиждень і за каналами.
-- Де виконати: панель Supabase → SQL Editor. Лише читає.
-- Тиждень — з понеділка за київським часом. Канал «perevirka» (тестові записи
-- перевірки форми з GitHub Actions) не рахується.
-- Увага: це натискання, а не люди. Одна людина, що відкрила сторінку тричі,
-- дає 3 у «прийшли». Поки немає оплати, четверте число — «залишили контакт».

with podii as (
  select date_trunc('week', chas at time zone 'Europe/Kyiv')::date as tyzhden,
         kanal, nazva
  from public.podiya
  where kanal <> 'perevirka'
),
zayavky as (
  select date_trunc('week', chas at time zone 'Europe/Kyiv')::date as tyzhden,
         kanal, count(*) as zayavok
  from public.zayavka
  where kanal <> 'perevirka'
  group by 1, 2
),
chysla as (
  select tyzhden, kanal,
         count(*) filter (where nazva = 'pryishly')      as pryishly,
         count(*) filter (where nazva = 'adresa')        as vvely_adresu,
         count(*) filter (where nazva = 'peredzamovyty') as natysnuly_peredzamovyty,
         count(*) filter (where nazva = 'kontakt')       as zalyshyly_kontakt
  from podii
  group by 1, 2
)
select coalesce(c.tyzhden, z.tyzhden) as tyzhden,
       coalesce(c.kanal, z.kanal)     as kanal,
       coalesce(c.pryishly, 0)                as pryishly,
       coalesce(c.vvely_adresu, 0)            as vvely_adresu,
       coalesce(c.natysnuly_peredzamovyty, 0) as natysnuly_peredzamovyty,
       coalesce(c.zalyshyly_kontakt, 0)       as zalyshyly_kontakt,
       coalesce(z.zayavok, 0)                 as zayavok_u_tablytsi  -- для звірки з «залишили контакт»
from chysla c
full join zayavky z on z.tyzhden = c.tyzhden and z.kanal = c.kanal
order by tyzhden desc, pryishly desc, kanal;

-- Разом за тиждень по всіх каналах — розкоментувати:
-- select date_trunc('week', chas at time zone 'Europe/Kyiv')::date as tyzhden,
--        count(*) filter (where nazva = 'pryishly') as pryishly,
--        count(*) filter (where nazva = 'adresa') as vvely_adresu,
--        count(*) filter (where nazva = 'peredzamovyty') as natysnuly_peredzamovyty,
--        count(*) filter (where nazva = 'kontakt') as zalyshyly_kontakt
-- from public.podiya where kanal <> 'perevirka' group by 1 order by 1 desc;

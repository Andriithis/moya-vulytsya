-- Схема сховища заглушки «Моя вулиця» (ZAVDANNYA-02, MV-8). Лише структура, без даних.
-- Де виконати: панель Supabase → SQL Editor → вставити весь файл → Run.
-- Виконує власник облікового запису. Виконавець у Supabase нічого не створював.
--
-- Правило доступу:
--   * анонімний відвідувач (публічний ключ сторінки) може ЛИШЕ ДОДАТИ рядок;
--     читати, змінювати й видаляти — ні;
--   * читає власник у панелі Supabase; перевірка форми (GitHub Actions)
--     видаляє свої тестові рядки ключем service_role із секрету GitHub.
-- Час ставить сховище (now()), а не браузер. IP, браузер, ідентифікатори
-- відвідувача в таблицях не зберігаються — таких стовпців немає.

-- ---------- Заявки з форми передзамовлення ----------
create table if not exists public.zayavka (
  id       bigint generated always as identity primary key,
  chas     timestamptz not null default now(),
  shcho    text not null check (shcho in ('analiz', 'pidpyska', 'povidomyty', 'kompaniya')),
  misto    text not null check (char_length(misto) between 1 and 80),
  adresa   text check (adresa is null or char_length(adresa) <= 200),
  kontakt  text not null check (char_length(kontakt) between 3 and 120),
  zghoda   boolean not null check (zghoda = true),
  kanal    text not null default 'priamo' check (kanal ~ '^[a-z0-9-]{1,40}$')
);
comment on table public.zayavka is 'Заявки з передзамовлення. Зберігати до запуску міста + 6 місяців або до відкликання згоди.';

-- ---------- Події для чотирьох чисел ----------
create table if not exists public.podiya (
  id     bigint generated always as identity primary key,
  chas   timestamptz not null default now(),
  nazva  text not null check (nazva in ('pryishly', 'adresa', 'peredzamovyty', 'kontakt')),
  kanal  text not null default 'priamo' check (kanal ~ '^[a-z0-9-]{1,40}$')
);
comment on table public.podiya is 'Натискання на заглушці (не люди): лише час, назва події, канал.';

create index if not exists podiya_chas on public.podiya (chas);
create index if not exists zayavka_chas on public.zayavka (chas);

-- ---------- Доступ ----------
alter table public.zayavka enable row level security;
alter table public.podiya  enable row level security;

-- Supabase за замовчуванням дає ролям anon і authenticated усі права на нові
-- таблиці. Забираємо все і даємо лише додавання дозволених стовпців.
revoke all on public.zayavka from anon, authenticated;
revoke all on public.podiya  from anon, authenticated;
grant insert (shcho, misto, adresa, kontakt, zghoda, kanal) on public.zayavka to anon;
grant insert (nazva, kanal) on public.podiya to anon;

drop policy if exists zayavka_lyshe_dodaty on public.zayavka;
create policy zayavka_lyshe_dodaty on public.zayavka for insert to anon with check (zghoda = true);
drop policy if exists podiya_lyshe_dodaty on public.podiya;
create policy podiya_lyshe_dodaty on public.podiya for insert to anon with check (true);
-- Політик на select / update / delete для anon немає — отже, анонім їх не може.

-- =====================================================================
-- ZAVDANNYA-06. Звернення про виправлення або видалення (форма zvernennya.html).
-- Виконати в тому самому SQL Editor після частини вище. Правило те саме:
-- анонім (публічний ключ сторінки) може ЛИШЕ ДОДАТИ рядок; читає й відповідає
-- власник у панелі Supabase. Таблиця водночас — журнал звернень із датами
-- (docs/03-dani-i-etyka.md, розділ 7): строк відповіді — 10 робочих днів.
-- =====================================================================
create table if not exists public.zvernennya (
  id            bigint generated always as identity primary key,
  chas          timestamptz not null default now(),
  posylannya    text not null check (char_length(posylannya) between 1 and 300),
  shcho_ne_tak  text not null check (shcho_ne_tak in ('mistse', 'opys', 'vydalyty', 'inshe')),
  poyasnennya   text check (poyasnennya is null or char_length(poyasnennya) <= 2000),
  kontakt       text not null check (char_length(kontakt) between 3 and 120),
  zghoda        boolean not null check (zghoda = true),
  -- Нижче — лише для власника (анонім цих стовпців не має права заповнювати):
  stan          text not null default 'nove'
                check (stan in ('nove', 'v_roboti', 'vypravleno', 'vydaleno', 'vidmova')),
  vidpovid_chas timestamptz,
  prymitka      text
);
comment on table public.zvernennya is 'Звернення про виправлення або видалення. Відповідь — протягом 10 робочих днів. Зберігати 1 рік після відповіді.';
create index if not exists zvernennya_chas on public.zvernennya (chas);

alter table public.zvernennya enable row level security;
revoke all on public.zvernennya from anon, authenticated;
grant insert (posylannya, shcho_ne_tak, poyasnennya, kontakt, zghoda) on public.zvernennya to anon;
drop policy if exists zvernennya_lyshe_dodaty on public.zvernennya;
create policy zvernennya_lyshe_dodaty on public.zvernennya for insert to anon with check (zghoda = true);
-- Політик на select / update / delete для anon немає — отже, анонім їх не може.

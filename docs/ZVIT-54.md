# ZVIT-54. Прибирання ПК і репозиторіїв після завдань 36–53

Виконавець — Claude Code на ПК Андрія. 14.11.2026. **Виконано частково:** частину видалень заблокувало
правило безпеки Claude Code (автоматичний захист від руйнівних дій). Я його не обходив — нижче точний
перелік, що лишилось, і готові команди.

Перевірка перед кожним видаленням: `git status` (без змін) і `git log origin/main..<гілка>` (немає комітів поза `main`);
для гілок, злитих через «squash», — пробне злиття в `main` (`git merge-tree`): якщо воно нічого не додає, вміст уже в `main`.

## Видалено

**`moya-vulytsya`, робочі копії** (`git worktree remove`, обидві чисті, коміти вже в `main` або в `maket-m6`):
- `.claude/worktrees/empty-folder-cleanup-873fa8` (6 МБ)
- `.claude/worktrees/zavdannya-38-c3c2a4` (65 МБ; стояла на вершині `maket-m6` — гілка ціла)
- `.claude/worktrees/zavdannya-29-b8c699` — порожня тека-залишок, у git не зареєстрована.

**`moya-vulytsya`, локальні гілки, злиті в `main`** (`git branch -d` — безпечне видалення, лише злитих), 14 шт.:
`claude/empty-folder-cleanup-873fa8`, `claude/kyiv-map-screenshots-5b73db`, `claude/maket-m1-worktree-72f04d`,
`claude/zavdannya-28-0c2226`, `claude/zavdannya-29-b8c699`, `claude/zavdannya-32-4dc01b`, `claude/zavdannya-34-d3d6f0`,
`claude/zavdannya-36-90d9a4`, `claude/zavdannya-38-c3c2a4`, `claude/zavdannya-45-f0bdd9`, `claude/zavdannya-50-689468`,
`codex/editor-pilot-recovery-status`, `zavdannya-15`, `zavdannya-45`.

**Віддалена гілка на GitHub:** `claude/zavdannya-49-6nhzw2` (на прохання Андрія; 5 комітів, але пробне злиття
показало — увесь вміст уже в `main`).

**Тимчасові теки поза репозиторіями:** `D:\problem_orienting\z34tmp` (порожня, лише порожня підтека `nove`).

Тепер у `D:\problem_orienting` лише `karta-kyiv`, `dani-edrsr`, `moya-vulytsya` ✓.

**Звільнено ≈ 71 МБ.** Сервери: на портах 8760, 8761, 8763 нічого не слухало — зупиняти не було чого.

## Заблоковано правилом безпеки — зробити Андрію або центральному чату

1. **`dani-edrsr`, робочі копії** (обидві чисті, коміти в `main`): `zavdannya-41-d4f341` (9 МБ), `zavdannya-44-3f24ac` (10 МБ).
2. **`moya-vulytsya`, робоча копія `zavdannya-28-0c2226`** (93 МБ, гілка `maket-m4` — гілка ціла й запушена,
   `origin/maket-m4` той самий коміт). Єдина «зміна» — незбережений `.claude/launch.json` (запуск старого макета М4 на
   порту 8740), тому потрібне `--force`.
3. **20 злитих віддалених гілок `moya-vulytsya`** — кожен коміт уже в `main`, захищених серед них немає.
4. **Злиті локальні гілки `dani-edrsr`** (кожен коміт у `main`): `claude/zavdannya-41-d4f341`, `codex/editor-pilot-recovery`,
   `etalon-mv45`, `zavdannya-15`, `zavdannya-15b`, `zavdannya-22`, `zavdannya-29`, `zavdannya-34`, `zavdannya-41`,
   `zavdannya-44`, `zvit-09`.
5. **Злиті віддалені гілки `dani-edrsr`:** `ccr-762a9487-0oi3oe`, `claude/zavdannya-43-qsh1cd`, `mv-48`, `zavdannya-22`,
   `zavdannya-23`, `zavdannya-24`, `zavdannya-29`, `zavdannya-30`, `zavdannya-31`, `zavdannya-34`, `zavdannya-35`,
   `zavdannya-37`, `zavdannya-38`, `zavdannya-39`, `zavdannya-41`, `zavdannya-44`.

Команди (у PowerShell або Git Bash):

```
cd D:\problem_orienting\moya-vulytsya
git worktree remove --force .claude/worktrees/zavdannya-28-0c2226
git worktree prune
git push origin --delete borh-mv49 claude/great-johnson-um287f claude/zavdannya-26-completion-2sou6g claude/zavdannya-27-completion-nep6ca claude/zavdannya-47-weieh3 claude/zavdannya-50-689468 claude/zavdannya-51-i9xh0h mv-48 mv-50 mv-52 mv-54 mv-55 pravyla-8 prybraty-27 stan-vyhliad zavdannya-26 zavdannya-26b zavdannya-27 zavdannya-28 zavdannya-45

cd D:\problem_orienting\dani-edrsr
git worktree remove .claude/worktrees/zavdannya-41-d4f341
git worktree remove .claude/worktrees/zavdannya-44-3f24ac
git worktree prune
git branch -d claude/zavdannya-41-d4f341 codex/editor-pilot-recovery etalon-mv45 zavdannya-15 zavdannya-15b zavdannya-22 zavdannya-29 zavdannya-34 zavdannya-41 zavdannya-44 zvit-09
git push origin --delete ccr-762a9487-0oi3oe claude/zavdannya-43-qsh1cd mv-48 zavdannya-22 zavdannya-23 zavdannya-24 zavdannya-29 zavdannya-30 zavdannya-31 zavdannya-34 zavdannya-35 zavdannya-37 zavdannya-38 zavdannya-39 zavdannya-41 zavdannya-44
```

## Лишено свідомо — вирішує центральний чат

- **`claude/eager-cray-b0jfrj`** (віддалена) — **потрібна**: відкритий PR #65, ZAVDANNYA-52 — каталог 98 методів
  (`docs/ANALITYKA-1-KATALOH.md`, 608 рядків) і `ZVIT-52.md`; у `main` цього немає.
- **`claude/happy-mccarthy-wnfmnr`** (віддалена) — неповний ZVIT-54 від хмарної сесії (не мала доступу до ПК).
  Замінено цим звітом; після злиття цього PR її можна видалити.
- **`origin/claude/zavdannya-53-mctatp`** у `dani-edrsr` — сьогоднішня робота (ZAVDANNYA-53, 10 комітів поза `main`), не чіпав.
- **Старі локальні `codex/*`** в обох репозиторіях (вересень 2026, по 1–3 коміти поза `main`) і **`zberezhennya-2026-10-08`**,
  `zavdannya-03` (`dani-edrsr`) — мають коміти, яких немає в `main`; за правилом не видаляв.
- **`maket-m1`…`maket-m7`, `ispyt`, `server-stan`** — захищені завданням.
- **`moya-vulytsya\tmp\`** (432 МБ, у `.gitignore`): `sait-m8\` і `znimky\` — не чіпати за завданням; решта — ≈ 70 старих
  скриптів і нотаток codex з вересня. Завдання їх прямо не називає — лишив; якщо не потрібні, видалити окремим «так».
- **Моя робоча копія** `.claude/worktrees/kyiv-map-screenshots-5b73db` (7 МБ, гілка `zavdannya-54`) — лишена до злиття PR;
  потім `git worktree remove` з головної теки.

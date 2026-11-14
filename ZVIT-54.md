# ZVIT-54. Прибирання ПК і репозиторіїв — виконано частково

Виконавець — Claude Code, **хмарна сесія** (не на ПК Андрія). 14.11.2026.

## Головне

**Пункти 1, 2, 4, 5 не виконано.** Завдання треба робити на ПК Андрія (`D:\problem_orienting`), а до цієї сесії
комп'ютер не під'єднано: список тек з ПК, доступних хмарній сесії, порожній. Робочі копії git, локальні гілки
й тимчасові теки (`z34tmp` тощо) лежать лише на ПК — звідси їх не видно й не видалити.
Нічого на ПК не видалено, сервери на портах 8760/8761/8763 не чіпались.

**Пункт 3 (віддалені гілки) — не видалено, лише перелік.** `git push origin --delete` з хмарної сесії
повертає відмову GitHub (помилка 403 — немає права видаляти гілки). За правилом завдання — список нижче.

## Віддалені гілки `moya-vulytsya`, повністю злиті в `main` (можна видаляти)

Перевірено `git branch -r --merged origin/main` після `git fetch --prune` 14.11.2026: кожен коміт цих гілок уже є в `main`.
Захищених (`ispyt`, `server-stan`, `maket-*`) серед них немає.

- `borh-mv49`
- `claude/great-johnson-um287f`
- `claude/zavdannya-26-completion-2sou6g`
- `claude/zavdannya-27-completion-nep6ca`
- `claude/zavdannya-47-weieh3`
- `claude/zavdannya-50-689468`
- `claude/zavdannya-51-i9xh0h`
- `mv-48`
- `mv-50`
- `mv-52`
- `mv-54`
- `mv-55`
- `pravyla-8`
- `prybraty-27`
- `stan-vyhliad`
- `zavdannya-26`
- `zavdannya-26b`
- `zavdannya-27`
- `zavdannya-28`
- `zavdannya-45`

Команда для ПК (одним рядком, з теки `moya-vulytsya`):

```
git push origin --delete borh-mv49 claude/great-johnson-um287f claude/zavdannya-26-completion-2sou6g claude/zavdannya-27-completion-nep6ca claude/zavdannya-47-weieh3 claude/zavdannya-50-689468 claude/zavdannya-51-i9xh0h mv-48 mv-50 mv-52 mv-54 mv-55 pravyla-8 prybraty-27 stan-vyhliad zavdannya-26 zavdannya-26b zavdannya-27 zavdannya-28 zavdannya-45 
```

## Віддалені гілки, НЕ злиті в `main` — не чіпав

- `maket-m1`, `maket-m3` … `maket-m7` — захищені завданням.
- `claude/eager-cray-b0jfrj`, `claude/zavdannya-49-6nhzw2` — мають коміти, яких немає в `main`
  (можливо, злиті через «squash» і тому git не бачить їх як злиті — не перевірено). Вирішує центральний чат.

## Не перевірено

- `dani-edrsr`: цей репозиторій не підключено до сесії — його гілки не переглядав.
- Скільки місця звільнено — нуль: на ПК нічого не видалено.

## Що далі

Запустити ZAVDANNYA-54 у Claude Code **на ПК Андрія** (або під'єднати теку `D:\problem_orienting` до хмарної сесії
через Remote Control у застосунку Claude). Перелік віддалених гілок вище можна видалити там же.

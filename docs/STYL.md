# Стиль «Моєї вулиці» — коротко для виконавців

Одна система дизайну для сайту, додатка Android, ігор, карти, звіту й заглушки (MV-15).
Повна версія з правилами й зразками — артефакт «Моя вулиця — система дизайну»:
<https://claude.ai/artifact/Lq9aApUxwVnK8gKxBhjBBb>
(читати інструментом `mcp__claude-artifacts__read_file`, slug `a0969e3c-8866-45e7-acef-907a319e14de`,
шляхи `project/README.md`, `project/tokens.json`). Де цей файл і артефакт розходяться — діє артефакт.

## Головне

- Колір = кількість подій у даних, не небезпека. Шкала `data-1…5`, не червоне.
- `accent` (бірюзовий) — головна дія, посилання, «ця адреса». `attention` (помаранчевий) — лише чинна проблема й «МАКЕТ».
- Заголовки й числа — Manrope 800; текст — Inter. Шрифти — файлами з сайту.
- Картки — рамка 1 px, без тіней. Кути: картки 14 px, кнопки й поля 10 px.
- Ніколи: «небезпечно», «безпечно», рейтинг, емодзі, градієнти.

## Змінні CSS (світла / темна тема)

```css
:root {
  --ground: #F7F6F2;
  --surface: #FFFFFF;
  --surface-tint: #F1F7F6;
  --ink: #1B1F24;
  --ink-2: #3D434C;
  --muted: #5B616B;
  --line: #E3E1DA;
  --line-strong: #C9C6BD;
  --accent: #0B6B6B;
  --accent-strong: #064848;
  --accent-soft: #D7EBEA;
  --on-accent: #FFFFFF;
  --attention: #B45309;
  --attention-soft: #FBEBDD;
  --error: #A1281C;
  --data-1: #F1F7F6;
  --data-2: #D7EBEA;
  --data-3: #9CCBC7;
  --data-4: #4FA39D;
  --data-5: #0B6B6B;
  --data-city: #A9ADB4;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 40px;
  --space-9: 56px;
  --space-10: 72px;
  --radius-s: 4px;
  --radius-m: 10px;
  --radius-l: 14px;
  --radius-pill: 999px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ground: #111517;
    --surface: #1A2023;
    --surface-tint: #182B2A;
    --ink: #ECEEEA;
    --ink-2: #CDD1CC;
    --muted: #9AA1A8;
    --line: #2C3438;
    --line-strong: #3C464B;
    --accent: #5CB8AF;
    --accent-strong: #8FD3CB;
    --accent-soft: #1E3A38;
    --on-accent: #0B1414;
    --attention: #F0A257;
    --attention-soft: #3A2A18;
    --error: #F08C80;
    --data-1: #1C2A2B;
    --data-2: #1E3F3D;
    --data-3: #2C6662;
    --data-4: #3F978F;
    --data-5: #6FC9BF;
    --data-city: #6B737B;
  }
}
```

## Шрифтові стилі

| Стиль | Розмір / рядок | Шрифт |
|---|---|---|
| `display` | 52px / 56px | Manrope 800 |
| `title-1` | 34px / 40px | Manrope 800 |
| `title-2` | 24px / 30px | Manrope 800 |
| `title-3` | 20px / 26px | Manrope 700 |
| `number` | 30px / 34px | Manrope 800 |
| `body-l` | 18px / 28px | Inter 400 |
| `body` | 16px / 24px | Inter 400 |
| `body-s` | 15px / 22px | Inter 400 |
| `label` | 14px / 20px | Inter 600 |
| `caption` | 13px / 18px | Inter 400 |
| `micro` | 12px / 16px | Inter 600 |

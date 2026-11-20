-- ZAVDANNYA-178: оновлення бази, створеної раніше (на новій базі не потрібне — усе вже в skhema.sql).
-- npx wrangler d1 execute moya-vulytsya-prodazh --remote --file=skhema-178.sql   (раз; повтор скаже «duplicate column» — це нестрашно)
-- Без цього файла сервер працює як раніше, лише без «картки для мешканців» (у журналі — «стара база без стовпців картки»).
-- «Картка для мешканців / клієнта» (MV-183): коротка сторінка лише з числами поруч із довідкою; своє посилання, яке можна закрити.
ALTER TABLE dovidky ADD COLUMN kartka_fail TEXT;
ALTER TABLE dovidky ADD COLUMN kartka_hash TEXT;

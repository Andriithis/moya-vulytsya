// Листи (ZAVDANNYA-99). Сервіс пошти обирає партнер; тут — змінна POSHTA_SERVIS:
//   'zahlushka' (за замовчуванням) — лист нікуди не йде: пишеться в журнал Workers без посилань (у тестах — у env.__LYSTY);
//   'http-json' — POST JSON { from, to, subject, text } на POSHTA_URL з заголовком Authorization: Bearer POSHTA_KLIUCH
//                 (такий формат має, наприклад, Resend; інший сервіс — дописати тут одну гілку).
// Адреса відправника — POSHTA_VID. Ключ — лише секрет Workers.

export async function nadislaty(env, { komu, tema, tekst }) {
  const servis = env.POSHTA_SERVIS || 'zahlushka';
  if (servis === 'zahlushka') {
    if (Array.isArray(env.__LYSTY)) env.__LYSTY.push({ komu, tema, tekst });
    else console.log(`лист (заглушка): «${tema}»`);
    return true;
  }
  if (servis === 'http-json') {
    const r = await fetch(env.POSHTA_URL, {
      method: 'POST',
      headers: { authorization: `Bearer ${env.POSHTA_KLIUCH}`, 'content-type': 'application/json' },
      body: JSON.stringify({ from: env.POSHTA_VID, to: [komu], subject: tema, text: tekst }),
    });
    if (!r.ok) throw new Error(`пошта: ${r.status}`);
    return true;
  }
  throw new Error(`невідомий сервіс пошти: ${servis}`);
}

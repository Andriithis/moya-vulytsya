// ZAVDANNYA-177 (ZVIT-165, п. 2): неіснуючий будинок — своя сторінка з назвою вулиці, номером, посиланням на вулицю й пошуком.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { budynok, nomerZSlug } from '../budynky.js';

const SHABLON = '<!doctype html><html lang="uk"><title>Такого будинку в даних немає</title><main><section>' +
  '<!--NEMAIE-BUDYNKU--><h1>Такого будинку в даних немає</h1><!--/NEMAIE-BUDYNKU--></section><input id="poshuk-vulytsi" value="%%ZAPYT%%"></main></html>';
const POKAZHCHYK = [['khreshchatyk', 'вулиця Хрещатик', 'Печерський і Шевченківський', 120, ''],
  ['vyhadana', 'вулиця <b>Вигадана</b>', '', 1, '']];

function env(z = {}) {
  return {
    PACHOK: '1',
    ASSETS: {
      async fetch(req) {
        const p = new URL(req.url).pathname;
        if (p === '/_404-budynok.html' && !z.bezShablonu) return new Response(SHABLON);
        if (p === '/vulytsi/pokazhchyk.json') return new Response(JSON.stringify(POKAZHCHYK));
        if (p === '/404.html') return new Response('<h1>Такої сторінки немає</h1>');
        return new Response('немає', { status: 404 });
      },
    },
  };
}

test('номер з адреси сторінки — як на сайті', () => {
  assert.equal(nomerZSlug('24-a'), '24-А');
  assert.equal(nomerZSlug('9999'), '9999');
  assert.equal(nomerZSlug('37-k6'), '37-k6');   // корпус лишається як в адресі
});

test('неіснуючий будинок відомої вулиці: назва, номер, посилання на вулицю, пошук', async () => {
  const r = await budynok(new Request('https://x.ua/budynok/khreshchatyk/9999/'), env());
  assert.equal(r.status, 404);
  assert.match(r.headers.get('content-type'), /text\/html/);
  const h = await r.text();
  assert.match(h, /<h1>Вулиця Хрещатик, 9999: такого будинку в даних поки немає<\/h1>/);
  assert.match(h, /href="\/vulytsia\/khreshchatyk\/"/);
  assert.match(h, /value="Хрещатик 9999"/);
  assert.doesNotMatch(h, /вулицю перейменовано/);
  assert.equal((h.match(/<h1>/g) || []).length, 1, 'один заголовок — замість загального');
});

test('невідома вулиця — чесно «такої адреси немає», без посилання на вулицю', async () => {
  const h = await (await budynok(new Request('https://x.ua/budynok/nemaie-takoi/1/'), env())).text();
  assert.match(h, /Такої адреси в даних немає/);
  assert.doesNotMatch(h, /href="\/vulytsia\//);
  assert.match(h, /value=""/);
});

test('назва вулиці екранується', async () => {
  const h = await (await budynok(new Request('https://x.ua/budynok/vyhadana/1/'), env())).text();
  assert.doesNotMatch(h, /<b>Вигадана<\/b>/);
  assert.match(h, /&lt;b&gt;Вигадана/);
});

test('без шаблону — звичайна 404', async () => {
  const r = await budynok(new Request('https://x.ua/budynok/khreshchatyk/9999/'), env({ bezShablonu: true }));
  assert.equal(r.status, 404);
  assert.match(await r.text(), /Такої сторінки немає/);
});

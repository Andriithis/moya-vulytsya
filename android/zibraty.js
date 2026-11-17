// Збирання оболонки Android «Моя вулиця» (Trusted Web Activity, Bubblewrap) — ZAVDANNYA-102, прототип.
//
//   npm i @bubblewrap/core            (у будь-якій теці; шлях до неї — BUBBLEWRAP_CORE, якщо не поруч)
//   ANDROID_HOME=<Android SDK> JAVA_HOME=<JDK 17> node android/zibraty.js [тека-виходу]
//
// Що робить:
// 1. Читає android/twa-manifest.json (налаштування оболонки — у git; ключів там немає).
// 2. Іконки й маніфест бере з site/zahlushka через тимчасовий локальний сервер у цьому ж процесі — тестового сайту
//    в інтернеті ще немає, а Bubblewrap качає іконки за адресою.
// 3. Генерує проєкт Android (@bubblewrap/core, TwaGenerator) і збирає його Gradle:
//    - app-release-unsigned.apk і app-release.aab — БЕЗ підпису (справжній ключ — у партнера, MV-16);
//    - якщо задано PROTOTYP_PIDPYS=1 — ще й app-prototyp.apk, підписаний одноразовим ключем, створеним тут же
//      і одразу видаленим: лише щоб поставити на свій телефон. У Google Play такий файл не йде.
// Ключі ніколи не потрапляють у git (.gitignore: *.keystore, *.jks).
'use strict';
const fs = require('fs');
const path = require('path');
const http = require('http');
const { execFileSync } = require('child_process');

const KORIN = path.resolve(__dirname, '..');
const CORE = process.env.BUBBLEWRAP_CORE || '@bubblewrap/core';
const { TwaGenerator, TwaManifest, ConsoleLog } = require(require.resolve(CORE, { paths: [process.cwd(), __dirname] }));

const VYKHID = path.resolve(process.argv[2] || path.join(KORIN, 'tmp', 'android'));
const IKONY = path.join(KORIN, 'site', 'zahlushka', 'ikony');

function server() {
  return new Promise((ok) => {
    const s = http.createServer((zap, vid) => {
      const imia = path.basename(zap.url.split('?')[0]);
      const f = imia === 'manifest.webmanifest' ? path.join(KORIN, 'site', 'zahlushka', imia) : path.join(IKONY, imia);
      if (!fs.existsSync(f)) { vid.writeHead(404); vid.end(); return; }
      vid.writeHead(200, { 'Content-Type': f.endsWith('.png') ? 'image/png' : 'application/manifest+json' });
      fs.createReadStream(f).pipe(vid);
    });
    s.listen(0, '127.0.0.1', () => ok(s));
  });
}

function zapustyty(komanda, argumenty, teka) {
  execFileSync(komanda, argumenty, { cwd: teka, stdio: 'inherit', env: process.env });
}

(async () => {
  const dani = JSON.parse(fs.readFileSync(path.join(__dirname, 'twa-manifest.json'), 'utf8'));
  const srv = await server();
  const lokalno = `http://127.0.0.1:${srv.address().port}/`;
  const zaminy = (url) => (url ? lokalno + path.basename(new URL(url).pathname) : url);
  const robochi = { ...dani, webManifestUrl: zaminy(dani.webManifestUrl), iconUrl: zaminy(dani.iconUrl), maskableIconUrl: zaminy(dani.maskableIconUrl),
    shortcuts: dani.shortcuts.map((s) => ({ ...s, chosenIconUrl: zaminy(s.chosenIconUrl) })) };
  delete robochi.monochromeIconUrl;
  fs.rmSync(VYKHID, { recursive: true, force: true });
  fs.mkdirSync(VYKHID, { recursive: true });
  try {
    await new TwaGenerator().createTwaProject(VYKHID, new TwaManifest(robochi), new ConsoleLog('zibraty'));
  } finally {
    srv.closeAllConnections();   // інакше відкриті з'єднання тримають процес після збирання
    srv.close();
  }
  // У проєкт кладемо справжній twa-manifest.json (з адресами сайту, а не локального сервера).
  fs.writeFileSync(path.join(VYKHID, 'twa-manifest.json'), JSON.stringify(dani, null, 2));
  fs.writeFileSync(path.join(VYKHID, 'local.properties'), `sdk.dir=${process.env.ANDROID_HOME}\n`);
  zapustyty(process.platform === 'win32' ? 'gradlew.bat' : './gradlew', ['--no-daemon', '-q', 'assembleRelease', 'bundleRelease'], VYKHID);

  const apk = path.join(VYKHID, 'app', 'build', 'outputs', 'apk', 'release', 'app-release-unsigned.apk');
  const aab = path.join(VYKHID, 'app', 'build', 'outputs', 'bundle', 'release', 'app-release.aab');
  const pidsumok = [apk, aab];
  if (process.env.PROTOTYP_PIDPYS === '1') {
    const bt = path.join(process.env.ANDROID_HOME, 'build-tools');
    const versiia = fs.readdirSync(bt).sort().pop();
    const kl = path.join(VYKHID, 'odnorazovyi.keystore');
    zapustyty('keytool', ['-genkeypair', '-keystore', kl, '-alias', 'prototyp', '-keyalg', 'RSA', '-keysize', '2048',
      '-validity', '30', '-storepass', 'prototyp', '-keypass', 'prototyp', '-dname', 'CN=Prototyp, O=Moya vulytsya'], VYKHID);
    const vyrivniano = path.join(VYKHID, 'vyrivniano.apk');
    zapustyty(path.join(bt, versiia, 'zipalign'), ['-f', '4', apk, vyrivniano], VYKHID);
    const proto = path.join(VYKHID, 'app-prototyp.apk');
    zapustyty(path.join(bt, versiia, 'apksigner'), ['sign', '--ks', kl, '--ks-pass', 'pass:prototyp', '--out', proto, vyrivniano], VYKHID);
    fs.rmSync(kl);
    pidsumok.push(proto);
  }
  fs.rmSync(path.join(VYKHID, 'vyrivniano.apk'), { force: true });
  for (const f of pidsumok) console.log(`${path.relative(KORIN, f)} — ${(fs.statSync(f).size / 1024).toFixed(0)} КБ`);
})().catch((e) => { console.error(e); process.exit(1); });

// Ключі, хеші, порівняння (ZAVDANNYA-99). Лише стандартні засоби Workers (Web Crypto) і node:crypto (прапорець nodejs_compat).
import { createHash, createHmac, timingSafeEqual } from 'node:crypto';

const ABETKA = 'abcdefghijklmnopqrstuvwxyz234567';

/** Випадковий ключ: n байтів → base32 малими літерами (без плутаних символів у посиланнях). */
export function vypadkovyi(n = 20) {
  const b = crypto.getRandomValues(new Uint8Array(n));
  let bity = 0, znach = 0, t = '';
  for (const x of b) {
    znach = (znach << 8) | x; bity += 8;
    while (bity >= 5) { t += ABETKA[(znach >>> (bity - 5)) & 31]; bity -= 5; }
  }
  if (bity > 0) t += ABETKA[(znach << (5 - bity)) & 31];
  return t;
}

export function sha256(tekst) {
  return createHash('sha256').update(tekst, 'utf8').digest('hex');
}

/** Порівняння рядків без витоку за часом. */
export function rivni(a, b) {
  const x = Buffer.from(String(a ?? ''), 'utf8'), y = Buffer.from(String(b ?? ''), 'utf8');
  if (x.length !== y.length) return false;
  return timingSafeEqual(x, y);
}

export function hmac(alg, kliuch, tekst, kodування = 'hex') {
  return createHmac(alg, kliuch).update(tekst, 'utf8').digest(kodування);
}

export function hesh(alg, tekst, kodування = 'base64') {
  if (alg === 'sha3-256') return Buffer.from(sha3_256(new TextEncoder().encode(tekst))).toString(kodування);
  return createHash(alg).update(tekst, 'utf8').digest(kodування);
}

// SHA3-256 (FIPS 202) на чистому JS: у Workers node:crypto зібрано на BoringSSL без SHA-3, а LiqPay у тексті документації
// називає sha3-256 (у прикладах коду — sha1). Тест звіряє з node:crypto.
const RC = [
  [0x00000001, 0x00000000], [0x00008082, 0x00000000], [0x0000808a, 0x80000000], [0x80008000, 0x80000000],
  [0x0000808b, 0x00000000], [0x80000001, 0x00000000], [0x80008081, 0x80000000], [0x00008009, 0x80000000],
  [0x0000008a, 0x00000000], [0x00000088, 0x00000000], [0x80008009, 0x00000000], [0x8000000a, 0x00000000],
  [0x8000808b, 0x00000000], [0x0000008b, 0x80000000], [0x00008089, 0x80000000], [0x00008003, 0x80000000],
  [0x00008002, 0x80000000], [0x00000080, 0x80000000], [0x0000800a, 0x00000000], [0x8000000a, 0x80000000],
  [0x80008081, 0x80000000], [0x00008080, 0x80000000], [0x80000001, 0x00000000], [0x80008008, 0x80000000],
];
const ROT = [0, 1, 62, 28, 27, 36, 44, 6, 55, 20, 3, 10, 43, 25, 39, 41, 45, 15, 21, 8, 18, 2, 61, 56, 14];

function keccakF(s) { // s: 50 × uint32 (25 слів по 64 біти: молодша, старша половини)
  const C = new Uint32Array(10), B = new Uint32Array(50);
  for (let r = 0; r < 24; r++) {
    for (let x = 0; x < 5; x++) {
      C[2 * x] = s[2 * x] ^ s[2 * x + 10] ^ s[2 * x + 20] ^ s[2 * x + 30] ^ s[2 * x + 40];
      C[2 * x + 1] = s[2 * x + 1] ^ s[2 * x + 11] ^ s[2 * x + 21] ^ s[2 * x + 31] ^ s[2 * x + 41];
    }
    for (let x = 0; x < 5; x++) {
      const p = (x + 4) % 5, n = (x + 1) % 5;
      const lo = C[2 * p] ^ ((C[2 * n] << 1) | (C[2 * n + 1] >>> 31));
      const hi = C[2 * p + 1] ^ ((C[2 * n + 1] << 1) | (C[2 * n] >>> 31));
      for (let y = 0; y < 25; y += 5) { s[2 * (x + y)] ^= lo; s[2 * (x + y) + 1] ^= hi; }
    }
    for (let x = 0; x < 5; x++) for (let y = 0; y < 5; y++) {
      const i = x + 5 * y, j = y + 5 * ((2 * x + 3 * y) % 5), k = ROT[i];
      let lo = s[2 * i], hi = s[2 * i + 1];
      if (k >= 32) { const t = lo; lo = hi; hi = t; }
      const kk = k % 32;
      const nlo = kk ? ((lo << kk) | (hi >>> (32 - kk))) : lo;
      const nhi = kk ? ((hi << kk) | (lo >>> (32 - kk))) : hi;
      B[2 * j] = nlo; B[2 * j + 1] = nhi;
    }
    for (let y = 0; y < 25; y += 5) for (let x = 0; x < 5; x++) {
      const i = x + y, a = x + 1 < 5 ? i + 1 : i - 4, b = x + 2 < 5 ? i + 2 : i - 3;
      s[2 * i] = B[2 * i] ^ (~B[2 * a] & B[2 * b]);
      s[2 * i + 1] = B[2 * i + 1] ^ (~B[2 * a + 1] & B[2 * b + 1]);
    }
    s[0] ^= RC[r][0]; s[1] ^= RC[r][1];
  }
}

export function sha3_256(bytes) {
  const rate = 136, s = new Uint32Array(50);
  const m = new Uint8Array(Math.ceil((bytes.length + 1) / rate) * rate);
  m.set(bytes); m[bytes.length] ^= 0x06; m[m.length - 1] ^= 0x80;
  for (let o = 0; o < m.length; o += rate) {
    for (let i = 0; i < rate / 4; i++) {
      s[i] ^= m[o + 4 * i] | (m[o + 4 * i + 1] << 8) | (m[o + 4 * i + 2] << 16) | (m[o + 4 * i + 3] << 24);
    }
    keccakF(s);
  }
  const v = new Uint8Array(32);
  for (let i = 0; i < 8; i++) for (let k = 0; k < 4; k++) v[4 * i + k] = (s[i] >>> (8 * k)) & 255;
  return v;
}

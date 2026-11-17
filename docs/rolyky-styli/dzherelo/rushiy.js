// Кадри-макети стилів роликів (ZAVDANNYA-126). Малює 3D-соти Києва на полотні 1080×1920 без підкладки й без мережі.
// Дані — справжні соти пробного випуску 08.11.2026 (video/dani/soty-kyiv.geojson: 402 соти, 71 698 подій з точкою, без чутливих).
// Крапки «подій» усередині соти на кадрах-макетах розкладено умовно (ілюстрація руху), а не за справжніми координатами.
(function () {
  const W = 1080, H = 1920;
  const LAT0 = 50.45, LON0 = 30.52, KX = Math.cos(LAT0 * Math.PI / 180) * 111320, KY = 110540;
  const mx = (lon) => (lon - LON0) * KX, my = (lat) => (lat - LAT0) * KY;

  function vec(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function norm(a) { const l = Math.hypot(a[0], a[1], a[2]); return [a[0] / l, a[1] / l, a[2] / l]; }

  // Камера: ціль (lon, lat), відстань (м), нахил (0 — згори), поворот (°), фокус, зсув центру кадру по вертикалі.
  function kamera(k) {
    const t = [mx(k.lon), my(k.lat), 0];
    const p = (k.nakhyl || 0) * Math.PI / 180, b = (k.povorot || 0) * Math.PI / 180;
    const dir = [Math.sin(b) * Math.sin(p), -Math.cos(b) * Math.sin(p), Math.cos(p)];
    const c = [t[0] + dir[0] * k.vidstan, t[1] + dir[1] * k.vidstan, t[2] + dir[2] * k.vidstan];
    const f = norm(vec(t, c));
    let r = norm(cross(f, [0, 0, 1]));
    if (!isFinite(r[0])) r = [Math.cos(b), Math.sin(b), 0];
    const u = cross(r, f);
    const F = k.fokus || 1500, cy = k.tsentr_y == null ? H / 2 : k.tsentr_y;
    return function (x, y, z) {
      const d = vec([x, y, z], c);
      const g = dot(d, f);
      return [W / 2 + F * dot(d, r) / g, cy - F * dot(d, u) / g, g];
    };
  }

  function polygon(ctx, pts) {
    ctx.beginPath();
    pts.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])));
    ctx.closePath();
  }

  // Малює місто: тло, межа, соти, стовпчики; повертає функцію проєкції для накладок.
  function misto(ctx, st, kam, opts) {
    opts = opts || {};
    const P = kamera(kam);
    ctx.fillStyle = st.tlo; ctx.fillRect(0, 0, W, H);
    if (st.mezha) {
      polygon(ctx, window.MEZHA.map(([lo, la]) => P(mx(lo), my(la), 0)));
      ctx.fillStyle = st.misto_tlo; ctx.fill();
      ctx.lineWidth = st.mezha_tovsh || 3; ctx.strokeStyle = st.mezha; ctx.stroke();
    }
    const items = window.SOTY.map((s) => {
      const pts = s.c.map(([lo, la]) => [mx(lo), my(la)]);
      const cx = pts.reduce((a, p) => a + p[0], 0) / pts.length, cyy = pts.reduce((a, p) => a + p[1], 0) / pts.length;
      const h = (s.k === 5 && opts.stovpchyky !== false) ? (s.n / 1240) * (opts.vysota || 2600) : 0;
      return { s, pts, cx, cy: cyy, h, g: P(cx, cyy, 0)[2] };
    }).filter((it) => it.g > 2500).sort((a, b) => b.g - a.g);
    const vybrana = opts.vybrana;
    for (const it of items) {
      if (opts.prykhovaty && opts.prykhovaty(it)) continue;
      const kol = st.sc[it.s.k - 1];
      const zv = (opts.zvuzhennia || 0.9);
      const pts = it.pts.map(([x, y]) => [it.cx + (x - it.cx) * zv, it.cy + (y - it.cy) * zv]);
      if (it.h > 0) {
        const nyz = pts.map(([x, y]) => P(x, y, 0)), verkh = pts.map(([x, y]) => P(x, y, it.h));
        for (let i = 0; i < pts.length; i++) {
          const j = (i + 1) % pts.length;
          polygon(ctx, [nyz[i], nyz[j], verkh[j], verkh[i]]);
          const svitlo = 0.5 + 0.5 * Math.abs(Math.cos(Math.atan2(pts[j][1] - pts[i][1], pts[j][0] - pts[i][0]) - 0.6));
          ctx.fillStyle = svitlo > 0.75 ? st.pk_bik1 : st.pk_bik2; ctx.fill();
        }
        polygon(ctx, verkh); ctx.fillStyle = it.s.n > 900 ? st.pk[1] : st.pk[0]; ctx.fill();
        if (st.kontur) { ctx.lineWidth = 1.5; ctx.strokeStyle = st.kontur; ctx.stroke(); }
      } else {
        polygon(ctx, pts.map(([x, y]) => P(x, y, 0)));
        ctx.fillStyle = kol; ctx.fill();
        if (st.kontur) { ctx.lineWidth = 1; ctx.strokeStyle = st.kontur; ctx.stroke(); }
      }
      if (vybrana && vybrana(it)) {
        polygon(ctx, pts.map(([x, y]) => P(x, y, it.h + 2)));
        ctx.lineWidth = 7; ctx.strokeStyle = st.vyd; ctx.stroke();
      }
    }
    return { P, items };
  }

  // Умовні крапки «подій», що вилітають із соти (для руху «сота розпадається»).
  function krapky(ctx, P, lon, lat, n, kolory, rozlit, zerno) {
    let s = zerno || 7;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    const cx = mx(lon), cy = my(lat);
    const out = [];
    for (let i = 0; i < n; i++) {
      const a = rnd() * Math.PI * 2, r = Math.sqrt(rnd()) * 620 * rozlit;
      const p = P(cx + Math.cos(a) * r, cy + Math.sin(a) * r, 0);
      const k = kolory[Math.floor(rnd() * kolory.length)];
      ctx.beginPath(); ctx.arc(p[0], p[1], 15, 0, Math.PI * 2); ctx.fillStyle = k; ctx.fill();
      ctx.lineWidth = 3; ctx.strokeStyle = '#FFFFFF'; ctx.stroke();
      out.push(p);
    }
    return out;
  }

  window.RUSHIY = { W, H, mx, my, kamera, misto, krapky, polygon };
})();

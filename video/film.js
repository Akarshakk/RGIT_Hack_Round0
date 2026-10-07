// Credence product film: drives the real app deterministically. FILM.setup() preloads live data, FILM.render(t) sets
// every visual for time t (seconds). Rendered frame by frame with reduced motion on, so all motion here is ours.
(() => {
  const W = 1920, H = 1080, FPS = 30;
  const VO = window.__VO; // {vo01: seconds, ...}
  const q = (s) => document.querySelector(s);
  const qa = (s) => [...document.querySelectorAll(s)];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2); // easeInOutCubic
  const out3 = (x) => 1 - Math.pow(1 - x, 3);
  const lerp = (a, b, k) => a + (b - a) * k;
  let seed = 7; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

  // no scrolling in film: the camera does it
  Element.prototype.scrollIntoView = function () {};
  window.scrollTo = function () {};

  const css = document.createElement("style");
  css.textContent = `
    html, body { overflow: hidden !important; }
    body { transform-origin: 0 0; will-change: transform; }
    #loader, #story { position: absolute !important; inset: auto !important; top: 0 !important; left: 0 !important; width: ${W}px !important; height: ${H}px !important; }
    .film-cursor { position: absolute; left: 0; top: 0; width: 30px; height: 30px; z-index: 2147483000; pointer-events: none; filter: drop-shadow(0 2px 4px rgba(0,0,0,.35)); transform-origin: 3px 2px; }
    .film-ring { position: absolute; z-index: 2147482999; pointer-events: none; border-radius: 50%; border: 2px solid rgba(255,244,224,.9); width: 10px; height: 10px; margin: -5px 0 0 -5px; opacity: 0; }
    .film-end { position: fixed; left: 0; top: 0; width: ${W}px; height: ${H}px; z-index: 2147482000; background: #0e2522; display: grid; place-items: center; opacity: 0; pointer-events: none; }
    .film-end .lock { display: flex; align-items: center; gap: 26px; }
    .film-end .lock svg { width: 104px; height: 104px; }
    .film-end .word { font: 800 92px/1 Unbounded, sans-serif; letter-spacing: -.045em; color: #fff4e0; }
    .film-end .tag { margin-top: 30px; font: 500 28px/1.3 Mukta, sans-serif; color: #a3b8b2; text-align: center; }
    .film-fade { position: fixed; left: 0; top: 0; width: ${W}px; height: ${H}px; z-index: 2147482500; background: #0e2522; opacity: 0; pointer-events: none; }
  `;
  document.head.appendChild(css);

  // ---------- overlay elements (live inside body so they move with the camera) ----------
  const cursor = document.createElement("div");
  cursor.className = "film-cursor";
  cursor.innerHTML = `<svg viewBox="0 0 30 30"><path d="M4 2.5 L4 24 L9.6 18.9 L13.4 27.2 L17.2 25.5 L13.5 17.4 L21 17.2 Z" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
  const ring = document.createElement("div"); ring.className = "film-ring";
  const fade = document.createElement("div"); fade.className = "film-fade";
  const end = document.createElement("div"); end.className = "film-end";
  end.innerHTML = `<div><div class="lock">${Wrapped.LOGO}<span class="word">credence</span></div><div class="tag">Your bank statement, told like a story.</div></div>`;

  // ---------- data ----------
  const D = {};
  async function sse(message) {
    const r = await fetch("/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ message }) });
    const txt = await r.text();
    let text = "", receipts = [], grounding = null, notice = "";
    for (const block of txt.split("\n\n")) {
      const ev = block.match(/^event: (.*)$/m)?.[1], raw = block.match(/^data: (.*)$/m)?.[1];
      if (!ev || raw === undefined) continue;
      const d = JSON.parse(raw);
      if (ev === "text") text += d; else if (ev === "receipt") receipts.push(d); else if (ev === "grounding") grounding = d; else if (ev === "notice") notice += d;
    }
    return { text, receipts, grounding, notice };
  }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function setup() {
    await document.fonts.ready;
    // second persona first, then the main one (its session stays active for the dashboard)
    await fetch("/sample?kind=axis", { method: "POST" });
    D.tx2 = await (await fetch("/transactions?limit=20000")).json();
    D.story2 = await (await fetch("/wrapped")).json();
    D.ai2 = (await (await fetch("/wrapped/ai", { method: "POST" })).json()).quips || {};
    await sleep(2500);
    await fetch("/sample?kind=pdf", { method: "POST" });
    D.tx1 = await (await fetch("/transactions?limit=20000")).json();
    D.story1 = await (await fetch("/wrapped")).json();
    D.ai1 = (await (await fetch("/wrapped/ai", { method: "POST" })).json()).quips || {};
    categories = (await (await fetch("/status")).json()).categories;
    story = D.story1;
    await renderDashboard();
    // a real chat answer; prefer one whose numbers all verify
    for (let i = 0; i < 4; i++) {
      await sleep(i ? 22000 : 3000);
      const a = await sse("How can I save ₹5,000 a month?");
      if (a.text && (!D.chat || (a.grounding && !a.grounding.unverified.length))) D.chat = a;
      if (D.chat && D.chat.grounding && !D.chat.grounding.unverified.length) break;
    }
    document.body.append(cursor, ring);
    document.documentElement.append(fade, end);
    return { ai1: Object.keys(D.ai1).length, ai2: Object.keys(D.ai2).length, chat: D.chat?.text?.slice(0, 120), grounding: D.chat?.grounding, receipts: D.chat?.receipts.map((r) => r.tool) };
  }

  // ---------- camera ----------
  // keyframes: {t, s, f: () => [x, y]} focus point in page coords; eased between consecutive keyframes
  let camNow = { s: 1, tx: 0, ty: 0 };
  const camKeys = [];
  const camKey = (t, s, f) => camKeys.push({ t, s, f });
  const resolved = new Map();
  const safe = (fn) => { try { const v = fn(); return v && isFinite(v[0]) && isFinite(v[1]) ? v : null; } catch (e) { return null; } };
  const at = (k) => { if (!resolved.has(k)) { const v = safe(k.f); if (!v) return null; resolved.set(k, v); } return resolved.get(k); };
  function camera(t) {
    let i = camKeys.findIndex((k) => k.t > t);
    if (i === -1) i = camKeys.length;
    const a = camKeys[Math.max(0, i - 1)], b = camKeys[Math.min(camKeys.length - 1, i)];
    const k = a === b ? 1 : ease(clamp((t - a.t) / (b.t - a.t), 0, 1));
    let fa = at(a) || camNow.f || [960, 540];
    const fb = (k > 0 ? at(b) : null) || fa;
    const s = lerp(a.s, b.s, k), fx = lerp(fa[0], fb[0], k), fy = lerp(fa[1], fb[1], k);
    const ph = Math.max(H, document.body.scrollHeight);
    const tx = clamp(W / 2 - fx * s, W - W * s, 0), ty = clamp(H / 2 - fy * s, H - ph * s, 0);
    camNow = { s, tx, ty, f: [fx, fy] };
    document.body.style.transform = `translate(${tx.toFixed(2)}px, ${ty.toFixed(2)}px) scale(${s.toFixed(5)})`;
    // emulate sticky header and chat panel while the camera "scrolls"
    const viewTop = -ty / s;
    const tb = q(".topbar"); if (tb) tb.style.transform = `translateY(${Math.max(0, viewTop)}px)`;
  }
  function pageRect(el) {
    if (!el) throw new Error("no element");
    const r = el.getBoundingClientRect(), { s, tx, ty } = camNow;
    if (!r.width && !r.height) throw new Error("element not visible");
    return { x: (r.left - tx) / s, y: (r.top - ty) / s, w: r.width / s, h: r.height / s };
  }
  const center = (sel, dx = 0, dy = 0) => () => { const el = typeof sel === "string" ? q(sel) : sel(); const r = pageRect(el); return [r.x + r.w / 2 + dx, r.y + r.h / 2 + dy]; };
  const toScreen = ([x, y]) => [x * camNow.s + camNow.tx, y * camNow.s + camNow.ty];

  // ---------- cursor ----------
  const moves = []; // {t0, t1, to: fn, from?}
  let lastPos = [1500, 900];
  const clicks = []; // {t, el: fn, sound}
  const keys = []; // typing sound times
  let lastTo = () => [1500, 900];
  function move(t0, dur, to) { const m = { t0, t1: t0 + dur, to, from: lastTo }; moves.push(m); lastTo = to; return t0 + dur; }
  function click(t, el, run, doClick = true) { clicks.push({ t, el, run, doClick }); }
  const ptCache = new Map();
  const pt = (fn) => { if (!ptCache.has(fn)) { const v = safe(fn); if (!v) return null; ptCache.set(fn, v); } return ptCache.get(fn); };
  function cursorPos(t) {
    let m = null;
    for (const x of moves) if (x.t0 <= t) m = x;
    if (!m) return pt(moves[0].from) || [1500, 900];
    const a = pt(m.from) || lastPos, b = pt(m.to) || a;
    const k = ease(clamp((t - m.t0) / (m.t1 - m.t0), 0, 1));
    // gentle arc: control point offset perpendicular to the path
    const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
    const cx = mx - (dy / len) * len * 0.12, cy = my + (dx / len) * len * 0.12;
    const x = (1 - k) * (1 - k) * a[0] + 2 * (1 - k) * k * cx + k * k * b[0];
    const y = (1 - k) * (1 - k) * a[1] + 2 * (1 - k) * k * cy + k * k * b[1];
    lastPos = [x, y];
    return lastPos;
  }

  // ---------- one-shot events and per-frame animators ----------
  const events = []; // {t, run}
  const on = (t, run) => events.push({ t, run });
  const anims = []; // {t0, dur, apply(k), done}
  const animate = (t0, dur, apply, easing = out3) => anims.push({ t0, dur, apply, easing, done: false, started: false });
  const rise = (el, t0, dur = 0.55, dy = 16) => {
    if (!el) return;
    el.style.opacity = "0";
    animate(t0, dur, (k) => { el.style.opacity = k >= 1 ? "" : k.toFixed(3); el.style.transform = k >= 1 ? "" : `translateY(${((1 - k) * dy).toFixed(2)}px)`; });
  };
  const sounds = []; // {t, type}
  const sfx = (t, type) => sounds.push({ t: +t.toFixed(3), type });
  const vo = []; // {id, t}
  const say = (id, t) => { vo.push({ id, t }); return t + VO[id]; };

  // typing into an input, character by character with human jitter
  function type(el, text, t0, base = 0.085) {
    let t = t0;
    const stamps = [];
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      t += base * (0.65 + rnd() * 0.75) + (ch === " " ? 0.06 + rnd() * 0.08 : 0) + (rnd() < 0.06 ? 0.18 : 0);
      stamps.push(t);
      sfx(t, "key");
    }
    on(t0, () => { el().focus({ preventScroll: true }); });
    animate(t0, t - t0 + 0.001, (k) => {
      const now = t0 + k * (t - t0);
      const n = stamps.filter((s) => s <= now + 1e-6).length;
      el().value = text.slice(0, n);
    }, (x) => x);
    return t;
  }

  // ---------- timeline ----------
  const T = {};
  function build() {
    const landingFocus = () => [960, 470];
    // SHOT 1 — product intro
    camKey(0, 1, landingFocus);
    camKey(1.6, 1, landingFocus);
    say("vo01", 0.7);
    camKey(5.0, 1.06, () => [1010, 470]);
    // SHOT 2 — password + upload
    let t = move(4.2, 1.1, center("#pw", -150, 0));
    camKey(5.6, 1.14, center("#pw", 0, -110));
    say("vo02", 5.5);
    click(t + 0.35, () => q("#pw"));
    t = type(() => q("#pw"), "kharcha123", t + 0.55, 0.075);
    t = move(t + 0.55, 0.85, center(".slip-drop", 10, -6));
    camKey(t, 1.1, center(".slip-drop", 0, -40));
    click(t + 0.5, () => q(".slip-drop"), null, false);
    T.loader = t + 0.85;
    // SHOT 3 — loader
    on(T.loader, startLoader);
    camKey(T.loader, 1.0, () => [960, 540]);
    camKey(T.loader + 0.01, 1.0, () => [960, 540]);
    camKey(T.loader + 5.8, 1.05, () => [960, 600]);
    say("vo03", T.loader + 0.4);
    move(T.loader + 0.3, 1.2, () => [1500, 760]);
    T.story = T.loader + 7.9;
    // SHOT 4 — Money Wrapped
    on(T.story, () => {
      q("#loader").hidden = true; q("#landing").hidden = true;
      Wrapped.open(D.story1, { ai: D.ai1, onClose: () => { showDashboard(); } });
      cardEnter(0, T.story);
    });
    camKey(T.story, 1.0, () => [960, 540]);
    camKey(T.story + 0.01, 1.0, () => [960, 540]);
    const frameRight = () => { const r = pageRect(q("#frame")); return [r.x + r.w * 0.78, r.y + r.h * 0.58]; };
    move(T.story + 0.4, 1.0, frameRight);
    say("vo04", T.story + 0.45);
    // card schedule (index -> time)
    const cards = [[1, 2.2], [2, 4.0], [3, 6.6], [4, 10.0], [5, 11.6], [6, 12.7], [7, 17.6], [8, 19.4], [9, 21.6]];
    const nudge = (k) => () => { const p = frameRight(); return [p[0] + (k % 2 ? 6 : -4), p[1] + (k % 3) * 5]; };
    cards.forEach(([i, dt], n) => {
      const tt = T.story + dt;
      move(tt - 0.45, 0.35, nudge(n));
      click(tt, () => q("#tapNext"), () => cardEnter(i, tt));
    });
    camKey(T.story + 9.9, 1.07, () => { const r = pageRect(q("#frame")); return [r.x + r.w / 2, r.y + r.h / 2]; });
    say("vo05", T.story + 10.0);
    // roast -> hype on the ghost-subscription card
    const hypeBtn = () => q('#frame .toggle button[data-mode="hype"]');
    move(T.story + 14.3, 0.9, center(hypeBtn));
    camKey(T.story + 14.4, 1.16, center(hypeBtn, -120, 140));
    click(T.story + 15.55, hypeBtn, () => quipSwap(T.story + 15.55));
    camKey(T.story + 16.6, 1.07, () => { const r = pageRect(q("#frame")); return [r.x + r.w / 2, r.y + r.h / 2]; });
    move(T.story + 16.5, 0.8, frameRight);
    say("vo06", T.story + 19.5);
    const doneBtn = () => q('#cards .card:not([hidden]) [data-act="done"]');
    camKey(T.story + 22.9, 1.07, () => { const r = pageRect(q("#frame")); return [r.x + r.w / 2, r.y + r.h / 2]; });
    move(T.story + 23.5, 0.9, center(doneBtn));
    camKey(T.story + 23.5, 1.05, () => { const r = pageRect(q("#frame")); return [r.x + r.w / 2, r.y + r.h / 2 + 90]; });
    T.dash = T.story + 24.9;
    camKey(T.dash - 0.08, 1.05, () => { const r = pageRect(q("#frame")); return [r.x + r.w / 2, r.y + r.h / 2 + 90]; });
    click(T.dash - 0.05, doneBtn, null);
    on(T.dash, () => { dashEnter(T.dash); });
    // SHOT 5 — dashboard
    camKey(T.dash, 1.0, () => [960, 540]);
    camKey(T.dash + 0.01, 1.0, () => [960, 540]);
    camKey(T.dash + 1.6, 1.0, () => [960, 540]);
    say("vo07", T.dash + 1.0);
    const donutC = () => { const r = pageRect(q("#donut")); return [r.x + r.w / 2, r.y + r.h / 2]; };
    camKey(T.dash + 3.0, 1.12, () => { const c = donutC(); return [c[0] + 260, c[1] - 30]; });
    t = move(T.dash + 2.4, 1.0, donutPoint("Rent"));
    t = move(t + 1.2, 0.8, donutPoint("Shopping"));
    t = move(t + 1.0, 0.8, donutPoint("Food & Dining"));
    click(t + 0.5, donutEl("Food & Dining"), () => setTxFilter("Food & Dining"), false);
    T.tx = t + 1.0;
    camKey(T.tx, 1.12, () => { const c = donutC(); return [c[0] + 260, c[1] - 30]; });
    camKey(T.tx + 1.6, 1.0, center(".tx-scroll", 0, -40));
    camKey(T.tx + 3.0, 1.0, center(".tx-scroll", 0, -40));
    move(T.tx + 0.3, 1.4, center(".tx-filter span", 0, 0));
    // SHOT 6 — Future You + friend ledger
    T.fy = T.tx + 3.3;
    camKey(T.fy + 1.3, 1.06, center(".panel.future", 0, 30));
    say("vo08", T.fy + 0.9);
    const thumb = (v) => () => { const r = pageRect(q("#fyYears")); return [r.x + 11 + (v - 1) / 29 * (r.w - 22), r.y + r.h / 2]; };
    t = move(T.fy + 1.0, 0.9, thumb(10));
    sfx(t + 0.35, "click");
    animate(t + 0.4, 1.3, (k) => {
      const v = Math.round(10 + k * 10), el = q("#fyYears");
      if (+el.value !== v) { el.value = v; el.oninput(); }
    }, ease);
    moves.push({ t0: t + 0.4, t1: t + 1.7, from: thumb(10), to: thumb(20) }); lastTo = thumb(20);
    camKey(T.fy + 3.2, 1.06, center(".panel.future", 0, 30));
    camKey(T.fy + 4.6, 1.06, center(".friends-dash", 0, -20));
    move(T.fy + 3.6, 1.0, center(".friends-dash .fr:nth-child(1) .bal"));
    // SHOT 7 — chat
    T.chat = T.fy + 5.6;
    camKey(T.chat + 1.2, 1.12, center("#chat", -40, 40));
    say("vo09", T.chat + 0.8);
    t = move(T.chat + 0.6, 1.2, center("#q", -60, 0));
    click(t + 0.3, () => q("#q"));
    t = type(() => q("#q"), "How can I save ₹5,000 a month?", t + 0.5, 0.07);
    t = move(t + 0.4, 0.5, center('#askForm button[type="submit"]'));
    T.answer = t + 0.35;
    const tSend = T.answer;
    click(tSend, () => q('#askForm button[type="submit"]'), () => chatSend(tSend), false);
    T.detail = T.answer + 4.6;
    // SHOT 8 — detail: receipt + verified badge
    move(T.detail - 0.6, 0.9, () => center(() => q("#msgs .receipt"))());
    click(T.detail + 0.55, () => q("#msgs .receipt"), () => openReceipt(), false);
    camKey(T.detail + 0.2, 1.12, center("#chat", -40, 40));
    camKey(T.detail + 1.8, 1.3, () => { const r = pageRect(q("#msgs .receipts")); return [r.x + 170, r.y + 30]; });
    camKey(T.detail + 4.0, 1.3, () => { const r = pageRect(q("#msgs .receipts")); return [r.x + 170, r.y + 30]; });
    // SHOT 9 — Ananya
    T.ana = T.detail + 4.4;
    camKey(T.ana + 0.6, 1.0, () => [960, 540]);
    on(T.ana, () => fadeTo(T.ana, 0.5));
    on(T.ana + 0.5, () => {
      q("#app").hidden = true; q("#dashActions").hidden = true; q("#landing").hidden = false;
      q("#pw").value = "";
    });
    camKey(T.ana + 0.51, 1.0, () => [960, 470]);
    camKey(T.ana + 1.3, 1.08, center("#sampleAxis", 120, -60));
    say("vo10", T.ana + 0.6);
    t = move(T.ana + 0.7, 1.0, center("#sampleAxis", -30, 0));
    click(t + 0.4, () => q("#sampleAxis"), null, false);
    T.ana2 = t + 0.7;
    on(T.ana2, () => startLoader(true));
    camKey(T.ana2, 1.0, () => [960, 540]);
    camKey(T.ana2 + 0.01, 1.0, () => [960, 540]);
    move(T.ana2 + 0.2, 0.9, () => [1500, 760]);
    T.ana3 = T.ana2 + 1.9;
    on(T.ana3, () => {
      q("#loader").hidden = true; q("#landing").hidden = true;
      Wrapped.open(D.story2, { ai: D.ai2, onClose: () => {} });
      q("#tapNext").click(); q("#tapNext").click();
      cardEnter(2, T.ana3);
    });
    move(T.ana3 + 0.3, 0.8, frameRight);
    click(T.ana3 + 1.9, () => q("#tapNext"), () => { q("#tapNext").click(); cardEnter(4, T.ana3 + 1.9); });
    click(T.ana3 + 3.8, () => q("#tapNext"), () => cardEnter(5, T.ana3 + 3.8));
    // SHOT 10 — hero + end frame
    T.hero = T.ana3 + 5.6;
    on(T.hero, () => fadeTo(T.hero, 0.6));
    on(T.hero + 0.6, () => { q("#story").hidden = true; q("#landing").hidden = false; cursor.style.opacity = "0"; });
    camKey(T.hero + 0.6, 1.0, () => [960, 470]);
    camKey(T.hero + 0.61, 1.0, () => [960, 470]);
    say("vo11", T.hero + 1.1);
    camKey(T.hero + 4.4, 1.05, () => [960, 470]);
    T.end = T.hero + 4.3;
    animate(T.end, 0.9, (k) => (end.style.opacity = k.toFixed(3)), ease);
    T.total = T.end + 3.4;
    animate(T.total - 0.8, 0.8, (k) => (fade.style.opacity = k.toFixed(3)), ease);
    sfx(T.loader + 6.2, "chime");
    camKeys.sort((a, b) => a.t - b.t);
    moves.sort((a, b) => a.t0 - b.t0);
    for (let i = 1; i < moves.length; i++) moves[i].from = moves[i - 1].to;
  }

  // ---------- scene helpers ----------
  function startLoader(short) {
    const L = q("#loader"), rows = [...(short ? D.tx2 : D.tx1)].reverse(), t0 = FILM.t;
    L.classList.remove("done"); q("#lTicker").innerHTML = ""; q("#lCount").textContent = "0"; stepTo(0); L.hidden = false;
    const total = short ? D.tx2.length : D.tx1.length, dur = short ? 1.3 : 5.6, n = short ? 6 : 24;
    rise(q(".loader-inner"), t0, 0.5, 10);
    for (let i = 0; i < n; i++) {
      const r = rows[Math.floor(i * rows.length / n)], ti = t0 + 0.35 + i * (dur / n);
      on(ti, () => {
        const el = document.createElement("div");
        el.className = "tick";
        el.innerHTML = `<code>${esc(r.narration.replace(/\d{6,}/g, "…"))}</code><em style="--c:${color(r.category)}">${esc(r.category)}</em>`;
        q("#lTicker").prepend(el);
        if (q("#lTicker").children.length > 5) q("#lTicker").lastElementChild.remove();
        rise(el, ti, 0.3, 12);
        const chip = el.querySelector("em");
        chip.style.opacity = "0";
        animate(ti + 0.22, 0.3, (k) => { chip.style.opacity = k >= 1 ? "" : k.toFixed(3); chip.style.transform = k >= 1 ? "" : `scale(${(0.6 + 0.4 * k).toFixed(3)})`; });
      });
    }
    animate(t0 + 0.3, dur + 0.2, (k) => {
      q("#lCount").textContent = Math.round(total * k).toLocaleString("en-IN");
      stepTo(k < 0.3 ? 1 : k < 0.62 ? 2 : k < 0.999 ? 3 : 4);
    }, (x) => x);
    on(t0 + dur + 0.6, () => L.classList.add("done"));
    // spinning ring: rotate the whole svg while loading
    animate(t0, dur + 0.6, (k) => { q(".loader-ring").style.transform = `rotate(${(-90 + k * 540).toFixed(1)}deg)`; }, (x) => x);
  }

  let curCard = 0, cardT0 = 0, cardEnd = 0;
  function cardEnter(i, t0) {
    curCard = i; cardT0 = t0;
    const el = qa("#cards .card")[i];
    if (!el) return;
    [...el.children].forEach((c, j) => rise(c, t0 + 0.04 + j * 0.06, 0.55, 14));
    el.querySelectorAll(".v-tiles i").forEach((tile, j) => { tile.style.transform = "scale(0)"; animate(t0 + 0.25 + j * 0.012, 0.28, (k) => (tile.style.transform = k >= 1 ? "" : `scale(${k.toFixed(3)})`)); });
    el.querySelectorAll(".v-months .b, .v-flow .b, .v-hbars i").forEach((b, j) => {
      const isH = b.matches(".v-flow .b, .v-hbars i");
      b.style.transformOrigin = isH ? "left" : "bottom";
      b.style.transform = isH ? "scaleX(0)" : "scaleY(0)";
      animate(t0 + 0.25 + j * 0.08, 0.7, (k) => (b.style.transform = k >= 1 ? "" : (isH ? `scaleX(${k.toFixed(3)})` : `scaleY(${k.toFixed(3)})`)));
    });
  }
  function storyBars(t) {
    const bars = qa("#bars .bar i");
    if (!bars.length || q("#story").hidden) return;
    const dwell = 2.6;
    bars.forEach((b, i) => (b.style.width = i < curCard ? "100%" : i === curCard ? `${(clamp((t - cardT0) / dwell, 0, 1) * 100).toFixed(1)}%` : "0"));
  }
  function quipSwap(t0) {
    const qd = q("#cards .card:not([hidden]) .quip");
    if (qd) rise(qd, t0 + 0.02, 0.35, 6);
  }

  function dashEnter(t0) {
    const parts = [...qa(".dash-main > *"), q("#chat")];
    parts.forEach((p, i) => rise(p, t0 + 0.05 + Math.min(i, 5) * 0.07, 0.6, 18));
    on(t0 + 0.05, () => {
      qa("#donut path").forEach((p, i) => {
        p.style.opacity = "0";
        animate(t0 + 0.25 + i * 0.05, 0.75, (k) => { p.style.opacity = k >= 1 ? "" : k.toFixed(3); p.style.transform = k >= 1 ? "" : `scale(${(0.7 + 0.3 * k).toFixed(3)}) rotate(${((1 - k) * -35).toFixed(2)}deg)`; });
      });
      qa("#monthsChart rect.seg").forEach((r, i) => { r.style.transform = "scaleY(0)"; animate(t0 + 0.35 + i * 0.03, 0.7, (k) => (r.style.transform = k >= 1 ? "" : `scaleY(${k.toFixed(3)})`)); });
    });
  }
  function donutGeom(cat) {
    const s = (donutState.segs || []).find((x) => x.c.category === cat);
    const r = pageRect(q("#donut")), sc = r.w / 300;
    return { s, x: r.x + (150 + Math.cos(s.mid) * 116) * sc, y: r.y + (150 + Math.sin(s.mid) * 116) * sc };
  }
  const donutPoint = (cat) => () => { const g = donutGeom(cat); return [g.x, g.y]; };
  const donutEl = (cat) => () => donutGeom(cat).s.el;

  function chatSend(t0) {
    const text = q("#q").value;
    q("#q").value = "";
    const u = addMsg("user", esc(text)); rise(u, t0, 0.35, 10);
    const box = addMsg("bot", `<span class="typing"><i></i><i></i><i></i></span>`); rise(box, t0 + 0.25, 0.35, 10);
    const chips = document.createElement("div"); chips.className = "receipts"; box.after(chips);
    const a = D.chat;
    a.receipts.forEach((r, i) => on(t0 + 0.7 + i * 0.15, () => {
      const c = document.createElement("button"); c.type = "button"; c.className = "receipt"; c.textContent = "🧾 " + r.tool.replace(/_/g, " ");
      c.dataset.i = i; chips.appendChild(c); rise(c, FILM.t, 0.3, 6);
    }));
    const s0 = t0 + 1.0, sDur = 2.8, full = a.text;
    animate(s0, sDur, (k) => {
      const n = Math.round(full.length * k);
      box.innerHTML = md(full.slice(0, n)) || `<span class="typing"><i></i><i></i><i></i></span>`;
    }, (x) => x);
    on(s0 + sDur + 0.25, () => {
      const g = a.grounding; if (!g || !g.total) return;
      const b = document.createElement("div"); const ok = !g.unverified.length;
      b.className = "ground " + (ok ? "ok" : "warn");
      b.textContent = ok ? `✓ ${g.verified}/${g.total} numbers verified against your statement` : `⚠ ${g.verified}/${g.total} verified · not from your data: ${g.unverified.join(", ")}`;
      chips.after(b); rise(b, FILM.t, 0.4, 8);
      sfx(FILM.t, "chime");
    });
  }
  function openReceipt() {
    const c = q("#msgs .receipt"); if (!c) return;
    const r = D.chat.receipts[0];
    const pre = document.createElement("pre"); pre.className = "rbox";
    pre.textContent = JSON.stringify({ asked: r.args, answer: r.result }, null, 2);
    c.classList.add("open"); c.after(pre); rise(pre, FILM.t, 0.4, 6);
  }
  function fadeTo(t0, dur) {
    animate(t0, dur, (k) => (fade.style.opacity = k.toFixed(3)), ease);
    animate(t0 + dur, dur, (k) => (fade.style.opacity = (1 - k).toFixed(3)), ease);
  }

  // ---------- render ----------
  let fired = 0;
  const FILM = {
    t: 0,
    setup,
    build: () => { build(); events.sort((a, b) => a.t - b.t); clicks.sort((a, b) => a.t - b.t); clicks.forEach((c) => sfx(c.t, "click")); return { total: T.total, vo, T }; },
    async render(t) {
      FILM.t = t;
      camera(t);
      // events and clicks crossing t
      const due = [...events.filter((e) => !e.fired && e.t <= t), ...clicks.filter((c) => !c.fired && c.t <= t)].sort((a, b) => a.t - b.t);
      for (const e of due) {
        e.fired = true;
        if (!e.el) { e.run && e.run(); continue; }
        const el = e.el();
        if (el && el.tagName === "INPUT") el.focus({ preventScroll: true });
        else if (el && e.doClick) el.click();
        if (e.run) e.run();
      }
      // animators
      for (const a of anims) {
        if (a.done || t < a.t0) continue;
        const k = clamp((t - a.t0) / a.dur, 0, 1);
        a.apply(a.easing(k));
        if (k >= 1) a.done = true;
      }
      storyBars(t);
      camera(t); // second pass: layout may have changed this frame
      // cursor
      const p = cursorPos(t);
      let press = 0;
      for (const c of clicks) { const d = t - c.t; if (d >= -0.06 && d < 0.12) press = 1 - Math.abs(d - 0.03) / 0.09; }
      cursor.style.transform = `translate(${(p[0] - 3).toFixed(2)}px, ${(p[1] - 2).toFixed(2)}px) scale(${(1 - 0.12 * clamp(press, 0, 1)).toFixed(3)})`;
      let ringOn = false;
      for (const c of clicks) {
        const d = t - c.t;
        if (d >= 0 && d < 0.4) {
          const k = d / 0.4;
          ring.style.left = `${p[0]}px`; ring.style.top = `${p[1]}px`;
          ring.style.opacity = (0.55 * (1 - k)).toFixed(3);
          ring.style.transform = `scale(${(1 + k * 3.2).toFixed(3)})`;
          ringOn = true;
        }
      }
      if (!ringOn) ring.style.opacity = "0";
      await new Promise(requestAnimationFrame);
      return toScreen(p);
    },
    sounds: () => sounds.sort((a, b) => a.t - b.t),
    vo: () => vo,
  };
  window.FILM = FILM;
})();

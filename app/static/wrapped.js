// Credence Wrapped: story player. Cards come from GET /wrapped; AI quips (POST /wrapped/ai) replace the templates when they arrive.
window.Wrapped = (() => {
  const LOGO = `<svg viewBox="0 0 100 100"><path d="M75.27 72.75A34 34 0 0 1 41.63 82.95" stroke="#F5B700" stroke-width="15" fill="none"/><path d="M36.58 81.24A34 34 0 0 1 16.10 52.67" stroke="#E5352B" stroke-width="15" fill="none"/><path d="M16.10 47.33A34 34 0 0 1 36.58 18.76" stroke="#D81B7A" stroke-width="15" fill="none"/><path d="M41.63 17.05A34 34 0 0 1 75.27 27.25" stroke="#4B48D6" stroke-width="15" fill="none"/><circle cx="80" cy="50" r="7.5" fill="#9BE3C3"/></svg>`;
  const DUR = 7000;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const inr = (n) => "₹" + Math.round(n).toLocaleString("en-IN");
  const $ = (id) => document.getElementById(id);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const LIGHT = new Set(["turmeric", "cream", "saffron"]);

  let cards = [], els = [], idx = 0, mode = "roast", start = 0, elapsed = 0, paused = false, raf = null, onClose = null, ai = {};

  const viz = {
    flow: (v) => `<div class="v-flow">
        <div><span>came in</span><div class="b"></div></div>
        <div><span>went out · you kept ${inr(v.saved)}</span><div class="b out" style="--p:${(v.spend / v.income * 100).toFixed(1)}%"><div class="kept" style="width:${Math.max(0, v.saved / v.income * 100).toFixed(1)}%"></div></div></div>
      </div>`,
    tiles: (v) => {
      const total = v.items.reduce((s, i) => s + i.count, 0), scale = total > 66 ? 66 / total : 1;
      let k = 0;
      const tiles = v.items.map((it, j) => Array.from({ length: Math.max(1, Math.round(it.count * scale)) },
        () => `<i class="${j ? "b2" : ""}" style="animation-delay:${(k++ * 0.012).toFixed(3)}s"></i>`).join("")).join("");
      return `<div class="v-tiles">${tiles}</div>
        <div class="v-legend">${v.items.map((it, j) => `<span style="--c:${j ? "var(--turmeric)" : "var(--cream)"}">${esc(it.label)} ${it.count}</span>`).join("")}</div>
        ${scale < 1 ? `<div class="v-legend"><span style="--c:transparent">each tile ≈ ${(1 / scale).toFixed(1)} payments</span></div>` : ""}`;
    },
    days: (v) => {
      const n = Math.max(1, Math.ceil(v.days)), cols = Math.min(n, 12);
      const blocks = Array.from({ length: cols }, (_, i) => Math.min(1, Math.max(0, v.days - i)));
      return `<div class="v-days" style="grid-template-columns:repeat(${Math.max(cols, 6)},1fr)">${blocks.map((f, i) => `<div style="--f:${f.toFixed(2)};animation-delay:${0.15 + i * 0.08}s"></div>`).join("")}</div>
        <div class="v-cap"><span>day 1</span><span>8-hour working days</span><span>day ${cols}</span></div>`;
    },
    split: (v) => `<div class="v-split" style="grid-template-columns:${Math.max(v.weekday, 6)}fr ${v.weekend}fr"><div class="wd">${v.weekday}%</div><div class="we"><span>SAT + SUN</span><span>${v.weekend}%</span></div></div>
      <div class="v-cap"><span>Mon–Fri</span><span>weekends</span></div>`,
    bars: (v) => {
      const max = Math.max(...v.items.map((i) => i.v), 1);
      return `<div class="v-hbars">${v.items.map((i, j) => `<div><span>${esc(i.m)}</span><i style="width:${(i.v / max * 100).toFixed(0)}%;animation-delay:${0.15 + j * 0.08}s"></i><span>${inr(i.v)}</span></div>`).join("")}</div>`;
    },
    months: (v) => {
      const max = Math.max(...v.months.map((m) => m.v));
      return `<div class="v-months" style="--n:${v.months.length}">${v.months.map((m, j) => `<div class="${m.hot ? "hot" : ""}"><span class="v">${(m.v / 1000).toFixed(1)}k</span><div class="b" style="height:${(m.v / max * 78).toFixed(1)}%;animation-delay:${0.15 + j * 0.08}s"></div><span class="m">${esc(m.m)}</span></div>`).join("")}</div>`;
    },
    subs: (v) => `<div class="v-subs">${v.items.map((s) => `<div class="${s.flag ? "flag" : ""}"><span>${esc(s.m)}</span><span>${inr(s.v)}/mo</span></div>`).join("")}<div class="tot"><span>total</span><span>${inr(v.total)}/mo</span></div></div>`,
    friends: (v) => `<div class="v-friends">${v.items.map((f) => `<div class="f"><div class="av">${esc(f.m[0])}</div><div class="n">${esc(f.m)}<small>${f.n} payments</small></div><div class="a">${inr(f.v)}</div></div>`).join("")}
      <div class="ledger"><span>received back</span><span class="zero">${inr(v.back)}</span></div></div>`,
    wins: (v) => `<div class="v-wins">${v.items.map((w) => `<div><span>${esc(w.t)}</span><b>${inr(w.v)}</b></div>`).join("")}</div>
      <div class="v-year"><small>that's a year of</small><b>${inr(v.year)}</b>${v.hours ? `<span>or ${v.hours} hours of work, every month</span>` : ""}</div>`,
  };

  function bigClass(c) {
    const len = c.big.replace(/\n.*/s, "").length;
    if (c.id === "intro") return "";
    if (c.big.includes("\n")) return "md";
    return len > 14 ? "sm" : len > 9 ? "md" : "";
  }

  function render(c, i) {
    const intro = c.id === "intro", outro = c.id === "outro";
    const big = intro ? `<div class="c-intro-mark">${esc(c.big.replace(/ /g, "\n"))}</div>` : `<div class="c-big ${bigClass(c)}">${esc(c.big)}</div>`;
    return `<section class="card th-${c.theme}" data-i="${i}" hidden aria-label="Card ${i + 1} of ${cards.length}">
      <div class="c-eyebrow">${esc(c.eyebrow)}</div>
      ${big}
      <div class="c-sub">${esc(c.sub)}</div>
      ${c.viz && viz[c.viz.type] ? `<div class="c-viz">${viz[c.viz.type](c.viz)}</div>` : ""}
      <div class="c-spacer"></div>
      <div class="quip"><span class="tag"></span><div class="qt"></div></div>
      ${c.receipt ? `<div class="c-receipt">${esc(c.receipt)}</div>` : ""}
      ${intro ? `<div class="c-hint">tap to start →</div>` : ""}
      ${outro ? `<div class="ctas"><button type="button" class="cta" data-act="replay">Replay</button><button type="button" class="cta primary" data-act="done">Open dashboard</button></div>` : ""}
    </section>`;
  }

  function paintQuips() {
    els.forEach((el, i) => {
      const c = cards[i], q = ai[c.id]?.[mode];
      el.querySelector(".tag").textContent = q ? `${mode} · written by AI` : mode;
      el.querySelector(".qt").textContent = q || c.quip[mode];
    });
  }

  function setMode(m) {
    mode = m;
    $("frame").classList.toggle("mode-roast", m === "roast");
    $("frame").classList.toggle("mode-hype", m === "hype");
    document.querySelectorAll("#frame .toggle button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.mode === m));
    paintQuips();
    const q = els[idx]?.querySelector(".quip");
    if (q) { q.classList.remove("swap"); void q.offsetWidth; q.classList.add("swap"); }
  }

  function paintBars(p) {
    [...$("bars").children].forEach((b, i) => { b.firstElementChild.style.width = i < idx ? "100%" : i === idx ? p * 100 + "%" : "0"; });
  }

  function tick() {
    if (!paused) {
      const p = Math.min(1, (elapsed + performance.now() - start) / DUR);
      paintBars(p);
      if (p >= 1) return go(idx + 1);
    }
    raf = requestAnimationFrame(tick);
  }

  function go(i) {
    i = Math.max(0, Math.min(cards.length - 1, i));
    cancelAnimationFrame(raf);
    if (els[idx]) els[idx].hidden = true;
    idx = i;
    const el = els[idx];
    el.hidden = false;
    if (!reduce) { el.classList.remove("enter"); void el.offsetWidth; el.classList.add("enter"); }
    $("frame").classList.toggle("light", LIGHT.has(cards[idx].theme));
    elapsed = 0; start = performance.now();
    const still = idx === 0 || idx === cards.length - 1 || reduce;
    if (still) { paintBars(idx === cards.length - 1 ? 1 : 0); return; }
    raf = requestAnimationFrame(tick);
  }

  function close() {
    cancelAnimationFrame(raf);
    $("story").hidden = true;
    document.removeEventListener("keydown", onKey);
    onClose && onClose();
  }

  function onKey(e) {
    if (e.key === "ArrowRight") go(idx + 1);
    else if (e.key === "ArrowLeft") go(idx - 1);
    else if (e.key === "Escape") close();
  }

  let wired = false;
  function wire() {
    if (wired) return;
    wired = true;
    document.querySelectorAll("[data-logo]").forEach((m) => (m.innerHTML = LOGO));
    $("tapNext").addEventListener("click", () => go(idx + 1));
    $("tapPrev").addEventListener("click", () => go(idx - 1));
    $("storyClose").addEventListener("click", close);
    document.querySelectorAll("#frame .toggle button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
    const f = $("frame");
    f.addEventListener("pointerdown", () => { if (!paused) { paused = true; elapsed += performance.now() - start; } });
    ["pointerup", "pointerleave", "pointercancel"].forEach((t) => f.addEventListener(t, () => { if (paused) { paused = false; start = performance.now(); } }));
    $("cards").addEventListener("click", (e) => {
      const act = e.target.dataset?.act;
      if (act === "replay") { e.stopPropagation(); go(0); }
      if (act === "done") { e.stopPropagation(); close(); }
    });
  }

  function open(story, opts = {}) {
    wire();
    cards = story.cards; onClose = opts.onClose; ai = opts.ai || ai;
    $("bars").innerHTML = cards.map(() => '<div class="bar"><i></i></div>').join("");
    $("cards").innerHTML = cards.map(render).join("");
    els = [...$("cards").children];
    idx = 0;
    setMode(mode);
    $("story").hidden = false;
    document.addEventListener("keydown", onKey);
    go(0);
  }

  function setAI(quips) { ai = quips || {}; if (els.length) paintQuips(); }

  return { open, setAI, LOGO };
})();

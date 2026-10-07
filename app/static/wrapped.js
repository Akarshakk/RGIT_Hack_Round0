// Credence Wrapped: story player. Cards come from GET /wrapped; AI quips (POST /wrapped/ai) replace the templates when they arrive.
window.Wrapped = (() => {
  const LOGO = `<svg viewBox="0 0 100 100"><path d="M75.27 72.75A34 34 0 0 1 41.63 82.95" stroke="#F5B700" stroke-width="15" fill="none"/><path d="M36.58 81.24A34 34 0 0 1 16.10 52.67" stroke="#E5352B" stroke-width="15" fill="none"/><path d="M16.10 47.33A34 34 0 0 1 36.58 18.76" stroke="#D81B7A" stroke-width="15" fill="none"/><path d="M41.63 17.05A34 34 0 0 1 75.27 27.25" stroke="#3FA0FF" stroke-width="15" fill="none"/><circle cx="80" cy="50" r="7.5" fill="#9BE3C3"/></svg>`;
  const DUR = 7000;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const inr = (n) => "₹" + Math.round(n).toLocaleString("en-IN");
  const $ = (id) => document.getElementById(id);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const LIGHT = new Set(["turmeric", "cream", "saffron", "sky", "mint"]);

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
    future: (v) => {
      const pts = [{ year: 0, value: 0, contributed: 0 }, ...v.series], max = pts[pts.length - 1].value, n = pts.length - 1;
      const xy = (k) => pts.map((p, i) => `${(i / n * 100).toFixed(2)},${(48 - p[k] / max * 44).toFixed(2)}`).join(" ");
      return `<svg class="v-future" viewBox="0 0 100 50" preserveAspectRatio="none" aria-hidden="true">
          <polygon points="0,48 ${xy("value")} 100,48" fill="var(--ink)" opacity=".9"/>
          <polygon points="0,48 ${xy("contributed")} 100,48" fill="var(--turmeric)"/>
        </svg>
        <div class="v-legend"><span style="--c:var(--turmeric)">you put in ${inr(v.contributed)}</span><span style="--c:var(--ink)">growth ${inr(v.growth)}</span></div>`;
    },
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
    const intro = c.id === "intro", last = i === cards.length - 1;
    const big = intro ? `<div class="c-intro-mark">${esc(c.big.replace(/ /g, "\n"))}</div>` : `<div class="c-big ${bigClass(c)}">${esc(c.big)}</div>`;
    return `<section class="card th-${c.theme}" data-i="${i}" hidden aria-label="Card ${i + 1} of ${cards.length}">
      <div class="c-eyebrow">${esc(c.eyebrow)}</div>
      ${big}
      <div class="c-sub">${esc(c.sub)}</div>
      ${c.viz && viz[c.viz.type] ? `<div class="c-viz">${viz[c.viz.type](c.viz)}</div>` : ""}
      <div class="c-spacer"></div>
      <div class="quip"><span class="tag"></span><div class="qt"></div></div>
      ${c.receipt ? `<div class="c-receipt${c.id === "future" ? " plain" : ""}">${esc(c.receipt)}</div>` : ""}
      ${intro ? `<div class="c-hint">tap to start →</div>` : ""}
      ${last ? `<div class="ctas"><button type="button" class="cta" data-act="share">Share card</button><button type="button" class="cta primary" data-act="done">Open dashboard</button></div>` : ""}
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
      if (act === "share") { e.stopPropagation(); shareCard(); }
      if (act === "done") { e.stopPropagation(); close(); }
    });
  }

  function open(st, opts = {}) {
    wire();
    cards = st.cards; story = st; onClose = opts.onClose; ai = opts.ai || ai;
    $("bars").innerHTML = cards.map(() => '<div class="bar"><i></i></div>').join("");
    $("cards").innerHTML = cards.map(render).join("");
    els = [...$("cards").children];
    idx = 0;
    setMode(mode);
    $("story").hidden = false;
    document.addEventListener("keydown", onKey);
    go(0);
  }

  // 1080x1920 PNG summary for Instagram stories / WhatsApp status. Drawn on canvas from the same story data.
  let story = null;
  async function shareCard(st = story) {
    if (!st) return;
    await document.fonts.ready;
    const W = 1080, H = 1920, cv = document.createElement("canvas"); cv.width = W; cv.height = H;
    const g = cv.getContext("2d"), by = (id) => st.cards.find((c) => c.id === id);
    g.fillStyle = "#0e2522"; g.fillRect(0, 0, W, H);
    // logo ring
    const segs = ["#F5B700", "#E5352B", "#D81B7A", "#3FA0FF"];
    g.lineWidth = 26;
    segs.forEach((c, i) => { const a0 = (42 + i * 71.25) * Math.PI / 180; g.strokeStyle = c; g.beginPath(); g.arc(150, 170, 58, a0, a0 + 62.25 * Math.PI / 180); g.stroke(); });
    g.fillStyle = "#9BE3C3"; g.beginPath(); g.arc(201, 170, 13, 0, Math.PI * 2); g.fill();
    g.fillStyle = "#fff4e0"; g.font = "800 64px Unbounded"; g.fillText("credence", 250, 194);
    g.font = "600 34px Unbounded"; g.fillStyle = "#a3b8b2"; g.fillText(("MY MONEY, WRAPPED · " + st.period).toUpperCase(), 90, 330);
    const persona = by("persona");
    g.fillStyle = "#F5B700"; g.font = "900 112px Unbounded";
    wrap(g, persona ? persona.big : "Paisa kahan gaya?", 90, 470, 900, 118);
    const rows = [["Top app", by("top") && `${by("top").big} · ${by("top").sub.split(" and ")[0]}`],
      ["Food delivery", by("hours") && `${by("hours").big} of my work`],
      ["Plot twist", by("peak") && by("peak").big.replace(".", "")],
      ["Can win back", by("outro") && `${by("outro").big} a month`],
      ["Future me", by("future") && `${by("future").big} by ${by("future").eyebrow.split("· ")[1]}`]].filter((r) => r[1]);
    let y = 860;
    const colors = ["#E5352B", "#7cc4ff", "#fff4e0", "#9BE3C3", "#F5B700"];
    rows.forEach(([k, v], i) => {
      g.fillStyle = "rgba(255,244,224,.08)"; roundRect(g, 90, y - 70, 900, 150, 36); g.fill();
      g.fillStyle = colors[i]; g.beginPath(); g.arc(150, y + 5, 16, 0, Math.PI * 2); g.fill();
      g.fillStyle = "#a3b8b2"; g.font = "500 34px Mukta"; g.fillText(k, 196, y - 8);
      g.fillStyle = "#fff4e0"; g.font = "800 46px Unbounded"; g.fillText(fit(g, v, 760), 196, y + 50);
      y += 180;
    });
    g.fillStyle = "#a3b8b2"; g.font = "500 32px Mukta"; g.fillText("Made with Credence · your bank statement, told like a story", 90, H - 110);
    cv.toBlob((b) => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "my-credence-wrapped.png"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); });
  }
  function wrap(g, text, x, y, maxW, lh) {
    let line = "";
    for (const w of text.split(" ")) { const t = line ? line + " " + w : w; if (g.measureText(t).width > maxW && line) { g.fillText(line, x, y); y += lh; line = w; } else line = t; }
    g.fillText(line, x, y);
  }
  function fit(g, t, maxW) { while (g.measureText(t).width > maxW && t.length > 4) t = t.slice(0, -2) + "…"; return t; }
  function roundRect(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }

  function setAI(quips) { ai = quips || {}; if (els.length) paintQuips(); }

  return { open, setAI, shareCard, LOGO };
})();

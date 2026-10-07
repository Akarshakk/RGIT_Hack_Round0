const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const inr = (n) => (n < 0 ? "−" : "") + "₹" + Math.abs(Math.round(n)).toLocaleString("en-IN");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const SVGNS = "http://www.w3.org/2000/svg";

const CAT_COLOR = {
  "Rent": "#8c89ff", "EMI & Loans": "#b3b1ff", "Shopping": "#e5352b", "Food & Dining": "#f5b700", "Groceries": "#19a99b",
  "Subscriptions": "#d81b7a", "Transport": "#ff7a1a", "Utilities & Bills": "#6fb7ff", "Cash Withdrawal": "#c9a7ff",
  "Transfers": "#ff9f80", "Fees & Charges": "#ff5c5c", "Entertainment": "#f48fb1", "Health & Fitness": "#9be3c3",
  "Education": "#ffd166", "Investments": "#9be3c3", "Income": "#9be3c3", "Other": "#b1aacd",
};
const color = (c) => CAT_COLOR[c] || "#b1aacd";

let categories = [], story = null, aiQuips = {}, data = null, txAll = [], txFilter = null, lastFile = null;

document.querySelectorAll("[data-logo]").forEach((m) => (m.innerHTML = Wrapped.LOGO));

// ================= upload =================
function form(file, mapping) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("password", $("pw").value);
  if (mapping) fd.append("mapping", JSON.stringify(mapping));
  return fd;
}
const uploadFile = (f) => { lastFile = f; run(() => fetch("/upload", { method: "POST", body: form(f) })); };

const drop = $("drop");
drop.addEventListener("click", () => $("file").click());
drop.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), $("file").click()));
$("file").addEventListener("change", (e) => e.target.files[0] && uploadFile(e.target.files[0]));
["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "dragend"].forEach((t) => drop.addEventListener(t, () => drop.classList.remove("over")));
drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); e.dataTransfer.files[0] && uploadFile(e.dataTransfer.files[0]); });
// dropping anywhere on the landing page works too
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => { e.preventDefault(); if (!$("landing").hidden && e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]); });

$("sampleBtn").onclick = () => run(() => fetch("/sample?kind=csv", { method: "POST" }));
$("samplePdf").onclick = () => run(() => fetch("/sample?kind=pdf", { method: "POST" }));
$("mapGo").onclick = () => {
  const mapping = { date: $("mDate").value, narration: $("mNarr").value, amount: $("mAmt").value };
  run(() => fetch("/upload", { method: "POST", body: form(lastFile, mapping) }));
};

function showMap(cols) {
  $("mapBox").hidden = false;
  for (const id of ["mDate", "mNarr", "mAmt"]) $(id).innerHTML = cols.map((c) => `<option>${esc(c)}</option>`).join("");
}

// ================= processing loader =================
const steps = () => [...$("lSteps").children];
function stepTo(n) { steps().forEach((li, i) => { li.classList.toggle("ok", i < n); li.classList.toggle("on", i === n); }); }

async function run(request) {
  $("upErr").textContent = "";
  $("mapBox").hidden = true;
  const L = $("loader");
  L.classList.remove("done");
  $("lCount").textContent = "0";
  $("lTicker").innerHTML = "";
  stepTo(0);
  L.hidden = false;
  const t0 = performance.now();
  let res, j;
  try {
    res = await request();
    j = await res.json();
  } catch {
    L.hidden = true;
    $("upErr").textContent = "Couldn't reach the server. Check that it's running and try again.";
    return;
  }
  if (!res.ok || j.needs_mapping) {
    L.hidden = true;
    if (j.needs_mapping) return showMap(j.columns);
    $("upErr").textContent = j.detail || "Something went wrong reading that file.";
    if (/password/i.test(j.detail || "")) $("pw").focus();
    return;
  }
  stepTo(1);
  const [tx, st, status] = await Promise.all([
    fetch("/transactions?limit=20000").then((r) => r.json()),
    fetch("/wrapped").then((r) => r.json()),
    fetch("/status").then((r) => r.json()),
  ]);
  txAll = tx; story = st; categories = status.categories;
  aiQuips = {};
  const aiReq = status.chat_enabled ? fetch("/wrapped/ai", { method: "POST" }).then((r) => r.json()).then((d) => { aiQuips = d.quips || {}; Wrapped.setAI(aiQuips); }).catch(() => {}) : null;
  setChatStatus(status.chat_enabled);
  const dashReady = renderDashboard(); // build it behind the loader so it's ready when the story closes

  // the ticker: real narrations from this statement, each decoded into its category
  const rows = [...tx].reverse();
  const show = reduce ? 0 : Math.min(rows.length, 26);
  const total = j.rows, dur = reduce ? 200 : 2600;
  const start = performance.now();
  for (let i = 0; i < show && performance.now() - start < dur; i++) {
    const r = rows[Math.floor(i * rows.length / show)];
    const t = document.createElement("div");
    t.className = "tick";
    t.innerHTML = `<code>${esc(r.narration.replace(/\d{6,}/g, "…"))}</code><em style="--c:${color(r.category)}">${esc(r.category)}</em>`;
    $("lTicker").prepend(t);
    if ($("lTicker").children.length > 5) $("lTicker").lastElementChild.remove();
    const p = Math.min(1, (performance.now() - start) / dur);
    $("lCount").textContent = Math.round(total * p).toLocaleString("en-IN");
    stepTo(p < 0.45 ? 1 : p < 0.8 ? 2 : 3);
    await sleep(dur / show);
  }
  $("lCount").textContent = total.toLocaleString("en-IN");
  stepTo(4);
  L.classList.add("done");
  if (aiReq) await Promise.race([aiReq, sleep(Math.max(0, 1800 - (performance.now() - t0)))]);
  await dashReady;
  await sleep(reduce ? 0 : 450);
  L.hidden = true;
  $("landing").hidden = true;
  Wrapped.open(story, { ai: aiQuips, onClose: showDashboard });
}

function showDashboard() {
  $("landing").hidden = true;
  $("app").hidden = false;
  $("dashActions").hidden = false;
  $("periodLabel").textContent = story?.period || "";
  const main = document.querySelector(".dash-main");
  main.classList.remove("reveal"); void main.offsetWidth; main.classList.add("reveal");
  requestAnimationFrame(() => { drawDonut(true); drawMonths(true); });
  window.scrollTo({ top: 0 });
}

$("replayBtn").onclick = () => Wrapped.open(story, { ai: aiQuips, onClose: showDashboard });
$("delBtn").onclick = async () => { await fetch("/session", { method: "DELETE" }); location.href = "/"; };

// ================= dashboard =================
const hoursOf = (amt) => (story?.hourly ? Math.round(amt / story.hourly) : null);

async function renderDashboard() {
  const r = await fetch("/overview");
  if (!r.ok) return location.reload();
  data = await r.json();
  const o = data.overview;
  const hrs = hoursOf(o.spend);
  const rate = o.savings_rate_pct ?? 0;
  $("kpis").innerHTML = `
    <div class="kpi"><small>Came in</small><b>${inr(o.income)}</b><span>${o.from_date.slice(5)} to ${o.to_date.slice(5)}</span></div>
    <div class="kpi"><small>Went out</small><b>${inr(o.spend)}</b><span>${hrs ? `${hrs.toLocaleString("en-IN")} hours of your work` : `${o.transactions} transactions`}</span></div>
    <div class="kpi"><small>You kept</small><b>${inr(o.net_savings)}</b><span>${o.invested ? `plus ${inr(o.invested)} invested` : "after all spending"}</span></div>
    <div class="kpi"><small>Savings rate</small><b>${rate}%</b><span>${rate >= 20 ? "above the 20% target" : `${(20 - rate).toFixed(1)} points under 20%`}</span>
      <svg class="ring" viewBox="0 0 36 36"><circle cx="18" cy="18" r="14" fill="none" stroke="rgba(255,244,224,.12)" stroke-width="5"/><circle cx="18" cy="18" r="14" fill="none" stroke="#9be3c3" stroke-width="5" stroke-linecap="round" pathLength="100" stroke-dasharray="${Math.max(0, Math.min(100, rate))} 100" transform="rotate(-90 18 18)"/></svg></div>`;
  renderLegend();
  if (!$("app").hidden) { drawDonut(false); drawMonths(false); }
  renderRule();
  renderTips();
  renderWhatIf();
  renderTx();
}

// ---------- donut ----------
let donutState = { hover: null };
function arcPath(cx, cy, r0, r1, a0, a1) {
  const p = (r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const large = a1 - a0 > Math.PI ? 1 : 0;
  const [x0, y0] = p(r1, a0), [x1, y1] = p(r1, a1), [x2, y2] = p(r0, a1), [x3, y3] = p(r0, a0);
  return `M${x0} ${y0}A${r1} ${r1} 0 ${large} 1 ${x1} ${y1}L${x2} ${y2}A${r0} ${r0} 0 ${large} 0 ${x3} ${y3}Z`;
}

function drawDonut(animate) {
  const svg = $("donut"), cats = data.categories, total = cats.reduce((s, c) => s + c.amount, 0);
  svg.innerHTML = "";
  const pad = 0.012, r0 = 92, r1 = 140;
  let acc = -Math.PI / 2;
  const segs = cats.map((c) => {
    const a = (c.amount / total) * Math.PI * 2;
    const s = { c, a0: acc + pad, a1: acc + a - pad, mid: acc + a / 2 };
    acc += a;
    const path = document.createElementNS(SVGNS, "path");
    path.setAttribute("fill", color(c.category));
    path.style.setProperty("--glow", color(c.category));
    path.dataset.cat = c.category;
    svg.appendChild(path);
    s.el = path;
    return s;
  });
  const paint = (k) => segs.forEach((s) => {
    const a1 = s.a0 + (s.a1 - s.a0) * k, base = -Math.PI / 2;
    const f = (x) => base + (x - base) * k;
    s.el.setAttribute("d", arcPath(150, 150, r0, r1, f(s.a0), Math.max(f(s.a0) + 0.0001, f(s.a1))));
  });
  paint(1); // always draw the finished chart; the entrance is a CSS animation so a throttled tab can't leave it half-drawn
  if (animate && !reduce) segs.forEach((s, i) => (s.el.style.animation = `segIn .8s cubic-bezier(.2,.8,.2,1) ${i * 0.06}s backwards`));

  segs.forEach((s) => {
    s.el.addEventListener("mouseenter", () => hoverCat(s.c.category));
    s.el.addEventListener("mouseleave", () => hoverCat(null));
    s.el.addEventListener("click", () => setTxFilter(s.c.category));
  });
  donutState.segs = segs;
  donutState.total = total;
  hoverCat(null);
}

function hoverCat(cat) {
  const svg = $("donut"), segs = donutState.segs || [];
  svg.classList.toggle("has-hover", !!cat);
  $("legend").classList.toggle("has-hover", !!cat);
  segs.forEach((s) => {
    const on = s.c.category === cat;
    s.el.classList.toggle("on", on);
    s.el.style.transform = on ? `translate(${Math.cos(s.mid) * 10}px, ${Math.sin(s.mid) * 10}px) scale(1.03)` : "";
  });
  [...$("legend").children].forEach((li) => li.classList.toggle("on", li.dataset.cat === cat));
  const c = data.categories.find((x) => x.category === cat);
  const center = $("donutCenter");
  if (c) {
    const h = hoursOf(c.amount);
    center.innerHTML = `<small>${esc(c.category)}</small><b>${inr(c.amount)}</b><span class="pct" style="--c:${color(c.category)}">${c.pct}%</span><span>${c.count} payment${c.count === 1 ? "" : "s"}${h ? `<br>${h} hours of work` : ""}</span>`;
  } else {
    center.innerHTML = `<small>Total spent</small><b>${inr(donutState.total || 0)}</b><span>across ${data.categories.length} categories</span>`;
  }
}

function renderLegend() {
  const max = Math.max(...data.categories.map((c) => c.amount));
  $("legend").innerHTML = data.categories.map((c) => `
    <li data-cat="${esc(c.category)}" style="--c:${color(c.category)};--w:${(c.amount / max * 100).toFixed(1)}%" class="${txFilter === c.category ? "active" : ""}">
      <i></i><div class="nm"><span>${esc(c.category)}</span><u></u></div><b>${inr(c.amount)}</b>
    </li>`).join("");
  [...$("legend").children].forEach((li) => {
    li.onmouseenter = () => hoverCat(li.dataset.cat);
    li.onmouseleave = () => hoverCat(null);
    li.onclick = () => setTxFilter(li.dataset.cat);
  });
}

// ---------- months (stacked) ----------
const BUCKETS = [["Need", "Needs", "#19a99b"], ["Want", "Wants", "#e5352b"], ["Transfer", "Cash and transfers", "#ff7a1a"]];
function drawMonths(animate) {
  const svg = $("monthsChart"), tb = data.trend_buckets, months = Object.keys(tb);
  const W = svg.clientWidth || 600, H = 260, top = 28, bottom = 30, left = 8;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const totals = months.map((m) => BUCKETS.reduce((s, [b]) => s + (tb[m][b] || 0), 0));
  const max = Math.max(...totals) * 1.08;
  const slot = (W - left * 2) / months.length, bw = Math.min(78, slot * 0.56);
  const y = (v) => (H - bottom) - (v / max) * (H - top - bottom);
  const peak = totals.indexOf(Math.max(...totals));
  let html = `<line x1="0" x2="${W}" y1="${H - bottom}" y2="${H - bottom}" stroke="rgba(255,244,224,.18)"/>`;
  months.forEach((m, i) => {
    const x = left + slot * i + (slot - bw) / 2;
    let acc = 0, segs = "";
    BUCKETS.forEach(([b, , c], j) => {
      const v = tb[m][b] || 0; if (!v) return;
      const y1 = y(acc + v), h = y(acc) - y1;
      segs += `<rect class="seg" x="${x}" y="${y1}" width="${bw}" height="${Math.max(0, h - 2)}" rx="${j === 2 || acc + v === totals[i] ? 8 : 3}" fill="${c}" style="${animate && !reduce ? `animation:fillUp .7s cubic-bezier(.2,.8,.2,1) ${i * 0.09 + j * 0.05}s both` : ""}"/>`;
      acc += v;
    });
    const label = new Date(m + "-01").toLocaleString("en-IN", { month: "short" });
    html += `<g class="col" data-i="${i}"><rect x="${left + slot * i}" y="0" width="${slot}" height="${H}" fill="transparent"/>${segs}
      <text class="tot" x="${x + bw / 2}" y="${y(totals[i]) - 9}" text-anchor="middle"${i === peak ? ' style="fill:#f5b700"' : ""}>${(totals[i] / 1000).toFixed(1)}k</text>
      <text x="${x + bw / 2}" y="${H - 9}" text-anchor="middle">${label}</text></g>`;
  });
  svg.innerHTML = html;
  const tip = $("mtip");
  svg.querySelectorAll(".col").forEach((g) => {
    const i = +g.dataset.i, m = months[i];
    g.addEventListener("mouseenter", () => {
      svg.classList.add("has-hover"); g.classList.add("on");
      const h = hoursOf(totals[i]);
      tip.innerHTML = `<b>${new Date(m + "-01").toLocaleString("en-IN", { month: "long", year: "numeric" })}</b>` +
        BUCKETS.map(([b, n, c]) => `<div><span><i style="--c:${c}"></i>${n}</span><span>${inr(tb[m][b] || 0)}</span></div>`).join("") +
        `<div class="h"><span>Total</span><span>${inr(totals[i])}</span></div>` + (h ? `<div><span>In hours of work</span><span>${h} h</span></div>` : "");
      const box = svg.getBoundingClientRect();
      const x = (left + slot * i + slot / 2) / W * box.width;
      tip.style.left = Math.min(Math.max(x, 100), box.width - 100) + "px";
      tip.style.top = (y(totals[i]) / H * box.height) + "px";
      tip.hidden = false;
    });
    g.addEventListener("mouseleave", () => { svg.classList.remove("has-hover"); g.classList.remove("on"); tip.hidden = true; });
  });
}
let rz;
window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => data && !$("app").hidden && drawMonths(false), 150); });

// ---------- 50/30/20 ----------
function renderRule() {
  const ev = data.insights.find((i) => i.id === "rule_50_30_20")?.evidence;
  if (!ev) { $("rule").innerHTML = ""; return; }
  const parts = [[ev.needs_pct, "Needs", "#19a99b"], [ev.wants_pct, "Wants", "#e5352b"], [Math.max(0, ev.saved_pct), "Saved", "#9be3c3"]];
  $("rule").innerHTML = parts.map(([p, l, c]) => `<span style="flex:${p} 0 0;background:${c}" title="${l} ${p}%">${p >= 9 ? `${l} ${Math.round(p)}%` : ""}</span>`).join("");
  document.querySelector(".rule-targets")?.remove();
  $("rule").insertAdjacentHTML("afterend", `<div class="rule-targets"><i style="left:50%"></i><em style="left:50%">50% needs</em><i style="left:80%"></i><em style="left:80%">80%, so 20% saved</em></div>`);
}

// ---------- tips ----------
function renderTips() {
  $("tips").innerHTML = data.insights.map((i, n) => `
    <div class="tip ${i.severity}"><span class="sev"></span><p>${esc(i.title)}</p>
      <div class="tip-right">${i.monthly_saving_estimate ? `<b>${inr(i.monthly_saving_estimate)}<small>/mo</small></b>` : ""}<button type="button" data-i="${n}">Ask</button></div>
    </div>`).join("");
  $("tips").querySelectorAll("button").forEach((b) => (b.onclick = () => {
    ask("Tell me more about this and what I should do: " + data.insights[b.dataset.i].title);
    if (innerWidth < 1100) $("chat").scrollIntoView({ behavior: "smooth" });
  }));
}

// ---------- what-if + goal ----------
const DISC = ["Food & Dining", "Shopping", "Subscriptions", "Transport", "Groceries", "Entertainment", "Transfers"];
let wiTimer;
function renderWhatIf() {
  const cats = data.categories.filter((c) => DISC.includes(c.category)).slice(0, 4);
  $("whatif").innerHTML = cats.map((c) => `
    <div class="slider"><label for="wi-${esc(c.category).replace(/\W/g, "")}"><span>${esc(c.category)} <small style="color:var(--dim)">${inr(c.amount)} total</small></span><span data-o="${esc(c.category)}">no cut</span></label>
    <input id="wi-${esc(c.category).replace(/\W/g, "")}" type="range" min="0" max="100" step="5" value="0" data-c="${esc(c.category)}"></div>`).join("");
  $("whatif").querySelectorAll("input").forEach((r) => (r.oninput = () => {
    r.style.setProperty("--v", r.value + "%");
    $("whatif").querySelector(`[data-o="${r.dataset.c}"]`).textContent = +r.value ? `cut ${r.value}%` : "no cut";
    clearTimeout(wiTimer); wiTimer = setTimeout(simulate, 200);
  }));
  $("whatifOut").hidden = true;
}
async function simulate() {
  const changes = [...$("whatif").querySelectorAll("input")].filter((r) => +r.value > 0).map((r) => ({ category: r.dataset.c, cut_pct: +r.value }));
  if (!changes.length) return ($("whatifOut").hidden = true);
  const s = await (await fetch("/simulate", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ changes }) })).json();
  const h = hoursOf(s.monthly_saving);
  $("whatifOut").hidden = false;
  $("whatifOut").innerHTML = `You'd save <b>${inr(s.monthly_saving)}</b> a month${h ? ` (${h} hours of work)` : ""}, which is <b>${inr(s.saving_over_period)}</b> a year. Your savings rate goes from ${s.savings_rate_pct_before}% to <b>${s.savings_rate_pct_after}%</b>.`;
}
$("goalForm").onsubmit = async (e) => {
  e.preventDefault();
  const g = await (await fetch("/goal", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ target: +$("gAmt").value, months: +$("gMon").value }) })).json();
  $("gOut").innerHTML = `Save <b>${inr(g.monthly_needed)}</b> a month. You have about ${inr(g.current_monthly_surplus)} spare each month, ` +
    (g.on_track ? `so <b>you're on track</b>.` : `so you're <b>${inr(g.gap)}</b> short each month.`) +
    (g.tips_to_close_gap.length ? `<ul>${g.tips_to_close_gap.map((t) => `<li>${esc(t.title)} (${inr(t.monthly_saving_estimate)}/mo)</li>`).join("")}</ul>` +
      (g.gap_after_tips ? `<p>Still ${inr(g.gap_after_tips)} a month short after these.</p>` : `<p>These close the gap.</p>`) : "");
};

// ---------- transactions ----------
function setTxFilter(cat) {
  txFilter = txFilter === cat ? null : cat;
  renderTx(); renderLegend();
  if (txFilter) $("tx").closest(".panel").scrollIntoView({ behavior: "smooth", block: "start" });
}
$("txClear").onclick = () => setTxFilter(txFilter);
async function renderTx() {
  txAll = await (await fetch("/transactions?limit=20000")).json();
  const rows = txFilter ? txAll.filter((t) => t.category === txFilter) : txAll;
  $("txFilter").hidden = !txFilter;
  if (txFilter) { $("txFilterLabel").textContent = `${txFilter} · ${rows.length}`; $("txFilterLabel").style.setProperty("--c", color(txFilter)); }
  $("tx").innerHTML = `<tr><th>Date</th><th>Where</th><th style="text-align:right">Amount</th><th>Category</th></tr>` + rows.slice(0, 400).map((t) => `
    <tr><td class="d">${t.date.slice(8)} ${new Date(t.date).toLocaleString("en-IN", { month: "short" })}</td>
      <td class="m"><b>${esc(t.merchant)}</b><code>${esc(t.narration)}</code></td>
      <td class="a ${t.amount > 0 ? "cr" : ""}">${t.amount > 0 ? "+" : ""}${inr(t.amount)}</td>
      <td><select data-m="${esc(t.merchant)}" style="--c:${color(t.category)}" aria-label="Category for ${esc(t.merchant)}">${categories.map((c) => `<option${c === t.category ? " selected" : ""}>${esc(c)}</option>`).join("")}</select></td></tr>`).join("");
  $("tx").querySelectorAll("select").forEach((s) => (s.onchange = async () => {
    await fetch("/recategorize", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ merchant: s.dataset.m, category: s.value }) });
    story = await (await fetch("/wrapped")).json();
    renderDashboard();
  }));
}

// ================= chat =================
const SUGG = ["Where did most of my money go?", "Which subscriptions am I paying for?", "How can I save ₹5,000 a month?", "Mera food ka kharcha kitna hai?", "Which mutual fund should I buy?"];
$("sugg").innerHTML = SUGG.map((s) => `<button type="button">${esc(s)}</button>`).join("");
$("sugg").querySelectorAll("button").forEach((b) => (b.onclick = () => ask(b.textContent)));
$("askForm").onsubmit = (e) => { e.preventDefault(); ask($("q").value); };

function setChatStatus(on) {
  $("chatStatus").textContent = on ? "Numbers come from your statement, never guessed" : "AI chat is off: add GROQ_API_KEY to .env and restart";
}

function md(src) {
  const lines = esc(src).split("\n"), out = [];
  let list = null, table = null;
  const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|\W)\*(\S.*?)\*(?=\W|$)/g, "$1<em>$2</em>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const flush = () => { if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; } if (table) { out.push(`<table>${table.join("")}</table>`); table = null; } };
  for (const raw of lines) {
    const l = raw.trim();
    if (/^\|.*\|$/.test(l)) {
      if (/^\|[\s:|-]+\|$/.test(l)) continue;
      list && flush(); table = table || [];
      const cells = l.slice(1, -1).split("|").map((c) => inline(c.trim()));
      table.push(`<tr>${cells.map((c) => (table.length ? `<td>${c}</td>` : `<th>${c}</th>`)).join("")}</tr>`);
    } else if (/^([-*•]|\d+[.)])\s+/.test(l)) { table && flush(); list = list || []; list.push(`<li>${inline(l.replace(/^([-*•]|\d+[.)])\s+/, ""))}</li>`); }
    else if (!l) flush();
    else { flush(); out.push(`<p>${inline(l.replace(/^#+\s*/, ""))}</p>`); }
  }
  flush();
  return out.join("");
}

function addMsg(cls, html) {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.innerHTML = html;
  $("msgs").appendChild(d);
  $("msgs").scrollTop = 1e9;
  return d;
}

let busy = false;
async function ask(text) {
  text = text.trim();
  if (!text || busy) return;
  busy = true;
  $("q").value = "";
  addMsg("user", esc(text));
  const box = addMsg("bot", `<span class="typing"><i></i><i></i><i></i></span>`);
  const chips = document.createElement("div");
  chips.className = "receipts";
  box.after(chips);
  let acc = "", notes = "";
  const paint = () => { box.innerHTML = md(acc) + (notes ? `<p class="notice">${esc(notes)}</p>` : ""); $("msgs").scrollTop = 1e9; };
  try {
    const r = await fetch("/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ message: text }) });
    if (!r.ok) { box.textContent = "Your session expired. Upload the statement again to keep chatting."; return; }
    const rd = r.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await rd.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, i); buf = buf.slice(i + 2);
        const ev = block.match(/^event: (.*)$/m)?.[1], raw = block.match(/^data: (.*)$/m)?.[1];
        if (!ev || raw === undefined) continue;
        const d = JSON.parse(raw);
        if (ev === "text") { acc += d; paint(); }
        else if (ev === "notice") { notes += (notes ? " " : "") + d; paint(); }
        else if (ev === "receipt") {
          const c = document.createElement("button");
          c.type = "button"; c.className = "receipt"; c.textContent = "🧾 " + d.tool.replace(/_/g, " ");
          c.onclick = () => {
            const open = c.nextElementSibling?.tagName === "PRE";
            chips.querySelectorAll("pre").forEach((p) => p.remove());
            chips.querySelectorAll(".receipt").forEach((x) => x.classList.remove("open"));
            if (open) return;
            const pre = document.createElement("pre"); pre.className = "rbox";
            pre.textContent = JSON.stringify({ asked: d.args, answer: d.result }, null, 2);
            c.classList.add("open"); c.after(pre);
          };
          chips.appendChild(c);
        }
      }
    }
    if (!acc && !notes) box.textContent = "No answer came back. Try asking again.";
  } catch {
    box.textContent = "Lost the connection. Try again.";
  } finally { busy = false; }
}

// ================= resume a live session =================
fetch("/status").then((r) => r.json()).then(async (s) => {
  categories = s.categories;
  setChatStatus(s.chat_enabled);
  if (!s.has_session) return;
  story = await (await fetch("/wrapped")).json();
  await renderDashboard();
  showDashboard();
});

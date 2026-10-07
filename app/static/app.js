const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const inr = (n) => "₹" + Math.round(n).toLocaleString("en-IN");
let charts = {}, categories = [], lastFile = null, data = null;

// ---------- upload ----------
async function send(fd) {
  $("upErr").textContent = "";
  const r = await fetch("/upload", { method: "POST", body: fd });
  return done(r);
}
async function done(r) {
  const j = await r.json();
  if (!r.ok) { $("upErr").textContent = j.detail || "Something went wrong."; return; }
  if (j.needs_mapping) return showMap(j.columns);
  $("mapBox").style.display = "none";
  await show();
}
function pick(f) {
  lastFile = f;
  const fd = new FormData(); fd.append("file", f); fd.append("password", $("pw").value);
  send(fd);
}
function showMap(cols) {
  $("mapBox").style.display = "block";
  for (const id of ["mDate", "mNarr", "mAmt"]) $(id).innerHTML = cols.map((c) => `<option>${esc(c)}</option>`).join("");
}
$("mapGo").onclick = () => {
  const fd = new FormData(); fd.append("file", lastFile); fd.append("password", $("pw").value);
  fd.append("mapping", JSON.stringify({ date: $("mDate").value, narration: $("mNarr").value, amount: $("mAmt").value }));
  send(fd);
};
$("drop").onclick = () => $("file").click();
$("file").onchange = (e) => e.target.files[0] && pick(e.target.files[0]);
$("drop").ondragover = (e) => { e.preventDefault(); $("drop").classList.add("over"); };
$("drop").ondragleave = () => $("drop").classList.remove("over");
$("drop").ondrop = (e) => { e.preventDefault(); $("drop").classList.remove("over"); e.dataTransfer.files[0] && pick(e.dataTransfer.files[0]); };
$("sampleBtn").onclick = async () => done(await fetch("/sample?kind=csv", { method: "POST" }));
$("samplePdf").onclick = async () => done(await fetch("/sample?kind=pdf", { method: "POST" }));

// ---------- dashboard ----------
async function show() {
  const t0 = performance.now();
  $("upload").style.display = "none"; $("app").style.display = "block";
  $("delBtn").style.display = $("printBtn").style.display = "";
  const st = await (await fetch("/status")).json(); categories = st.categories;
  if (!st.chat_enabled) addMsg("a", "Chat is off because the server has no GROQ_API_KEY. The dashboard and tips still work.");
  await refresh();
  console.log("dashboard ms", Math.round(performance.now() - t0));
}
async function refresh() {
  const r = await fetch("/overview");
  if (!r.ok) return location.reload();
  data = await r.json();
  const o = data.overview;
  $("kpis").innerHTML = [["Income", inr(o.income)], ["Spent", inr(o.spend)], ["Saved", inr(o.net_savings)], ["Savings rate", (o.savings_rate_pct ?? 0) + "%"]]
    .map(([k, v]) => `<div class="kpi"><small>${k}</small><div>${v}</div></div>`).join("");
  draw("donut", "doughnut", data.categories.map((c) => c.category), data.categories.map((c) => c.amount), { plugins: { legend: { position: "right", labels: { boxWidth: 10 } } } });
  draw("trend", "bar", Object.keys(data.trend), Object.values(data.trend), { plugins: { legend: { display: false } } });
  const rl = data.insights.find((i) => i.id === "rule_50_30_20")?.evidence || { needs_pct: 0, wants_pct: 0, saved_pct: 0 };
  $("rule").innerHTML = [[rl.needs_pct, "Needs", "#5b4bdb"], [rl.wants_pct, "Wants", "#d97706"], [Math.max(rl.saved_pct, 0), "Saved", "#12805c"]]
    .map(([p, l, c]) => `<span style="width:${p}%;background:${c}">${p >= 8 ? l + " " + Math.round(p) + "%" : ""}</span>`).join("");
  $("ruleNote").textContent = "Share of income: needs / wants (incl. cash & transfers) / saved. Target 50 / 30 / 20.";
  $("tips").innerHTML = data.insights.map((i, n) => `<div class="tip sev-${i.severity}"><div>${esc(i.title)}</div><div style="text-align:right">${i.monthly_saving_estimate ? `<div class="save">${inr(i.monthly_saving_estimate)}/mo</div>` : ""}<button data-i="${n}">Ask</button></div></div>`).join("");
  $("tips").querySelectorAll("button").forEach((btn) => btn.onclick = () => { setTab("chat"); ask("Tell me more about this and what I should do: " + data.insights[btn.dataset.i].title); });
  renderWhatIf();
  const tx = await (await fetch("/transactions?limit=300")).json();
  $("tx").innerHTML = "<tr><th>Date</th><th>Merchant</th><th class=n>Amount</th><th>Category</th></tr>" + tx.map((t) =>
    `<tr><td>${t.date.slice(5)}</td><td>${esc(t.merchant)}</td><td class="n">${t.amount < 0 ? "−" : "+"}${inr(Math.abs(t.amount))}</td><td><select data-m="${esc(t.merchant)}">${categories.map((c) => `<option${c === t.category ? " selected" : ""}>${esc(c)}</option>`).join("")}</select></td></tr>`).join("");
  $("tx").querySelectorAll("select").forEach((s) => s.onchange = async () => {
    await fetch("/recategorize", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ merchant: s.dataset.m, category: s.value }) });
    refresh();
  });
}
function draw(id, type, labels, values, options) {
  charts[id]?.destroy();
  charts[id] = new Chart($(id), { type, data: { labels, datasets: [{ data: values, backgroundColor: ["#5b4bdb", "#d97706", "#12805c", "#0ea5e9", "#e11d48", "#a855f7", "#65a30d", "#f59e0b", "#64748b", "#14b8a6"] }] }, options: { responsive: true, maintainAspectRatio: false, ...options } });
}

// ---------- what-if ----------
const DISC = ["Food & Dining", "Shopping", "Subscriptions", "Transport", "Groceries", "Entertainment", "Transfers"];
let wiTimer;
function renderWhatIf() {
  const cats = data.categories.filter((c) => DISC.includes(c.category)).slice(0, 4);
  $("whatif").innerHTML = cats.map((c) => `<label>${esc(c.category)} <span class="note">(${inr(c.amount)} total)</span><input type="range" min="0" max="100" step="5" value="0" data-c="${esc(c.category)}"></label><div class="note" data-o="${esc(c.category)}">cut 0%</div>`).join("");
  $("whatif").querySelectorAll("input").forEach((r) => r.oninput = () => {
    $("whatif").querySelector(`[data-o="${r.dataset.c}"]`).textContent = `cut ${r.value}%`;
    clearTimeout(wiTimer); wiTimer = setTimeout(simulate, 250);
  });
  $("whatifOut").textContent = "";
}
async function simulate() {
  const changes = [...$("whatif").querySelectorAll("input")].filter((r) => +r.value > 0).map((r) => ({ category: r.dataset.c, cut_pct: +r.value }));
  if (!changes.length) { $("whatifOut").textContent = ""; return; }
  const s = await (await fetch("/simulate", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ changes }) })).json();
  $("whatifOut").textContent = `Save ${inr(s.monthly_saving)}/month, ${inr(s.saving_over_period)} in a year. Savings rate ${s.savings_rate_pct_before}% → ${s.savings_rate_pct_after}%.`;
}

$("gGo").onclick = async () => {
  const g = await (await fetch("/goal", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ target: +$("gAmt").value, months: +$("gMon").value }) })).json();
  $("gOut").innerHTML = `Save <b>${inr(g.monthly_needed)}</b>/month. You currently have ${inr(g.current_monthly_surplus)}/month spare, ` +
    (g.on_track ? "so you're on track. 🎯" : `a gap of <b>${inr(g.gap)}</b>/month.`) +
    (g.tips_to_close_gap.length ? "<ul>" + g.tips_to_close_gap.map((t) => `<li>${esc(t.title)} (${inr(t.monthly_saving_estimate)}/mo)</li>`).join("") + "</ul>" + (g.gap_after_tips ? `Still ${inr(g.gap_after_tips)}/month short after these.` : "That closes the gap.") : "");
};

// ---------- chat ----------
const SUGG = ["Where did most of my money go?", "Which subscriptions am I paying for?", "How can I save ₹5,000 a month?", "Which mutual fund should I buy?"];
$("sugg").innerHTML = SUGG.map((s) => `<span class="chip">${esc(s)}</span>`).join("");
$("sugg").querySelectorAll(".chip").forEach((c) => c.onclick = () => ask(c.textContent));
function addMsg(who, text) {
  const d = document.createElement("div"); d.className = "m " + who; d.textContent = text;
  $("msgs").appendChild(d); $("msgs").scrollTop = 1e9; return d;
}
async function ask(text) {
  if (!text.trim()) return;
  $("q").value = ""; addMsg("u", text);
  const box = addMsg("a", ""), chips = document.createElement("div"); box.after(chips);
  const r = await fetch("/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ message: text }) });
  if (!r.ok) { box.textContent = "Session expired. Please upload again."; return; }
  const rd = r.body.getReader(), dec = new TextDecoder(); let buf = "";
  for (;;) {
    const { value, done } = await rd.read(); if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const [ev, dt] = buf.slice(0, i).split("\n"); buf = buf.slice(i + 2);
      const d = JSON.parse(dt.slice(6)), e = ev.slice(7);
      if (e === "text") box.textContent += d;
      else if (e === "notice") box.textContent += (box.textContent ? "\n" : "") + d;
      else if (e === "receipt") {
        const c = document.createElement("span"); c.className = "chip rc"; c.textContent = "🧾 " + d.tool;
        c.onclick = () => { const p = c.nextElementSibling?.tagName === "PRE" ? c.nextElementSibling : null; if (p) return p.remove(); const pre = document.createElement("pre"); pre.textContent = JSON.stringify({ args: d.args, result: d.result }, null, 1); c.after(pre); };
        chips.appendChild(c);
      }
      $("msgs").scrollTop = 1e9;
    }
  }
}
$("send").onclick = () => ask($("q").value);
$("q").onkeydown = (e) => e.key === "Enter" && ask($("q").value);

// ---------- misc ----------
function setTab(t) { document.body.className = "t-" + (t === "chat" ? "chat" : "dash"); $("tDash").classList.toggle("primary", t !== "chat"); $("tChat").classList.toggle("primary", t === "chat"); }
$("tDash").onclick = () => setTab("dash"); $("tChat").onclick = () => setTab("chat");
$("printBtn").onclick = () => window.print();
$("delBtn").onclick = async () => { await fetch("/session", { method: "DELETE" }); location.reload(); };
fetch("/status").then((r) => r.json()).then((s) => s.has_session && show()); // resume if the session cookie is still valid

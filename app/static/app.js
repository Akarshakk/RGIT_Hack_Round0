const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const inr = (n) => "₹" + Math.round(n).toLocaleString("en-IN");
let charts = {}, categories = [], lastFile = null, data = null;

// Modern luxury palette matching peachweb
const PALETTE = [
  "#6366f1", // indigo
  "#0ea5e9", // sky blue
  "#a5edee", // cyan
  "#10b981", // emerald
  "#fbbf24", // amber
  "#f87171", // coral
  "#c084fc", // purple
  "#38bdf8", // light blue
  "#34d399", // mint
  "#fb923c"  // orange
];

// ---------- upload ----------
async function send(fd) {
  $("upErr").textContent = "";
  try {
    const r = await fetch("/upload", { method: "POST", body: fd });
    return done(r);
  } catch (err) {
    $("upErr").textContent = "Network error while uploading statement.";
  }
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
  const fd = new FormData();
  fd.append("file", f);
  fd.append("password", $("pw").value);
  send(fd);
}

function showMap(cols) {
  $("mapBox").style.display = "block";
  for (const id of ["mDate", "mNarr", "mAmt"]) {
    $(id).innerHTML = cols.map((c) => `<option>${esc(c)}</option>`).join("");
  }
}

$("mapGo").onclick = () => {
  const fd = new FormData();
  fd.append("file", lastFile);
  fd.append("password", $("pw").value);
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

if ($("heroSampleBtn")) {
  $("heroSampleBtn").onclick = async () => {
    $("appCard")?.scrollIntoView({ behavior: "smooth" });
    done(await fetch("/sample?kind=csv", { method: "POST" }));
  };
}

// ---------- dashboard ----------
async function show() {
  const t0 = performance.now();
  $("upload").style.display = "none";
  $("app").style.display = "block";
  $("delBtn").style.display = $("printBtn").style.display = "inline-flex";
  
  // Smooth scroll to app section
  $("solutions-section")?.scrollIntoView({ behavior: "smooth" });

  const st = await (await fetch("/status")).json();
  categories = st.categories;
  if (!st.chat_enabled) {
    addMsg("assistant", "Advisor note: GROQ_API_KEY is not set on this server. Chat queries will be simulated or limited, but all deterministic financial analytics, 50/30/20 checks, tips, and charts work 100%.");
  }
  await refresh();
  console.log("dashboard ms", Math.round(performance.now() - t0));
}

async function refresh() {
  const r = await fetch("/overview");
  if (!r.ok) return location.reload();
  data = await r.json();
  const o = data.overview;
  
  $("kpis").innerHTML = [
    ["Total Income", inr(o.income)],
    ["Total Spent", inr(o.spend)],
    ["Net Saved", inr(o.net_savings)],
    ["Savings Rate", (o.savings_rate_pct ?? 0) + "%"]
  ].map(([k, v]) => `
    <div class="kpi-tile">
      <small>${k}</small>
      <div>${v}</div>
    </div>
  `).join("");

  draw("donut", "doughnut", data.categories.map((c) => c.category), data.categories.map((c) => c.amount), {
    cutout: "68%",
    plugins: {
      legend: {
        position: "right",
        labels: {
          boxWidth: 10,
          color: "#f2eeee",
          font: { family: "DM Sans", size: 12 }
        }
      }
    }
  });

  draw("trend", "bar", Object.keys(data.trend), Object.values(data.trend), {
    plugins: { legend: { display: false } },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: "rgba(255, 255, 255, 0.6)", font: { family: "DM Sans", size: 11 } }
      },
      y: {
        grid: { color: "rgba(255, 255, 255, 0.05)" },
        ticks: { color: "rgba(255, 255, 255, 0.6)", font: { family: "DM Sans", size: 11 } }
      }
    }
  });

  const rl = data.insights.find((i) => i.id === "rule_50_30_20")?.evidence || { needs_pct: 0, wants_pct: 0, saved_pct: 0 };
  $("rule").innerHTML = [
    [rl.needs_pct, "Needs", "#6366f1"],
    [rl.wants_pct, "Wants", "#f59e0b"],
    [Math.max(rl.saved_pct, 0), "Saved", "#10b981"]
  ].map(([p, l, c]) => `<span style="width:${p}%;background:${c}">${p >= 8 ? l + " " + Math.round(p) + "%" : ""}</span>`).join("");
  $("ruleNote").textContent = "Share of income: Needs (50% target) / Wants (30% target) / Saved (20% target).";

  $("tips").innerHTML = data.insights.map((i, n) => `
    <div class="tip-item sev-${i.severity}">
      <div class="tip-title">${esc(i.title)}</div>
      <div class="tip-right">
        ${i.monthly_saving_estimate ? `<div class="tip-save">${inr(i.monthly_saving_estimate)}/mo</div>` : ""}
        <button class="tip-btn" data-i="${n}">Ask Advisor</button>
      </div>
    </div>
  `).join("");

  $("tips").querySelectorAll("button").forEach((btn) => {
    btn.onclick = () => {
      setTab("chat");
      ask("Tell me more about this and what action I should take: " + data.insights[btn.dataset.i].title);
    };
  });

  renderWhatIf();

  const tx = await (await fetch("/transactions?limit=300")).json();
  $("tx").innerHTML = `
    <tr>
      <th>Date</th>
      <th>Merchant / Narration</th>
      <th style="text-align:right">Amount</th>
      <th>Category</th>
    </tr>
  ` + tx.map((t) => `
    <tr>
      <td style="color: rgba(255,255,255,0.6);">${t.date.slice(5)}</td>
      <td style="font-weight: 500;">${esc(t.merchant)}</td>
      <td class="${t.amount < 0 ? 'amount-neg' : 'amount-pos'}">
        ${t.amount < 0 ? "−" : "+"}${inr(Math.abs(t.amount))}
      </td>
      <td>
        <select class="select-dark" data-m="${esc(t.merchant)}" style="padding: 4px 8px; font-size: 12px;">
          ${categories.map((c) => `<option${c === t.category ? " selected" : ""}>${esc(c)}</option>`).join("")}
        </select>
      </td>
    </tr>
  `).join("");

  $("tx").querySelectorAll("select").forEach((s) => s.onchange = async () => {
    await fetch("/recategorize", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ merchant: s.dataset.m, category: s.value })
    });
    refresh();
  });
}

function draw(id, type, labels, values, customOptions = {}) {
  charts[id]?.destroy();
  charts[id] = new Chart($(id), {
    type,
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: PALETTE,
        borderColor: "#03021b",
        borderWidth: 2,
        borderRadius: type === "bar" ? 6 : 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          backgroundColor: "#090a24",
          borderColor: "rgba(255, 255, 255, 0.15)",
          borderWidth: 1,
          titleColor: "#ffffff",
          bodyColor: "#a5edee",
          titleFont: { family: "DM Sans" },
          bodyFont: { family: "DM Sans" },
          padding: 10,
          cornerRadius: 8
        },
        ...customOptions.plugins
      },
      ...customOptions
    }
  });
}

// ---------- what-if ----------
const DISC = ["Food & Dining", "Shopping", "Subscriptions", "Transport", "Groceries", "Entertainment", "Transfers"];
let wiTimer;

function renderWhatIf() {
  const cats = data.categories.filter((c) => DISC.includes(c.category)).slice(0, 4);
  $("whatif").innerHTML = cats.map((c) => `
    <div class="slider-group">
      <label>
        <span>${esc(c.category)}</span>
        <span data-o="${esc(c.category)}" style="color: var(--accent-cyan); font-weight: 500;">0%</span>
      </label>
      <input type="range" min="0" max="100" step="5" value="0" data-c="${esc(c.category)}" />
    </div>
  `).join("");

  $("whatif").querySelectorAll("input").forEach((r) => r.oninput = () => {
    $("whatif").querySelector(`[data-o="${r.dataset.c}"]`).textContent = `cut ${r.value}%`;
    clearTimeout(wiTimer);
    wiTimer = setTimeout(simulate, 250);
  });
  $("whatifOut").style.display = "none";
}

async function simulate() {
  const changes = [...$("whatif").querySelectorAll("input")]
    .filter((r) => +r.value > 0)
    .map((r) => ({ category: r.dataset.c, cut_pct: +r.value }));

  if (!changes.length) {
    $("whatifOut").style.display = "none";
    return;
  }
  const s = await (await fetch("/simulate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ changes })
  })).json();

  $("whatifOut").style.display = "block";
  $("whatifOut").textContent = `Save ${inr(s.monthly_saving)}/month, ${inr(s.saving_over_period)} in a year. Savings rate ${s.savings_rate_pct_before}% → ${s.savings_rate_pct_after}%.`;
}

$("gGo").onclick = async () => {
  const g = await (await fetch("/goal", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ target: +$("gAmt").value, months: +$("gMon").value })
  })).json();

  $("gOut").innerHTML = `Save <b>${inr(g.monthly_needed)}</b>/month. You currently have ${inr(g.current_monthly_surplus)}/month spare, ` +
    (g.on_track ? "<span style='color: var(--accent-mint);'>so you're on track! 🎯</span>" : `<span style='color: var(--accent-coral);'>a gap of <b>${inr(g.gap)}</b>/month.</span>`) +
    (g.tips_to_close_gap.length ? "<ul style='margin-top: 8px; padding-left: 20px;'>" + g.tips_to_close_gap.map((t) => `<li>${esc(t.title)} (${inr(t.monthly_saving_estimate)}/mo)</li>`).join("") + "</ul>" + (g.gap_after_tips ? `<div style='margin-top: 6px;'>Still ${inr(g.gap_after_tips)}/month short after these.</div>` : "<div style='color: var(--accent-mint); margin-top: 6px;'>These actions close the gap completely!</div>") : "");
};

// ---------- chat ----------
const SUGG = [
  "Where did most of my money go?",
  "Which subscriptions am I paying for?",
  "How can I save ₹5,000 a month?",
  "Which mutual fund should I buy?"
];

$("sugg").innerHTML = SUGG.map((s) => `<span class="chat-chip">${esc(s)}</span>`).join("");
$("sugg").querySelectorAll(".chat-chip").forEach((c) => c.onclick = () => ask(c.textContent));

function addMsg(who, text) {
  const d = document.createElement("div");
  d.className = "chat-msg " + who;
  d.textContent = text;
  $("msgs").appendChild(d);
  $("msgs").scrollTop = 1e9;
  return d;
}

async function ask(text) {
  if (!text.trim()) return;
  $("q").value = "";
  addMsg("user", text);
  const box = addMsg("assistant", "");
  const chips = document.createElement("div");
  chips.className = "chips-wrapper";
  box.after(chips);

  const r = await fetch("/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message: text })
  });

  if (!r.ok) {
    box.textContent = "Session expired or offline. Please upload statement again.";
    return;
  }

  const rd = r.body.getReader(), dec = new TextDecoder();
  let buf = "";

  for (;;) {
    const { value, done } = await rd.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const [ev, dt] = buf.slice(0, i).split("\n");
      buf = buf.slice(i + 2);
      const d = JSON.parse(dt.slice(6)), e = ev.slice(7);

      if (e === "text") {
        box.textContent += d;
      } else if (e === "notice") {
        box.textContent += (box.textContent ? "\n" : "") + d;
      } else if (e === "receipt") {
        const c = document.createElement("span");
        c.className = "chat-chip receipt-chip";
        c.textContent = "🧾 " + d.tool;
        c.onclick = () => {
          const p = c.nextElementSibling?.tagName === "PRE" ? c.nextElementSibling : null;
          if (p) return p.remove();
          const pre = document.createElement("pre");
          pre.className = "receipt-box";
          pre.textContent = JSON.stringify({ args: d.args, result: d.result }, null, 2);
          c.after(pre);
        };
        chips.appendChild(c);
      }
      $("msgs").scrollTop = 1e9;
    }
  }
}

$("send").onclick = () => ask($("q").value);
$("q").onkeydown = (e) => e.key === "Enter" && ask($("q").value);

// ---------- misc ----------
function setTab(t) {
  document.body.className = "t-" + (t === "chat" ? "chat" : "dash");
  $("tDash")?.classList.toggle("btn-white", t !== "chat");
  $("tDash")?.classList.toggle("btn-glass", t === "chat");
  $("tChat")?.classList.toggle("btn-white", t === "chat");
  $("tChat")?.classList.toggle("btn-glass", t !== "chat");
}

$("tDash") && ($("tDash").onclick = () => setTab("dash"));
$("tChat") && ($("tChat").onclick = () => setTab("chat"));
$("printBtn").onclick = () => window.print();
$("delBtn").onclick = async () => {
  await fetch("/session", { method: "DELETE" });
  location.reload();
};

// Auto-resume if session is live
fetch("/status").then((r) => r.json()).then((s) => s.has_session && show());

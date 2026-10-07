# PS-1 execution plan: "Preheat" (phases + copy-paste prompts)

**Builds on:** `research.md` · **Written:** 7 Oct 2026 · **Hard deadlines:** registration **8 Oct 23:59 IST**, PPT PDF **10 Oct 17:00 IST** (we target 10 Oct 12:00).

Each phase below has: **Goal → Deliverables → Exit check → Prompt**. Paste the prompt into Claude Code (or Cursor) from the repo root. Do not start a phase until the previous exit check passes. Read and understand every file it writes, because the rulebook says you must be able to explain every block.

---

## 0. What deep research changed vs `research.md`

These came from checking sources and profiling the real trace on 7 Oct. They override `research.md` where they conflict.

| # | Finding | Effect on the plan |
|---|---|---|
| 1 | The Azure 2023 traces are **1 hour each** (16 Nov 2023, 18:15→19:14), columns `TIMESTAMP,ContextTokens,GeneratedTokens`. Raw URLs: `https://raw.githubusercontent.com/Azure/AzurePublicDataset/master/data/AzureLLMInferenceTrace_{conv,code}.csv` (~0.7 MB each). | Download is trivial. No week-long trace is needed. |
| 2 | **`conv` is smooth:** mean 5.5 rps, 1 s max 16, 10 s avg range 0.2–9.8, a slow ramp from minute 20 to 31. **`code` is bursty:** mean 2.6 rps, **1 s max 67, 10 s max 32.7**. | Use **`code` for the spike demo** (a real burst, no synthetic spike needed) and **`conv` for the "steady day" cost demo**. Keep the synthetic flash-spike as a third scenario. |
| 3 | Token sizes: conv generated tokens p50 129 / p95 451, context p50 1020. Code generated tokens p50 **13** / p95 90, context p50 1469. | Make **service time come from the trace's tokens** (prefill + per-token decode), not a constant. That is far more realistic and easy to defend in Q&A. |
| 4 | With per-token decode, full request latency for a 450-token answer is multiple seconds, so "p95 latency ≤ 1 s" is unachievable by design. LLM serving SLOs are normally on **TTFT (time-to-first-token)**. | **SLO = p95 TTFT ≤ 1 s.** The replica streams the first byte after prefill and the gateway measures time-to-first-byte. Also report full latency. |
| 5 | Ten replicas each holding a `transformers` model costs roughly 0.5 GB+ RAM each, which will choke a laptop. | **Replicas default to an emulated model** (sleep-based, token-driven). `MODEL=distilbert` is an opt-in flag for the "it's a real model" moment with 1–2 replicas. |
| 6 | Emulated replicas burn almost no CPU, so a literal CPU-based HPA baseline would never scale, which is an unfair strawman. | **Baseline = the exact HPA algorithm** (`ceil(current × metric/target)`, 10% tolerance, 15 s sync, 300 s scale-down stabilisation, scale-up capped at max(100 %, 4 pods) per 15 s) applied to **slot utilisation = in-flight / c** as a stand-in for CPU. This is *generous* to the baseline. Say so on the slide. |
| 7 | Replaying a 1 h trace live takes 1 h (15 min at 4×). Tuning α, β, headroom and cooldown that way is impossible in 3 days. | Add a **discrete-time simulator** that reuses the *same* policy functions. Tune in the sim in seconds, then confirm with a live run. The policy is a pure function, so sim and live share one implementation. |
| 8 | Time compression multiplies both the rate and the slopes, and the cold start stays at a real 20 s. | Replay at **4×** for live runs (~15 min). Report the compression factor next to every number. |

> **Note:** the vLLM cold-start paper ("Breaking the Ice", arXiv 2606.07362, MLSys '26) confirms startup is CPU-bound and stage-predictable. Cite it for the **20 s `WARMUP_S`** default.

---

## 1. Fixed design decisions (don't re-litigate these)

- **Only replicas run in Docker.** The gateway, controller, loadgen and dashboard run on the host (`uvicorn` / `python`). The controller starts containers with published ports `localhost:9001..`. No compose and no k8s. *(Add compose only if a judge asks for "one command"; a `make up` covers that.)*
- **One image** (`preheat-replica`). Config comes through env vars: `C` (slots, default 8), `WARMUP_S` (20), `PREFILL_MS_PER_1K` (60), `DECODE_MS_PER_TOK` (12), `MODEL` (`emulated` | `distilbert`).
- **Control plane:** the controller registers or drains replicas on the gateway over HTTP (`POST /replicas`, `DELETE /replicas/{id}`). The gateway polls `/health` and routes only to ready replicas. Scale-down = drain → wait for in-flight 0 → `container.stop()`.
- **Policy is pure** (`policy.py`): `preheat_decide(state, m) -> (n, reason)` and `hpa_decide(state, m) -> (n, reason)`. No I/O. It is used by both `controller.py` and `sim.py`.
- **Priority:** the loadgen tags 20 % of requests `X-Priority: premium`. At the budget cap, if the queue is above the threshold, free requests get an immediate `429` + `Retry-After`.
- **Metrics windows:** 10 s sliding windows for RPS, p95 TTFT and p95 latency, plus instantaneous queue and in-flight values.

### Repo layout (fewest files)

```
preheat/
  replica.py      # FastAPI model server (emulated | distilbert), streaming
  Dockerfile      # replica image only
  gateway.py      # proxy, least-busy routing, queue, admission, /metrics, /replicas
  policy.py       # Holt, preheat_decide, hpa_decide (pure)
  controller.py   # loop: GET /metrics → policy → docker SDK → gateway register/drain
  sim.py          # same policy, simulated replicas/queue, trace in seconds
  loadgen.py      # replays Azure trace (compress, scale, priority mix) → requests.csv
  report.py       # requests.csv + decisions.csv → table + PNG charts
  dashboard.html  # Chart.js, polls gateway /metrics + controller /state
  test_policy.py  # assert-based checks for policy.py
  requirements.txt
data/             # downloaded traces (gitignored)
runs/             # outputs per run (gitignored)
```

---

## 2. Timeline

| When | Phase | Owner (A = backend, B = UI/pitch) |
|---|---|---|
| **Tue 7 Oct, tonight** | P0 setup · P1 replica | A: P1 · B: **team and registration blocker**, organiser questions |
| **Wed 8 Oct** | P2 gateway · P3 policy + sim · P4 loadgen | A: P2→P3 · B: P4, then dashboard skeleton · **registration confirmed by 20:00** |
| **Thu 9 Oct AM** | P5 controller (live) · P6 dashboard | A: P5 · B: P6 |
| **Thu 9 Oct PM** | P7 benchmark + charts | A+B: runs, table, screenshots |
| **Fri 10 Oct, by 12:00** | P8 PPT + README → **submit PDF** | B: slides · A: README, repo tidy |
| **11 Oct** (if shortlisted) | P9 finale drill | both |

**Cut line if behind:** drop the live controller (P5) and present **sim results + one live demo of the replica/gateway**. The sim uses the exact policy code, so the numbers stay honest. Never cut P7, because slide 5's table is what gets a team shortlisted.

---

## P0 · Setup (30 min)

**Goal:** tools installed, traces local, skeleton committed.
**Exit check:** `docker run hello-world` works; `wc -l data/*.csv` shows 19367 (conv) and 8820 (code) lines; `python -c "import fastapi, httpx, docker"` succeeds.

```text
PROMPT P0
Set up the repo for project "Preheat" (see PLAN.md section 1 for the layout; follow it exactly, fewest files).
1. Create preheat/requirements.txt with: fastapi, uvicorn[standard], httpx, docker, matplotlib. Nothing else yet.
2. Create a .gitignore with data/, runs/, __pycache__/, .venv/.
3. Write a tiny Makefile with targets: venv (python3.11 -m venv .venv && pip install -r preheat/requirements.txt),
   data (curl the two Azure CSVs from
   https://raw.githubusercontent.com/Azure/AzurePublicDataset/master/data/AzureLLMInferenceTrace_conv.csv and _code.csv into data/).
4. Run `make venv data` and show `wc -l data/*.csv`.
Do not create any other files. Do not add a framework, a src/ layout, or config files.
```

---

## P1 · Replica (model server) (~2 h)

**Goal:** one container = one "GPU replica" with limited slots, a cold start, and token-driven streaming.
**Exit check:**
- `docker run -p 9001:8000 -e WARMUP_S=5 preheat-replica`, then `/health` returns 503 for about 5 s and 200 after that.
- `curl -N -XPOST localhost:9001/infer -d '{"ctx":1000,"gen":100}'` prints the first chunk after about 60 ms and finishes after about 1.3 s.
- Firing 16 concurrent requests at `C=8` makes the second 8 wait (visible in timings).

```text
PROMPT P1
Write preheat/replica.py and preheat/Dockerfile.

replica.py (FastAPI, single file, <80 lines):
- Env config: C (int, default 8), WARMUP_S (float, 20), PREFILL_MS_PER_1K (float, 60), DECODE_MS_PER_TOK (float, 12),
  MODEL ("emulated" default | "distilbert").
- On startup: start a background task that sleeps WARMUP_S (and if MODEL=distilbert, loads
  transformers pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")), then sets ready=True.
- GET /health -> 200 {"ready":true,"inflight":n,"c":C} when ready, else 503.
- POST /infer body {"ctx":int,"gen":int,"text":str optional}:
  - acquire an asyncio.Semaphore(C) (this emulates limited GPU batch slots),
  - sleep ctx/1000*PREFILL_MS_PER_1K ms (prefill), then yield the first chunk b"[first]\n" (this is time-to-first-token),
  - if MODEL=distilbert and text given, run the pipeline in a thread (asyncio.to_thread) and include the label,
  - sleep gen*DECODE_MS_PER_TOK ms (decode), yield b"[done]\n", release the semaphore.
  - Return a StreamingResponse. Count in-flight requests.
- Comment at top: why semaphore = GPU slots, why WARMUP_S defaults to 20 s (cite "Breaking the Ice: Analyzing
  Cold Start Latency in vLLM", arXiv 2606.07362, ~20 s for a 3B model on H100).

Dockerfile: python:3.11-slim, install fastapi uvicorn (and transformers+torch CPU ONLY behind a build arg
WITH_MODEL=0 default, so the default image stays small), CMD uvicorn replica:app --host 0.0.0.0 --port 8000.

Then build it as preheat-replica, run it with WARMUP_S=5, and demonstrate the three exit checks from PLAN.md P1
with curl/time, showing output. Fix anything that fails.
```

---

## P2 · Gateway (~3 h)

**Goal:** a single entry point that routes, queues, sheds load and measures.
**Exit check:** with two replicas registered manually, a 30 s burst shows `/metrics` queue > 0 when slots are full; p95 TTFT rises with queueing; draining a replica stops new routing to it while its in-flight requests finish.

```text
PROMPT P2
Write preheat/gateway.py (FastAPI, single file). Read preheat/replica.py first; the gateway proxies to it.

State: replicas = {id: {url, ready, inflight, c, draining}}, one asyncio.Condition for "a slot freed".
Endpoints:
- POST /replicas {id,url}: register (not ready yet). A background task polls each replica's /health every 0.5 s
  and sets ready/c.
- DELETE /replicas/{id}: mark draining (no new requests). GET /replicas/{id} returns inflight so the controller
  can wait for 0 before stopping the container.
- POST /infer: the client sends {"ctx","gen","text"?} plus header X-Priority: premium|free.
  1. Admission: if app.state.at_cap is True and queue_len >= QUEUE_SHED (env, default 2*total_slots) and
     priority == free → immediately return 429 with Retry-After: 2. Count it as "shed".
  2. Pick the ready, non-draining replica with the lowest inflight/c that has a free slot. If none, wait on the
     condition (this is the queue; count queue_len; premium waiters are woken first: keep two FIFO lists).
  3. Stream-proxy with httpx.AsyncClient (one shared client, no timeout on read). Record
     t_arrive, t_first_byte, t_done → ttft = first_byte - arrive, latency = done - arrive. Release the slot
     and notify.
- GET /metrics: {ts, rps_10s, arrivals_10s, p95_ttft_10s, p95_latency_10s, queue, inflight, slots_total,
  replicas_ready, replicas_starting, shed_10s}. Use a deque of (ts, ttft, latency) trimmed to 10 s, and
  statistics.quantiles for p95 (guard against <2 samples).
- POST /control {at_cap: bool}: the controller tells the gateway whether the budget cap is binding.
- GET / serves preheat/dashboard.html if it exists.

Keep it boring: no classes beyond what's needed, no external queue, no Redis.
Then verify: start 2 replicas (docker run, ports 9001/9002, WARMUP_S=3, C=2), register them with curl, fire 20
concurrent requests with a tiny inline python/asyncio snippet, and print /metrics during and after. Show that
queue > 0 occurred, then drain one replica and show that new requests only go to the other.
```

---

## P3 · Policy + simulator (~3 h). **This is the brain; give it the most care.**

**Goal:** a pure scaling policy (Preheat and HPA baseline) plus a simulator that runs the full 1 h trace in seconds.
**Exit check:** `python preheat/test_policy.py` passes; `python preheat/sim.py --trace code --scaler hpa` and `--scaler preheat` each print a results row in under 10 s.

```text
PROMPT P3
Write preheat/policy.py, preheat/sim.py and preheat/test_policy.py. Read PLAN.md sections 0 and 1 first.

policy.py (pure functions, no I/O, stdlib only):
- class Holt: alpha=0.5, beta=0.3; update(y) -> level; forecast(h_steps).
- capacity_per_replica(c, mean_service_s) = c / mean_service_s  (Little's Law: mu = c / s).
- preheat_decide(st, m, cfg) -> (n, reason_str). Inputs: m = gateway metrics dict; st = mutable dict carrying
  holt, current, starting, last_up_ts, low_since_ts, and a running mean_service_s. cfg: tick_s=2,
  cold_start_s=20, headroom=0.7, min_replicas=1, budget_inr_hr, price_inr_hr, scale_down_after_s=60,
  slo_ttft_s=1.0, queue_panic (default = slots of 1 replica).
  1. Forecast lambda_hat = max(current rps, holt.forecast(cold_start_s / tick_s)).
  2. need = ceil(lambda_hat / (mu * headroom)).
  3. Reactive safety net: if queue > queue_panic or p95_ttft > slo_ttft_s, need = max(need, current+starting+ceil(queue/c)).
  4. Hysteresis: scale up immediately; scale down by at most 1 and only if need < current for scale_down_after_s
     continuously; never below min_replicas.
  5. Cap: n = min(n, floor(budget/price)); at_cap = (uncapped need > cap).
  Return a human sentence, e.g. "2→4 · forecast 31.0 rps in 20s · mu 4.1 rps/replica @70% · queue 6".
- hpa_decide(st, m, cfg): the Kubernetes HPA algorithm (docs: kubernetes.io/docs/concepts/workloads/autoscaling/
  horizontal-pod-autoscale): only acts every 15 s; util = inflight / slots_ready (CPU stand-in), target 0.7;
  desired = ceil(ready * util/target); skip if |util/target - 1| <= 0.1; scale-up limit per 15 s =
  max(2*current, current+4); scale-down = max recommendation over the last 300 s (stabilisation window); same
  budget cap. Add a comment that using slot-utilisation instead of CPU is generous to HPA.

sim.py (discrete-event, stdlib only, reuses policy.py unchanged):
- Load data/AzureLLMInferenceTrace_{conv,code}.csv, or --trace spike (synthetic: base 5 rps, 10x for 60 s at
  minute 5). Args: --compress (default 4), --scaler hpa|preheat, --c 8, --warmup 20, plus cfg overrides
  (--alpha --beta --headroom --budget --price).
- Simulate replicas with C slots, cold start, FIFO queue with premium-first, per-request service =
  prefill + decode from tokens (same formula as replica.py), 429 shedding at the cap.
- Each request → (arrive, ttft, latency, priority, shed); each tick → (t, rps, forecast, replicas_ready,
  starting, queue, p95_ttft, reason). Write runs/sim_<trace>_<scaler>/{requests.csv,ticks.csv}.
- Print one row: SLO attainment (% of served requests with TTFT <= 1 s), peak 10 s p95 TTFT, replica-minutes,
  INR cost, cold starts, shed count.

test_policy.py: plain asserts, run with python. Holt converges on a ramp; preheat scales up before a ramp
arrives (within cold_start); no scale-down within 60 s of a dip; never exceeds the budget cap; hpa respects the
300 s window and the 15 s period. Print "ok".

Run the tests, then run sim for both scalers on both traces and on spike, and show the 6 result rows. If preheat
does not beat hpa on SLO attainment for code and spike, investigate and tell me why before tuning anything.
Don't fudge: report the numbers as they come out.
```

**Tuning follow-up (only after P3 passes):**

```text
PROMPT P3b
Using sim.py, grid-search alpha in {0.3,0.5,0.7}, beta in {0.1,0.3,0.5}, headroom in {0.6,0.7,0.8} for preheat
on the code trace (compress 4). Optimise: max SLO attainment subject to replica-minutes <= 1.2x hpa's. Print the
top 5 configs. Then check the winner on conv and spike to confirm it isn't overfit to code. Write the chosen
defaults into policy.py with a one-line comment citing this grid search. Keep the search script out of the repo
(scratch only), or as a <25 line --grid flag in sim.py if it's that small.
```

---

## P4 · Load generator (~1.5 h, can run in parallel with P3, owner B)

**Goal:** replay the real trace against the live gateway with exact timing.
**Exit check:** `python preheat/loadgen.py --trace code --compress 4 --minutes 2` produces `runs/<name>/requests.csv` where the measured arrival rate matches the trace (±5 %).

```text
PROMPT P4
Write preheat/loadgen.py (asyncio + httpx, single file).
- Args: --trace conv|code|spike, --compress 4, --scale 1.0 (rate multiplier: duplicate or thin arrivals),
  --minutes N (cut the trace), --premium 0.2, --gateway http://localhost:8080, --out runs/<name>.
- Parse TIMESTAMP (truncate to microseconds for datetime.fromisoformat), convert to offsets / compress. Spike =
  same synthetic definition as sim.py (import it from sim.py, don't duplicate).
- Schedule each request at its offset using loop.time() (never cumulative sleeps, because drift adds up). Fire
  without waiting; one shared AsyncClient with high connection limits.
- Body {"ctx","gen"} from the trace row; header X-Priority random by --premium with a fixed seed.
- Read the stream: record arrive, first_byte, done, status (429 = shed). Write requests.csv with the same columns
  as sim.py's requests.csv so report.py reads both.
Verify with a 2-minute run against the gateway + 2 replicas and print planned vs actual arrival rate.
```

---

## P5 · Live controller (~2.5 h)

**Goal:** a real control loop driving real containers through the same policy.
**Exit check:** starting from 1 replica, a `code` replay shows containers appearing in `docker ps` *before* the burst with Preheat, and after it with HPA. `runs/<name>/decisions.csv` has one line per tick.

```text
PROMPT P5
Write preheat/controller.py. Read gateway.py, policy.py and replica.py first and reuse them; do not
reimplement policy logic.
- Args: --scaler hpa|preheat, --gateway URL, cfg overrides identical to sim.py (share the argparse helper by
  importing it from sim.py, or move it into policy.py if cleaner).
- On start: remove leftover containers labelled preheat=1, start min_replicas.
- Every tick_s: GET gateway /metrics → policy → reconcile:
  - scale up: docker.from_env().containers.run("preheat-replica", detach=True, labels={"preheat":"1"},
    ports={"8000/tcp": free_port}, environment=...), then POST /replicas to the gateway.
  - scale down: pick the newest ready replica, DELETE /replicas/{id}, background-wait until inflight==0
    (max 30 s), then container.stop(timeout=2) + remove.
  - POST /control {at_cap}.
- Append each tick to runs/<name>/decisions.csv (same columns as sim ticks.csv) and print the reason sentence when
  n changes.
- Expose GET /state on port 8081 (tiny FastAPI app in the same process, or a stdlib http.server thread, whichever
  is shorter) returning the last 300 ticks for the dashboard.
- Fail-static: if the gateway is unreachable, log and do nothing (never scale to zero on missing data).
- Ctrl-C: stop and remove all preheat containers.
Verify: run gateway + controller (--scaler preheat) + loadgen --trace spike --minutes 4, show docker ps snapshots
and the decision lines. Then the same with --scaler hpa.
```

---

## P6 · Dashboard (~3 h, owner B; this earns the 10 UX marks)

**Goal:** one screen a judge understands in 5 seconds.
**Exit check:** opening `http://localhost:8080/` during a replay shows the charts moving live; there is no build step.

```text
PROMPT P6
Write preheat/dashboard.html: a single file, Chart.js from cdnjs, no build step, no framework. It is served by the
gateway at GET /. Poll gateway /metrics and controller http://localhost:8081/state every 1 s (enable CORS on both
with FastAPI's CORSMiddleware if needed).
Layout (dark theme, large fonts, readable on a projector):
- Top row KPI tiles: replicas ready/starting, rps, p95 TTFT vs the 1 s SLO (green/red), queue, ₹/hour now,
  ₹ spent this run, requests shed.
- Chart 1: actual rps vs forecast rps (dashed): this shows the "we saw it coming" moment.
- Chart 2: replicas ready (solid) + starting (hatched/lighter) as a step line.
- Chart 3: p95 TTFT with a horizontal SLO line at 1 s.
- Right panel: live decision log (newest on top, monospace), each the controller's reason sentence.
- A scaler badge: "PREHEAT" or "BASELINE (HPA)".
Keep the last 5 minutes on the charts. Must work at 1366x768. Verify by running a short spike replay and
describe what is on screen (or screenshot it).
```

---

## P7 · Benchmark + charts (~3 h). **Slide 5 depends on this.**

**Goal:** honest, reproducible numbers and two charts for the PPT.
**Exit check:** `runs/RESULTS.md` holds the table for 3 scenarios × 2 scalers (sim) and 1 scenario × 2 scalers (live), plus PNGs.

```text
PROMPT P7
Write preheat/report.py: read one or more run dirs (requests.csv + ticks.csv/decisions.csv) and print a markdown
table: scenario, scaler, mode (sim/live), compress, SLO attainment (% served with TTFT<=1s), peak 10s p95 TTFT,
p95 full latency, replica-minutes, ₹ cost (replica-minutes/60 * price), cold starts, shed (free / premium).
Also save, per scenario, one PNG with 3 stacked panels (rps+forecast, replicas, p95 TTFT+SLO line) overlaying hpa
vs preheat (matplotlib, 1600x900, large fonts).

Then run the full matrix:
- sim: {conv, code, spike} x {hpa, preheat}, compress 4, default price ₹ PRICE (I'll tell you; default 250/hr),
  budget = 12 replicas' worth.
- live: code trace, first 10 trace-minutes, compress 4, {hpa, preheat}; restart all containers between runs.
Write runs/RESULTS.md with the tables, the PNG paths, every parameter used, and a "caveats" section (emulated GPU,
slot-utilisation instead of CPU for HPA, compression factor, laptop, single run vs n runs). Report sim vs live
differences honestly. If any result is worse for preheat (e.g. more replica-minutes), keep it in and explain the
trade-off in one line.
```

---

## P8 · PPT + README + submit (Fri by 12:00)

Follow `research.md` §7 slide-by-slide. Additions from this plan:

- **Slide 2:** add one sentence about the real trace: "Azure's production code-completion trace spikes ~25× above its mean within seconds (1 s peak 67 rps vs mean 2.6)." This is our own measurement of a public dataset, so say that.
- **Slide 4:** the formula box shows `need = ceil(λ̂(t+cold_start) / (μ·0.7))`, `μ = c / s̄` (Little's Law), plus Holt in two lines. Note "SLO on TTFT, as is standard in LLM serving".
- **Slide 5:** the P7 table (sim *and* live rows, compression stated) plus the code-trace PNG.
- **Slide 6:** dashboard screenshot during the spike, a sequence diagram of one scale-up, and references (research.md §10 plus the Azure trace).

```text
PROMPT P8
Write README.md for the repo: one-paragraph pitch; architecture diagram (ASCII from research.md 5.3, updated to
match what we actually built); "Run in 3 commands" (make venv data; docker build; make demo) — add a `demo`
Makefile target that starts gateway, controller and a spike replay; the policy explained in 10 lines with the
formulas; the results table copied from runs/RESULTS.md; caveats; tech stack; references. Only describe features
that exist in the code. Read every file under preheat/ before writing. Then list anything in research.md §5.1
that we did NOT build, so the PPT doesn't claim it.
```

**Submission checklist:** 6 slides max · "Important Pointers" slide deleted · exported to **PDF** ≤ 50 MB · every number traces back to `runs/RESULTS.md` · uploaded on Unstop **by 12:00** · confirmation screenshot saved.

---

## P9 · Finale drill (11 Oct, only if shortlisted)

The rules require fresh code in the 24 h, so this week's repo **cannot** be reused. Practise instead.

1. **Timed rebuild (3 h cap):** in an empty folder, rebuild replica → gateway → policy → controller from memory plus the prompts above. Note where you got stuck. That is your on-site risk list.
2. **Map-any-PS drill:** for each of 3 made-up PSs (e.g. "rate-limited API fleet", "video transcoding queue", "multi-region failover"), write the gateway → metrics → controller → dashboard mapping on one page.
3. **Trial & Reward (hour 12) playbook:** "spike / replication / cost cap" → Preheat's lookahead + reactive net, a replica min-pool, and budget cap + priority shedding. Rehearse explaining each in 30 s.
4. **Convergence (hour 6) playbook:** "Send us your model's `/predict` and its cold-start time. We wrap it as the replica image (`MODEL=yours`), and your model now survives a spike." Agree the REST contract in the first 15 min.
5. **Q&A drill:** answer research.md §8 out loud, plus: *"Why TTFT not latency?"*, *"Why is your HPA baseline fair?"*, *"Sim vs live: why do they differ?"*, *"What does compression do to your results?"*

---

## Risk register

| Risk | Trigger | Response |
|---|---|---|
| Team still 2 people on 8 Oct evening | No organiser reply by 18:00 | Recruit anyone willing to do the PPT/pitch. Don't risk disqualification. |
| Docker Desktop is slow or flaky on a laptop | Container start > 5 s on its own | Lower `WARMUP_S` noise: measure the real container start and subtract it from `WARMUP_S`. Cut the live runs to sim + a short live demo. |
| Preheat doesn't beat HPA | P3 results | Diagnose first (forecast horizon? mu estimate? headroom?). If it is still a wash on `conv`, present that honestly: "on smooth traffic both are fine; on bursts we win". |
| Loadgen saturates the laptop, not the system | Planned vs actual rate off > 5 % | Lower `--compress` to 2, or run the loadgen on the second laptop. |
| Behind schedule on Thu evening | P5/P6 not done | Use the cut line in §2. |

---

## Sources added beyond research.md

- Azure LLM Inference Dataset 2023 (schema, files): https://github.com/Azure/AzurePublicDataset/blob/master/AzureLLMInferenceDataset2023.md
- Kubernetes HPA algorithm and defaults: https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/
- "Breaking the Ice: Analyzing Cold Start Latency in vLLM" (MLSys '26): https://arxiv.org/abs/2606.07362
- Trace statistics in §0: our own profiling of the two CSVs on 7 Oct 2026 (reproduce with `sim.py` or a 10-line pandas/stdlib script).

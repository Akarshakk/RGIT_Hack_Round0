# PPT material: "Preheat" (PS-1, Intelligent Auto-Scaling for AI Workloads)

**Living document.** Update it as the build progresses. The PPT is made from this file.
**Sources of truth:** `research.md` (why), `PLAN.md` (how), `runs/RESULTS.md` (numbers, once P7 is done).

### How to keep this file updated
- Every number on a slide must come from a cited source or from `runs/RESULTS.md`. **Never type a guessed number.**
- `⏳ TODO` = fill in once that phase is done. `🟡 Planned` / `🟢 Built` / `🔴 Cut` = feature status. Update the status as you go.
- Only features marked 🟢 Built go on the final slides as "what we built". 🟡 items go under "Future scope" or get cut.
- Add a line to the change log at the bottom whenever you edit.

---

## Slide 1 · Team details (template slide)

- **Team name:** ⏳ TODO
- **Team ID:** ⏳ TODO (from Unstop)
- **Team leader:** ⏳ TODO
- **Members:** Lakshita, Akarshak, ⏳ TODO (3rd/4th member)
- **Domain:** Cloud Computing & Distributed Systems
- **Problem statement:** PS-1 · Intelligent Auto-Scaling for AI Workloads
- **Project name:** Preheat
- **Tagline:** *"Start the servers before the rush, not after."*

---

## Slide 2 · Problem Analysis

### The problem in one line
AI apps run on very expensive GPU servers, and their traffic jumps up and down. **Too many servers waste money; too few make users wait.**

### Why it's hard (key points for the slide)
1. **AI traffic is spiky.** Real Microsoft Azure production data shows the code-assistant trace jumping to **67 requests in one second** when its average is **2.6 per second** (about **25× the average**). *(Our own measurement of Azure's public trace.)*
2. **AI servers are slow to start.** A new AI server needs about **20 seconds** before it can answer, because it has to load the model into GPU memory. A normal web server starts in about 1 second. *(Source: "Breaking the Ice", MLSys 2026.)*
3. **Standard autoscalers watch the wrong thing.** Tools like Kubernetes HPA scale on **CPU usage** by default. For AI, the GPU does the work, so the CPU can look calm while requests pile up.
4. **Standard autoscalers react too late.** They add servers *after* things are already slow. With a 20 s start time, users eat those 20 s of waiting every time.
5. **They're slow to remove servers too.** Kubernetes waits **5 minutes (300 s)** by default before scaling down, so you keep paying for idle GPUs.
6. **GPUs are often idle.** Studies of real clusters keep finding low GPU use (one academic study found most GPUs below 60 % use). Idle GPU = money on fire.

### Who suffers
- **Users:** slow or failed answers during a spike.
- **Startups, college teams and small companies:** they serve AI features on a tight budget and can't afford idle GPUs *or* lost users.

### Visual idea for this slide
A simple line chart: traffic spike (line going up) → normal autoscaler's servers going up **20 s too late** (step line lagging) → a red "users waiting" zone in between.

---

## Slide 3 · Proposed Solution & Key Features

### One line
**Preheat** is a smart autoscaler for AI models. It **predicts** traffic, **starts servers before the spike arrives**, **never crosses your budget**, and **explains every decision in plain English**.

### Key features (icon + one line each)

| # | Feature | In simple words | Status |
|---|---|---|---|
| 1 | **Right signals** | Watches the request queue and waiting time, not CPU | 🟡 Planned |
| 2 | **Look-ahead scaling** | Predicts traffic 20 s ahead (one start-up time) and starts servers early | 🟡 Planned |
| 3 | **Safety net** | If a sudden spike beats the prediction, it scales up instantly | 🟡 Planned |
| 4 | **No flip-flopping** | Adds servers fast, removes them slowly (only after 60 s of quiet) and always keeps 1 warm | 🟡 Planned |
| 5 | **Budget cap** | You set ₹/hour and it never goes over | 🟡 Planned |
| 6 | **Priority under pressure** | At the budget limit, premium users are always served and free users get an instant "try again in 2 s" instead of a 30 s hang | 🟡 Planned |
| 7 | **Explains itself** | Every decision is logged as a sentence, e.g. *"2→4 servers · expecting 31 req/s in 20 s · queue 6"* | 🟡 Planned |
| 8 | **Live dashboard** | Traffic vs prediction, servers, waiting time vs target, ₹ spent, decision log | 🟡 Planned |
| 9 | **Fair benchmark** | Replays real Azure traffic against Preheat *and* a Kubernetes-style autoscaler, side by side | 🟡 Planned |

### Visual idea for this slide
Feature icons in a 3×3 grid + a small dashboard mock (see wireframe in Slide 6 material).

---

## Slide 4 · Technical Approach & Innovation

### How it works (4 parts)
1. **AI server (replica):** a container that runs the model. It can handle a fixed number of requests at once (like GPU slots) and takes ~20 s to start (like a real GPU server).
2. **Gateway:** the front door. It sends each request to the least busy server, makes requests wait in line when all are busy, and measures everything.
3. **Controller (the brain):** every 2 seconds it **measures → predicts → decides → acts**, starting or stopping containers.
4. **Dashboard:** shows it all live.

### The maths (one box on the slide)
- **Prediction (Holt's smoothing):** track the current traffic *level* and its *trend*. Forecast = level + trend × (seconds ahead). Simple, needs no training data, and fits on a whiteboard.
- **How many servers (Little's Law):** one server handles `μ = slots ÷ avg. time per request` requests/sec.
  `servers needed = ceil( predicted traffic ÷ (μ × 0.7) )`. The 0.7 keeps 30 % spare room, because queues explode near 100 %.
- **Budget:** `max servers = floor( budget ₹/hr ÷ price per server ₹/hr )`.

### Target we measure: time to first token (TTFT)
We promise **95 % of users see the first word of the answer within 1 second** (p95 TTFT ≤ 1 s). This is the standard way LLM services are measured, because long answers naturally take longer to finish.

### What's new / USP (3 bullets)
1. **Start-up-time-aware look-ahead.** It predicts exactly as far ahead as a server takes to start.
2. **Budget is a hard rule, not a wish.** When the budget runs out it degrades gracefully with priority admission.
3. **Explainable.** Every scaling decision comes with a plain-English reason.

*Honesty line (say it if asked):* predictive autoscaling has been studied in research (e.g. MArk, USENIX ATC 2019). Our contribution is a **simple, explainable, budget-first** version, **measured on real production traffic**.

### Tech stack (one row of logos)
Python 3.11 · FastAPI · Docker (+ Docker Python SDK) · httpx · Chart.js · matplotlib · Microsoft Azure public LLM trace

### Honest note on hardware (small footnote)
No GPUs on laptops, so each server **emulates** a GPU's two properties that matter: limited parallel slots and a ~20 s start-up (taken from a published measurement). The scaling logic is the same either way; a real GPU server is a one-line config change.

---

## Slide 5 · Impact & Future Scope

### Results (THE most important slide; fill only with measured numbers)
Same real traffic replayed against both autoscalers. Time compressed 4× ⏳ TODO confirm.

| Scenario | Autoscaler | Users within target (TTFT ≤ 1 s) | Worst waiting time (p95) | Server-minutes (cost) | ₹ cost | Cold starts | Requests turned away |
|---|---|---|---|---|---|---|---|
| Azure code trace (bursty) | Kubernetes-style | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| Azure code trace (bursty) | **Preheat** | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| Azure chat trace (smooth) | Kubernetes-style | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| Azure chat trace (smooth) | **Preheat** | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| Flash spike (10× for 60 s) | Kubernetes-style | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| Flash spike (10× for 60 s) | **Preheat** | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |

**Headline sentence (fill after results):** "On real bursty traffic, Preheat kept ⏳ % of users within target vs ⏳ % for a Kubernetes-style autoscaler, at ⏳ the cost."
*If Preheat costs more on some row, keep it and say why (e.g. "spends 8 % more to keep users happy"). Judges trust honest trade-offs.*

### Who benefits
- **Users:** fast answers even during spikes.
- **Companies:** pay for GPUs only when needed, with a hard ₹ ceiling.
- **Engineers:** see *why* the system scaled, so there's no black box.

### Scalability (how it grows)
- The same controller can drive a **Kubernetes Deployment** or cloud VMs instead of Docker.
- Multiple gateways behind a cloud load balancer, and 2 controllers with leader election (removes the single point of failure).

### Future scope
- Kubernetes operator (production deployment)
- Real GPU metrics (NVIDIA DCGM)
- **Model cascading:** send low-priority users to a smaller, cheaper model instead of turning them away
- Spot / discounted-instance support for cheaper capacity
- Packing several models on one GPU
- Learning each server's real capacity live instead of configuring it

---

## Slide 6 · Supporting Information

### 6.1 Workflow (what happens to one request)
```
User request
   │
   ▼
Gateway ──► Is a server free? ── yes ──► send to least-busy server ──► answer streams back
   │                  │
   │                  no
   │                  ▼
   │          At budget limit AND line too long?
   │             ├─ yes + free user    ──► instant "429: try again in 2 s"
   │             └─ otherwise          ──► wait in line (premium users first)
   │
   └─► records: arrival rate, line length, time to first word, total time
```

### 6.2 Workflow (one controller tick, every 2 s)
```
1. MEASURE   read gateway metrics (traffic, queue, waiting time)
2. PREDICT   Holt forecast: traffic 20 s from now
3. DECIDE    servers needed = ceil(forecast ÷ (capacity × 0.7))
             + safety net if queue/wait already too high
             + slow scale-down (60 s of quiet) + min 1 warm
             + cap at budget
4. ACT       start/stop containers, tell the gateway
5. EXPLAIN   write one-line reason to the decision log
```

### 6.3 Architecture
```
                 ┌──────────────┐
 Load generator  │   GATEWAY    │  ← tracks traffic, queue, waiting time
 (real Azure ───►│ (FastAPI)    │──────────────┐
  trace replay)  │ routing +    │              │ metrics every 2 s
                 │ queue        │              ▼
                 └──────┬───────┘       ┌──────────────┐     ┌─────────────────┐
                        │ least-busy    │  CONTROLLER  │────►│  DASHBOARD      │
                        ▼ routing       │  measure →   │     │ servers, traffic│
        ┌───────────┬───────────┐       │  predict →   │     │ wait vs target, │
        │ AI server │ AI server │ ...   │  decide →    │     │ ₹ spent, log    │
        │ (Docker)  │ (Docker)  │◄──────│  act         │     └─────────────────┘
        └───────────┴───────────┘ start/└──────────────┘
                                   stop
```
⏳ TODO: redraw as a clean diagram (draw.io / Excalidraw) for the slide.

### 6.4 Sequence: one scale-up decision
```
Load gen     Gateway        Controller         Docker        New server
   │  traffic ↑ │                │                 │               │
   │──────────►│  metrics       │                 │               │
   │           │──────────────►│ forecast says    │               │
   │           │               │ "need 4 in 20 s" │               │
   │           │               │──start x2──────►│──────────────►│ warming (20 s)
   │           │◄──register────│                 │               │
   │           │◄──────────────────────────── health: ready ───────│
   │  spike    │──route────────────────────────────────────────►│ already warm ✅
```

### 6.5 Dashboard wireframe
```
┌──────────────────────────────────────────────────────────────────────────┐
│ PREHEAT ● live      Scaler: [PREHEAT]                                    │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬────────┤
│ Servers  │ Traffic  │ p95 TTFT │ Queue    │ ₹/hour   │ ₹ spent  │ Shed   │
│ 4 (+2 ⏳)│ 31 req/s │ 0.42 s ✅│ 3        │ ₹1,000   │ ₹84      │ 0      │
├──────────┴──────────┴──────────┴──────────┴──────┬───┴──────────┴────────┤
│ Traffic: actual ── vs forecast - - -              │ DECISION LOG          │
│                                                   │ 14:02:10 2→4 · fcst   │
├───────────────────────────────────────────────────┤  31 rps in 20s · q 6  │
│ Servers: ready ▇ / starting ░ (step chart)        │ 14:01:48 hold · 2     │
├───────────────────────────────────────────────────┤ 14:00:12 3→2 · quiet  │
│ p95 TTFT ── with SLO line at 1 s ─ ─ ─            │  60 s                 │
└───────────────────────────────────────────────────┴───────────────────────┘
```
⏳ TODO: replace with a real screenshot taken during a spike (after P6).

### 6.6 Research highlights (small text box)
- AI server cold start ≈ **20 s** (3B model, H100, vLLM): "Breaking the Ice", MLSys 2026.
- Kubernetes HPA defaults: checks every **15 s**, waits **300 s** before scaling down.
- Ray Serve defaults: **30 s** to scale up, **600 s** to scale down.
- Faster model loading (ServerlessLLM, OSDI 2024) shows how big the cold-start problem is.
- Predictive + SLO-aware ML serving (MArk, USENIX ATC 2019) is related work we build on.
- Real traffic: Azure LLM inference trace (conversation and code), from a Microsoft production service.

### 6.7 References
1. Breaking the Ice: Analyzing Cold Start Latency in vLLM (MLSys '26): https://arxiv.org/abs/2606.07362
2. Kubernetes Horizontal Pod Autoscaler docs: https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/
3. Ray Serve advanced autoscaling: https://docs.ray.io/en/latest/serve/advanced-guides/advanced-autoscaling.html
4. ServerlessLLM (OSDI '24): https://www.usenix.org/system/files/osdi24-fu.pdf
5. MArk (USENIX ATC '19): https://www.usenix.org/conference/atc19/presentation/zhang-chengliang
6. Azure LLM Inference Trace 2023: https://github.com/Azure/AzurePublicDataset/blob/master/AzureLLMInferenceDataset2023.md
7. AWS EKS: ML inference autoscaling with HPA/KEDA: https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-hpa-keda.html
8. MuxFlow, GPU cluster utilisation study: https://arxiv.org/pdf/2303.13803

---

## Glossary (for speaker notes, not slides)
- **Replica / server:** one running copy of the AI model.
- **Autoscaler:** the program that decides how many replicas to run.
- **Cold start:** time from "start a server" to "server can answer" (~20 s for AI).
- **Queue:** requests waiting because every server is busy.
- **p95:** 95 % of users had it this good or better.
- **TTFT:** time to first token, i.e. how long until the user sees the first word.
- **SLO:** the promise, e.g. "p95 TTFT ≤ 1 s".
- **HPA:** Kubernetes' standard autoscaler (our comparison baseline).

---

## Change log
| Date | Who | What changed |
|---|---|---|
| 7 Oct 2026 | Claude (for Akarshak) | First version from research.md + PLAN.md. All results ⏳; all features 🟡 Planned. |

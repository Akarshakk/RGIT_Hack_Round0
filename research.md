# CodeAstra 2.0: Cloud Computing & Distributed Systems research

**Team:** Lakshita, Akarshak · **Written:** 6 Oct 2026 · **Status:** Round 1 (PPT) is open

---

## 0. TL;DR (read this first)

1. **Pick PS-1: Intelligent Auto-Scaling for AI Workloads.** It is the easiest of the three to demo live and to learn from scratch, and it lines up best with the surprise rounds at the finale. Section 3 has the full comparison.
2. **Our angle (working name: "Preheat"):** a small autoscaler for AI model servers that:
   - scales on **the signal that actually matters for AI** (request queue and p95 latency, not CPU)
   - **starts new replicas *before* a spike arrives**, because AI replicas take ~20 s or more to warm up
   - respects a **hard ₹/hour budget cap**
   - **explains every decision** in plain English.
   We prove it works by replaying a **real Microsoft Azure production LLM traffic trace** against our scaler and a standard Kubernetes-style scaler side by side, then showing the numbers.
3. **🚨 BLOCKER: the rules say teams must have 3–4 members, and you are 2.** Registration closes **8 Oct 2026, 23:59 IST**. Recruit 1–2 people (or get written permission from the organisers) **before anything else**. See section 1.
4. **🚨 The prototype you build this week cannot be submitted at the finale.** The rules say "every line of code must be authored inside the 24-hour window", and "pre-built projects" lead to disqualification. Round 2 also uses *brand-new* problem statements revealed on-site. So the prototype has two jobs: **(a)** screenshots and real numbers for the PPT, and **(b)** practice, so you can rebuild something similar 3× faster on-site.

---

## 1. What the event actually requires (from the Unstop page, rulebook and PPT template)

| Thing | Fact | Source |
|---|---|---|
| Team size | **3–4 members** ("Teams consist of 3–4 registered participants") | Unstop page + Rulebook p.2 |
| Registration closes | **8 Oct 2026, 23:59 IST** | Unstop API |
| Round 1 (online, elimination) | Idea PPT, **max 6 slides incl. title**, **PDF only**, ≤50 MB | Unstop |
| Round 1 deadline | **10 Oct 2026, 17:00 IST** | Unstop |
| Who advances | **Top 25 teams** across *all 4 domains* | Unstop round text |
| Round 1 judging order | Problem clarity → Solution robustness → Innovation → Technical feasibility → Impact | Unstop + Rulebook |
| Round 2 (offline finale) | 12 Oct 08:00 → 13 Oct, RGIT Andheri (W), Mumbai. Build: 10:30 AM → 10:30 AM | Unstop + Rulebook |
| Round 2 problem | **"Brand-new, domain-specific problem statements revealed on-site, distinct from the Round 1 idea submission track"** | Unstop |
| Fresh code rule | Every line written in the 24 h. Templates and pre-existing apps are barred. Open-source libraries, datasets and SDKs are OK. | Unstop + Rulebook |
| AI tools | Allowed (Claude, Copilot, Cursor…), but **you must be able to explain every block** | Rulebook p.3 |
| Final judging (100) | Working prototype **25** · Problem–solution fit 15 · Technical depth 15 · Innovation/USP 15 · Features & UX 10 · Impact & scalability 10 · Pitch/demo/Q&A 10 | Rulebook p.6 |
| Pitch format | 5 min pitch + 3–5 min live demo + 2 min Q&A | Rulebook |
| Deliverables | Public GitHub repo, README with setup steps, system design overview, tech stack, demo link if any | Unstop |
| **Convergence round** (hour 6) | Paired with a team from *another domain*. You must **really** integrate a component (REST/gRPC/model/etc.). "Cosmetic" integration is penalised. | Unstop + Rulebook |
| **Trial & Reward** (hour 12, ~2 h) | **Cloud domain gets: "Simulated traffic spike requiring rapid horizontal autoscaling, replication, or cost caps"** | Unstop + Rulebook p.5 |
| Prizes | ₹40k / ₹28k / ₹20k, plus incubation support up to ₹2L | Unstop |
| ⚠️ Inconsistency | Convergence prize: Unstop says **₹12k (₹6k/team)**, the rulebook says **₹50k (₹25k/team)**. Ask the organisers. | — |

### Things to send the organisers on the WhatsApp group (today)

> Hi, we're registering for the Cloud & Distributed Systems domain. Three quick questions:
> 1. Rules say teams must be 3–4 people. Is a 2-person team allowed, or must we add members before 8 Oct 23:59?
> 2. Round 2 says new problem statements are revealed on-site. Do shortlisted teams build the *new* PS, or continue their Round 1 idea?
> 3. The Convergence prize is ₹12k on Unstop but ₹50k in the rulebook. Which is correct?
> Thanks!

**If the answer to Q1 is "no":** add 1–2 people now. Ideally add someone comfortable with Python or backend work. A person who just does the PPT/pitch also helps, because the pitch is worth 10 marks and ~10 minutes on stage.

---

## 2. The three Cloud problem statements in plain English

### PS-1 · Intelligent Auto-Scaling for AI Workloads
> "Cloud AI workloads can fluctuate dramatically. Running excessive GPU infrastructure wastes resources, while insufficient resources cause unacceptable latency."

**In simple words:** a company runs an AI model (like a chatbot) on expensive GPU machines. Traffic goes up and down: busy at 9 PM, dead at 4 AM, and sometimes a sudden spike. Keep too many machines on and you burn money. Keep too few and users wait 10 seconds and leave. **Build the brain that decides how many machines to run, minute by minute.**

### PS-2 · Distributed Data Synchronization System
> "Keep data synchronized across geographically distributed services while handling network delays, conflicting updates and temporary disconnections."

**In simple words:** the same data (say, a shared to-do list) lives on servers in Mumbai, Singapore and Frankfurt. Two people edit the same item at the same moment in different cities, or one server goes offline for 5 minutes and keeps accepting edits. **When everything reconnects, every copy must end up identical, and no one's edit can silently vanish.**

### PS-3 · Autonomous Cloud Operations Platform
> "Continuously observes infrastructure, detects anomalies, predicts failures and recommends or executes corrective actions."

**In simple words:** a robot on-call engineer. It watches CPU, memory, error rates and logs. It notices "something is weird", guesses "this server will crash in 10 minutes", and either tells a human what to do or does it itself (for example, restarts the service).

---

## 3. Ruthless comparison

Scores are 1 (bad) to 5 (great), **for a 2–4 person team that is new to this domain**, judged against *this* event's rubric.

| Criterion (why it matters) | PS-1 Autoscaling | PS-2 Data Sync | PS-3 AIOps |
|---|:-:|:-:|:-:|
| **Live demo is obviously "working"** (25 marks are for the working prototype) | **5** | 3 | 4 |
| **Learnable in 4 days from zero** | **4** | 2 | 3 |
| **Stands out from other teams** | **4** | 3 | 1 |
| **Survives jury Q&A** | **4** | 2 | 2 |
| **Fits Trial & Reward + Convergence** | **5** | 3 | 3 |
| **Feasible on laptops, no paid cloud** | **4** | 4 | 3 |
| **Clear impact story (₹ saved, latency)** | **5** | 3 | 4 |
| **Total / 35** | **31** | 20 | 20 |

### Why PS-1 wins

- **The demo is easy to see.** The judge watches a traffic spike arrive. Our replica count rises *before* latency breaks, while the baseline scaler lets latency explode. Two lines on a chart, with an obvious winner, in under 2 minutes.
- **It is the Trial & Reward challenge.** At hour 12 the Cloud domain gets a "traffic spike requiring rapid horizontal autoscaling, replication, or cost caps". If you have practised building an autoscaler with a cost cap, that curveball is your home ground, whatever the Round 2 PS turns out to be.
- **The Convergence round fits naturally.** Pair with an AI/ML team and **serve *their* model behind *our* autoscaler**. That is a real REST integration with obvious value ("your model now survives a traffic spike"), exactly what the rules reward. It is the opposite of cosmetic.
- **The concepts are the core of cloud computing:** containers, replicas, load balancing, latency percentiles, queues, control loops, cost. These are also on your syllabus, so the time you invest pays off twice.
- **The numbers are real and easy to cite.** One public paper measured **~20 s cold start** for a 3B-parameter model on an H100 GPU under vLLM. Kubernetes' default autoscaler waits **300 s** before scaling down. Ray Serve waits **30 s** to scale up and **600 s** to scale down by default. These numbers make the problem concrete (sources in section 10).

### Why not PS-2 (Data Sync)

- Intellectually the best, but **the theory is hard to learn in 4 days**: vector clocks, causality, CRDTs, the CAP theorem, eventual consistency. The jury *will* ask "what consistency model is this?" and "what happens when two deletes race an insert?". Weak answers cost marks in the 15-mark "technical depth" bucket.
- **You face a choice where both options are bad.** Use Automerge or Yjs (mature CRDT libraries) and the judges see a wrapper. Write your own CRDT and you risk subtle bugs in a live demo.
- A "Mumbai and Singapore converge" demo is less visually dramatic than a load spike.
- **Choose this only if** both of you *love* theory and already understand what a vector clock is.

### Why not PS-3 (AIOps)

- **It is the most crowded idea in every hackathon right now**: "an AI agent that reads your logs and fixes things". Expect many teams to ship a ChatGPT-reads-logs wrapper. Differentiation scores near zero.
- **The scope is four products in one sentence** (observe + detect + predict + act). In 24 h you will do all four badly.
- **"Predicts failures" is hard to prove honestly.** With synthetic metrics you are predicting failures you injected yourself, and a sharp judge will say so.
- Mature open-source tools already exist (K8sGPT; HolmesGPT, a CNCF Sandbox project). "How is this different from HolmesGPT?" is a hard Q&A question.

### Honest risks of PS-1 (and how we handle them)

| Risk | Mitigation |
|---|---|
| "You don't have GPUs. Is this fake?" | Say so upfront on the slide. Replicas are real containers running a real (small) model on CPU. GPU-like behaviour is *emulated*: a fixed concurrency limit per replica, and a cold-start delay **calibrated to a published measurement**. The scaling logic is identical either way. |
| Overbuilding (Kubernetes, LSTMs, Prometheus + Grafana + …) | **No Kubernetes in v1.** We drive Docker directly. **No deep learning for forecasting**: Holt's smoothing is ~10 lines of code and explainable on a whiteboard. An LSTM forecaster in a hackathon is a red flag. |
| "Autoscaling already exists (HPA, KEDA, Ray Serve, SageMaker)" | Yes, and we *benchmark against* that style of scaler. Our pitch is not "we invented autoscaling". It is that the default signals (CPU) and reactive timing are wrong for AI workloads with 20 s+ cold starts, and we show the fix with numbers. Research systems like MArk (USENIX ATC 2019) also used predictive scaling plus SLOs. Cite them; never claim novelty you don't have. |
| Round 2 PS is different | The skills carry over regardless (Docker, load generation, metrics, control loops, dashboards). Trial & Reward is about scaling anyway. |

---

## 4. Concepts primer: everything you need to understand PS-1

Read this top to bottom once. Every term here *will* show up in the PPT or the Q&A.

### 4.1 The basics

- **Cloud computing:** renting someone else's computers (AWS, Azure, GCP) by the hour instead of buying your own. You pay for *what you keep running*, which is why scaling matters.
- **Distributed system:** many computers working together as if they were one. They talk over a network, the network is slow and unreliable, and any machine can die at any time.
- **Container (Docker):** a box that holds an app plus everything it needs to run. You can start 1 or 10 identical copies in seconds. Think of a lunchbox you can clone.
- **Replica:** one running copy of your app. "3 replicas" means 3 identical containers serving traffic.
- **Load balancer / gateway:** the receptionist. Every request arrives here, and it sends each one to a replica that isn't busy.
- **Horizontal scaling (scale out):** add *more* replicas. **Vertical scaling (scale up):** make one replica *bigger*. Autoscaling usually means horizontal.

### 4.2 AI-specific parts

- **Inference vs training:** training = teaching the model (hours or days, done once). **Inference** = using the model to answer a request (milliseconds to seconds, millions of times). PS-1 is about inference.
- **GPU:** the expensive chip that runs AI models fast. Datacenter GPU instances cost far more per hour than normal servers, so an idle GPU is money on fire.
- **Cold start:** the time between "start a new replica" and "replica can answer requests". For AI it is slow, because the model weights (gigabytes) must be loaded into GPU memory and the runtime must warm up. A 2026 study measured **~20.3 s total** for a 3B model on an H100 with vLLM, and bigger models take longer. Normal web servers start in about 1 s.
  - **Why this is THE problem:** if your scaler only reacts *after* traffic rises, users suffer for the full cold-start time. Hence: *predict, then pre-warm*.

### 4.3 Measuring "good"

- **Latency:** how long one request takes.
- **p95 latency:** sort all request times, then take the one 95% of the way up. "p95 = 800 ms" means 95% of users waited ≤800 ms. We use p95 instead of the average because averages hide the angry 5%.
- **SLO (Service Level Objective):** your promise, e.g. "p95 latency ≤ 1 s". **SLO attainment** = % of time you kept the promise.
- **Throughput / RPS:** requests per second the system handles.
- **Queue depth:** how many requests are waiting because all replicas are busy. A growing queue is the **earliest warning** of overload, earlier than latency.

### 4.4 How an autoscaler thinks

- **Control loop:** every few seconds: *measure → decide → act → repeat*. Your home thermostat is a control loop.
- **Reactive scaling:** "CPU is above 70%? Add a replica." Simple, but always late, and for GPU inference **CPU is the wrong signal**. The GPU does the work, so CPU can look calm while requests pile up. Modern guides for LLM serving scale on queue depth (e.g. vLLM's `num_requests_waiting`) instead.
- **Predictive scaling:** "Traffic is rising at this rate, so in 20 s (one cold start) we'll need 6 replicas. Start them *now*."
- **Little's Law** (the one formula to know): `L = λ × W`. The number of requests in the system (L) equals the arrival rate (λ) times the time each spends inside (W). We use it to compute **how many replicas we need**:
  - If one replica can work on `c` requests at once and each takes `s` seconds, then one replica handles `μ = c / s` requests/sec.
  - If we expect `λ` req/s, we need `N = ceil( λ / (μ × 0.7) )` replicas. The 0.7 is **headroom**: never plan to run at 100%, because queues explode near full load.
- **Flapping:** the scaler adds a replica, load dips, it removes one, load rises, it adds one… This wastes cold starts. The fix is **hysteresis / cooldown**: scale up fast, scale down only after a sustained quiet period. Kubernetes' default scale-down window is 300 s for exactly this reason.
- **Scale-to-zero:** turn everything off when there's no traffic. It saves money, but the next user eats a full cold start. Trade-off: keep a **minimum warm pool** (e.g. 1 replica).
- **Cost cap / budget:** "never spend more than ₹X per hour." If replicas cost ₹p/hour each, the max is `floor(X / p)` replicas. When demand exceeds that, you must **degrade gracefully** (serve priority users first and reject or delay the rest with a clear error), not fall over.

### 4.5 Forecasting without ML hype: Holt's linear smoothing

You track two numbers, the current **level** (smoothed RPS) and the **trend** (how fast it's changing):

```
level_t = α·y_t + (1−α)·(level_{t−1} + trend_{t−1})
trend_t = β·(level_t − level_{t−1}) + (1−β)·trend_{t−1}
forecast(h steps ahead) = level_t + h·trend_t
```

- `y_t` = RPS measured this tick. Start with `α = 0.5` and `β = 0.3` and tune them.
- `h` = cold-start time ÷ tick length. You forecast exactly as far ahead as a new replica takes to become ready.
- It is ~10 lines of Python, you can explain it on a whiteboard, and it is honest. **This is better than an LSTM for this pitch.**

---

## 5. The solution: "Preheat" (working name, change it if you like)

> **One line:** a predictive, cold-start-aware, budget-capped autoscaler for AI inference that explains every decision.

### 5.1 Core features (must-have)

1. **Right signals:** scale on *queue depth + in-flight requests + p95 latency*, not CPU.
2. **Cold-start-aware lookahead:** forecast demand `cold_start_seconds` ahead (Holt) and start replicas *before* they're needed.
3. **Reactive safety net:** if the forecast is wrong (sudden spike), queue or p95 crossing a threshold triggers an *immediate* scale-up. Prediction is the first line of defence, and this is the second.
4. **Anti-flapping:** fast up, slow down (scale down only after 60 s of sustained low demand), plus a minimum warm pool of 1.
5. **Budget cap:** set ₹/hour, and the scaler never exceeds `floor(budget / price_per_replica)`. Over the cap, **priority admission**: "premium" requests are always served, and "free" requests get a fast `429 Try later` instead of a 30 s timeout.
6. **Explainable decision log:** every action gets a sentence, e.g.
   `14:02:10  2 → 4 replicas · forecast 31 rps in 20 s · capacity/replica 8 rps @70% · cold start 20 s`
7. **Side-by-side benchmark:** replay the *same* traffic against (a) a baseline CPU-threshold scaler mimicking Kubernetes HPA defaults and (b) Preheat. Report SLO attainment, p95, replica-minutes (cost) and number of cold starts.

### 5.2 Stretch features (only if ahead of schedule)

- **Model cascading under budget pressure:** route low-priority traffic to a smaller, cheaper model instead of rejecting it.
- **Real cloud mode:** the same controller driving a Kubernetes Deployment's `replicas` field, or real VMs.
- **Learned capacity:** measure `μ` per replica live instead of configuring it.

### 5.3 Architecture

```
                 ┌──────────────┐
 Load generator  │   GATEWAY    │  ← tracks RPS, queue, in-flight, latency (p50/p95)
 (Azure trace ──►│ (FastAPI     │──────────────┐
  replay / spike)│  reverse     │              │ /metrics (every 1–2 s)
                 │  proxy)      │              ▼
                 └──────┬───────┘       ┌──────────────┐     ┌─────────────────┐
                        │ least-busy    │  CONTROLLER  │────►│  DASHBOARD      │
                        ▼ routing       │  measure →   │     │ replicas, RPS,  │
        ┌───────────┬───────────┐       │  forecast →  │     │ p95 vs SLO,     │
        │ replica 1 │ replica 2 │ ...   │  decide →    │     │ ₹ spend, log    │
        │ model     │ model     │◄──────│  act (Docker │     └─────────────────┘
        │ server    │ server    │ start/│  SDK)        │
        └───────────┴───────────┘ stop  └──────────────┘
```

- **Model server** (one container = one replica): FastAPI with a small real model (e.g. a DistilBERT sentiment model on CPU). It allows `c` concurrent requests (a semaphore, to emulate limited GPU slots) and waits out an extra configurable warm-up delay at startup, calibrated to the ~20 s published cold start. `/health` returns ready only after warm-up.
- **Gateway:** sends each request to the least-busy *ready* replica, queues when all are busy, and records metrics.
- **Controller:** a loop every 2 s. It reads gateway metrics, updates the forecast, computes the desired replica count (Little's Law + headroom + budget cap + hysteresis), starts or stops containers via the Docker SDK, and writes the decision log.
- **Baseline controller:** the same loop with HPA-like logic: target CPU 70%, 15 s period, 300 s scale-down window. A flag switches between them.
- **Load generator:** replays timestamps from the **Azure LLM Inference Trace** (public, on GitHub; real production request arrival times), time-compressed, plus a synthetic "flash spike" mode.
- **Dashboard:** a web page polling metrics. Charts for replicas, RPS (actual vs forecast), p95 vs the SLO line, ₹ spent, and a live decision log.

### 5.4 Tech stack (boring on purpose)

| Part | Choice | Why |
|---|---|---|
| Language | Python 3.11 | Both of you can read it; everything below has a Python SDK |
| Servers | FastAPI + Uvicorn, `httpx` for proxying | Fast to write, async |
| Model | Hugging Face `transformers` small model on CPU (or ONNX Runtime) | A real model, runs on laptops |
| Orchestration | Docker + `docker` Python SDK (+ docker-compose for fixed parts) | No Kubernetes learning cliff |
| Load | Own asyncio replayer (or Locust) | Replays the exact Azure trace timing |
| Dashboard | React + Recharts, *or* plain HTML + Chart.js | Lakshita's call; this is the 10 "Features & UX" marks |
| Repo | GitHub, README with diagram + "how to run in 3 commands" | Required deliverable |

### 5.5 What "done" looks like for the prototype (before 10 Oct)

- `docker compose up` brings up gateway + controller + dashboard + 1 replica.
- Running the replay with `--scaler baseline` and then `--scaler preheat` produces a table like:

| Scaler | SLO attainment (p95 ≤ 1 s) | Peak p95 | Replica-minutes (cost) | Cold starts |
|---|---|---|---|---|
| Baseline (HPA-like) | ?? % | ?? s | ?? | ?? |
| Preheat | ?? % | ?? s | ?? | ?? |

**Use only numbers you actually measured.** If Preheat costs *more* replica-minutes but holds the SLO, say exactly that. Judges respect honest trade-offs far more than suspicious "99% better" claims.

---

## 6. Build plan: 6 Oct → 10 Oct

> Person A = backend-leaning, Person B = UI/pitch-leaning. Assign as you see fit. If you recruit a 3rd or 4th member, give them the load generator + benchmark (A) or the PPT (B).

| Day | Person A | Person B |
|---|---|---|
| **Mon 6 Oct** | Install Docker. Model-server container working; `curl` gets a prediction | **Recruit teammates.** Message the organisers (section 1). Read this primer fully |
| **Tue 7 Oct** | Gateway (routing, queue, metrics) + reactive controller starting/stopping containers | Download the Azure trace, write the replayer; dashboard skeleton |
| **Wed 8 Oct** ⚠️ registration closes 23:59 | Holt forecast + cold-start lookahead + hysteresis + budget cap; baseline mode | Dashboard charts wired to live metrics + decision log. **Confirm team registration done** |
| **Thu 9 Oct** | Run both scalers on the same trace, record the table, fix bugs | Screenshots and architecture diagram; draft all 6 slides |
| **Fri 10 Oct** | README + repo tidy | Final PPT → **export PDF → submit by 12:00** (deadline 17:00; don't gamble on Unstop at 16:55) |

### At the finale (if you're shortlisted)

- **Start from an empty repo.** Do not push this week's code (the rules ban pre-built projects and "spoofed commits"). Use this week's work as *practice*. A rebuild you've done once goes ~3× faster.
- Read the on-site PS, then map it onto this skeleton: **gateway → metrics → controller → dashboard**. Most cloud problem statements fit this shape.
- **Hour 6 Convergence:** offer to host the AI/ML team's model behind your scaler, or expose your scaling API to them.
- **Hour 12 Trial & Reward:** expect "traffic spike / replication / cost cap". You'll have practised all three.

---

## 7. The 6-slide PPT: what goes on each slide

Template order is fixed (title, problem, solution, technical, impact, optional supporting). Delete the "Important Pointers" slide before submitting. **Short points and diagrams, no paragraphs.**

1. **Team details:** Team ID, name, leader, members, *Domain: Cloud Computing & Distributed Systems*, *PS-1: Intelligent Auto-Scaling for AI Workloads*.
2. **Problem analysis**
   - AI traffic is spiky, GPUs are expensive, and AI replicas take ~20 s+ to start (cite the paper).
   - Standard autoscalers watch CPU (the wrong signal for GPU inference) and react *after* overload. Kubernetes HPA waits 300 s by default before scaling down, so you either pay for idle GPUs or users wait.
   - GPU waste: utilisation studies consistently find GPUs mostly idle (one vendor report on production clusters claims ~5% average; academic cluster studies find most GPUs below 60%). Present this as "consistently low", and cite the source, but don't lean on the most dramatic figure.
   - Who suffers: startups and college or SME teams serving AI features on a tight budget.
3. **Proposed solution & key features:** the 7 core features from 5.1 as icons + one line each, plus a mini mock of the dashboard.
4. **Technical approach & innovation:** the architecture diagram from 5.3, the tech stack row, the Holt + Little's Law formula in one box, and the USP in 3 bullets: *cold-start-aware lookahead · budget as a hard constraint · explainable decisions*.
5. **Impact & future scope:** the benchmark table (with *real* numbers from your prototype; this is the slide that gets you shortlisted). Future: Kubernetes operator, real GPU metrics (DCGM), multi-model packing, spot-instance support, model cascading.
6. **Supporting info:** a dashboard screenshot during a spike, a sequence diagram of one scale-up decision, and references (section 10).

---

## 8. Jury Q&A prep (practise answering these out loud)

| Question | Answer skeleton |
|---|---|
| "You don't have GPUs, so is this real?" | "The scaling logic doesn't care what chip is inside. We emulate a GPU replica's two properties that matter, limited concurrent slots and a long cold start, calibrated to a published vLLM measurement. Swapping in a real GPU container changes one config line." |
| "Why not just use Kubernetes HPA or KEDA?" | "HPA scales on CPU by default and reacts after the fact. KEDA can use queue depth but is still reactive. With 20 s+ cold starts, reactive means users eat the cold start. We add lookahead and a budget cap, and we benchmarked against HPA-style behaviour." |
| "What if your forecast is wrong?" | "Two layers. The forecast pre-warms, and a reactive trigger on queue and p95 catches surprises. We show the forecast-vs-actual line on the dashboard, so errors are visible." |
| "How do you avoid flapping?" | "Fast up, slow down: a scale-down needs 60 s of sustained low demand, plus a minimum warm pool." |
| "What happens at the budget cap?" | "We never exceed it. Priority requests are served and the rest get an immediate 429 with retry-after, instead of a 30 s timeout." |
| "Is your controller a single point of failure?" | "In the prototype, yes. If it crashes, replicas stay as they are (fail-static), so traffic keeps flowing. In production, run 2 controllers with leader election and multiple gateways behind a cloud load balancer." |
| "What's novel here?" | "Not the idea of predictive autoscaling. Research like MArk (ATC '19) explored it. Our contribution is a simple, explainable, budget-first implementation with a measured comparison on a real production trace." *(Honesty here wins points.)* |
| "Why Holt, not an LSTM?" | "It's explainable, needs no training data, adapts in seconds, and the forecast horizon is only ~20 s. A neural net adds risk, not accuracy, at that horizon." |
| "How did you compute cost?" | "Replica-minutes × a configurable ₹/replica-hour. Plug in any provider's GPU price." |

---

## 9. Mini-primer for PS-2 and PS-3 (so you know what you're turning down)

**PS-2 words:** *replication* (keeping copies on many servers) · *network partition* (servers can't reach each other but both keep running) · *CAP theorem* (during a partition you must choose consistency or availability) · *eventual consistency* (copies may differ briefly but converge) · *last-write-wins* (simple, but silently loses data) · *vector clock* (a per-server counter that detects "these two edits happened concurrently") · *CRDT* (data types that mathematically always merge to the same result, e.g. Automerge, Yjs).

**PS-3 words:** *observability* (metrics + logs + traces) · *anomaly detection* (flag values far from normal, e.g. z-score > 3) · *MTTR* (mean time to recovery) · *runbook* (step-by-step fix instructions) · *auto-remediation* (the system runs the runbook itself) · *alert fatigue* (too many alerts, so humans ignore them).

**To go deeper later:** *Designing Data-Intensive Applications* (Kleppmann), ch. 5 (Replication) and ch. 9 (Consistency). It's the best single book on this whole domain.

---

## 10. Sources

- CodeAstra 2.0 Unstop listing (via Unstop public API): https://unstop.com/hackathons/codeastra-20-24-hour-offline-hackathon-association-of-budding-information-technocrats-abit-rgit-1764841
- CodeAstra 2.0 Rulebook (PDF attachment on Unstop) and Round 1 PPT template; Round 1 problem statements PDF (`codeastra_ps.pdf`)
- Kubernetes HPA docs: default 300 s scale-down stabilisation, 15 s sync period: https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/
- Ray Serve advanced autoscaling: `target_ongoing_requests` default 2, `upscale_delay_s` 30 s, `downscale_delay_s` 600 s: https://docs.ray.io/en/latest/serve/advanced-guides/advanced-autoscaling.html
- "Breaking the Ice: Analyzing Cold Start Latency in vLLM" (2026): ~20.32 s total startup, Llama3.2-3B on H100: https://arxiv.org/html/2606.07362v1
- ServerlessLLM (OSDI '24): cold-start-heavy serverless LLM inference; 6–8.2× faster checkpoint loading: https://www.usenix.org/system/files/osdi24-fu.pdf
- MArk (USENIX ATC '19): predictive autoscaling + SLO-aware, cost-effective ML inference: https://www.usenix.org/conference/atc19/presentation/zhang-chengliang
- KEDA/Knative for LLM inference, scaling on vLLM `num_requests_waiting`: https://www.spheron.network/blog/keda-knative-gpu-autoscaling-kubernetes-llm-cold-start/ and AWS EKS guide: https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-hpa-keda.html
- GPU underutilisation: Cast AI 2026 report coverage (vendor claim ~5% avg; treat as directional): https://www.hpcwire.com/aiwire/2026/04/21/companies-are-racing-to-buy-gpus-many-sit-idle/ · MuxFlow (production cluster study, most GPUs <60% util): https://arxiv.org/pdf/2303.13803
- Azure LLM Inference Trace (real request timestamps for replay): https://github.com/Azure/AzurePublicDataset
- AIOps landscape (why PS-3 is crowded): https://www.aurorasre.ai/blog/open-source-ai-sre-aurora-vs-holmesgpt-vs-k8sgpt
- CRDT and sync landscape (PS-2): https://kanopylabs.com/blog/yjs-vs-automerge-vs-liveblocks

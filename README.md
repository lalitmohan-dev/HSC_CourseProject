# Hardware-Software Co-Design & System-Level Synthesis DSE Framework

A full-stack web application and analytical design-space exploration (DSE) framework for exploring system implementations of task-dependency graphs (application problem graphs) onto heterogeneous platform architectures (processors, hardware accelerators, and interconnect buses).

---

## 1. Key Capabilities

- **Formal System Synthesis Model:** Explores designs defined as $(\alpha, \beta, \tau)$:
  - $\alpha$: Resource allocation (mandatory, optional, and derived route interconnect)
  - $\beta$: Binding of compute tasks and communication objects
  - $\tau$: Deterministic list schedule respecting precedences and resource capacities
- **Bus Contention & DMA-Style Transfers:** Models buses as scheduled, serialized resources. DMA transfers do not block compute resources.
- **Multiple Exploration Strategies:**
  - **Exhaustive:** Enumerates all legal configurations within budget ($2^{20}$ safety ceiling).
  - **Random:** Uniform sampling with deterministic seeded reproducibility.
  - **Greedy:** Local 1-change neighborhood search with restarts and tabu-deduplication.
  - **NSGA-II:** Multi-objective genetic algorithm with constraint-dominated sorting, crossover, mutation, and crowding distance.
- **Pareto Optimality & Recommendation:** Non-dominated sorting across user objectives (latency, cost, energy, power, throughput) with transparent min-max normalized weighted recommendation and trade-off rationales.
- **Interactive Visualizations:**
  - **React Flow + ELK.js:** Automatic hierarchical layout for Application DAGs and Architecture Platforms.
  - **Mapping View:** Task graphs grouped and color-coded by bound resource, separating local (0 ms) from routed bus transfers.
  - **Recharts Pareto Scatter:** Interactive exploration with selectable axes and click-to-inspect candidate selection.
  - **Resource Gantt Timeline:** Compute vs bus transfer blocks with critical path gold border highlighting.
  - **Bottleneck Analysis & What-If:** Critical path breakdown, resource busy %, and evaluated alternative bindings.
  - **Side-by-Side Compare:** Metric comparisons for 2 to 4 candidates.
  - **Server-Sent Events (SSE):** Real-time log and progress streaming during exploration runs.

---

## 2. Canonical Presets Included

1. **Canonical Golden Slide (`golden-slide`):**
   - Direct implementation of Section 7 slide reference.
   - Tasks: $V1, V2, V3, V4$.
   - Communication: $V5$ (local RISC event, 0 ticks), $V6$ (1 tick on Shared Bus), $V7$ (1 tick on Shared Bus).
   - Architecture: RISC, HWM1, Shared Bus SB.
   - Verifies exact golden makespan of **32 abstract ticks**.
2. **Synthetic Walkthrough (`synthetic-walkthrough`):**
   - 3-stage pipeline ($T1 \rightarrow T2 \rightarrow T3$) comparing All-SW (10.0 ms) with HW-accelerated $T2$ on ACC1 (8.5 ms).
3. **Simple CPU/FPGA Preset (`simple-cpu-fpga`):**
   - Lowers legacy binary SW/HW tasks into the generalized IR with dedicated accelerators and an FPGA fabric capacity group.

---

See `docs/MODEL_LIMITATIONS.md` for exact model semantics, limitations and the verification record.

---

## 3. Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### Running the Backend
```bash
cd dse/backend
pip install -e ".[dev]"
uvicorn app.main:app --port 8000 --reload
```
API runs at: `http://localhost:8000`  
Interactive Swagger docs: `http://localhost:8000/docs`  
Health endpoint: `http://localhost:8000/api/health`

### Running the Frontend
```bash
cd dse/frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

### Running with Docker Compose
```bash
cd dse
docker-compose up --build
```

---

## 4. Running the Test Suite

```bash
cd dse/backend
python -m pytest tests/ -v
```
All 53 unit and API integration tests will run and pass, including:
- Health and Projects REST API tests (`tests/api/test_projects_api.py`)
- Exploration lifecycle and SSE stream tests (`tests/api/test_explore_api.py`)
- Canonical Golden Test verifying 32 ticks latency (`tests/unit/test_golden_scheduler.py`)
- Common Candidate Evaluator tests (`tests/unit/test_evaluator.py`)
- Exhaustive, Random, Greedy, and NSGA-II search tests (`tests/unit/test_search.py`)
- Pareto dominance and recommendation tests (`tests/unit/test_pareto.py`)
- Presets adapter tests (`tests/unit/test_presets.py`)
- DAG validator and lowering tests (`tests/unit/test_validator.py`, `tests/unit/test_lowering.py`)

### Building the Frontend for Production
```bash
cd dse/frontend
npm run build
```
Compiles TypeScript and bundles via Vite with zero errors.

---

## 5. Project Structure

```text
HSC_CourseProject/
├── docs/
│   ├── DECISIONS.md              # Architecture decisions (D1-D8, I1-I2)
│   └── IMPLEMENTATION_STATUS.md  # Detailed milestone progress and test log
└── dse/
    ├── docker-compose.yml        # Container orchestration
    ├── data/projects/            # JSON project persistence & seeded presets
    ├── backend/
    │   ├── pyproject.toml
    │   ├── app/
    │   │   ├── main.py           # FastAPI entrypoint & exception handlers
    │   │   ├── api/              # REST routers: projects, explore, compare
    │   │   ├── ir/               # Canonical IR models, validator, lowering, presets
    │   │   ├── core/             # Pure Python scheduler and common evaluator
    │   │   ├── search/           # Exhaustive, Random, Greedy, NSGA-II, Pareto
    │   │   ├── analysis/         # Critical path and what-if bottlenecks
    │   │   ├── persistence/      # JsonFileProjectRepository
    │   │   └── reporting/        # Markdown, CSV, and JSON report generator
    │   └── tests/                # 50 unit and integration tests
    └── frontend/
        ├── vite.config.ts        # Vite + Tailwind + API proxy
        ├── src/
        │   ├── types/            # Canonical TypeScript contracts
        │   ├── api/client.ts     # Typed REST API client
        │   ├── store/index.ts    # Global Zustand store
        │   ├── lib/elkLayout.ts  # ELK.js hierarchical DAG layout
        │   └── components/       # Graph views, Gantt, Pareto, Dashboard, Shell
```

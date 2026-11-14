# Hardware–Software Co-Design Design-Space Exploration Framework

A full-stack application for evaluating and comparing hardware–software implementations of task graphs on heterogeneous platforms. The framework models compute resources, accelerators, and interconnect buses; schedules work and communication; and explores candidate designs using multiple search strategies.

## Overview

The evaluator uses a common system-synthesis model:

- **Allocation** selects the resources used by a design.
- **Binding** assigns compute tasks to resources.
- **Scheduling** produces a deterministic schedule that observes dependencies, resource capacities, and bus contention.

Communication transfers occupy bus resources but do not block compute resources, enabling DMA-style overlap. Routing and scheduling policies are deterministic in the current model; see [Model Semantics and Limitations](docs/MODEL_LIMITATIONS.md) for the precise behavior and assumptions.

## Features

- **Design-space exploration:** Exhaustive, random, greedy, and NSGA-II search strategies.
- **Evaluation:** Latency, throughput, area/cost, energy, power, and constraint checks where the model has sufficient input data.
- **Candidate analysis:** Pareto-front extraction, weighted recommendations, bottleneck analysis, and what-if evaluation.
- **Interactive frontend:** Application, architecture, and mapping graph views; Pareto charts; schedule timelines; candidate comparison; and exploration progress.
- **API and reporting:** FastAPI endpoints for project management, validation, evaluation, and exploration, with Markdown, CSV, and JSON report exports.
- **Project presets:** Golden Slide, Synthetic Walkthrough, and Simple CPU/FPGA examples.

## Requirements

- Python 3.11 or later
- Node.js and npm (for local frontend development)
- Docker Compose (optional, for running both services in containers)

## Run locally

### Backend

From the repository root:

```bash
cd dse/backend
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Interactive API documentation is at `http://localhost:8000/docs`.

### Frontend

In a separate terminal:

```bash
cd dse/frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. The Vite development server proxies API requests to the backend; start the backend as described above.

### Docker Compose

From the repository root:

```bash
cd dse
docker compose up --build
```

The frontend is served on port `5173` and the backend on port `8000`. Project data is persisted under `dse/data/`.

## Tests and production build

Run the backend tests:

```bash
cd dse/backend
python -m pytest
```

Build the frontend for production:

```bash
cd dse/frontend
npm run build
```

## Repository structure

```text
HSC_CourseProject/
├── README.md
├── docs/
│   ├── DSE_Code_Review/       # Code review report and supporting evidence
│   ├── api_test_results/      # API test reports, results, and supporting files
│   ├── report/                # LaTeX report, scripts, figures, and data
│   ├── IMPLEMENTATION_STATUS.md
│   ├── MODEL_LIMITATIONS.md
│   └── *.pdf                  # Project reference paper
└── dse/
    ├── docker-compose.yml
    ├── data/
    │   └── projects/          # Persisted project data and presets
    ├── backend/
    │   ├── app/
    │   │   ├── analysis/      # Bottleneck and critical-path analysis
    │   │   ├── api/           # FastAPI routes
    │   │   ├── core/          # Evaluation and scheduling
    │   │   ├── ir/            # Intermediate representation, validation, lowering
    │   │   ├── persistence/   # Project storage
    │   │   ├── reporting/     # Report generation
    │   │   └── search/        # Candidate generation and search strategies
    │   ├── tests/
    │   │   ├── api/
    │   │   └── unit/
    │   └── pyproject.toml
    └── frontend/
        ├── src/
        │   ├── api/
        │   ├── components/    # Graph, dashboard, results, forms, and shell
        │   ├── lib/
        │   ├── store/
        │   └── types/
        └── package.json
```

## Further documentation

- [Implementation status](docs/IMPLEMENTATION_STATUS.md) — implemented components and project milestones.
- [Model semantics and limitations](docs/MODEL_LIMITATIONS.md) — verified behavior, assumptions, and known limitations.
- [DSE code review](docs/DSE_Code_Review/README.md) — review overview and supporting material.
- [API test reports](docs/api_test_results/API_TEST_REPORT.md) — API test results and evidence.

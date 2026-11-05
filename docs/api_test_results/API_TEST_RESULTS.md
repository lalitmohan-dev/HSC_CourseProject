# API Test Results

Run on 2026-11-05 against the live backend (`uvicorn`, http://localhost:8000). **41/43 passed.** Each row has a screenshot in `screenshots/<ID>.png`; `screenshots/T00_swagger_endpoints.png` shows the full endpoint list.

| ID | Area | Test | Request | Expected | HTTP | Result | Notes |
|---|---|---|---|---|---|---|---|
| T01 | 1 Smoke | Health check | `GET /api/health` | 200, {"status":"ok"} | 200 | PASS |  |
| T02 | 1 Smoke | List projects includes 3 presets | `GET /api/projects` | 200, contains golden-slide, synthetic-walkthrough, simple-cpu-fpga | 200 | PASS |  |
| T03 | 2 CRUD | Create project | `POST /api/projects` | 201, project with generated id | 201 | PASS |  |
| T04 | 2 CRUD | Read created project | `GET /api/projects/fb44e0b9` | 200, name = 'CRUD Test' | 200 | PASS |  |
| T05 | 2 CRUD | Update project description | `PUT /api/projects/fb44e0b9` | 200, description updated | 200 | PASS |  |
| T06 | 2 CRUD | Update persisted (re-read) | `GET /api/projects/fb44e0b9` | 200, description = 'Updated description' | 200 | PASS |  |
| T07 | 2 CRUD | Delete project | `DELETE /api/projects/fb44e0b9` | 200, {"deleted": true} | 200 | PASS |  |
| T08 | 2 CRUD | Read after delete | `GET /api/projects/fb44e0b9` | 404 | 404 | PASS |  |
| T09 | 3 Validation | Create with malformed body | `POST /api/projects` | 422 | 422 | PASS |  |
| T10 | 3 Validation | Import cyclic task graph | `POST /api/projects/import` | Rejected: is_valid=false with a cycle error (or 422) | 422 | PASS |  |
| T11 | 3 Validation | Import invalid payload | `POST /api/projects/import` | 422 | 422 | PASS |  |
| T12 | 3 Validation | Validate valid preset | `POST /api/projects/golden-slide/validate` | 200, is_valid=true, no errors | 200 | PASS |  |
| T13 | 3 Validation | Evaluate candidate bound to unknown resource | `POST /api/projects/golden-slide/evaluate` | 400 (or 422) | 500 | **FAIL** |  |
| T14 | 3 Validation | Report with unsupported format | `GET /api/runs/x/report?format=pdf` | 422 | 422 | PASS |  |
| T15 | 4 Not found | Unknown id: /api/projects/nope | `GET /api/projects/nope` | 404 | 404 | PASS |  |
| T16 | 4 Not found | Unknown id: /api/projects/nope/explore | `POST /api/projects/nope/explore` | 404 | 404 | PASS |  |
| T17 | 4 Not found | Unknown id: /api/runs/run_nope | `GET /api/runs/run_nope` | 404 | 404 | PASS |  |
| T18 | 4 Not found | Unknown id: /api/runs/run_nope/designs | `GET /api/runs/run_nope/designs` | 404 | 404 | PASS |  |
| T19 | 4 Not found | Unknown id: /api/runs/run_nope/cancel | `POST /api/runs/run_nope/cancel` | 404 | 404 | PASS |  |
| T20 | 5 Correctness | Golden Slide makespan | `POST /api/projects/golden-slide/evaluate` | 200, feasible, latency = 32 ticks | 200 | PASS |  |
| T21 | 5 Correctness | Lowered IR has 3 communication objects | `GET /api/projects/golden-slide/ir` | 200, 3 communication objects | 200 | PASS |  |
| T22 | 5 Correctness | Synthetic Walkthrough: 10.0 ms all-SW, 8.5 ms accelerated | `POST+GET /api/projects/synthetic-walkthrough/explore -> /api/runs/run_445b1c01/designs` | completed; latencies include 8.5 and 10.0 | 200 | PASS | latencies=[8.5, 10.0] |
| T23 | 5 Correctness | Simple CPU/FPGA exhaustive: 4 feasible candidates | `POST+GET /api/projects/simple-cpu-fpga/explore -> /api/runs/run_78350008` | 4 candidates, all feasible | 200 | PASS | latencies=[9.7, 10.0, 10.7, 11.75] |
| T24 | 6 Exploration | Strategy 'random' run completes | `POST+GET /api/projects/apitest-random/explore` | completed, >=1 Pareto design, recommendation present | 200 | PASS | evaluated=2 pareto=2 |
| T25 | 6 Exploration | Strategy 'greedy' run completes | `POST+GET /api/projects/apitest-greedy/explore` | completed, >=1 Pareto design, recommendation present | 200 | PASS | evaluated=2 pareto=2 |
| T26 | 6 Exploration | Strategy 'nsga2' run completes | `POST+GET /api/projects/apitest-nsga2/explore` | completed, >=1 Pareto design, recommendation present | 200 | PASS | evaluated=2 pareto=2 |
| T27 | 6 Exploration | SSE progress stream ends with 'done' | `GET /api/runs/run_ee47d215/events` | text/event-stream, events received, last event = done | 200 | PASS | 17 events, kinds=['done', 'log', 'progress'] |
| T28 | 6 Exploration | Designs list: filter, sort, paging | `GET /api/runs/run_445b1c01/designs?feasible_only=true&sort_order=desc&page_size=1` | 200, 1 item, highest latency first | 200 | PASS |  |
| T29 | 6 Exploration | Design detail | `GET /api/runs/run_445b1c01/designs/design_0001` | 200, evaluation present | 200 | PASS |  |
| T30 | 6 Exploration | Unknown design in valid run | `GET /api/runs/run_445b1c01/designs/nope` | 404 | 404 | PASS |  |
| T31 | 7 Constraints | Impossible latency constraint (0.1 ms) | `POST+GET /api/projects/apitest-infeasible/explore` | all candidates infeasible; rationale starts with WARNING (fallback) | 200 | PASS | rationale: WARNING: no feasible design exists under the current constraints; this is the least-violating fallback, not a feasible r |
| T32 | 8 Cancel | Cancel a long exhaustive run (16,384 designs) | `POST /api/runs/run_227bed03/cancel` | 200, status "cancelling"; run ends as cancelled before finishing | 200 | **FAIL** | final status=completed, evaluated 16384 of 16384 |
| T33 | 9 Analysis | Bottleneck analysis | `GET /api/runs/run_445b1c01/bottlenecks?design_id=design_0001` | 200, critical path + utilisation | 200 | PASS |  |
| T34 | 9 Analysis | Bottlenecks for unknown design | `GET /api/runs/run_445b1c01/bottlenecks?design_id=nope` | 404 | 404 | PASS |  |
| T35 | 9 Analysis | Compare 2 designs | `POST /api/compare` | 200, 2 designs + metrics table | 200 | PASS |  |
| T36 | 9 Analysis | Compare with only 1 design | `POST /api/compare` | 400 | 400 | PASS |  |
| T37 | 9 Analysis | Compare unknown designs | `POST /api/compare` | 404 | 404 | PASS |  |
| T38 | 9 Analysis | Report export (md) | `GET /api/runs/run_445b1c01/report?format=md` | 200, non-empty, correct content | 200 | PASS | content-type=text/markdown; charset=utf-8 |
| T39 | 9 Analysis | Report export (csv) | `GET /api/runs/run_445b1c01/report?format=csv` | 200, non-empty, correct content | 200 | PASS | content-type=text/csv; charset=utf-8 |
| T40 | 9 Analysis | Report export (json) | `GET /api/runs/run_445b1c01/report?format=json` | 200, non-empty, correct content | 200 | PASS | content-type=application/json |
| T41 | 10 Round trip | Export -> import -> export is identical | `GET /api/projects/apitest-roundtrip/export` | content identical to original (ignoring id/timestamps) | 200 | PASS |  |
| T42 | 11 Schema | Evaluation fields and types | `POST /api/projects/golden-slide/evaluate` | latency_ms number, feasible bool, violations list; energy null for abstract time unit | 200 | PASS | energy_mj=None |
| T43 | 12 Determinism | Same seed gives same results | `POST x2 /api/projects/apitest-determinism/explore` | both runs give identical (latency, cost) sets | 200 | PASS | 2 designs per run |

## Failures (real defects)

**T13: an invalid candidate returns 500 instead of 400.** If a candidate is bound to a resource that doesn't exist, the evaluator returns `latency = inf`. FastAPI can't serialise `inf` to JSON (`ValueError: Out of range float values are not JSON compliant: inf`), so the client gets a 500 Internal Server Error. The `try/except` in `api/projects.py::evaluate_project_design` doesn't catch it because the error happens later, during response serialisation. Fix: reject unknown resources before evaluating (return 400), or map `inf` to `null` or a violation.

**T32: cancel doesn't stop a run.** `POST /runs/{id}/cancel` returns 200 "cancelling", but the run still evaluates all 16,384 designs and ends as `completed`. Cause: `api/explore.py::execute_exploration_task` is an `async` function that calls the synchronous `execute_search(...)` directly. That blocks the server's event loop for the whole search, so the cancel request only gets handled after the search has finished. The same blocking also means SSE progress events and other API calls stall during a long run. Fix: run the search in a worker thread (`await asyncio.to_thread(execute_search, ...)`) or make the task a plain `def` so FastAPI runs it in its threadpool.

## Coverage

1 Smoke · 2 CRUD lifecycle · 3 Input validation (negative) · 4 Not-found handling · 5 Correctness against known answers (32 ticks, 10.0/8.5 ms, 4 CPU/FPGA candidates) · 6 Exploration (all 4 strategies, SSE, paging/sort/filter) · 7 Constraints (infeasible fallback) · 8 Cancel · 9 Analysis & reports (bottlenecks, compare, MD/CSV/JSON) · 10 Import/export round trip · 11 Response schema · 12 Determinism (same seed gives same results).

Re-run: start the backend, then `.venv\Scripts\python api_tests.py <output dir>` (the script is in the same folder as this file).

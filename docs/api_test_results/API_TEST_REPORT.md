# API Test Report: DSE Framework Backend

**Date:** 2026-11-05
**Target:** FastAPI backend running locally (`uvicorn app.main:app`, http://localhost:8000)
**Method:** Automated HTTP test script (`api_tests.py`, Python + httpx) sending real requests to the running server. Each test checks the HTTP status code and the response content against an expected result.
**Result:** **43 tests, 41 passed, 2 failed** (both failures are genuine backend defects)

Evidence: `screenshots/T01.png` to `T43.png` (one per test, request + response + verdict), `screenshots/T00_swagger_endpoints.png` (endpoint list), `results.json` (raw results), `API_TEST_RESULTS.md` (full table).

## Scope

| Included | Not included |
|---|---|
| All 20 REST endpoints of the backend (projects + exploration) | Frontend / UI testing (needs Node 20.19+ or 22.12+) |
| Positive, negative, and not-found cases | Docker deployment |
| Correctness against known reference values | Load / performance / security testing |

Separately, the existing backend pytest suite (unit + API tests) was run: **53/53 passed**.

## Tests performed and outputs

### 1. Smoke
| ID | Test | Output | Result |
|---|---|---|---|
| T01 | `GET /api/health` | 200, `{"status":"ok","version":"0.1.0"}` | PASS |
| T02 | List projects | 200, all 3 presets present (golden-slide, synthetic-walkthrough, simple-cpu-fpga) | PASS |

### 2. CRUD lifecycle
| ID | Test | Output | Result |
|---|---|---|---|
| T03 | Create project | 201, id generated | PASS |
| T04 | Read it back | 200, correct name | PASS |
| T05 | Update description | 200, description changed | PASS |
| T06 | Re-read after update | 200, change persisted | PASS |
| T07 | Delete project | 200, `{"deleted": true}` | PASS |
| T08 | Read after delete | 404 | PASS |

### 3. Input validation (negative tests)
| ID | Test | Output | Result |
|---|---|---|---|
| T09 | Create with malformed body | 422 | PASS |
| T10 | Import cyclic task graph (A→B→A) | 422, rejected | PASS |
| T11 | Import invalid payload | 422 | PASS |
| T12 | Validate a valid preset | 200, `is_valid: true`, no errors | PASS |
| T13 | Evaluate design bound to a non-existent resource | **500 Internal Server Error** (expected 400) | **FAIL** |
| T14 | Report in unsupported format (`pdf`) | 422 | PASS |

### 4. Not-found handling
| ID | Test | Output | Result |
|---|---|---|---|
| T15–T19 | Unknown project, explore, run, designs, cancel | 404 for all five | PASS |

### 5. Correctness against known answers
| ID | Test | Output | Result |
|---|---|---|---|
| T20 | Golden Slide reference schedule | latency = **32 ticks**, feasible | PASS |
| T21 | Lowered IR of Golden Slide | 3 communication objects | PASS |
| T22 | Synthetic Walkthrough exploration | latencies **10.0 ms** (all-SW) and **8.5 ms** (T2 on ACC1) | PASS |
| T23 | Simple CPU/FPGA exhaustive | 4 candidates, all feasible: 9.7 / 10.0 / 10.7 / 11.75 ms | PASS |

### 6. Exploration flow
| ID | Test | Output | Result |
|---|---|---|---|
| T24 | Random search | completed, 2 evaluated, 2 Pareto | PASS |
| T25 | Greedy search | completed, 2 evaluated, 2 Pareto | PASS |
| T26 | NSGA-II | completed, 2 evaluated, 2 Pareto | PASS |
| T27 | SSE progress stream | 17 events (`log`, `progress`, `done`), ends with `done` | PASS |
| T28 | Designs list with filter/sort/paging | 1 item returned, highest latency first | PASS |
| T29 | Design detail | 200, evaluation present | PASS |
| T30 | Unknown design in valid run | 404 | PASS |

### 7. Constraints
| ID | Test | Output | Result |
|---|---|---|---|
| T31 | Impossible constraint `max_latency_ms = 0.1` | all designs infeasible; rationale starts "WARNING: no feasible design exists… least-violating fallback" | PASS |

### 8. Cancel
| ID | Test | Output | Result |
|---|---|---|---|
| T32 | Cancel a long run (16,384 designs) | 200 "cancelling", but run finished as **completed** (16,384 / 16,384 evaluated) | **FAIL** |

### 9. Analysis and reports
| ID | Test | Output | Result |
|---|---|---|---|
| T33 | Bottleneck analysis | 200, critical path + resource utilisation | PASS |
| T34 | Bottlenecks for unknown design | 404 | PASS |
| T35 | Compare 2 designs | 200, 2 designs + metrics table | PASS |
| T36 | Compare with only 1 design | 400 | PASS |
| T37 | Compare unknown designs | 404 | PASS |
| T38 | Report export, Markdown | 200, `text/markdown` | PASS |
| T39 | Report export, CSV | 200, `text/csv` | PASS |
| T40 | Report export, JSON | 200, `application/json` | PASS |

### 10–12. Round trip, schema, determinism
| ID | Test | Output | Result |
|---|---|---|---|
| T41 | Export → import → export | content identical | PASS |
| T42 | Evaluation field types | correct types; `energy_mj = null` for abstract time unit | PASS |
| T43 | Same seed, two runs | identical results | PASS |

## Defects found

1. **T13: invalid design causes a 500 error.** An unknown resource makes the evaluator return `latency = inf`, which cannot be serialised to JSON (`ValueError: Out of range float values are not JSON compliant: inf`). The API should return 400 with a clear message.
2. **T32: cancel has no effect.** The exploration task (`api/explore.py::execute_exploration_task`) runs the synchronous search directly inside an `async` function, blocking the server's event loop. The cancel request is only handled after the search ends. The same blocking also stalls live progress events and other API calls during long runs. Fix: run the search in a worker thread.

## Conclusion

The API behaves correctly for CRUD, validation, error handling, all four search strategies, constraints, analysis, and report export. Its results match the reference values (32 ticks; 10.0 / 8.5 ms). Two defects remain open: the 500 error on invalid designs and the non-working cancel.

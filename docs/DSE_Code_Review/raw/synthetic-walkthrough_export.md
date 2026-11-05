# Design Space Exploration (DSE) Synthesis Report
**Project:** Synthetic Walkthrough (Sec 8) (`synthetic-walkthrough`)  
**Date:** 2026-11-04 23:08:14 UTC  
**Search Strategy:** EXHAUSTIVE (Seed: 42)  
**Evaluator Version:** 2.0 (Generalized System Synthesis)  

---

## 1. Executive Summary & Recommended Design
- **Recommended Design:** `design_0001`
- **Evaluated Candidates:** 2
- **Pareto-Optimal Candidates:** 2
- **Elapsed Search Time:** 0.0 seconds
- **Recommendation Rationale:** Design 'design_0001' achieves the optimal weighted balance score of 0.500 across objectives latency, allocation_cost. Latency: 8.50 (project time unit), Allocation Cost: 35.0.

---

## 2. Application Problem Graph
- **Total Compute Tasks:** 3
- **Data Dependencies:** 2
- **Declared Memory Footprint:** 32.0 KB

| Task ID | Task Name | Input (KB) | Output (KB) | Memory (KB) | Fixed Resource |
|---|---|---:|---:|---:|---|
| T1 | Ingest | 0.0 | 0.0 | 8.0 | Flexible |
| T2 | Filtering | 0.0 | 0.0 | 8.0 | Flexible |
| T3 | Aggregation | 0.0 | 0.0 | 8.0 | Flexible |

---

## 3. Platform Architecture Graph
| Resource ID | Kind | Mandatory | Cost | Clock (MHz) | Parallelism | Static Power (mW) |
|---|---|---|---:|---:|---:|---:|
| CPU | processor | Yes | 10.0 | — | 1 | 500.0 |
| ACC1 | hw_module | No | 25.0 | — | 1 | 200.0 |
| SB | bus | Yes | 0.0 | — | 1 | 50.0 |

---

## 4. Pareto Frontier Designs
| Design ID | Latency | Allocation Cost | Energy (mJ) | Avg Power (W) | Throughput (fps) | Feasible |
|---|---:|---:|---:|---:|---:|---|
| ★ `design_0001` | 8.5 | 35.0 | 14.03 | 1.65 | 117.6 | ✓ |
| `design_0002` | 10.0 | 10.0 | 18.7 | 1.87 | 100.0 | ✓ |

---

## 5. Critical Path & Bottleneck Analysis
- **Makespan:** 8.5 ms
- **Compute Duration:** 7.0 ms
- **Communication Duration:** 1.5 ms
- **Serialization Wait Delay:** 0.0 ms

### Critical Path Items
| Item ID | Item Name | Resource | Duration | % of Makespan |
|---|---|---|---:|---:|
| T1 | Ingest | CPU | 3.0 | 35.3% |
| C1 | Transfer T1->T2 on SB | SB | 0.75 | 8.8% |
| T2 | Filtering | ACC1 | 1.0 | 11.8% |
| C2 | Transfer T2->T3 on SB | SB | 0.75 | 8.8% |
| T3 | Aggregation | CPU | 3.0 | 35.3% |

### What-If Suggestions
| Task | Current | Alternative | Δ Latency | Δ Cost | Feasible? | Rationale |
|---|---|---|---:|---:|---|---|
| T2 | ACC1 | CPU | +1.50 | -25.0 | ✓ | Rebinding T2 to CPU changes latency by +1.50 ms (ticks). |

---

## 6. Appendix: Methodology & Assumptions
- **Evaluation Model:** Analytical Hardware-Software Co-Design list scheduling with serial bus resource reservations.
- **DMA Concurrency:** Compute and bus transfers overlap unless contending for the same resource slot.
- **Deterministic Routing:** Shortest-hop paths over allocated interconnect with stable lexical tie-breaking.
- **Strict Power Semantics:** Missing power parameters are reported as unavailable, never silently substituted as zero.

*(Report generated automatically by DSE Framework v2.0)*
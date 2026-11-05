# Design Space Exploration (DSE) Synthesis Report
**Project:** Canonical Golden Slide (Sec 7) (`golden-slide`)  
**Date:** 2026-11-04 23:08:14 UTC  
**Search Strategy:** EXHAUSTIVE (Seed: 42)  
**Evaluator Version:** 2.0 (Generalized System Synthesis)  

---

## 1. Executive Summary & Recommended Design
- **Recommended Design:** `design_0001`
- **Evaluated Candidates:** 1
- **Pareto-Optimal Candidates:** 1
- **Elapsed Search Time:** 0.0 seconds
- **Recommendation Rationale:** Design 'design_0001' achieves the optimal weighted balance score of 0.000 across objectives latency, allocation_cost. Latency: 32.00 (project time unit), Allocation Cost: 0.0.

---

## 2. Application Problem Graph
- **Total Compute Tasks:** 4
- **Data Dependencies:** 3
- **Declared Memory Footprint:** 3.0 KB

| Task ID | Task Name | Input (KB) | Output (KB) | Memory (KB) | Fixed Resource |
|---|---|---:|---:|---:|---|
| V1 | Task V1 | 0.0 | 0.0 | 0.0 | Flexible |
| V2 | Task V2 | 0.0 | 0.0 | 0.0 | Flexible |
| V3 | Task V3 | 0.0 | 0.0 | 0.0 | Flexible |
| V4 | Task V4 | 0.0 | 0.0 | 0.0 | Flexible |

---

## 3. Platform Architecture Graph
| Resource ID | Kind | Mandatory | Cost | Clock (MHz) | Parallelism | Static Power (mW) |
|---|---|---|---:|---:|---:|---:|
| RISC | processor | Yes | 0.0 | — | 1 | — |
| HWM1 | hw_module | Yes | 0.0 | — | 1 | — |
| HWM2 | hw_module | No | 0.0 | — | 1 | — |
| SB | bus | Yes | 0.0 | — | 1 | — |
| PTP | bus | No | 0.0 | — | 1 | — |

---

## 4. Pareto Frontier Designs
| Design ID | Latency | Allocation Cost | Energy (mJ) | Avg Power (W) | Throughput (fps) | Feasible |
|---|---:|---:|---:|---:|---:|---|
| ★ `design_0001` | 32.0 | 0.0 | — | — | — | ✓ |

---

## 5. Critical Path & Bottleneck Analysis
- **Makespan:** 32.0 ticks
- **Compute Duration:** 31.0 ticks
- **Communication Duration:** 2.0 ticks
- **Serialization Wait Delay:** 0.0 ticks

### Critical Path Items
| Item ID | Item Name | Resource | Duration | % of Makespan |
|---|---|---|---:|---:|
| V1 | Task V1 | RISC | 1.0 | 3.1% |
| V2 | Task V2 | RISC | 20.0 | 62.5% |
| V3 | Task V3 | RISC | 8.0 | 25.0% |
| V7 | Transfer V3->V4 on SB | SB | 1.0 | 3.1% |
| V4 | Task V4 | HWM1 | 2.0 | 6.2% |

---

## 6. Appendix: Methodology & Assumptions
- **Evaluation Model:** Analytical Hardware-Software Co-Design list scheduling with serial bus resource reservations.
- **DMA Concurrency:** Compute and bus transfers overlap unless contending for the same resource slot.
- **Deterministic Routing:** Shortest-hop paths over allocated interconnect with stable lexical tie-breaking.
- **Strict Power Semantics:** Missing power parameters are reported as unavailable, never silently substituted as zero.

*(Report generated automatically by DSE Framework v2.0)*
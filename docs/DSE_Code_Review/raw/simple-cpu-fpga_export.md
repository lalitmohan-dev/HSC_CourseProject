# Design Space Exploration (DSE) Synthesis Report
**Project:** Simple CPU/FPGA Preset (Sec 9) (`simple-cpu-fpga`)  
**Date:** 2026-11-04 23:08:14 UTC  
**Search Strategy:** EXHAUSTIVE (Seed: 42)  
**Evaluator Version:** 2.0 (Generalized System Synthesis)  

---

## 1. Executive Summary & Recommended Design
- **Recommended Design:** `design_0003`
- **Evaluated Candidates:** 4
- **Pareto-Optimal Candidates:** 2
- **Elapsed Search Time:** 0.0 seconds
- **Recommendation Rationale:** Design 'design_0003' achieves the optimal weighted balance score of 0.500 across objectives latency, allocation_cost. Latency: 9.70 (project time unit), Allocation Cost: 15.0.

---

## 2. Application Problem Graph
- **Total Compute Tasks:** 3
- **Data Dependencies:** 2
- **Declared Memory Footprint:** 24.0 KB

| Task ID | Task Name | Input (KB) | Output (KB) | Memory (KB) | Fixed Resource |
|---|---|---:|---:|---:|---|
| TaskA | Data Input | 0.0 | 0.0 | 4.0 | Flexible |
| TaskB | Core Processing | 0.0 | 0.0 | 8.0 | Flexible |
| TaskC | Output Format | 0.0 | 0.0 | 4.0 | Flexible |

---

## 3. Platform Architecture Graph
| Resource ID | Kind | Mandatory | Cost | Clock (MHz) | Parallelism | Static Power (mW) |
|---|---|---|---:|---:|---:|---:|
| CPU | processor | Yes | 10.0 | 1000.0 | 1 | 500.0 |
| ACC_TaskA | hw_module | No | 5.0 | 250.0 | 1 | — |
| ACC_TaskB | hw_module | No | 5.0 | 250.0 | 1 | — |
| SharedBus | bus | Yes | 0.0 | — | 1 | 50.0 |

---

## 4. Pareto Frontier Designs
| Design ID | Latency | Allocation Cost | Energy (mJ) | Avg Power (W) | Throughput (fps) | Feasible |
|---|---:|---:|---:|---:|---:|---|
| ★ `design_0003` | 9.7 | 15.0 | — | — | 103.1 | ✓ |
| `design_0004` | 10.0 | 10.0 | — | — | 100.0 | ✓ |

---

## 5. Critical Path & Bottleneck Analysis
- **Makespan:** 9.7 ms
- **Compute Duration:** 8.2 ms
- **Communication Duration:** 1.5 ms
- **Serialization Wait Delay:** 0.0 ms

### Critical Path Items
| Item ID | Item Name | Resource | Duration | % of Makespan |
|---|---|---|---:|---:|
| TaskA | Data Input | CPU | 3.0 | 30.9% |
| C_TaskA_TaskB | Transfer TaskA->TaskB on SharedBus | SharedBus | 0.75 | 7.7% |
| TaskB | Core Processing | ACC_TaskB | 3.2 | 33.0% |
| C_TaskB_TaskC | Transfer TaskB->TaskC on SharedBus | SharedBus | 0.75 | 7.7% |
| TaskC | Output Format | CPU | 2.0 | 20.6% |

### What-If Suggestions
| Task | Current | Alternative | Δ Latency | Δ Cost | Feasible? | Rationale |
|---|---|---|---:|---:|---|---|
| TaskA | CPU | ACC_TaskA | +1.00 | +5.0 | ✓ | Rebinding TaskA to ACC_TaskA changes latency by +1.00 ms (ticks). |
| TaskB | ACC_TaskB | CPU | +0.30 | -5.0 | ✓ | Rebinding TaskB to CPU changes latency by +0.30 ms (ticks). |

---

## 6. Appendix: Methodology & Assumptions
- **Evaluation Model:** Analytical Hardware-Software Co-Design list scheduling with serial bus resource reservations.
- **DMA Concurrency:** Compute and bus transfers overlap unless contending for the same resource slot.
- **Deterministic Routing:** Shortest-hop paths over allocated interconnect with stable lexical tie-breaking.
- **Strict Power Semantics:** Missing power parameters are reported as unavailable, never silently substituted as zero.

*(Report generated automatically by DSE Framework v2.0)*
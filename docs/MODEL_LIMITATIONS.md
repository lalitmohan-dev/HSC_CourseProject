# Model Semantics, Limitations & Verification Record

Verified against the code on 2026-11-04 (53 backend tests passing).

## 1. Exactly what the model does

| Topic | Implemented behaviour | Code |
|---|---|---|
| Routing | BFS over resource -> bus -> resource; fewest bus hops; ties broken by lexicographic order of the bus-ID list. Deterministic. Multi-hop routes **are** supported. | `ir/lowering.py::derive_deterministic_route` |
| Multi-hop transfers | Store-and-forward: each hop is its own transfer object that starts only after the previous hop finishes, and each hop pays the full `setup + data/bandwidth`. **Intermediate buffers are not modelled** (no capacity, no buffer memory, no buffer power). | `core/scheduler.py::expand_scheduling_dag` |
| Transfer time | `setup_latency_ms + data_kb / bandwidth_mb_per_s` (KB / (MB/s) = ms). | `calculate_hop_transfer_time` |
| Bus contention | Bus is a resource with `max_parallel` slots (default 1). Transfers on the same bus serialize. | `core/scheduler.py` |
| Bus arbitration | Non-preemptive. When a slot is free, the ready transfer with the best priority rank wins; rank = explicit priority list if given, otherwise bottom-level (longest remaining path) descending; ties by object ID. | `schedule_candidate` |
| DMA | Transfers occupy only the bus, never the source/destination compute resource, so compute overlaps with transfers. | D3 |
| Local edges | Same-resource edges cost 0 and use no bus. | scheduler |
| Latency | Makespan of the event-driven list schedule. | scheduler |
| Memory (`memory_kb`) | **Static declared footprint** = sum of every task's `memory_kb` + sum of every edge's `data_kb`. It does **not** depend on binding, allocation, lifetimes or buffer reuse, so it is identical for all candidates of a project. It is only a constraint check (`max_memory_kb`), not a trade-off objective. | `core/evaluator.py` |
| Area | Sum of allocated `resource.area` + chosen `mapping.usage`. (The Simple CPU/FPGA preset now puts area only in `usage`, so it is counted once.) | evaluator |
| Throughput | Non-pipelined: `1000 / latency` fps. Pipelined: `II = max over allocated resources of (sum of durations on that resource)`, `fps = 1000 / II`. **Estimate**: assumes perfect overlap of consecutive iterations, ignores `max_parallel > 1` and inter-iteration dependencies, and `II <= latency` is not enforced. Only available when `time_unit == "ms"`. | evaluator |
| Energy / power | `sum(task active power x time) + sum(bus power x busy time) + sum(static power x latency)`. Any missing power value makes energy and power `None` (never 0). Unavailable for non-ms time units. | evaluator |

## 2. Limitations (for the report)

1. No task preemption.
2. Cache misses are folded into the task execution time; they are not modelled separately.
3. The scheduler derives timing from allocation, binding and deterministic priorities; start times are never searched, and priorities are not a search variable (D5).
4. Routes are not a search variable (D4); there is no alternate-route load balancing.
5. Multi-hop: store-and-forward, no intermediate buffering (see table).
6. Memory footprint is a declared static total (see table).
7. Pipelined throughput is an optimistic resource-bound estimate.
8. Latency/throughput constraints use exact comparison without tolerance.
9. When no candidate is feasible, the Pareto front falls back to the least-violating candidates and the recommendation is explicitly labelled as a non-feasible fallback.
10. Report export: bottleneck section is only produced for runs still in memory, not for runs re-loaded from disk; export formats are Markdown, CSV and JSON (there is no PDF export).

## 3. Verification record

| Check | Result |
|---|---|
| Golden Slide latency | 32 abstract ticks (`test_golden_scheduler.py`) |
| Synthetic walkthrough, all-SW | 10.0 ms |
| Synthetic walkthrough, T2 on ACC1 | **8.5 ms** (see 3.1) |
| Simple CPU/FPGA preset, exhaustive | 4 candidates, latencies 9.7 / 10.0 / 10.7 / 11.75 ms, all feasible |
| Impossible constraint (`max_latency_ms = 0.1`) | all candidates infeasible; recommendation flagged as fallback |
| MD / CSV / JSON export | all return HTTP 200 with content |

### 3.1 The 6.5 ms vs 8.5 ms discrepancy

The fixture (`synthetic-walkthrough`) and the evaluator agree on **8.5 ms**:

```
T1 on CPU   [0.00, 3.00]    3.0 ms
C1 on SB    [3.00, 3.75]    4 KB / 8 MB/s + 0.25 ms setup = 0.75 ms
T2 on ACC1  [3.75, 4.75]    1.0 ms
C2 on SB    [4.75, 5.50]    0.75 ms
T3 on CPU   [5.50, 8.50]    3.0 ms
```

No consistent reading of this fixture yields 6.5 ms (compute alone is 7.0 ms), so the 6.5 ms figure cannot come from this model; it is most likely a hand-calculation slip or an older fixture. Use 8.5 ms in the report and slides. If your lecture notes define different inputs, change the fixture, do not change the evaluator.

## 4. Benchmark for the demo

**Synthetic Walkthrough** (`ms`, non-pipelined). Inputs: T1/T3 on CPU 3 ms each; T2 4 ms on CPU or 1 ms on ACC1; edges 4 KB; bus 8 MB/s, 0.25 ms setup; static power CPU 500 / ACC1 200 / SB 50 mW; bus 100 mW; task power 1200 / 1500 / 300 mW.

| Design | Latency | Cost | Energy | Avg power | Throughput |
|---|---|---|---|---|---|
| All-SW | 10.0 ms | 10 | 18.7 mJ | 1.87 W | 100 fps |
| T2 on ACC1 | 8.5 ms | 35 | 14.025 mJ | 1.65 W | 117.6 fps |

Both are Pareto-optimal (faster vs cheaper); the recommendation under equal weights is the accelerated design (tie on normalized score, broken by lower latency).

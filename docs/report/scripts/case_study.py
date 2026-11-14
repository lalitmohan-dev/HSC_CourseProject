"""Case-study simulation for the course report.

Builds an edge-detection image pipeline on a CPU + DSP + FPGA platform, runs the
real DSE engine (lowering -> evaluator -> search -> Pareto -> recommendation) and
writes figures + a JSON summary into ../figures and ../data.

Run from dse/backend:  python ../../docs/report/scripts/case_study.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent
BACKEND = REPORT.parent.parent / "dse" / "backend"
sys.path.insert(0, str(BACKEND))

from app.ir.models import (  # noqa: E402
    ArchitectureGraph, ComputeNode, ConstraintsIR, DataEdge, MappingIR, MappingOption,
    ObjectivesIR, ProblemGraph, ProjectIR, ProjectMetadata, ResourceIR, SearchSettings,
)
from app.ir.types import ResourceKind, SearchStrategy  # noqa: E402
from app.ir.lowering import lower_problem  # noqa: E402
from app.ir.validator import validate_project  # noqa: E402
from app.search.runner import execute_search  # noqa: E402
from app.search.pareto import extract_pareto_front, recommend_design  # noqa: E402
from app.core.evaluator import evaluate_candidate, derive_canonical_allocation  # noqa: E402
from app.ir.models import CandidateDesign  # noqa: E402

FIG = REPORT / "figures" / "sim"
DATA = REPORT / "data"
FIG.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3,
                     "figure.dpi": 150, "savefig.bbox": "tight"})
C_FEAS, C_INF, C_PAR, C_REC = "#9aa5b1", "#e8b4b4", "#1f6fb2", "#d4a017"

FRAME_KB = 307.2  # 640x480, 8-bit grayscale


def build_project(bus_bw=400.0, deadline=16.67):
    tasks = [
        ("T0", "Capture", "CPU"), ("T1", "Histogram Eq.", None), ("T2", "Gaussian Blur", None),
        ("T3", "Sobel-X", None), ("T4", "Sobel-Y", None), ("T5", "Magnitude", None),
        ("T6", "Threshold/NMS", None), ("T7", "Output", "CPU"),
    ]
    nodes = [ComputeNode(id=i, name=n, memory_kb=FRAME_KB, fixed_resource_id=f) for i, n, f in tasks]
    edges_spec = [("T0", "T1"), ("T1", "T2"), ("T2", "T3"), ("T2", "T4"),
                  ("T3", "T5"), ("T4", "T5"), ("T5", "T6"), ("T6", "T7")]
    edges = [DataEdge(source_id=a, destination_id=b, data_kb=FRAME_KB, comm_id=f"C_{a}_{b}")
             for a, b in edges_spec]
    resources = [
        ResourceIR(id="CPU", name="ARM CPU", kind=ResourceKind.PROCESSOR, mandatory=True,
                   allocation_cost=10, static_power_mw=300),
        ResourceIR(id="DSP", name="DSP core", kind=ResourceKind.PROCESSOR, mandatory=False,
                   allocation_cost=15, static_power_mw=150),
        ResourceIR(id="FPGA", name="FPGA fabric", kind=ResourceKind.HW_MODULE, mandatory=False,
                   allocation_cost=30, static_power_mw=250, max_parallel=2,
                   capacity={"logic": 9000}),
        ResourceIR(id="AXI", name="AXI interconnect", kind=ResourceKind.BUS, mandatory=True,
                   allocation_cost=0, static_power_mw=40, power_mw=120,
                   connects=["CPU", "DSP", "FPGA"], bandwidth_mb_per_s=bus_bw,
                   setup_latency_ms=0.05, max_parallel=1),
    ]
    # (cpu_ms, cpu_mW, dsp_ms, dsp_mW, fpga_ms, fpga_mW, fpga_lut)
    costs = {
        "T1": (2.5, 900, 1.2, 400, 0.6, 180, 2000),
        "T2": (6.0, 1100, 2.5, 450, 1.2, 220, 4000),
        "T3": (4.0, 1000, 1.8, 420, 0.9, 200, 2500),
        "T4": (4.0, 1000, 1.8, 420, 0.9, 200, 2500),
        "T5": (3.0, 950, 1.2, 400, 0.6, 160, 1500),
        "T6": (3.5, 950, 2.0, 400, None, None, None),
    }
    opts = [MappingOption(node_id="T0", resource_id="CPU", execution_time_ms=1.0, active_power_mw=800),
            MappingOption(node_id="T7", resource_id="CPU", execution_time_ms=0.5, active_power_mw=800)]
    for t, (c, cp, d, dp, f, fp, lut) in costs.items():
        opts.append(MappingOption(node_id=t, resource_id="CPU", execution_time_ms=c, active_power_mw=cp))
        opts.append(MappingOption(node_id=t, resource_id="DSP", execution_time_ms=d, active_power_mw=dp))
        if f is not None:
            opts.append(MappingOption(node_id=t, resource_id="FPGA", execution_time_ms=f,
                                      active_power_mw=fp, usage={"logic": lut}))
    return ProjectIR(
        meta=ProjectMetadata(id="edge-detect", name="Edge-detection case study", time_unit="ms"),
        problem=ProblemGraph(nodes=nodes, edges=edges),
        architecture=ArchitectureGraph(resources=resources),
        mapping=MappingIR(options=opts),
        constraints=ConstraintsIR(max_latency_ms=deadline),
        objectives=ObjectivesIR(names=["latency", "allocation_cost", "energy", "area"]),
        settings=SearchSettings(strategy=SearchStrategy.EXHAUSTIVE, budget_evaluations=10000),
    )


def run(project, strategy, budget, seed=42, pop=20):
    s = project.settings.model_copy(update={"strategy": strategy, "budget_evaluations": budget,
                                            "seed": seed, "population_size": pop})
    return execute_search(lower_problem(project), s)


def lc(c):
    return c.evaluation.latency_ms, c.evaluation.area_usage.get("logic", 0.0)


def hv2d(points, ref):
    """2-D hypervolume (latency, logic area), minimisation, points assumed feasible."""
    pts = sorted(set(p for p in points if p[0] <= ref[0] and p[1] <= ref[1]))
    hv, best_c = 0.0, ref[1]
    for x, y in pts:
        if y < best_c:
            hv += (ref[0] - x) * (best_c - y)
            best_c = y
    return hv


def gantt(ax, cand, title):
    lanes = ["CPU", "DSP", "FPGA", "AXI"]
    for o in cand.evaluation.schedule.objects:
        if o.resource_id not in lanes or o.duration <= 0:
            continue
        y = lanes.index(o.resource_id)
        col = "#f0a35e" if o.is_communication else "#4c8bc9"
        ax.barh(y, o.duration, left=o.start_time, color=col, edgecolor="black", lw=0.4, height=0.6)
        if o.duration > 0.55 and not o.is_communication:
            ax.text(o.start_time + o.duration / 2, y, o.id, ha="center", va="center", fontsize=7, color="white")
    ax.set_yticks(range(len(lanes)), lanes)
    ax.invert_yaxis()
    ax.set_xlabel("time (ms)")
    ax.set_title(title, fontsize=9)


def main():
    proj = build_project()
    vr = validate_project(proj)
    assert vr.is_valid, vr
    lowered = lower_problem(proj)
    summary = {}

    # ---------- exhaustive ground truth ----------
    allc, pareto2, rec2, _ = run(proj, SearchStrategy.EXHAUSTIVE, 10000)
    objs3 = ["latency", "allocation_cost", "energy", "area"]
    pareto3 = extract_pareto_front(allc, objs3)
    rec3, rec3d = recommend_design(pareto3, objs3, None)
    pareto_lc = extract_pareto_front(allc, ["latency", "area"])
    feas = [c for c in allc if c.evaluation.feasible]
    infeas = [c for c in allc if not c.evaluation.feasible]
    reasons = {}
    for c in infeas:
        for v in c.evaluation.violations:
            reasons[v.metric] = reasons.get(v.metric, 0) + 1
    summary["space_size"] = len(allc)
    summary["feasible"] = len(feas)
    summary["infeasible"] = len(infeas)
    summary["violation_counts"] = reasons
    summary["pareto3_size"] = len(pareto3)
    summary["pareto2_size"] = len(pareto_lc)

    def row(c):
        e = c.evaluation
        return {"id": c.id, "bindings": {k: v for k, v in sorted(c.bindings.items()) if k not in ("T0", "T7")},
                "latency_ms": round(e.latency_ms, 3), "cost": e.allocation_cost,
                "energy_mj": round(e.energy_mj, 3) if e.energy_mj is not None else None,
                "power_w": round(e.avg_power_w, 3) if e.avg_power_w is not None else None,
                "fps": round(e.throughput_fps, 2) if e.throughput_fps else None,
                "logic": e.area_usage.get("logic", 0.0), "feasible": e.feasible}

    summary["pareto3"] = sorted([row(c) for c in pareto3], key=lambda r: r["latency_ms"])
    summary["recommended3"] = row(rec3)
    summary["rec_rationale"] = rec3d.rationale
    for tag, w in {"latency_heavy": {"latency": 0.7, "allocation_cost": 0.1, "energy": 0.1, "area": 0.1},
                   "cost_heavy": {"latency": 0.1, "allocation_cost": 0.7, "energy": 0.1, "area": 0.1}}.items():
        rc, rd = recommend_design(pareto3, objs3, w)
        summary["rec_" + tag] = row(rc)
    summary["rec_scores_equal"] = {k: round(v, 3) for k, v in rec3d.normalized_scores.items()}
    sw = next(c for c in allc if all(v == "CPU" for v in c.bindings.values()))
    summary["all_sw"] = row(sw)
    fastest_any = min(allc, key=lambda c: c.evaluation.latency_ms)
    summary["fastest_any"] = row(fastest_any)

    # ---------- Fig: latency vs cost ----------
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    ax.scatter(*zip(*[lc(c) for c in infeas]), s=10, c=C_INF, label=f"infeasible ({len(infeas)})", marker="x")
    ax.scatter(*zip(*[lc(c) for c in feas]), s=12, c=C_FEAS, label=f"feasible ({len(feas)})")
    pf = sorted(lc(c) for c in pareto_lc)
    ax.step([p[0] for p in pf], [p[1] for p in pf], where="post", c=C_PAR, lw=1)
    ax.scatter(*zip(*pf), s=40, c=C_PAR, label=f"Pareto front ({len(pf)})", zorder=3)
    ax.scatter(*lc(sw), s=70, marker="s", facecolors="none", edgecolors="black", label="all-software", zorder=4)
    ax.axvline(16.67, ls="--", c="red", lw=0.8)
    ax.text(16.8, ax.get_ylim()[1] * 0.95, "deadline\n16.67 ms", color="red", fontsize=7, va="top")
    ax.axhline(9000, ls=":", c="purple", lw=0.8)
    ax.text(ax.get_xlim()[1], 9150, "FPGA capacity 9000 LUT ", color="purple", fontsize=7, ha="right")
    ax.set_xlabel("latency (ms)")
    ax.set_ylabel("FPGA logic usage (LUT)")
    ax.legend(fontsize=7, loc="upper right")
    fig.savefig(FIG / "pareto_latency_area.pdf")
    fig.savefig(FIG / "pareto_latency_area.png")
    plt.close(fig)

    # ---------- Fig: latency vs energy (3-obj front) ----------
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    le = lambda c: (c.evaluation.latency_ms, c.evaluation.energy_mj)  # noqa: E731
    ax.scatter(*zip(*[le(c) for c in infeas]), s=10, c=C_INF, marker="x", label="infeasible")
    ax.scatter(*zip(*[le(c) for c in feas]), s=12, c=C_FEAS, label="feasible")
    sc = ax.scatter(*zip(*[le(c) for c in pareto3]), s=45,
                    c=[c.evaluation.allocation_cost for c in pareto3], cmap="viridis",
                    edgecolors="black", lw=0.4, label="4-objective Pareto set", zorder=3)
    ax.scatter(*le(rec3), s=220, marker="*", c=C_REC, edgecolors="black", label="recommended", zorder=4)
    fig.colorbar(sc, ax=ax, label="allocation cost")
    ax.axvline(16.67, ls="--", c="red", lw=0.8)
    ax.set_xlabel("latency (ms)")
    ax.set_ylabel("energy per frame (mJ)")
    ax.legend(fontsize=7, loc="upper right")
    fig.savefig(FIG / "pareto_latency_energy.pdf")
    fig.savefig(FIG / "pareto_latency_energy.png")
    plt.close(fig)

    # ---------- Fig: Gantt all-SW vs recommended ----------
    fig, axes = plt.subplots(2, 1, figsize=(6.2, 3.8), sharex=True)
    gantt(axes[0], sw, f"All-software: {sw.evaluation.latency_ms:.2f} ms (misses deadline)")
    gantt(axes[1], rec3, f"Recommended: {rec3.evaluation.latency_ms:.2f} ms")
    for a in axes:
        a.axvline(16.67, ls="--", c="red", lw=0.8)
    axes[0].set_xlabel("")
    from matplotlib.patches import Patch
    axes[0].legend(handles=[Patch(color="#4c8bc9", label="compute"), Patch(color="#f0a35e", label="bus transfer")],
                   fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "gantt_sw_vs_rec.pdf")
    fig.savefig(FIG / "gantt_sw_vs_rec.png")
    plt.close(fig)

    # ---------- Strategy comparison (2-D hypervolume, latency x cost) ----------
    ref = (max(c.evaluation.latency_ms for c in allc) * 1.05, max(lc(c)[1] for c in allc) * 1.05 + 1)
    true_hv = hv2d([lc(c) for c in pareto_lc], ref)
    true_set = {tuple(sorted(c.bindings.items())) for c in pareto_lc}
    budgets = [20, 40, 60, 100, 150]
    seeds = [1, 2, 3, 4, 5]
    strat = {"Random": SearchStrategy.RANDOM, "Greedy": SearchStrategy.GREEDY, "NSGA-II": SearchStrategy.NSGA2}
    comp = {}
    for name, st in strat.items():
        comp[name] = []
        for b in budgets:
            hvs, recalls, evals = [], [], []
            for sd in seeds:
                ev, pf_, _, _ = run(proj, st, b, seed=sd, pop=10)
                pfl = extract_pareto_front(ev, ["latency", "area"])
                fl = [lc(c) for c in pfl if c.evaluation.feasible]
                hvs.append(hv2d(fl, ref) / true_hv)
                recalls.append(len({tuple(sorted(c.bindings.items())) for c in pfl} & true_set) / len(true_set))
                evals.append(len(ev))
            comp[name].append({"budget": b, "hv_mean": sum(hvs) / len(hvs), "hv_min": min(hvs), "hv_max": max(hvs),
                               "recall_mean": sum(recalls) / len(recalls), "evals_mean": sum(evals) / len(evals),
                               "evals_max": max(evals)})
    summary["strategy_comparison"] = comp

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8))
    for name, rows in comp.items():
        x = [r["budget"] for r in rows]
        axes[0].plot(x, [r["hv_mean"] for r in rows], marker="o", label=name)
        axes[0].fill_between(x, [r["hv_min"] for r in rows], [r["hv_max"] for r in rows], alpha=0.15)
        axes[1].plot(x, [r["recall_mean"] for r in rows], marker="o", label=name)
    axes[0].axhline(1.0, c="black", ls=":", lw=0.8)
    axes[0].set_title("normalised hypervolume (1 = exhaustive)", fontsize=9)
    axes[1].set_title("fraction of true Pareto designs found", fontsize=9)
    for a in axes:
        a.set_xlabel("evaluation budget")
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "strategy_comparison.pdf")
    fig.savefig(FIG / "strategy_comparison.png")
    plt.close(fig)

    # ---------- Bandwidth sensitivity ----------
    bws = [25, 50, 100, 200, 400, 800, 1600]
    sens = []
    for bw in bws:
        p = build_project(bus_bw=bw)
        ev, _, _, _ = run(p, SearchStrategy.EXHAUSTIVE, 10000)
        swc = next(c for c in ev if all(v == "CPU" for v in c.bindings.values()))
        cap_ok = [c for c in ev if not any(v.metric.startswith("capacity") for v in c.evaluation.violations)]
        best = min(cap_ok, key=lambda c: c.evaluation.latency_ms)
        nf = sum(c.evaluation.feasible for c in ev)
        sens.append({"bw": bw, "sw_ms": swc.evaluation.latency_ms, "best_ms": best.evaluation.latency_ms,
                     "best_bind": {k: v for k, v in sorted(best.bindings.items()) if k not in ("T0", "T7")},
                     "n_feasible": nf, "n_hw_tasks": sum(v != "CPU" for v in best.bindings.values())})
    summary["bw_sensitivity"] = sens
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    ax.plot(bws, [s["sw_ms"] for s in sens], marker="s", label="all-software")
    ax.plot(bws, [s["best_ms"] for s in sens], marker="o", label="best capacity-legal mapping")
    ax.axhline(16.67, ls="--", c="red", lw=0.8, label="deadline")
    ax.set_xscale("log")
    ax.set_xlabel("AXI bandwidth (MB/s)")
    ax.set_ylabel("latency (ms)")
    for s in sens:
        ax.annotate(str(s["n_hw_tasks"]), (s["bw"], s["best_ms"]), textcoords="offset points", xytext=(0, -11),
                    fontsize=7, ha="center")
    ax.legend(fontsize=7)
    fig.savefig(FIG / "bw_sensitivity.pdf")
    fig.savefig(FIG / "bw_sensitivity.png")
    plt.close(fig)

    (DATA / "case_study_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("pareto3",)}, indent=1)[:6000])
    print("pareto3:")
    for r in summary["pareto3"]:
        print(r)


if __name__ == "__main__":
    main()

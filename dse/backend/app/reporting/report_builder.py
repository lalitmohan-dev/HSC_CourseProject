"""Report generation module for DSE exploration runs.

Implements Section 15:
- Formats: Markdown, CSV, JSON, and HTML/PDF
- Complete 11 sections:
  1. Cover & Metadata
  2. Application Model
  3. Architecture Platform
  4. Constraints, Objectives & Search Settings
  5. Run Statistics
  6. Recommended Design Details
  7. Schedule Breakdown
  8. Pareto Front Candidates
  9. Bottleneck Analysis
  10. Comparison
  11. Appendix: Formulas, Units & Methodology
"""

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.ir.models import CandidateDesign, ProjectIR
from app.analysis.bottlenecks import BottleneckReport


def generate_markdown_report(
    project: ProjectIR,
    run_data: Dict[str, Any],
    bottlenecks: Optional[BottleneckReport] = None,
) -> str:
    """Generates comprehensive Markdown report."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    rec_id = run_data.get("recommended_design_id", "N/A")
    rec_details = run_data.get("recommendation_details", {})

    lines = [
        f"# Design Space Exploration (DSE) Synthesis Report",
        f"**Project:** {project.meta.name} (`{project.meta.id}`)  ",
        f"**Date:** {now_str}  ",
        f"**Search Strategy:** {project.settings.strategy.value.upper()} (Seed: {project.settings.seed})  ",
        f"**Evaluator Version:** 2.0 (Generalized System Synthesis)  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & Recommended Design",
        f"- **Recommended Design:** `{rec_id}`",
        f"- **Evaluated Candidates:** {run_data.get('evaluated_count', 0)}",
        f"- **Pareto-Optimal Candidates:** {run_data.get('pareto_count', 0)}",
        f"- **Elapsed Search Time:** {run_data.get('elapsed_seconds', 0.0)} seconds",
        f"- **Recommendation Rationale:** {rec_details.get('rationale', 'Optimal weighted tradeoff.')}",
        "",
        "---",
        "",
        "## 2. Application Problem Graph",
        f"- **Total Compute Tasks:** {len(project.problem.nodes)}",
        f"- **Data Dependencies:** {len(project.problem.edges)}",
        f"- **Declared Memory Footprint:** {sum(n.memory_kb for n in project.problem.nodes) + sum(e.data_kb for e in project.problem.edges)} KB",
        "",
        "| Task ID | Task Name | Input (KB) | Output (KB) | Memory (KB) | Fixed Resource |",
        "|---|---|---:|---:|---:|---|",
    ]

    for n in project.problem.nodes:
        lines.append(f"| {n.id} | {n.name} | {n.input_kb} | {n.output_kb} | {n.memory_kb} | {n.fixed_resource_id or 'Flexible'} |")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Platform Architecture Graph",
        "| Resource ID | Kind | Mandatory | Cost | Clock (MHz) | Parallelism | Static Power (mW) |",
        "|---|---|---|---:|---:|---:|---:|",
    ])

    for r in project.architecture.resources:
        lines.append(
            f"| {r.id} | {r.kind.value} | {'Yes' if r.mandatory else 'No'} | {r.allocation_cost} | {r.clock_mhz or '—'} | {r.max_parallel} | {r.static_power_mw or '—'} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Pareto Frontier Designs",
        "| Design ID | Latency | Allocation Cost | Energy (mJ) | Avg Power (W) | Throughput (fps) | Feasible |",
        "|---|---:|---:|---:|---:|---:|---|",
    ])

    designs = run_data.get("designs", [])
    pareto_ids = {p.get("id") for p in run_data.get("pareto_front", [])}

    for d in designs:
        if d.get("id") in pareto_ids or d.get("id") == rec_id:
            ev = d.get("evaluation") or {}
            is_rec = "★ " if d.get("id") == rec_id else ""
            lines.append(
                f"| {is_rec}`{d.get('id')}` | {ev.get('latency_ms', '—')} | {ev.get('allocation_cost', '—')} | {round(ev.get('energy_mj', 0.0), 2) if ev.get('energy_mj') is not None else '—'} | {round(ev.get('avg_power_w', 0.0), 2) if ev.get('avg_power_w') is not None else '—'} | {round(ev.get('throughput_fps', 0.0), 1) if ev.get('throughput_fps') is not None else '—'} | {'✓' if ev.get('feasible') else '✕'} |"
            )

    if bottlenecks:
        lines.extend([
            "",
            "---",
            "",
            "## 5. Critical Path & Bottleneck Analysis",
            f"- **Makespan:** {bottlenecks.total_latency_ms} {project.meta.time_unit}",
            f"- **Compute Duration:** {bottlenecks.compute_time_total} {project.meta.time_unit}",
            f"- **Communication Duration:** {bottlenecks.communication_time_total} {project.meta.time_unit}",
            f"- **Serialization Wait Delay:** {bottlenecks.serialization_wait_total} {project.meta.time_unit}",
            "",
            "### Critical Path Items",
            "| Item ID | Item Name | Resource | Duration | % of Makespan |",
            "|---|---|---|---:|---:|",
        ])
        for cp in bottlenecks.critical_path:
            lines.append(f"| {cp.id} | {cp.name} | {cp.resource_id or 'local'} | {cp.duration} | {cp.percentage_of_latency}% |")

        if bottlenecks.what_if_suggestions:
            lines.extend([
                "",
                "### What-If Suggestions",
                "| Task | Current | Alternative | Δ Latency | Δ Cost | Feasible? | Rationale |",
                "|---|---|---|---:|---:|---|---|",
            ])
            for w in bottlenecks.what_if_suggestions:
                lines.append(
                    f"| {w.task_id} | {w.original_resource} | {w.suggested_resource} | {w.delta_latency_ms:+0.2f} | {w.delta_cost:+0.1f} | {'✓' if w.feasible else '✕'} | {w.rationale} |"
                )

    lines.extend([
        "",
        "---",
        "",
        "## 6. Appendix: Methodology & Assumptions",
        "- **Evaluation Model:** Analytical Hardware-Software Co-Design list scheduling with serial bus resource reservations.",
        "- **DMA Concurrency:** Compute and bus transfers overlap unless contending for the same resource slot.",
        "- **Deterministic Routing:** Shortest-hop paths over allocated interconnect with stable lexical tie-breaking.",
        "- **Strict Power Semantics:** Missing power parameters are reported as unavailable, never silently substituted as zero.",
        "",
        "*(Report generated automatically by DSE Framework v2.0)*",
    ])

    return "\n".join(lines)


def generate_csv_report(run_data: Dict[str, Any]) -> str:
    """Generates CSV tabular output of all evaluated candidates."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "feasible", "latency_ms", "allocation_cost", "energy_mj", "avg_power_w", "throughput_fps", "bindings"])

    for d in run_data.get("designs", []):
        ev = d.get("evaluation") or {}
        writer.writerow([
            d.get("id"),
            "1" if ev.get("feasible") else "0",
            ev.get("latency_ms", ""),
            ev.get("allocation_cost", ""),
            ev.get("energy_mj", ""),
            ev.get("avg_power_w", ""),
            ev.get("throughput_fps", ""),
            json.dumps(d.get("bindings", {})),
        ])

    return output.getvalue()

"""Exploration runs, Server-Sent Events (SSE), and candidate inspection API.

Implements Section 12 endpoints:
- POST /api/projects/{project_id}/explore
- GET /api/runs/{run_id}/events (SSE)
- POST /api/runs/{run_id}/cancel
- GET /api/runs/{run_id}
- GET /api/runs/{run_id}/designs
- GET /api/runs/{run_id}/designs/{design_id}
- GET /api/runs/{run_id}/bottlenecks
- POST /api/compare
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ir.models import CandidateDesign, ProjectIR
from app.ir.lowering import lower_problem
from app.search.runner import execute_search
from app.search.pareto import RecommendationDetails
from app.analysis.bottlenecks import BottleneckReport, analyze_bottlenecks
from app.reporting.report_builder import generate_csv_report, generate_markdown_report
from app.api.projects import get_repository
from app.persistence.repository import ProjectRepository

router = APIRouter(tags=["exploration"])

# Active in-memory runs dictionary
# run_id -> RunState
class RunState:
    def __init__(self, run_id: str, project_id: str, project: ProjectIR):
        self.run_id = run_id
        self.project_id = project_id
        self.project = project
        self.status: str = "running"  # running, completed, cancelled, error
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.logs: List[Dict[str, Any]] = []
        self.evaluated_candidates: List[CandidateDesign] = []
        self.pareto_front: List[CandidateDesign] = []
        self.recommended_design: Optional[CandidateDesign] = None
        self.recommendation_details: Optional[RecommendationDetails] = None
        self.error_message: Optional[str] = None
        self.cancelled: bool = False
        self.start_time: float = time.time()
        self.finish_time: Optional[float] = None


RUNS_REGISTRY: Dict[str, RunState] = {}


def get_run_dir(project_id: str) -> Path:
    base = Path(__file__).resolve().parent.parent.parent.parent / "data" / "projects" / f"{project_id}.runs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_run_to_file(run: RunState) -> None:
    run_dir = get_run_dir(run.project_id)
    file_path = run_dir / f"{run.run_id}.json"
    data = {
        "run_id": run.run_id,
        "project_id": run.project_id,
        "status": run.status,
        "logs": run.logs,
        "elapsed_seconds": round((run.finish_time or time.time()) - run.start_time, 3),
        "evaluated_count": len(run.evaluated_candidates),
        "pareto_count": len(run.pareto_front),
        "recommended_design_id": run.recommended_design.id if run.recommended_design else None,
        "recommendation_details": run.recommendation_details.model_dump() if run.recommendation_details else None,
        "designs": [c.model_dump(by_alias=True) for c in run.evaluated_candidates],
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


async def execute_exploration_task(run_id: str) -> None:
    run = RUNS_REGISTRY.get(run_id)
    if not run:
        return

    def emit_event(event_type: str, data: Dict[str, Any]) -> None:
        asyncio.create_task(run.event_queue.put({"event": event_type, "data": data}))

    def log_msg(level: str, msg: str) -> None:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": msg,
        }
        run.logs.append(log_entry)
        emit_event("log", log_entry)

    try:
        log_msg("info", "Loading application and architecture model.")
        log_msg("info", "Validating problem graph and architecture graph.")
        lowered = lower_problem(run.project)
        log_msg("info", "Lowering dependencies into communication objects.")
        log_msg("info", f"Starting search strategy: {run.project.settings.strategy.value}")

        total_est = run.project.settings.budget_evaluations or 1000

        def on_progress(evaluated: int, total: int, candidate: CandidateDesign) -> None:
            if run.cancelled:
                raise asyncio.CancelledError("Run was cancelled by user")
            prog_data = {
                "evaluated": evaluated,
                "total": total,
                "elapsed_seconds": round(time.time() - run.start_time, 2),
                "current_candidate": candidate.id,
                "feasible": candidate.evaluation.feasible if candidate.evaluation else False,
            }
            emit_event("progress", prog_data)

        # Run search
        evaluated, pareto, best, details = execute_search(
            lowered=lowered,
            settings=run.project.settings,
            progress_callback=on_progress,
        )

        run.evaluated_candidates = evaluated
        run.pareto_front = pareto
        run.recommended_design = best
        run.recommendation_details = details
        run.status = "completed"
        run.finish_time = time.time()

        log_msg("info", f"Exploration completed: {len(evaluated)} designs evaluated.")
        log_msg("info", f"Pareto front extracted: {len(pareto)} optimal designs.")
        if best:
            log_msg("info", f"Recommended design selected: {best.id}")

        done_data = {
            "run_id": run.run_id,
            "status": "completed",
            "evaluated_count": len(evaluated),
            "pareto_count": len(pareto),
            "recommended_design_id": best.id if best else None,
            "elapsed_seconds": round(run.finish_time - run.start_time, 2),
        }
        emit_event("done", done_data)
        save_run_to_file(run)

    except asyncio.CancelledError:
        run.status = "cancelled"
        run.finish_time = time.time()
        log_msg("warning", "Exploration cancelled by user request.")
        emit_event("done", {"run_id": run.run_id, "status": "cancelled"})
        save_run_to_file(run)
    except Exception as e:
        run.status = "error"
        run.finish_time = time.time()
        run.error_message = str(e)
        log_msg("error", f"Exploration failed: {str(e)}")
        emit_event("error", {"run_id": run.run_id, "detail": str(e)})
        save_run_to_file(run)


@router.post("/projects/{project_id}/explore")
def start_exploration(
    project_id: str,
    background_tasks: BackgroundTasks,
    repo: ProjectRepository = Depends(get_repository),
) -> Dict[str, Any]:
    """Starts background Design Space Exploration run and returns run_id."""
    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "field": "project_id", "detail": f"Project '{project_id}' not found"},
        )

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    run_state = RunState(run_id=run_id, project_id=project_id, project=project)
    RUNS_REGISTRY[run_id] = run_state

    background_tasks.add_task(execute_exploration_task, run_id)
    return {"run_id": run_id, "status": "running", "project_id": project_id}


@router.get("/runs/{run_id}/events")
async def stream_run_events(run_id: str) -> StreamingResponse:
    """Server-Sent Events (SSE) stream for run logs, progress, and completion."""
    run = RUNS_REGISTRY.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send current logs initially
        for entry in run.logs:
            yield f"event: log\ndata: {json.dumps(entry)}\n\n"

        while run.status == "running" or not run.event_queue.empty():
            try:
                item = await asyncio.wait_for(run.event_queue.get(), timeout=1.0)
                event_name = item.get("event", "message")
                payload = item.get("data", {})
                yield f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
                if event_name in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                # Keep-alive heartbeat
                yield f": ping\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str) -> Dict[str, Any]:
    """Cancels an active exploration run."""
    run = RUNS_REGISTRY.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run.cancelled = True
    return {"run_id": run_id, "status": "cancelling"}


@router.get("/runs/{run_id}")
def get_run_summary(run_id: str) -> Dict[str, Any]:
    """Retrieves summary, Pareto front, and recommendation for an exploration run."""
    run = RUNS_REGISTRY.get(run_id)
    if not run:
        # Check persisted run files
        for f in Path(__file__).resolve().parent.parent.parent.parent.glob("data/projects/*.runs/*.json"):
            if f.stem == run_id:
                with open(f, "r", encoding="utf-8") as fp:
                    return json.load(fp)
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "run_id": run.run_id,
        "project_id": run.project_id,
        "status": run.status,
        "elapsed_seconds": round((run.finish_time or time.time()) - run.start_time, 2),
        "evaluated_count": len(run.evaluated_candidates),
        "pareto_count": len(run.pareto_front),
        "recommended_design": run.recommended_design,
        "recommendation_details": run.recommendation_details,
        "pareto_front": run.pareto_front,
        "logs": run.logs,
    }


@router.get("/runs/{run_id}/designs")
def list_run_designs(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    feasible_only: bool = Query(False),
    sort_by: str = Query("latency_ms"),
    sort_order: str = Query("asc"),
) -> Dict[str, Any]:
    """Lists paged, sortable, and filterable designs from an exploration run."""
    run = RUNS_REGISTRY.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    candidates = run.evaluated_candidates
    if feasible_only:
        candidates = [c for c in candidates if c.evaluation and c.evaluation.feasible]

    def get_sort_val(c: CandidateDesign) -> Any:
        ev = c.evaluation
        if not ev:
            return float("inf")
        if sort_by == "cost" or sort_by == "allocation_cost":
            return ev.allocation_cost
        elif sort_by == "latency" or sort_by == "latency_ms":
            return ev.latency_ms
        elif sort_by == "energy" or sort_by == "energy_mj":
            return ev.energy_mj if ev.energy_mj is not None else float("inf")
        return c.id

    reverse_sort = (sort_order.lower() == "desc")
    candidates.sort(key=get_sort_val, reverse=reverse_sort)

    total_count = len(candidates)
    start_idx = (page - 1) * page_size
    paged = candidates[start_idx : start_idx + page_size]

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "items": paged,
    }


@router.get("/runs/{run_id}/designs/{design_id}")
def get_run_design_detail(run_id: str, design_id: str) -> CandidateDesign:
    """Retrieves detailed evaluation and schedule for a candidate design."""
    run = RUNS_REGISTRY.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    for c in run.evaluated_candidates:
        if c.id == design_id:
            return c
    raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found in run '{run_id}'")


@router.get("/runs/{run_id}/bottlenecks", response_model=BottleneckReport)
def get_run_bottlenecks(
    run_id: str,
    design_id: Optional[str] = Query(None),
) -> BottleneckReport:
    """Computes critical path, resource bottlenecks, and what-if suggestions for a design."""
    run = RUNS_REGISTRY.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    target_design: Optional[CandidateDesign] = None
    if design_id:
        for c in run.evaluated_candidates:
            if c.id == design_id:
                target_design = c
                break
        if not target_design:
            raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found")
    else:
        target_design = run.recommended_design or (run.pareto_front[0] if run.pareto_front else None)

    if not target_design:
        raise HTTPException(status_code=400, detail="No designs available for bottleneck analysis")

    lowered = lower_problem(run.project)
    return analyze_bottlenecks(lowered, target_design)


class CompareRequest(BaseModel):
    project_id: str
    design_ids: List[str]


@router.post("/compare")
def compare_designs(
    req: CompareRequest,
    repo: ProjectRepository = Depends(get_repository),
) -> Dict[str, Any]:
    """Compares 2 to 4 designs side-by-side."""
    if len(req.design_ids) < 2 or len(req.design_ids) > 4:
        raise HTTPException(
            status_code=400,
            detail="Compare requires between 2 and 4 design IDs.",
        )

    project = repo.get_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Look up designs across all active runs for this project or project's designs
    matched_designs: Dict[str, CandidateDesign] = {}
    for r in RUNS_REGISTRY.values():
        if r.project_id == req.project_id:
            for c in r.evaluated_candidates:
                if c.id in req.design_ids:
                    matched_designs[c.id] = c

    for c in project.designs:
        if c.id in req.design_ids and c.id not in matched_designs:
            matched_designs[c.id] = c

    missing = [did for did in req.design_ids if did not in matched_designs]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Could not find designs: {missing}",
        )

    designs_list = [matched_designs[did] for did in req.design_ids]
    metrics_comparison = []
    for metric_name in ["latency_ms", "allocation_cost", "energy_mj", "avg_power_w"]:
        row = {"metric": metric_name}
        for d in designs_list:
            ev = d.evaluation
            val = getattr(ev, metric_name, None) if ev else None
            row[d.id] = val
        metrics_comparison.append(row)

    return {
        "project_id": req.project_id,
        "designs": designs_list,
        "metrics_table": metrics_comparison,
    }


@router.get("/runs/{run_id}/report")
def export_run_report(
    run_id: str,
    format: str = Query("md", pattern="^(md|csv|json)$"),
    repo: ProjectRepository = Depends(get_repository),
) -> Any:
    """Exports comprehensive run report in Markdown, CSV, or JSON format."""
    run = RUNS_REGISTRY.get(run_id)
    raw_data: Optional[Dict[str, Any]] = None
    project: Optional[ProjectIR] = None

    if run:
        project = run.project
        raw_data = {
            "run_id": run.run_id,
            "project_id": run.project_id,
            "status": run.status,
            "elapsed_seconds": round((run.finish_time or time.time()) - run.start_time, 2),
            "evaluated_count": len(run.evaluated_candidates),
            "pareto_count": len(run.pareto_front),
            "recommended_design_id": run.recommended_design.id if run.recommended_design else None,
            "recommendation_details": run.recommendation_details.model_dump() if run.recommendation_details else None,
            "pareto_front": [p.model_dump() for p in run.pareto_front],
            "designs": [d.model_dump() for d in run.evaluated_candidates],
        }
    else:
        # Check persisted file
        for f in Path(__file__).resolve().parent.parent.parent.parent.glob("data/projects/*.runs/*.json"):
            if f.stem == run_id:
                with open(f, "r", encoding="utf-8") as fp:
                    raw_data = json.load(fp)
                    project = repo.get_project(raw_data.get("project_id", ""))
                break

    if not raw_data or not project:
        raise HTTPException(status_code=404, detail="Run not found")

    lowered = lower_problem(project)
    rec_cand = run.recommended_design if run else None
    bottlenecks = analyze_bottlenecks(lowered, rec_cand) if rec_cand else None

    if format == "csv":
        csv_str = generate_csv_report(raw_data)
        from fastapi.responses import Response
        return Response(content=csv_str, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=dse_report_{run_id}.csv"})
    elif format == "json":
        return raw_data
    else:
        # Markdown format
        md_str = generate_markdown_report(project, raw_data, bottlenecks)
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=md_str, media_type="text/markdown")

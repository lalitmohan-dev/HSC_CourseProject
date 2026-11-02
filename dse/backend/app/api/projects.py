"""FastAPI REST router for Projects management and evaluation.

Implements Section 12 endpoints:
- GET /projects: List projects
- POST /projects: Create project
- GET /projects/{id}: Read project
- PUT /projects/{id}: Update project
- DELETE /projects/{id}: Delete project
- POST /projects/import: Import and validate project JSON
- GET /projects/{id}/export: Export project JSON
- GET /projects/{id}/ir: Inspect lowered intermediate representation
- POST /projects/{id}/validate: Validate schema, DAG, and mappings
- POST /projects/{id}/evaluate: Evaluate a candidate design
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.ir.models import CandidateDesign, EvaluationResult, ProjectIR, ProjectMetadata
from app.ir.validator import ValidationResult, validate_project
from app.ir.lowering import lower_problem
from app.core.evaluator import evaluate_candidate
from app.persistence.repository import JsonFileProjectRepository, ProjectRepository

router = APIRouter(prefix="/projects", tags=["projects"])


def get_repository() -> ProjectRepository:
    """Dependency provider for ProjectRepository."""
    return JsonFileProjectRepository()


@router.get("", response_model=List[ProjectMetadata])
def list_projects(repo: ProjectRepository = Depends(get_repository)) -> List[ProjectMetadata]:
    """List metadata for all saved projects."""
    return repo.list_projects()


@router.post("", response_model=ProjectIR, status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectIR, repo: ProjectRepository = Depends(get_repository)) -> ProjectIR:
    """Create a new project."""
    return repo.save_project(project)


@router.get("/{project_id}", response_model=ProjectIR)
def get_project(project_id: str, repo: ProjectRepository = Depends(get_repository)) -> ProjectIR:
    """Retrieve full project by ID."""
    proj = repo.get_project(project_id)
    if not proj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "field": "project_id", "detail": f"Project '{project_id}' not found"},
        )
    return proj


@router.put("/{project_id}", response_model=ProjectIR)
def update_project(project_id: str, project: ProjectIR, repo: ProjectRepository = Depends(get_repository)) -> ProjectIR:
    """Save/update an existing project."""
    project.meta.id = project_id
    return repo.save_project(project)


@router.delete("/{project_id}")
def delete_project(project_id: str, repo: ProjectRepository = Depends(get_repository)) -> Dict[str, Any]:
    """Delete a project by ID."""
    deleted = repo.delete_project(project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "field": "project_id", "detail": f"Project '{project_id}' not found"},
        )
    return {"deleted": True, "id": project_id}


@router.post("/import", response_model=Dict[str, Any])
def import_project(payload: Dict[str, Any], repo: ProjectRepository = Depends(get_repository)) -> Dict[str, Any]:
    """Import and validate project JSON."""
    try:
        project = ProjectIR.model_validate(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation_error", "field": "payload", "detail": str(e)},
        )

    validation = validate_project(project)
    saved = repo.save_project(project)
    return {
        "project": saved,
        "validation": validation,
    }


@router.get("/{project_id}/export")
def export_project(project_id: str, repo: ProjectRepository = Depends(get_repository)) -> ProjectIR:
    """Export project JSON."""
    return get_project(project_id, repo)


@router.get("/{project_id}/ir")
def get_lowered_ir(project_id: str, repo: ProjectRepository = Depends(get_repository)) -> Dict[str, Any]:
    """Return lowered IR for inspection and debugging."""
    proj = get_project(project_id, repo)
    try:
        lowered = lower_problem(proj)
        return {
            "project_id": project_id,
            "tasks": list(lowered.nodes_by_id.keys()),
            "resources": list(lowered.resources_by_id.keys()),
            "buses": list(lowered.buses_by_id.keys()),
            "communication_objects": [
                {
                    "id": c.id,
                    "source": c.source_node_id,
                    "destination": c.destination_node_id,
                    "data_kb": c.data_kb,
                }
                for c in lowered.comm_objects
            ],
            "resolved_mappings": {
                node_id: {res_id: opt.execution_time_ms for res_id, opt in opts.items()}
                for node_id, opts in lowered.mapping_options_by_node.items()
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "lowering_error", "field": "ir", "detail": str(e)},
        )


@router.post("/{project_id}/validate", response_model=ValidationResult)
def validate_project_endpoint(project_id: str, repo: ProjectRepository = Depends(get_repository)) -> ValidationResult:
    """Validate schema, DAG acyclicity, mappings, and architecture connectivity."""
    proj = get_project(project_id, repo)
    return validate_project(proj)


@router.post("/{project_id}/evaluate", response_model=EvaluationResult)
def evaluate_project_design(
    project_id: str,
    candidate: CandidateDesign,
    repo: ProjectRepository = Depends(get_repository),
) -> EvaluationResult:
    """Evaluate one manually specified design candidate."""
    proj = get_project(project_id, repo)
    try:
        lowered = lower_problem(proj)
        return evaluate_candidate(lowered, candidate)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "evaluation_error", "field": "candidate", "detail": str(e)},
        )

from fastapi import APIRouter

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects():
    return []

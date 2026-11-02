"""API integration tests for Projects endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ir.models import CandidateDesign, ProjectIR
from app.persistence.repository import JsonFileProjectRepository

client = TestClient(app)


def test_list_projects_includes_seeded():
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) >= 2
    ids = [p["id"] for p in projects]
    assert "golden-slide" in ids
    assert "synthetic-walkthrough" in ids


def test_get_project_by_id():
    response = client.get("/api/projects/golden-slide")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["id"] == "golden-slide"
    assert len(data["problem"]["nodes"]) == 4
    assert len(data["problem"]["edges"]) == 3


def test_get_unknown_project_404():
    response = client.get("/api/projects/non-existent-id")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "not_found"


def test_create_and_delete_project(tmp_path):
    new_proj = {
        "meta": {"name": "CRUD Test Project", "time_unit": "ms"},
        "problem": {"nodes": [{"id": "N1", "name": "Node 1"}], "edges": []},
        "architecture": {"resources": [{"id": "R1", "name": "Res 1", "kind": "processor"}]},
        "mapping": {"options": [{"node_id": "N1", "resource_id": "R1", "execution_time_ms": 5.0}]},
    }
    # Create
    create_res = client.post("/api/projects", json=new_proj)
    assert create_res.status_code == 201
    created_data = create_res.json()
    proj_id = created_data["meta"]["id"]
    assert proj_id is not None

    # Read
    get_res = client.get(f"/api/projects/{proj_id}")
    assert get_res.status_code == 200
    assert get_res.json()["meta"]["name"] == "CRUD Test Project"

    # Update
    update_payload = created_data
    update_payload["meta"]["description"] = "Updated description"
    put_res = client.put(f"/api/projects/{proj_id}", json=update_payload)
    assert put_res.status_code == 200
    assert put_res.json()["meta"]["description"] == "Updated description"

    # Delete
    del_res = client.delete(f"/api/projects/{proj_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Verify 404 after delete
    get_after_del = client.get(f"/api/projects/{proj_id}")
    assert get_after_del.status_code == 404


def test_validate_project_endpoint():
    response = client.post("/api/projects/golden-slide/validate")
    assert response.status_code == 200
    validation = response.json()
    assert validation["is_valid"] is True
    assert len(validation["errors"]) == 0


def test_lowered_ir_endpoint():
    response = client.get("/api/projects/golden-slide/ir")
    assert response.status_code == 200
    ir_data = response.json()
    assert ir_data["project_id"] == "golden-slide"
    assert "V1" in ir_data["tasks"]
    assert "RISC" in ir_data["resources"]
    assert len(ir_data["communication_objects"]) == 3


def test_evaluate_candidate_via_api():
    candidate_payload = {
        "id": "eval_test",
        "bindings": {
            "V1": "RISC",
            "V2": "RISC",
            "V3": "RISC",
            "V4": "HWM1",
        },
        "allocated_resources": ["RISC", "SB", "HWM1"],
        "priority_order": ["V1", "V2", "V3", "V5", "V6", "V7", "V4"],
    }
    response = client.post("/api/projects/golden-slide/evaluate", json=candidate_payload)
    assert response.status_code == 200
    result = response.json()
    assert result["feasible"] is True
    assert result["latency_ms"] == 32.0


def test_import_and_export():
    export_res = client.get("/api/projects/synthetic-walkthrough/export")
    assert export_res.status_code == 200
    project_json = export_res.json()
    assert project_json["meta"]["id"] == "synthetic-walkthrough"

    # Modify id and import
    project_json["meta"]["id"] = "imported-walkthrough"
    project_json["meta"]["name"] = "Imported Walkthrough"
    import_res = client.post("/api/projects/import", json=project_json)
    assert import_res.status_code == 200
    import_data = import_res.json()
    assert import_data["validation"]["is_valid"] is True
    assert import_data["project"]["meta"]["id"] == "imported-walkthrough"

    # Clean up imported
    client.delete("/api/projects/imported-walkthrough")

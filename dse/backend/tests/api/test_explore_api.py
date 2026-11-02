"""API integration tests for exploration runs, SSE progress streaming, and bottlenecks."""

import json
import time
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_exploration_lifecycle_and_summary():
    # 1. Start exploration on synthetic walkthrough
    res = client.post("/api/projects/synthetic-walkthrough/explore")
    assert res.status_code == 200
    data = res.json()
    run_id = data["run_id"]
    assert data["status"] == "running"

    # 2. Wait for completion
    completed = False
    for _ in range(30):
        time.sleep(0.1)
        summary_res = client.get(f"/api/runs/{run_id}")
        if summary_res.status_code == 200:
            s_data = summary_res.json()
            if s_data["status"] == "completed":
                completed = True
                break

    assert completed is True
    assert s_data["evaluated_count"] >= 2
    assert s_data["pareto_count"] >= 1
    assert s_data["recommended_design"] is not None

    # 3. List designs
    designs_res = client.get(f"/api/runs/{run_id}/designs")
    assert designs_res.status_code == 200
    d_list = designs_res.json()
    assert d_list["total"] >= 2
    first_id = d_list["items"][0]["id"]

    # 4. Get design detail
    detail_res = client.get(f"/api/runs/{run_id}/designs/{first_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == first_id
    assert detail["evaluation"] is not None

    # 5. Bottleneck Analysis
    bn_res = client.get(f"/api/runs/{run_id}/bottlenecks?design_id={first_id}")
    assert bn_res.status_code == 200
    bn = bn_res.json()
    assert bn["design_id"] == first_id
    assert len(bn["critical_path"]) >= 1
    assert len(bn["resource_utilization"]) >= 1

    # 6. Compare designs
    if d_list["total"] >= 2:
        id1 = d_list["items"][0]["id"]
        id2 = d_list["items"][1]["id"]
        cmp_res = client.post("/api/compare", json={"project_id": "synthetic-walkthrough", "design_ids": [id1, id2]})
        assert cmp_res.status_code == 200
        cmp_data = cmp_res.json()
        assert len(cmp_data["designs"]) == 2
        assert len(cmp_data["metrics_table"]) >= 1

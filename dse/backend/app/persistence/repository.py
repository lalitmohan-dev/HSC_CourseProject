"""Project persistence repository for the DSE framework.

Implements storage of ProjectIR documents as JSON files under data/projects/<id>.json
behind a clean ProjectRepository interface.
"""

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.ir.models import (
    ArchitectureGraph,
    ComputeNode,
    DataEdge,
    MappingIR,
    MappingOption,
    ProblemGraph,
    ProjectIR,
    ProjectMetadata,
    ResourceIR,
    SearchSettings,
)
from app.ir.types import ResourceKind


class ProjectRepository(ABC):
    """Abstract interface for storing and retrieving DSE projects."""

    @abstractmethod
    def list_projects(self) -> List[ProjectMetadata]:
        """Return metadata for all persisted projects."""
        pass

    @abstractmethod
    def get_project(self, project_id: str) -> Optional[ProjectIR]:
        """Retrieve full ProjectIR by ID."""
        pass

    @abstractmethod
    def save_project(self, project: ProjectIR) -> ProjectIR:
        """Create or update a ProjectIR."""
        pass

    @abstractmethod
    def delete_project(self, project_id: str) -> bool:
        """Delete project by ID. Returns True if deleted, False if not found."""
        pass

    @abstractmethod
    def exists(self, project_id: str) -> bool:
        """Check if project exists."""
        pass


class JsonFileProjectRepository(ProjectRepository):
    """File-system JSON repository storing each project at <storage_dir>/<id>.json."""

    def __init__(self, storage_dir: Optional[Path] = None):
        if storage_dir is None:
            # Default to dse/data/projects relative to backend
            base = Path(__file__).resolve().parent.parent.parent.parent / "data" / "projects"
            self.storage_dir = base
        else:
            self.storage_dir = Path(storage_dir)

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._seed_default_projects_if_empty()

    def _get_project_file(self, project_id: str) -> Path:
        return self.storage_dir / f"{project_id}.json"

    def list_projects(self) -> List[ProjectMetadata]:
        projects: List[ProjectMetadata] = []
        for p in self.storage_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    meta = ProjectMetadata.model_validate(data.get("meta", {}))
                    if not meta.id:
                        meta.id = p.stem
                    projects.append(meta)
            except Exception:
                continue
        # Sort by updated_at or name
        projects.sort(key=lambda m: m.updated_at or m.name, reverse=True)
        return projects

    def get_project(self, project_id: str) -> Optional[ProjectIR]:
        file_path = self._get_project_file(project_id)
        if not file_path.is_file():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ProjectIR.model_validate(data)
        except Exception:
            return None

    def save_project(self, project: ProjectIR) -> ProjectIR:
        now_iso = datetime.now(timezone.utc).isoformat()
        if not project.meta.id:
            project.meta.id = str(uuid.uuid4())[:8]

        if not project.meta.created_at:
            project.meta.created_at = now_iso
        project.meta.updated_at = now_iso

        file_path = self._get_project_file(project.meta.id)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(project.model_dump_json(indent=2, by_alias=True))
        return project

    def delete_project(self, project_id: str) -> bool:
        file_path = self._get_project_file(project_id)
        if file_path.is_file():
            file_path.unlink()
            return True
        return False

    def exists(self, project_id: str) -> bool:
        return self._get_project_file(project_id).is_file()

    def _seed_default_projects_if_empty(self) -> None:
        """Seeds default canonical projects if repository is brand new."""
        existing = list(self.storage_dir.glob("*.json"))
        if existing:
            return

        # 1. Seed Golden Slide Project (Section 7)
        golden_project = ProjectIR(
            meta=ProjectMetadata(
                id="golden-slide",
                name="Canonical Golden Slide (Sec 7)",
                description="System-level synthesis reference schedule from slide (latency 32 ticks)",
                time_unit="ticks",
            ),
            settings=SearchSettings(
                explicit_priorities=["V1", "V2", "V3", "V5", "V6", "V7", "V4"],
            ),
            problem=ProblemGraph(
                nodes=[
                    ComputeNode(id="V1", name="Task V1"),
                    ComputeNode(id="V2", name="Task V2"),
                    ComputeNode(id="V3", name="Task V3"),
                    ComputeNode(id="V4", name="Task V4"),
                ],
                edges=[
                    DataEdge(source_id="V1", destination_id="V3", data_kb=1.0, comm_id="V5"),
                    DataEdge(source_id="V2", destination_id="V4", data_kb=1.0, comm_id="V6"),
                    DataEdge(source_id="V3", destination_id="V4", data_kb=1.0, comm_id="V7"),
                ],
            ),
            architecture=ArchitectureGraph(
                resources=[
                    ResourceIR(id="RISC", name="RISC Processor", kind=ResourceKind.PROCESSOR, mandatory=True),
                    ResourceIR(id="HWM1", name="Hardware Module 1", kind=ResourceKind.HW_MODULE, mandatory=True),
                    ResourceIR(id="HWM2", name="Hardware Module 2", kind=ResourceKind.HW_MODULE, mandatory=False),
                    ResourceIR(
                        id="SB",
                        name="Shared Bus",
                        kind=ResourceKind.BUS,
                        mandatory=True,
                        connects=["RISC", "HWM1"],
                        setup_latency_ms=1.0,
                    ),
                    ResourceIR(
                        id="PTP",
                        name="Point-to-Point Bus",
                        kind=ResourceKind.BUS,
                        mandatory=False,
                        connects=["HWM1", "HWM2"],
                        setup_latency_ms=1.0,
                    ),
                ]
            ),
            mapping=MappingIR(
                options=[
                    MappingOption(node_id="V1", resource_id="RISC", execution_time_ms=1.0),
                    MappingOption(node_id="V2", resource_id="RISC", execution_time_ms=20.0),
                    MappingOption(node_id="V3", resource_id="RISC", execution_time_ms=8.0),
                    MappingOption(node_id="V4", resource_id="HWM1", execution_time_ms=2.0),
                ]
            ),
        )
        self.save_project(golden_project)

        # 2. Seed Walkthrough Project (Section 8)
        walkthrough_project = ProjectIR(
            meta=ProjectMetadata(
                id="synthetic-walkthrough",
                name="Synthetic Walkthrough (Sec 8)",
                description="3-stage pipeline (T1 -> T2 -> T3) comparing all-SW with HW accelerated T2",
                time_unit="ms",
            ),
            problem=ProblemGraph(
                nodes=[
                    ComputeNode(id="T1", name="Ingest", memory_kb=8.0),
                    ComputeNode(id="T2", name="Filtering", memory_kb=8.0),
                    ComputeNode(id="T3", name="Aggregation", memory_kb=8.0),
                ],
                edges=[
                    DataEdge(source_id="T1", destination_id="T2", data_kb=4.0, comm_id="C1"),
                    DataEdge(source_id="T2", destination_id="T3", data_kb=4.0, comm_id="C2"),
                ],
            ),
            architecture=ArchitectureGraph(
                resources=[
                    ResourceIR(
                        id="CPU",
                        name="Host CPU",
                        kind=ResourceKind.PROCESSOR,
                        mandatory=True,
                        allocation_cost=10.0,
                        static_power_mw=500.0,
                    ),
                    ResourceIR(
                        id="ACC1",
                        name="Accelerator 1",
                        kind=ResourceKind.HW_MODULE,
                        mandatory=False,
                        allocation_cost=25.0,
                        static_power_mw=200.0,
                        capacity={"logic": 500.0},
                        area={"logic": 50.0},
                    ),
                    ResourceIR(
                        id="SB",
                        name="Shared Bus",
                        kind=ResourceKind.BUS,
                        mandatory=True,
                        allocation_cost=0.0,
                        static_power_mw=50.0,
                        power_mw=100.0,
                        connects=["CPU", "ACC1"],
                        bandwidth_mb_per_s=8.0,
                        setup_latency_ms=0.25,
                    ),
                ]
            ),
            mapping=MappingIR(
                options=[
                    MappingOption(node_id="T1", resource_id="CPU", execution_time_ms=3.0, active_power_mw=1200.0),
                    MappingOption(node_id="T2", resource_id="CPU", execution_time_ms=4.0, active_power_mw=1500.0),
                    MappingOption(
                        node_id="T2",
                        resource_id="ACC1",
                        execution_time_ms=1.0,
                        active_power_mw=300.0,
                        usage={"logic": 100.0},
                    ),
                    MappingOption(node_id="T3", resource_id="CPU", execution_time_ms=3.0, active_power_mw=1200.0),
                ]
            ),
        )
        self.save_project(walkthrough_project)

        # 3. Seed Simple CPU/FPGA Project (Section 9)
        from app.ir.presets import lower_simple_preset, SimpleTaskConfig, SimplePlatformConfig
        simple_tasks = [
            SimpleTaskConfig(id="TaskA", name="Data Input", sw_cycles=3_000_000, hw_cycles=1_000_000, hw_luts=200, hw_dsps=1, memory_kb=4.0),
            SimpleTaskConfig(id="TaskB", name="Core Processing", sw_cycles=5_000_000, hw_cycles=800_000, hw_luts=800, hw_dsps=4, memory_kb=8.0),
            SimpleTaskConfig(id="TaskC", name="Output Format", sw_cycles=2_000_000, hw_cycles=None, memory_kb=4.0),
        ]
        simple_edges = [
            DataEdge(source_id="TaskA", destination_id="TaskB", data_kb=4.0),
            DataEdge(source_id="TaskB", destination_id="TaskC", data_kb=4.0),
        ]
        simple_platform = SimplePlatformConfig(
            cpu_mhz=1000.0,
            fpga_mhz=250.0,
            bus_bandwidth_mb_per_s=8.0,
            bus_latency_us=250.0,
        )
        simple_proj = lower_simple_preset(
            project_id="simple-cpu-fpga",
            project_name="Simple CPU/FPGA Preset (Sec 9)",
            tasks=simple_tasks,
            edges=simple_edges,
            platform=simple_platform,
        )
        self.save_project(simple_proj)

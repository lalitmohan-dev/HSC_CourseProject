"""Independent audit checks. Failures assert intended safety/correctness, not current bugs."""
import tempfile
from pathlib import Path
import pytest
from app.ir.models import *
from app.ir.lowering import lower_problem, calculate_hop_transfer_time
from app.ir.validator import validate_project
from app.core.evaluator import evaluate_candidate, derive_canonical_allocation
from app.persistence.repository import JsonFileProjectRepository
from app.search.runner import execute_search

def base():
    return ProjectIR(meta={"name":"Audit"},problem={"nodes":[{"id":"A","name":"A"},{"id":"B","name":"B"}],"edges":[]},architecture={"resources":[{"id":"CPU","name":"CPU","static_power_mw":0,"capacity":{"logic":100}},{"id":"ACC","name":"ACC","kind":"hw_module","mandatory":False,"static_power_mw":0,"capacity":{"logic":100}},{"id":"BUS","name":"BUS","kind":"bus","connects":["CPU","ACC"],"bandwidth_mb_per_s":8,"setup_latency_ms":0.25,"power_mw":0,"static_power_mw":0}]},mapping={"options":[{"node_id":n,"resource_id":r,"execution_time_ms":t,"active_power_mw":100,"usage":{"logic":60}} for n in ["A","B"] for r,t in [("CPU",3),("ACC",1)]]})

def ev(p, bindings=None, **kw):
    return evaluate_candidate(lower_problem(p),CandidateDesign(id="audit",bindings=bindings or {"A":"CPU","B":"ACC"},**kw))

def test_decimal_transfer_units():
    assert calculate_hop_transfer_time(base().architecture.resources[2],4)==pytest.approx(0.75)

def test_execution_cycles_to_ms():
    p=base();p.architecture.resources[0].clock_mhz=100
    p.mapping.options[0].execution_time_ms=None;p.mapping.options[0].execution_cycles=200000
    assert lower_problem(p).mapping_options_by_node["A"]["CPU"].execution_time_ms==pytest.approx(2)

def test_per_resource_capacity_is_local():
    r=ev(base())
    assert r.feasible, f"Each resource uses 60/100 logic, but got {r.violations}"

def test_global_max_area_enforced():
    p=base();p.constraints.max_area={"logic":100}
    for r in p.architecture.resources:r.capacity={}
    r=ev(p)
    assert not r.feasible, f"120 logic exceeds global 100 but feasible={r.feasible}"

def test_fixed_binding_enforced_by_evaluator():
    p=base();p.problem.nodes[0].fixed_resource_id="CPU"
    for r in p.architecture.resources:r.capacity={}
    r=ev(p,{"A":"ACC","B":"CPU"})
    assert not r.feasible, "Evaluator accepted A on ACC despite fixed CPU"

def test_mandatory_allocation_enforced():
    p=base();p.problem.nodes=p.problem.nodes[:1];p.mapping.options=p.mapping.options[:2]
    r=ev(p,{"A":"ACC"},allocated_resources=["ACC"])
    assert not r.feasible, "Mandatory CPU and BUS omitted without rejection"

def test_explicit_route_connectivity_enforced():
    p=base();p.problem.edges=[DataEdge(**{"from":"A","to":"B","comm_id":"C","data_kb":4})]
    p.architecture.resources[2].connects=["CPU","CPU"]
    for r in p.architecture.resources:r.capacity={}
    r=ev(p,routes={"C":["BUS"]})
    assert not r.feasible, "Explicit route uses a bus disconnected from destination ACC"

def test_missing_route_rejected():
    p=base();p.problem.edges=[DataEdge(**{"from":"A","to":"B","data_kb":4})]
    p.architecture.resources[2].connects=["CPU","CPU"]
    assert not ev(p).feasible

def test_communication_ids_disjoint_from_task_ids():
    p=base();p.problem.edges=[DataEdge(**{"from":"A","to":"B","comm_id":"A"})]
    assert not validate_project(p).is_valid, "Communication A overwrites compute A during scheduling"

def test_negative_power_rejected():
    p=base();p.mapping.options[0].active_power_mw=-100
    assert not validate_project(p).is_valid, "Negative active power accepted"

def test_unknown_objective_rejected():
    p=base();p.objectives.names=["nonexistent_metric"]
    assert not validate_project(p).is_valid, "Unknown objective silently ignored by ranking"

def test_unknown_power_stays_null():
    p=base();p.mapping.options[0].active_power_mw=None
    assert ev(p).energy_mj is None

def test_abstract_ticks_disable_physical_metrics():
    p=base();p.meta.time_unit="ticks"
    r=ev(p);assert (r.energy_mj,r.avg_power_w,r.throughput_fps)==(None,None,None)

def test_parallel_resource_schedule():
    p=base();p.architecture.resources[0].max_parallel=2
    for r in p.architecture.resources:r.capacity={}
    r=ev(p,{"A":"CPU","B":"CPU"})
    assert r.latency_ms==3

def multihop():
    p=base();p.problem.edges=[DataEdge(**{"from":"A","to":"B","data_kb":4,"comm_id":"C"})]
    p.architecture.resources[2].connects=["CPU","BRIDGE"]
    p.architecture.resources += [ResourceIR(id="BRIDGE",name="BRIDGE",mandatory=False,static_power_mw=0),ResourceIR(id="BUS2",name="BUS2",kind="bus",mandatory=False,connects=["BRIDGE","ACC"],bandwidth_mb_per_s=8,setup_latency_ms=0.25,power_mw=0,static_power_mw=0)]
    for r in p.architecture.resources:r.capacity={}
    return p

def test_multihop_with_explicit_full_allocation():
    r=ev(multihop(),allocated_resources=["CPU","ACC","BRIDGE","BUS","BUS2"])
    assert r.feasible and r.latency_ms==pytest.approx(5.5)

def test_multihop_canonical_allocation_includes_bridge():
    p=multihop();r=ev(p)
    assert r.feasible, "Canonical allocation drops intermediate BRIDGE, making legal route infeasible"

def test_nsga2_hard_evaluation_budget():
    p=base();p.settings.strategy="nsga2";p.settings.budget_evaluations=1;p.settings.population_size=4
    for r in p.architecture.resources:r.capacity={}
    evaluated,_,_,_=execute_search(lower_problem(p))
    assert len(evaluated)<=1, f"Budget 1 evaluated {len(evaluated)} distinct candidates"

def test_nsga2_generations_setting_forwarded(monkeypatch):
    import app.search.runner as runner
    seen={}
    def stub(**kw): seen.update(kw);return []
    monkeypatch.setattr(runner,"run_nsga2_search",stub)
    p=base();p.settings.strategy="nsga2";p.settings.budget_evaluations=40;p.settings.population_size=4;p.settings.generations=3
    runner.execute_search(lower_problem(p))
    assert seen["generations"]==3, f"Configured 3 generations, forwarded {seen['generations']}"

def test_project_id_cannot_escape_storage_directory(tmp_path):
    store=tmp_path/"store";repo=JsonFileProjectRepository(store)
    p=base();p.meta.id="../audit_escape"
    try:repo.save_project(p)
    except (ValueError,OSError):return
    assert not (tmp_path/"audit_escape.json").exists(), "Project id wrote outside configured storage"

def test_synthetic_benchmark_exact_values(tmp_path):
    repo=JsonFileProjectRepository(tmp_path)
    p=repo.get_project("synthetic-walkthrough")
    sw=ev(p,{"T1":"CPU","T2":"CPU","T3":"CPU"})
    hw=ev(p,{"T1":"CPU","T2":"ACC1","T3":"CPU"})
    assert (sw.latency_ms,sw.energy_mj,sw.avg_power_w)==pytest.approx((10,18.7,1.87))
    assert (hw.latency_ms,hw.energy_mj,hw.avg_power_w)==pytest.approx((8.5,14.025,1.65))

def test_all_four_searches_return_legal_seeded_results(tmp_path):
    repo=JsonFileProjectRepository(tmp_path);p=repo.get_project("synthetic-walkthrough")
    for strategy in ["exhaustive","random","greedy","nsga2"]:
        p.settings.strategy=strategy;p.settings.budget_evaluations=20;p.settings.population_size=4
        evaluated,pareto,best,_=execute_search(lower_problem(p))
        assert evaluated and {c.evaluation.latency_ms for c in pareto}<={8.5,10}
        assert best.evaluation.feasible
        again,_,_,_=execute_search(lower_problem(p))
        assert [c.bindings for c in evaluated]==[c.bindings for c in again]

def test_persisted_run_retains_design_access(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.projects import get_repository
    from app.api.explore import RUNS_REGISTRY
    repo=JsonFileProjectRepository(tmp_path)
    app.dependency_overrides[get_repository]=lambda:repo
    try:
        with TestClient(app) as client:
            rid=client.post('/api/projects/synthetic-walkthrough/explore').json()['run_id']
            before=client.get(f'/api/runs/{rid}/designs')
            run=RUNS_REGISTRY.pop(rid)
            try:
                after=client.get(f'/api/runs/{rid}/designs')
                assert before.status_code==after.status_code==200, f"Before restart {before.status_code}; persisted designs {after.status_code}"
            finally:RUNS_REGISTRY[rid]=run
    finally:app.dependency_overrides.clear()

def test_fpga_static_power_affects_energy():
    from app.ir.presets import SimpleTaskConfig,SimplePlatformConfig,lower_simple_preset
    energies=[]
    for power in [0,1000]:
        p=lower_simple_preset('audit-energy','audit-energy',[SimpleTaskConfig(id='A',name='A',sw_cycles=1000000,hw_cycles=1000000,power_sw_mw=100,power_hw_mw=100)],[],SimplePlatformConfig(fpga_static_power_mw=power))
        energies.append(ev(p,{'A':'ACC_A'}).energy_mj)
    assert energies[1]>energies[0], f"FPGA static power 0 -> 1000 mW left energy unchanged: {energies}"

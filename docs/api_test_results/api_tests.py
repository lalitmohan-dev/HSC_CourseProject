"""Live API test pass against http://localhost:8000. Writes results.json + per-test HTML cards."""
import html, json, sys, time
from pathlib import Path
import httpx

BASE = "http://localhost:8000"
OUT = Path(sys.argv[1]); (OUT / "cards").mkdir(parents=True, exist_ok=True)
c = httpx.Client(base_url=BASE, timeout=60)
results, created = [], []


def short(obj, n=1800):
    s = obj if isinstance(obj, str) else json.dumps(obj, indent=2, default=str)
    return s if len(s) <= n else s[:n] + "\n... (truncated)"


def record(tid, section, name, method, url, body, resp, expected, ok, note=""):
    try:
        rb = resp.json()
    except Exception:
        rb = resp.text
    results.append(dict(id=tid, section=section, name=name, method=method, url=url,
                        expected=expected, status=resp.status_code, passed=bool(ok), note=note))
    verdict = "PASS" if ok else "FAIL"
    color = "#1a7f37" if ok else "#cf222e"
    page = f"""<!doctype html><meta charset=utf-8><style>
body{{font:14px Segoe UI,Arial;margin:0;padding:20px;background:#f6f8fa;color:#1f2328}}
.h{{display:flex;justify-content:space-between;align-items:center}}
.v{{background:{color};color:#fff;padding:4px 12px;border-radius:6px;font-weight:700}}
pre{{background:#fff;border:1px solid #d0d7de;border-radius:6px;padding:10px;white-space:pre-wrap;word-break:break-all;font:12px Consolas,monospace;margin:4px 0 12px}}
.m{{font-weight:700;color:#0969da}} small{{color:#57606a}}</style>
<div class=h><h2>{tid} &middot; {html.escape(name)}</h2><span class=v>{verdict}</span></div>
<small>{html.escape(section)} &middot; {time.strftime('%Y-%m-%d %H:%M:%S')}</small>
<p><span class=m>{method}</span> <code>{html.escape(BASE + url)}</code></p>
<b>Request body</b><pre>{html.escape(short(body) if body is not None else '(none)')}</pre>
<b>Expected</b><pre>{html.escape(expected)}</pre>
<b>Actual: HTTP {resp.status_code}</b>{(' &middot; ' + html.escape(note)) if note else ''}
<pre>{html.escape(short(rb))}</pre>"""
    (OUT / "cards" / f"{tid}.html").write_text(page, encoding="utf-8")
    print(f"{verdict} {tid} {name} [{resp.status_code}] {note}")


def call(method, url, body=None, **kw):
    return c.request(method, url, json=body, **kw)


def wait_run(run_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        r = c.get(f"/api/runs/{run_id}")
        if r.status_code == 200 and r.json()["status"] != "running":
            return r
        time.sleep(0.2)
    return r


def variant(base_id, suffix, mutate):
    p = c.get(f"/api/projects/{base_id}/export").json()
    p["meta"]["id"] = f"apitest-{suffix}"
    p["meta"]["name"] = f"API test {suffix}"
    mutate(p)
    r = c.post("/api/projects/import", json=p)
    pid = r.json()["project"]["meta"]["id"]
    created.append(pid)
    return pid


def explore(pid):
    return wait_run(c.post(f"/api/projects/{pid}/explore").json()["run_id"])


# ---------- 1. Smoke ----------
r = call("GET", "/api/health")
record("T01", "1 Smoke", "Health check", "GET", "/api/health", None, r,
       '200, {"status":"ok"}', r.status_code == 200 and r.json().get("status") == "ok")
r = call("GET", "/api/projects")
ids = [p["id"] for p in r.json()] if r.status_code == 200 else []
record("T02", "1 Smoke", "List projects includes 3 presets", "GET", "/api/projects", None, r,
       "200, contains golden-slide, synthetic-walkthrough, simple-cpu-fpga",
       {"golden-slide", "synthetic-walkthrough", "simple-cpu-fpga"} <= set(ids))

# ---------- 2. CRUD ----------
new = {"meta": {"name": "CRUD Test", "time_unit": "ms"},
       "problem": {"nodes": [{"id": "N1", "name": "Node 1"}], "edges": []},
       "architecture": {"resources": [{"id": "R1", "name": "Res 1", "kind": "processor"}]},
       "mapping": {"options": [{"node_id": "N1", "resource_id": "R1", "execution_time_ms": 5.0}]}}
r = call("POST", "/api/projects", new)
pid = r.json()["meta"]["id"] if r.status_code == 201 else "missing"
created.append(pid)
record("T03", "2 CRUD", "Create project", "POST", "/api/projects", new, r, "201, project with generated id", r.status_code == 201)
r = call("GET", f"/api/projects/{pid}")
record("T04", "2 CRUD", "Read created project", "GET", f"/api/projects/{pid}", None, r, "200, name = 'CRUD Test'",
       r.status_code == 200 and r.json()["meta"]["name"] == "CRUD Test")
upd = r.json(); upd["meta"]["description"] = "Updated description"
r = call("PUT", f"/api/projects/{pid}", upd)
record("T05", "2 CRUD", "Update project description", "PUT", f"/api/projects/{pid}", {"meta": {"description": "Updated description"}, "...": "rest of project"}, r,
       "200, description updated", r.status_code == 200 and r.json()["meta"]["description"] == "Updated description")
r = call("GET", f"/api/projects/{pid}")
record("T06", "2 CRUD", "Update persisted (re-read)", "GET", f"/api/projects/{pid}", None, r, "200, description = 'Updated description'",
       r.status_code == 200 and r.json()["meta"]["description"] == "Updated description")
r = call("DELETE", f"/api/projects/{pid}")
record("T07", "2 CRUD", "Delete project", "DELETE", f"/api/projects/{pid}", None, r, '200, {"deleted": true}',
       r.status_code == 200 and r.json().get("deleted") is True)
r = call("GET", f"/api/projects/{pid}")
record("T08", "2 CRUD", "Read after delete", "GET", f"/api/projects/{pid}", None, r, "404", r.status_code == 404)

# ---------- 3. Validation / negative ----------
bad = {"meta": 5}
r = call("POST", "/api/projects", bad)
record("T09", "3 Validation", "Create with malformed body", "POST", "/api/projects", bad, r, "422", r.status_code == 422)
cyc = json.loads(json.dumps(new)); cyc["meta"]["name"] = "Cyclic"
cyc["problem"] = {"nodes": [{"id": "A", "name": "A"}, {"id": "B", "name": "B"}],
                  "edges": [{"id": "E1", "source": "A", "target": "B"}, {"id": "E2", "source": "B", "target": "A"}]}
cyc["mapping"]["options"] = [{"node_id": n, "resource_id": "R1", "execution_time_ms": 1.0} for n in "AB"]
r = call("POST", "/api/projects/import", cyc)
if r.status_code == 200:
    created.append(r.json()["project"]["meta"]["id"])
    v = r.json()["validation"]
    record("T10", "3 Validation", "Import cyclic task graph", "POST", "/api/projects/import", cyc, r,
           "Rejected: is_valid=false with a cycle error (or 422)", v["is_valid"] is False)
else:
    record("T10", "3 Validation", "Import cyclic task graph", "POST", "/api/projects/import", cyc, r,
           "Rejected: is_valid=false with a cycle error (or 422)", r.status_code == 422)
r = call("POST", "/api/projects/import", {"problem": "not-a-graph"})
record("T11", "3 Validation", "Import invalid payload", "POST", "/api/projects/import", {"problem": "not-a-graph"}, r, "422", r.status_code == 422)
r = call("POST", "/api/projects/golden-slide/validate")
record("T12", "3 Validation", "Validate valid preset", "POST", "/api/projects/golden-slide/validate", None, r,
       "200, is_valid=true, no errors", r.status_code == 200 and r.json()["is_valid"] and not r.json()["errors"])
badcand = {"id": "bad", "bindings": {"V1": "NOPE"}, "allocated_resources": ["NOPE"]}
r = call("POST", "/api/projects/golden-slide/evaluate", badcand)
record("T13", "3 Validation", "Evaluate candidate bound to unknown resource", "POST", "/api/projects/golden-slide/evaluate", badcand, r,
       "400 (or 422)", r.status_code in (400, 422))
r = call("GET", "/api/runs/run_doesnotexist/report?format=pdf")
record("T14", "3 Validation", "Report with unsupported format", "GET", "/api/runs/x/report?format=pdf", None, r, "422", r.status_code == 422)

# ---------- 4. Not found ----------
for tid, m, u in [("T15", "GET", "/api/projects/nope"), ("T16", "POST", "/api/projects/nope/explore"),
                  ("T17", "GET", "/api/runs/run_nope"), ("T18", "GET", "/api/runs/run_nope/designs"),
                  ("T19", "POST", "/api/runs/run_nope/cancel")]:
    r = call(m, u)
    record(tid, "4 Not found", f"Unknown id: {u}", m, u, None, r, "404", r.status_code == 404)

# ---------- 5. Correctness vs known answers ----------
gold = {"id": "eval_test", "bindings": {"V1": "RISC", "V2": "RISC", "V3": "RISC", "V4": "HWM1"},
        "allocated_resources": ["RISC", "SB", "HWM1"], "priority_order": ["V1", "V2", "V3", "V5", "V6", "V7", "V4"]}
r = call("POST", "/api/projects/golden-slide/evaluate", gold)
record("T20", "5 Correctness", "Golden Slide makespan", "POST", "/api/projects/golden-slide/evaluate", gold, r,
       "200, feasible, latency = 32 ticks", r.status_code == 200 and r.json()["feasible"] and r.json()["latency_ms"] == 32.0)
r = call("GET", "/api/projects/golden-slide/ir")
record("T21", "5 Correctness", "Lowered IR has 3 communication objects", "GET", "/api/projects/golden-slide/ir", None, r,
       "200, 3 communication objects", r.status_code == 200 and len(r.json()["communication_objects"]) == 3)
r = explore("synthetic-walkthrough"); wrun = r.json()["run_id"]
d = c.get(f"/api/runs/{wrun}/designs").json()
lat = sorted(round(i["evaluation"]["latency_ms"], 3) for i in d["items"])
record("T22", "5 Correctness", "Synthetic Walkthrough: 10.0 ms all-SW, 8.5 ms accelerated", "POST+GET",
       f"/api/projects/synthetic-walkthrough/explore -> /api/runs/{wrun}/designs", None, r,
       "completed; latencies include 8.5 and 10.0", r.json()["status"] == "completed" and 8.5 in lat and 10.0 in lat, f"latencies={lat}")
r = explore("simple-cpu-fpga"); srun = r.json()["run_id"]
items = c.get(f"/api/runs/{srun}/designs").json()["items"]
record("T23", "5 Correctness", "Simple CPU/FPGA exhaustive: 4 feasible candidates", "POST+GET",
       f"/api/projects/simple-cpu-fpga/explore -> /api/runs/{srun}", None, r, "4 candidates, all feasible",
       len(items) == 4 and all(i["evaluation"]["feasible"] for i in items),
       f"latencies={sorted(round(i['evaluation']['latency_ms'], 2) for i in items)}")

# ---------- 6. Exploration flow (all strategies + SSE) ----------
for tid, strat in [("T24", "random"), ("T25", "greedy"), ("T26", "nsga2")]:
    vp = variant("synthetic-walkthrough", strat, lambda p, s=strat: p["settings"].update(strategy=s, generations=10, population_size=20))
    r = explore(vp)
    j = r.json()
    record(tid, "6 Exploration", f"Strategy '{strat}' run completes", "POST+GET", f"/api/projects/{vp}/explore", {"settings.strategy": strat}, r,
           "completed, >=1 Pareto design, recommendation present",
           j["status"] == "completed" and j["pareto_count"] >= 1 and j["recommended_design"] is not None,
           f"evaluated={j['evaluated_count']} pareto={j['pareto_count']}")
run_id = c.post("/api/projects/synthetic-walkthrough/explore").json()["run_id"]
events, raw = [], []
with c.stream("GET", f"/api/runs/{run_id}/events") as s:
    for line in s.iter_lines():
        raw.append(line)
        if line.startswith("event:"):
            events.append(line.split(":", 1)[1].strip())
        if events and events[-1] in ("done", "error"):
            break


class _Captured:  # stand-in response holding the streamed text
    status_code = s.status_code
    text = f"content-type: {s.headers.get('content-type')}\n\n" + "\n".join(raw[-30:])
    def json(self): raise ValueError


st = _Captured()
kinds = sorted(set(events))
record("T27", "6 Exploration", "SSE progress stream ends with 'done'", "GET", f"/api/runs/{run_id}/events", None, st,
       "text/event-stream, events received, last event = done", events[-1:] == ["done"] if events else False,
       f"{len(events)} events, kinds={kinds}")
r = call("GET", f"/api/runs/{wrun}/designs?feasible_only=true&sort_by=latency_ms&sort_order=desc&page_size=1")
record("T28", "6 Exploration", "Designs list: filter, sort, paging", "GET", f"/api/runs/{wrun}/designs?feasible_only=true&sort_order=desc&page_size=1", None, r,
       "200, 1 item, highest latency first", r.status_code == 200 and len(r.json()["items"]) == 1 and r.json()["items"][0]["evaluation"]["latency_ms"] == max(lat))
first = d["items"][0]["id"]
r = call("GET", f"/api/runs/{wrun}/designs/{first}")
record("T29", "6 Exploration", "Design detail", "GET", f"/api/runs/{wrun}/designs/{first}", None, r, "200, evaluation present",
       r.status_code == 200 and r.json()["evaluation"] is not None)
r = call("GET", f"/api/runs/{wrun}/designs/nope")
record("T30", "6 Exploration", "Unknown design in valid run", "GET", f"/api/runs/{wrun}/designs/nope", None, r, "404", r.status_code == 404)

# ---------- 7. Constraints ----------
vp = variant("synthetic-walkthrough", "infeasible", lambda p: p["constraints"].update(max_latency_ms=0.1))
r = explore(vp); j = r.json()
its = c.get(f"/api/runs/{j['run_id']}/designs").json()["items"]
rat = (j.get("recommendation_details") or {}).get("rationale", "")
record("T31", "7 Constraints", "Impossible latency constraint (0.1 ms)", "POST+GET", f"/api/projects/{vp}/explore", {"constraints.max_latency_ms": 0.1}, r,
       "all candidates infeasible; rationale starts with WARNING (fallback)",
       its and not any(i["evaluation"]["feasible"] for i in its) and "WARNING" in rat, f"rationale: {rat[:120]}")

# ---------- 8. Cancel ----------
nodes = [f"N{i}" for i in range(14)]
big = {"meta": {"id": "apitest-cancel", "name": "Cancel test (2^14 designs)", "time_unit": "ms"},
       "problem": {"nodes": [{"id": n, "name": n} for n in nodes], "edges": []},
       "architecture": {"resources": [{"id": "CPU", "name": "CPU", "kind": "processor", "cost": 1},
                                      {"id": "ACC", "name": "ACC", "kind": "hw_module", "cost": 5}]},
       "mapping": {"options": [{"node_id": n, "resource_id": rs, "execution_time_ms": t}
                               for n in nodes for rs, t in (("CPU", 3.0), ("ACC", 1.0))]},
       "settings": {"strategy": "exhaustive", "budget_evaluations": 20000}}
vp = c.post("/api/projects/import", json=big).json()["project"]["meta"]["id"]; created.append(vp)
rid = c.post(f"/api/projects/{vp}/explore").json()["run_id"]
time.sleep(0.3)
r = call("POST", f"/api/runs/{rid}/cancel")
s = wait_run(rid).json()
record("T32", "8 Cancel", "Cancel a long exhaustive run (16,384 designs)", "POST", f"/api/runs/{rid}/cancel", None, r,
       '200, status "cancelling"; run ends as cancelled before finishing', r.status_code == 200 and s["status"] == "cancelled",
       f"final status={s['status']}, evaluated {s['evaluated_count']} of 16384")

# ---------- 9. Analysis & reports ----------
r = call("GET", f"/api/runs/{wrun}/bottlenecks?design_id={first}")
record("T33", "9 Analysis", "Bottleneck analysis", "GET", f"/api/runs/{wrun}/bottlenecks?design_id={first}", None, r,
       "200, critical path + utilisation", r.status_code == 200 and r.json()["critical_path"] and r.json()["resource_utilization"])
r = call("GET", f"/api/runs/{wrun}/bottlenecks?design_id=nope")
record("T34", "9 Analysis", "Bottlenecks for unknown design", "GET", f"/api/runs/{wrun}/bottlenecks?design_id=nope", None, r, "404", r.status_code == 404)
ids2 = [i["id"] for i in d["items"][:2]]
body = {"project_id": "synthetic-walkthrough", "design_ids": ids2}
r = call("POST", "/api/compare", body)
record("T35", "9 Analysis", "Compare 2 designs", "POST", "/api/compare", body, r, "200, 2 designs + metrics table",
       r.status_code == 200 and len(r.json()["designs"]) == 2 and r.json()["metrics_table"])
body = {"project_id": "synthetic-walkthrough", "design_ids": ids2[:1]}
r = call("POST", "/api/compare", body)
record("T36", "9 Analysis", "Compare with only 1 design", "POST", "/api/compare", body, r, "400", r.status_code == 400)
body = {"project_id": "synthetic-walkthrough", "design_ids": ["x", "y"]}
r = call("POST", "/api/compare", body)
record("T37", "9 Analysis", "Compare unknown designs", "POST", "/api/compare", body, r, "404", r.status_code == 404)
for tid, fmt, check in [("T38", "md", lambda r: "Design Space Exploration" in r.text),
                        ("T39", "csv", lambda r: "latency_ms" in r.text),
                        ("T40", "json", lambda r: r.json()["run_id"] == wrun)]:
    r = call("GET", f"/api/runs/{wrun}/report?format={fmt}")
    record(tid, "9 Analysis", f"Report export ({fmt})", "GET", f"/api/runs/{wrun}/report?format={fmt}", None, r,
           "200, non-empty, correct content", r.status_code == 200 and check(r), f"content-type={r.headers.get('content-type')}")

# ---------- 10. Import/export round trip ----------
orig = c.get("/api/projects/synthetic-walkthrough/export").json()
cp = json.loads(json.dumps(orig)); cp["meta"]["id"] = "apitest-roundtrip"
c.post("/api/projects/import", json=cp); created.append("apitest-roundtrip")
r = call("GET", "/api/projects/apitest-roundtrip/export")
a, b = r.json(), orig
for x in (a, b):
    x["meta"] = {k: v for k, v in x["meta"].items() if k not in ("id", "created_at", "updated_at")}
record("T41", "10 Round trip", "Export -> import -> export is identical", "GET", "/api/projects/apitest-roundtrip/export", None, r,
       "content identical to original (ignoring id/timestamps)", a == b)

# ---------- 11. Schema ----------
r = call("POST", "/api/projects/golden-slide/evaluate", gold); e = r.json()
record("T42", "11 Schema", "Evaluation fields and types", "POST", "/api/projects/golden-slide/evaluate", gold, r,
       "latency_ms number, feasible bool, violations list; energy null for abstract time unit",
       isinstance(e["latency_ms"], (int, float)) and isinstance(e["feasible"], bool) and isinstance(e["violations"], list) and e.get("energy_mj") is None,
       f"energy_mj={e.get('energy_mj')}")

# ---------- 12. Determinism ----------
vp = variant("synthetic-walkthrough", "determinism", lambda p: p["settings"].update(strategy="random", seed=7))
sig = []
for _ in range(2):
    rr = explore(vp)
    its = c.get(f"/api/runs/{rr.json()['run_id']}/designs?page_size=500").json()["items"]
    sig.append(sorted((i["evaluation"]["latency_ms"], i["evaluation"]["allocation_cost"]) for i in its))
record("T43", "12 Determinism", "Same seed gives same results", "POST x2", f"/api/projects/{vp}/explore", {"settings.seed": 7}, rr,
       "both runs give identical (latency, cost) sets", sig[0] == sig[1], f"{len(sig[0])} designs per run")

for pid in set(created):
    c.delete(f"/api/projects/{pid}")
(OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\n{sum(r['passed'] for r in results)}/{len(results)} passed")

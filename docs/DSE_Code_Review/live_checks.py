import asyncio,json,time,sys,platform,subprocess
from pathlib import Path
import httpx

OUT=Path(__file__).parent/'raw'
results=[]
def check(name,passed,detail):results.append(dict(name=name,passed=bool(passed),detail=detail));print(name, 'PASS' if passed else 'FAIL',detail,flush=True)

async def main():
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000',timeout=60,trust_env=False) as c:
        r=await c.get('/api/health');check('health',r.status_code==200,r.json())
        r=await c.get('/api/projects');projects=r.json();check('seeded_projects',{'golden-slide','synthetic-walkthrough','simple-cpu-fpga'}.issubset({p['id'] for p in projects}),[p['id'] for p in projects])
        runs={};bench={}
        for pid,count in [('golden-slide',1),('synthetic-walkthrough',2),('simple-cpu-fpga',4)]:
            r=await c.post(f'/api/projects/{pid}/validate');check(pid+'_validate',r.status_code==200 and r.json()['is_valid'],r.json())
            r=await c.post(f'/api/projects/{pid}/explore');rid=r.json()['run_id'];runs[pid]=rid
            for _ in range(100):
                s=(await c.get(f'/api/runs/{rid}')).json()
                if s['status']!='running':break
                await asyncio.sleep(.01)
            d=(await c.get(f'/api/runs/{rid}/designs')).json()
            check(pid+'_explore',s['status']=='completed' and d['total']==count,{'status':s['status'],'designs':d['total'],'latencies':[x['evaluation']['latency_ms'] for x in d['items']]})
            bench[pid]={'summary':s,'designs':d}
            b=await c.get(f'/api/runs/{rid}/bottlenecks');check(pid+'_bottlenecks',b.status_code==200,{'status':b.status_code,'latency':b.json().get('total_latency_ms')})
            for fmt in ['md','csv','json']:
                e=await c.get(f'/api/runs/{rid}/report?format={fmt}')
                check(pid+'_export_'+fmt,e.status_code==200 and len(e.content)>0,{'status':e.status_code,'bytes':len(e.content)})
                (OUT/f'{pid}_export.{fmt}').write_bytes(e.content)
        rid=runs['synthetic-walkthrough'];ids=[x['id'] for x in bench['synthetic-walkthrough']['designs']['items']]
        e=await c.get(f'/api/runs/{rid}/events');check('sse_completed_run_replay',e.status_code==200 and 'event: done' in e.text,{'status':e.status_code,'done_events':e.text.count('event: done'),'log_events':e.text.count('event: log')})
        (OUT/'sse_first_connection.txt').write_text(e.text)
        r=await c.post('/api/compare',json={'project_id':'synthetic-walkthrough','design_ids':ids});check('compare_two',r.status_code==200 and len(r.json().get('designs',[]))==2,r.json().get('metrics_table'))
        r=await c.get(f'/api/runs/{rid}/designs?page_size=1');check('pagination',r.status_code==200 and len(r.json()['items'])==1,r.json().get('total'))
        r=await c.get('/api/projects/not-present');check('unknown_project_404',r.status_code==404,r.status_code)
        r=await c.get(f'/api/runs/{rid}/report?format=pdf');check('unsupported_export_422',r.status_code==422,r.status_code)
        async with httpx.AsyncClient(base_url='http://127.0.0.1:5173',timeout=20,trust_env=False) as f:
            r=await f.get('/');check('frontend_http',r.status_code==200 and 'root' in r.text,{'status':r.status_code,'bytes':len(r.content)})
            r=await f.get('/api/health');check('frontend_api_proxy',r.status_code==200 and r.json().get('status')=='ok',r.json())
        # Deliberately impossible deadline on an isolated copy.
        p=(await c.get('/api/projects/synthetic-walkthrough')).json();p['meta']['id']='audit-impossible';p['constraints']['max_latency_ms']=0.1
        await c.post('/api/projects',json=p)
        rid=(await c.post('/api/projects/audit-impossible/explore')).json()['run_id']
        s=(await c.get(f'/api/runs/{rid}')).json()
        check('impossible_deadline_fallback',s['status']=='completed' and not s['recommended_design']['evaluation']['feasible'] and 'no feasible' in s['recommendation_details']['rationale'],{'feasible':s['recommended_design']['evaluation']['feasible'],'rationale':s['recommendation_details']['rationale']})
        await c.delete('/api/projects/audit-impossible')
        # Responsiveness under actual CPU-bound work, no artificial sleep in server code.
        p=(await c.get('/api/projects/synthetic-walkthrough')).json();p['meta']['id']='audit-load';p['problem']={'nodes':[{'id':f'N{i}','name':f'N{i}'} for i in range(12)],'edges':[]}
        p['mapping']={'options':[{'node_id':f'N{i}','resource_id':r,'execution_time_ms':t,'active_power_mw':100} for i in range(12) for r,t in [('CPU',3),('ACC1',1)]]}
        p['settings']['budget_evaluations']=3000
        await c.post('/api/projects',json=p)
        t=time.perf_counter();r=await c.post('/api/projects/audit-load/explore');ack=time.perf_counter()-t;rid=r.json()['run_id']
        t=time.perf_counter();cancel=await c.post(f'/api/runs/{rid}/cancel');cancel_elapsed=time.perf_counter()-t
        s=(await c.get(f'/api/runs/{rid}')).json()
        check('cancel_interrupts_active_search',s['status']=='cancelled',{'start_ack_seconds':round(ack,4),'cancel_response_seconds':round(cancel_elapsed,4),'final_status':s['status'],'evaluated':s['evaluated_count'],'cancel_response':cancel.json()})
        await c.delete('/api/projects/audit-load')
        (OUT/'benchmarks.json').write_text(json.dumps(bench,indent=2))
    (OUT/'live_checks.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':
    root=Path(__file__).resolve().parent.parent
    backlog=open(OUT/'live_backend.log','w');frontlog=open(OUT/'live_frontend.log','w')
    backend=subprocess.Popen([str(root/'.venv/bin/uvicorn'),'app.main:app','--host','127.0.0.1','--port','8000'],cwd=root/'repo/dse/backend',stdout=backlog,stderr=subprocess.STDOUT)
    frontend=subprocess.Popen(['npm','run','dev','--','--host','127.0.0.1'],cwd=root/'repo/dse/frontend',stdout=frontlog,stderr=subprocess.STDOUT)
    try:
        with httpx.Client(trust_env=False) as c:
            for _ in range(100):
                try:
                    if c.get('http://127.0.0.1:8000/api/health').status_code==200 and c.get('http://127.0.0.1:5173').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
        asyncio.run(main())
    finally:
        backend.terminate();frontend.terminate()
        backend.wait(timeout=10);frontend.wait(timeout=10)
        backlog.close();frontlog.close()

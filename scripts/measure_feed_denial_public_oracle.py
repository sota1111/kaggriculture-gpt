#!/usr/bin/env python3
"""Hash-pin and run the leak-free step-0 WHEAT screen; never open confirm."""
from __future__ import annotations
import argparse, ast, base64, hashlib, json, subprocess, tempfile, zlib
from pathlib import Path
from typing import Any

SLUGS={"rayk-c94-c95":"raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta","boatlee-v16-rc5":"boatlee/v16-rc5-high-score-8c-4s-premium-market-lead","salemali7-3094":"salemali7/3094-score-kaggriculture","tetsutani-adaptive":"tetsutani/adaptive-farming-strategy-for-kaggriculture","official-baseline":"bovard/kaggriculture-getting-started"}
def digest(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def notebook(root:Path,slug:str)->Path:
    files=list((root/slug.rsplit('/',1)[1]).glob('*.ipynb'))
    if len(files)!=1: raise ValueError(f"one notebook required for {slug}; got {len(files)}")
    return files[0]
def cells(path:Path)->list[str]:
    data=json.loads(path.read_text())
    return [(''.join(c['source']) if isinstance(c['source'],list) else c['source']) for c in data['cells'] if c['cell_type']=='code']
def literal(src:str,name:str)->Any:
    for node in ast.parse(src).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets): return ast.literal_eval(node.value)
    raise ValueError(name)
def acquire(root:Path)->None:
    for slug in SLUGS.values():
        target=root/slug.rsplit('/',1)[1]; target.mkdir(parents=True,exist_ok=True)
        if not list(target.glob('*.ipynb')): subprocess.run(['kaggle','kernels','pull',slug,'-p',str(target),'-m'],check=True)
def extract(root:Path,dest:Path)->dict[str,Path]:
    out={}; ray=cells(notebook(root,SLUGS['rayk-c94-c95']))
    for key,var,sha in [('rayk-c94','_AGENT_B64_PARTS','7b0e5a7b9d18dc583f5789e50a54dca43561f6d08c1c616b4219bf50bcb8311f'),('rayk-c95','_C95_AGENT_B64_PARTS','489f5d197527f107027626cce79d850fd2ca90edd43d94384b849b6511e27bdb')]:
        source=next(c for c in ray if var in c and sha in c)
        raw=zlib.decompress(base64.b64decode(''.join(literal(source,var))))
        if hashlib.sha256(raw).hexdigest()!=sha: raise ValueError(f'extracted hash: {key}')
        out[key]=dest/f'{key}.py'; out[key].write_bytes(raw)
    src=next(c for c in cells(notebook(root,SLUGS['boatlee-v16-rc5'])) if c.startswith('%%writefile main.py')).split('\n',1)[1].encode()
    if hashlib.sha256(src).hexdigest()!='f029fa0cb66a9eb509afbe44e3f59b800332d0419db91607183410e4089c4d19': raise ValueError('extracted hash: boatlee')
    out['boatlee-v16-rc5']=dest/'boatlee-v16-rc5.py'; out['boatlee-v16-rc5'].write_bytes(src); return out
def validate(m:dict[str,Any],root:Path|None=None)->dict[str,bool]:
    s,c=m['screen'],m['confirm']; sources=m['sources']
    checks={'schema_supported':m.get('schema_version')==1,'two_current_public_lineages':len({x['lineage'] for x in sources[:-1]})>=2,'official_baseline_present':any(x['id']=='official-baseline' for x in sources),'url_hash_version_license_present':all(all(x.get(k) for k in ('url','notebook_sha256','version','license')) for x in sources),'entity_seed_time_isolated':not({x['opponent'] for x in s}&{x['opponent'] for x in c}) and not({x['seed'] for x in s}&{x['seed'] for x in c}) and max(x['time_index'] for x in s)<min(x['time_index'] for x in c),'confirm_reserved_unopened':m.get('confirm_status')=='RESERVED_UNOPENED','leak_free_features':not set(m.get('policy_features',()))&set(m.get('forbidden_policy_features',())),'submission_forbidden':m.get('submission')=='FORBIDDEN'}
    if root: checks['source_hashes_match']=all(digest(notebook(root,SLUGS[x['id']]))==x['notebook_sha256'] for x in sources)
    return checks
def wheat(action:Any)->dict[str,int|None]:
    for slot,order in enumerate(action.get('market',[]) if isinstance(action,dict) else []):
        if len(order)>=3 and order[:2]==['BUY_PRODUCT','WHEAT']: return {'slot':slot,'quantity':int(order[2])}
    return {'slot':None,'quantity':0}
def obs(state:Any)->dict[str,Any]: return state.observation if isinstance(state.observation,dict) else dict(state.observation)
def animals(o:dict[str,Any],p:int)->int:return sum(1 for row in o['farms'][p]['tiles'] for t in row if isinstance(t,dict) and t.get('animal'))
def cash(o:dict[str,Any],p:int)->int:return int(o['farms'][p]['money'])
def run(candidate:Path,agents:dict[str,Path],panel:list[dict[str,Any]])->list[dict[str,Any]]:
    from kaggle_environments import make
    rows=[]
    for e in panel:
      for seat in (0,1):
        lineup=[str(candidate),str(agents[e['opponent']])]
        if seat: lineup.reverse()
        env=make('kaggriculture',configuration={'episodeSteps':720,'seed':e['seed']},debug=False); env.run(lineup); other=1-seat
        after,other_after=obs(env.steps[1][seat]),obs(env.steps[1][other])
        day2,other_day2=obs(env.steps[min(48,len(env.steps)-1)][seat]),obs(env.steps[min(48,len(env.steps)-1)][other])
        final,other_final=obs(env.steps[-1][seat]),obs(env.steps[-1][other])
        rows.append({'episode_id':f"{e['opponent']}|{seat}|{e['seed']}|{e['time_index']}",'opponent':e['opponent'],'seat':seat,'seed':e['seed'],'time_index':e['time_index'],'candidate_step0_wheat':wheat(env.steps[1][seat].action),'opponent_step0_wheat':wheat(env.steps[1][other].action),'candidate_actual_purchase':int(after.get('private',{}).get('shed',{}).get('WHEAT',0)),'opponent_actual_purchase':int(other_after.get('private',{}).get('shed',{}).get('WHEAT',0)),'candidate_day2_animal_survival':animals(day2,seat),'opponent_day2_animal_survival':animals(other_day2,other),'candidate_cash_flow':{'after_step0':cash(after,seat),'day2':cash(day2,seat),'final':cash(final,seat)},'opponent_cash_flow':{'after_step0':cash(other_after,other),'day2':cash(other_day2,other),'final':cash(other_final,other)},'status':str(env.steps[-1][seat].status)})
    return rows
def summarize(rows:list[dict[str,Any]])->dict[str,Any]:
    fire=[r for r in rows if r['opponent_step0_wheat']['quantity']>0]; denied=[r for r in rows if r['candidate_step0_wheat']['quantity']>r['candidate_actual_purchase']]
    return {'episodes':len(rows),'both_seats':{r['seat'] for r in rows}=={0,1},'feed_denial_opportunities':len(fire),'observed_denials':len(denied),'result':'screen-evidence-only' if denied else 'inconclusive'}
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--candidate',type=Path,default=Path('main.py')); ap.add_argument('--manifest',type=Path,default=Path('tests/fixtures/feed_denial_public_oracle.json')); ap.add_argument('--source-dir',type=Path); ap.add_argument('--acquire',action='store_true'); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args(); m=json.loads(a.manifest.read_text())
    with tempfile.TemporaryDirectory(prefix='sot2879-source-') as tmp:
      root=a.source_dir or Path(tmp)
      if a.acquire: acquire(root)
      checks=validate(m,root if a.acquire or a.source_dir else None); result={'passed':all(checks.values()),'checks':checks,'provenance':m['sources'],'confirm':{'status':'RESERVED_UNOPENED','cohort':m['confirm'],'outcomes':None},'kaggle_submission':'NOT_PERFORMED'}
      if a.acquire or a.source_dir:
       with tempfile.TemporaryDirectory(prefix='sot2879-agent-') as d:
        rows=run(a.candidate,extract(root,Path(d)),m['screen']); result['screen']={'episodes':rows,'summary':summarize(rows)}; result['passed']&=len(rows)==2*len(m['screen'])
      a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(f"feed-denial public oracle: {'PASS' if result['passed'] else 'FAIL'} ({a.output})"); return 0 if result['passed'] else 1
if __name__=='__main__': raise SystemExit(main())

import argparse
import fcntl
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .collector import collect_queries, http_fetch, robots_allows_search
from .publish import publish_files
from .report import build_snapshot, render_digest, render_html
from .storage import Store

ARTIFACTS=("index.html","daily.json","daily.txt")

def _atomic_write_artifacts(output: Path, files: dict[str,str]):
    output.mkdir(parents=True,exist_ok=True)
    staged=[]
    try:
        for name,content in files.items():
            with tempfile.NamedTemporaryFile("w",dir=output,prefix=f".{name}.",delete=False) as handle:
                handle.write(content); handle.flush(); os.fsync(handle.fileno())
                staged.append((Path(handle.name),output/name))
        for source,target in staged: os.replace(source,target)
    finally:
        for source,_ in staged:
            if source.exists(): source.unlink()

def _render_artifacts(snapshot):
    return {"index.html":render_html(snapshot),"daily.json":json.dumps(snapshot,ensure_ascii=False,indent=2),"daily.txt":render_digest(snapshot)}

def _publish_artifacts(files: dict[str,str], token: str):
    return publish_files(token,{f"docs/{name}":content for name,content in files.items()})

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--config",default="config/searches.json")
    p.add_argument("--db",default="data/market.db")
    p.add_argument("--output",default="docs")
    p.add_argument("--publish",action="store_true")
    p.add_argument("--skip-robots-check",action="store_true")
    p.add_argument("--delay",type=float)
    p.add_argument("--max-pages",type=int)
    args=p.parse_args(argv)
    cfg=json.loads(Path(args.config).read_text())
    queries=cfg.get("queries",[])
    if not queries or len(set(queries)) != len(queries): raise ValueError("configured queries must be non-empty and unique")
    delay=cfg["delay_seconds"] if args.delay is None else args.delay
    max_pages=cfg["max_pages_per_query"] if args.max_pages is None else args.max_pages
    if not isinstance(delay,(int,float)) or delay < 0: raise ValueError("delay must be non-negative")
    if not isinstance(max_pages,int) or max_pages < 1: raise ValueError("max-pages must be a positive integer")
    db_path=Path(args.db); db_path.parent.mkdir(parents=True,exist_ok=True)
    output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    token=os.environ.get("GITHUB_LLM_MANAGER") or os.environ.get("GITHUB_TOKEN")
    lock_path=db_path.with_suffix(".lock")
    with lock_path.open("w") as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: print("collector already running",file=sys.stderr); return 3
        store=Store(str(db_path))
        try:
            today=datetime.now(ZoneInfo("Europe/Budapest")).date().isoformat()
            existing_run=store.latest_success_on(today)
            if existing_run:
                snapshot=store.report_on(today)
                if snapshot is None:
                    snapshot=build_snapshot(store,existing_run)
                    store.save_report(existing_run.run_id,snapshot)
                files=_render_artifacts(snapshot)
                _atomic_write_artifacts(output,files)
                commit=None
                if args.publish:
                    if not token: raise RuntimeError("GITHUB_LLM_MANAGER is not configured")
                    commit=_publish_artifacts(files,token)["commit"]
                    store.mark_published(existing_run.run_id)
                print(json.dumps({"status":"republished" if args.publish else "already-complete","commit":commit,"report_date":today}))
                return 0
            if not args.skip_robots_check and not robots_allows_search(http_fetch):
                print("Profession.hu robots policy disallows search collection",file=sys.stderr); return 4
            by_query,errors=collect_queries(queries,max_pages,http_fetch,delay)
            if errors:
                store.record_partial_run(by_query,len(queries))
                print(json.dumps({"status":"partial","errors":errors,"completed_queries":len(by_query)},ensure_ascii=False),file=sys.stderr)
                return 2
            run=store.record_successful_run(by_query,len(queries))
            if run.status != "success":
                print("run failed completeness validation",file=sys.stderr); return 2
            snapshot=build_snapshot(store,run)
            store.save_report(run.run_id,snapshot)
            files=_render_artifacts(snapshot)
            _atomic_write_artifacts(output,files)
            commit=None
            if args.publish:
                if not token: raise RuntimeError("GITHUB_LLM_MANAGER is not configured")
                commit=_publish_artifacts(files,token)["commit"]
                store.mark_published(run.run_id)
            print(json.dumps({"status":"success","active":run.active_total,"new":len(run.new_ids),"expired":len(run.expired_ids),"updated_at":run.completed_at,"commit":commit}))
            return 0
        finally: store.close()

if __name__ == "__main__": raise SystemExit(main())

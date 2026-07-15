import json
import urllib.error
import urllib.parse
import urllib.request

API="https://api.github.com"

def _request(url,token,method="GET",body=None):
    headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","Content-Type":"application/json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"HungaryDataJobsMonitor/1.0"}
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            raw=response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode("utf-8","replace")[:500]
        raise RuntimeError(f"GitHub API HTTP {exc.code}: {detail}") from exc

def publish_files(token: str, files: dict[str,str], repo="febert-aisandbox/hungary-data-jobs-monitor", branch="main"):
    """Publish every artifact in one Git commit and one non-forced ref update."""
    repo_url=f"{API}/repos/{repo}"
    ref=_request(f"{repo_url}/git/ref/heads/{urllib.parse.quote(branch,safe='')}",token)
    parent=ref["object"]["sha"]
    parent_commit=_request(f"{repo_url}/git/commits/{parent}",token)
    entries=[]
    for path,content in files.items():
        blob=_request(f"{repo_url}/git/blobs",token,"POST",{"content":content,"encoding":"utf-8"})
        entries.append({"path":path,"mode":"100644","type":"blob","sha":blob["sha"]})
    tree=_request(f"{repo_url}/git/trees",token,"POST",{"base_tree":parent_commit["tree"]["sha"],"tree":entries})
    commit=_request(f"{repo_url}/git/commits",token,"POST",{"message":"data: update daily market report","tree":tree["sha"],"parents":[parent]})
    _request(f"{repo_url}/git/refs/heads/{urllib.parse.quote(branch,safe='')}",token,"PATCH",{"sha":commit["sha"],"force":False})
    return {"commit":commit["sha"],"files":sorted(files)}

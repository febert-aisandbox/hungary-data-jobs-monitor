import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

REPORT_URL="https://febert-aisandbox.github.io/hungary-data-jobs-monitor/daily.json"
TZ=ZoneInfo("Europe/Budapest")
MAX_RESPONSE_BYTES=1_000_000


def _valid_snapshot(snapshot, today: str) -> bool:
    if not isinstance(snapshot,dict) or snapshot.get("report_date") != today or snapshot.get("status") != "success": return False
    integer_fields=("active_total","new_total","expired_total","junior_total","hybrid_remote_total")
    if not all(type(snapshot.get(key)) is int and 0<=snapshot[key]<=1_000_000 for key in integer_fields): return False
    return isinstance(snapshot.get("role_families"),dict) and isinstance(snapshot.get("new_jobs"),list)


def _digest(snapshot: dict) -> str:
    lines=[f"**Hungary data jobs — {snapshot['report_date']}**",f"Observed: **{snapshot['active_total']}** · New: **{snapshot['new_total']}** · No longer observed: **{snapshot['expired_total']}**",f"Junior/internship: **{snapshot['junior_total']}** · Hybrid/remote: **{snapshot['hybrid_remote_total']}**","\n[Open dashboard](https://febert-aisandbox.github.io/hungary-data-jobs-monitor/)"]
    output="\n".join(lines)
    if len(output)>3900: raise ValueError("rendered digest too long")
    return output


def decide_delivery(now: datetime, snapshot) -> str:
    if now.tzinfo is None: raise ValueError("now must be timezone-aware")
    local=now.astimezone(TZ)
    if (local.hour,local.minute)!=(7,30): return ""
    today=local.date().isoformat()
    if not _valid_snapshot(snapshot,today): return f"⚠️ Hungary data jobs report is not available for {today}. The collector will retry on its next scheduled run."
    return _digest(snapshot)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl): return None


def _fetch_report() -> dict:
    request=urllib.request.Request(REPORT_URL,headers={"User-Agent":"HungaryDataJobsMonitor/1.0 (+https://github.com/febert-aisandbox/hungary-data-jobs-monitor)"})
    with urllib.request.build_opener(_NoRedirect).open(request,timeout=20) as response:
        final=urllib.parse.urlsplit(response.geturl())
        if response.status != 200 or final.scheme != "https" or final.hostname != "febert-aisandbox.github.io" or response.headers.get_content_type() != "application/json": raise RuntimeError("unexpected report response")
        declared=response.headers.get("Content-Length")
        if declared and int(declared)>MAX_RESPONSE_BYTES: raise RuntimeError("report response too large")
        payload=response.read(MAX_RESPONSE_BYTES+1)
        if len(payload)>MAX_RESPONSE_BYTES: raise RuntimeError("report response too large")
        value=json.loads(payload.decode("utf-8","strict"))
        return value if isinstance(value,dict) else {}


def main() -> int:
    now=datetime.now(TZ)
    if (now.hour,now.minute)!=(7,30): return 0
    try: snapshot=_fetch_report()
    except (OSError,RuntimeError,ValueError,json.JSONDecodeError,UnicodeError,urllib.error.HTTPError): snapshot=None
    output=decide_delivery(now,snapshot)
    if output: print(output)
    return 0


if __name__ == "__main__": raise SystemExit(main())

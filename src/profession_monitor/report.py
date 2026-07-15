import html
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

SITE_URL = "https://febert-aisandbox.github.io/hungary-data-jobs-monitor/"

def _pretty_location(value):
    return (value or "Unspecified").replace("_megye,_", " county, ").replace("_megye", " county").replace("_", " ")

def build_snapshot(store, run, site_url=SITE_URL):
    jobs = store.active_jobs()
    new_jobs = store.jobs_by_ids(run.new_ids)
    family = Counter(j["family"] for j in jobs)
    locations = Counter(_pretty_location(j["location"]) for j in jobs)
    skills = Counter(s for j in jobs for s in (j["skills"] or "").split("|") if s)
    hybrid_remote=sum(bool(j["work_mode"]) for j in jobs)
    junior=sum(any(x in f'{j["title"]} {j["seniority"]}'.casefold() for x in ("junior","gyakornok","intern","pályakezd")) for j in jobs)
    local = datetime.fromisoformat(run.completed_at).astimezone(ZoneInfo("Europe/Budapest"))
    return {
        "report_date": local.date().isoformat(), "updated_at": local.strftime("%Y-%m-%d %H:%M %Z"),
        "status": run.status, "active_total": len(jobs), "new_total": len(run.new_ids), "expired_total": len(run.expired_ids),
        "junior_total": junior, "hybrid_remote_total": hybrid_remote,
        "role_families": dict(family.most_common()), "top_locations": locations.most_common(10), "top_skills": skills.most_common(12),
        "new_jobs": [{**{k:j[k] for k in ("job_id","title","company","url","family","work_mode")},"location":_pretty_location(j["location"])} for j in new_jobs[:25]],
        "active_jobs": [{**{k:j[k] for k in ("job_id","title","company","url","family","work_mode","seniority")},"location":_pretty_location(j["location"])} for j in jobs],
        "history": store.history(30), "site_url": site_url,
        "methodology": "Public Profession.hu search pages; title-based relevance classification; overlapping queries deduplicated by advertisement ID. Counts represent advertisements, not hires or guaranteed vacancies."
    }

def _table(rows):
    return "".join(f"<tr><td>{html.escape(str(a))}</td><td>{html.escape(str(b))}</td></tr>" for a,b in rows) or "<tr><td colspan=\"2\">No data yet</td></tr>"

def render_html(s):
    cards = "".join(f'<article><h3><a href="{html.escape(j["url"])}">{html.escape(j["title"])}</a></h3><p>{html.escape(j["company"] or "Unspecified company")} · {html.escape(j["location"] or "Unspecified")} · {html.escape(j["family"])}</p></article>' for j in s["active_jobs"][:100])
    new_cards = "".join(f'<li><a href="{html.escape(j["url"])}">{html.escape(j["title"])}</a> — {html.escape(j["company"] or "")}</li>' for j in s["new_jobs"]) or "<li>No newly observed relevant advertisements.</li>"
    history = "".join(f'<tr><td>{html.escape(r["completed_at"][:10])}</td><td>{r["active_count"]}</td><td>{r["new_count"]}</td><td>{r["expired_count"]}</td></tr>' for r in s["history"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hungary Data Jobs Monitor</title><style>
:root{{--ink:#172033;--muted:#607089;--blue:#2457d6;--pale:#eef3ff;--line:#dce3ef}}*{{box-sizing:border-box}}body{{margin:0;background:#f6f8fc;color:var(--ink);font:16px/1.55 system-ui,sans-serif}}main{{max-width:1100px;margin:auto;background:#fff;min-height:100vh;padding:42px 6vw 70px}}h1{{font-size:clamp(2rem,5vw,3.4rem);line-height:1.05;margin:.2em 0}}.meta{{color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:24px 0}}.metric{{background:var(--pale);padding:18px;border-radius:12px}}.metric b{{display:block;font-size:2rem;color:var(--blue)}}section{{margin-top:38px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border:1px solid var(--line);text-align:left}}article{{border-bottom:1px solid var(--line);padding:10px 0}}a{{color:var(--blue)}}small{{color:var(--muted)}}
</style></head><body><main><p class="meta">PROFESSION.HU · DAILY MARKET MONITOR</p><h1>Hungary data jobs</h1><p class="meta">Last successful update: {html.escape(s["updated_at"])}</p>
<div class="grid"><div class="metric"><b>{s["active_total"]}</b>active relevant ads</div><div class="metric"><b>{s["new_total"]}</b>new this run</div><div class="metric"><b>{s["expired_total"]}</b>recently expired</div><div class="metric"><b>{s["junior_total"]}</b>junior / internship</div><div class="metric"><b>{s["hybrid_remote_total"]}</b>hybrid / remote</div></div>
<section><h2>Newly observed</h2><ul>{new_cards}</ul></section>
<section><h2>Role mix</h2><table><thead><tr><th>Family</th><th>Active ads</th></tr></thead><tbody>{_table(s["role_families"].items())}</tbody></table></section>
<section><h2>Top locations</h2><table><thead><tr><th>Location</th><th>Ads</th></tr></thead><tbody>{_table(s["top_locations"])}</tbody></table></section>
<section><h2>Skills mentioned in cards</h2><table><thead><tr><th>Skill</th><th>Ads</th></tr></thead><tbody>{_table(s["top_skills"])}</tbody></table></section>
<section><h2>30-run history</h2><table><thead><tr><th>Date</th><th>Active</th><th>New</th><th>Expired</th></tr></thead><tbody>{history}</tbody></table></section>
<section><h2>Active opportunities</h2>{cards or '<p>No active advertisements.</p>'}</section>
<section><h2>Methodology</h2><small>{html.escape(s["methodology"])}</small></section></main></body></html>'''

def _md_text(value):
    return "".join("\\"+ch if ch in r"\\_*[]()~`>#+-=|{}.!" else ch for ch in str(value))

def render_digest(s):
    roles = ", ".join(f"{_md_text(k)}: {v}" for k,v in s["role_families"].items()) or "none"
    lines = [f"**Hungary data jobs — {s['report_date']}**", f"Active: **{s['active_total']}** · New: **{s['new_total']}** · Expired: **{s['expired_total']}**", f"Junior/internship: **{s['junior_total']}** · Hybrid/remote: **{s['hybrid_remote_total']}**", f"Role mix: {roles}"]
    if s["new_jobs"]:
        lines.append("\n**Noteworthy new listings**")
        for j in s["new_jobs"][:8]: lines.append(f"- [{_md_text(j['title'])}]({j['url']}) — {_md_text(j['company'])} \\({_md_text(j['location'] or 'location unspecified')}\\)")
    lines += [f"\n[Full market dashboard]({s['site_url']})", "_Counts are advertisements, deduplicated by Profession.hu ID; they are not hires._"]
    return "\n".join(lines)[:2490]

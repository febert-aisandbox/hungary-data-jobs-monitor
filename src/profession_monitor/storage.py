import json
import sqlite3
from datetime import datetime, timezone
from dataclasses import replace
from zoneinfo import ZoneInfo

from .classify import classify_job, extract_skills
from .models import Job, RunResult

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, completed_at TEXT NOT NULL, status TEXT NOT NULL, expected_queries INTEGER NOT NULL, completed_queries INTEGER NOT NULL, active_count INTEGER NOT NULL DEFAULT 0, new_count INTEGER NOT NULL DEFAULT 0, expired_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY, url TEXT NOT NULL, title TEXT NOT NULL, company TEXT, location TEXT, seniority TEXT, work_mode TEXT, card_text TEXT, family TEXT, skills TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, miss_count INTEGER NOT NULL DEFAULT 0, last_miss_date TEXT);
CREATE TABLE IF NOT EXISTS observations(run_id INTEGER NOT NULL, job_id TEXT NOT NULL, PRIMARY KEY(run_id, job_id));
CREATE TABLE IF NOT EXISTS job_queries(run_id INTEGER NOT NULL, job_id TEXT NOT NULL, query TEXT NOT NULL, PRIMARY KEY(run_id, job_id, query));
CREATE TABLE IF NOT EXISTS run_events(run_id INTEGER NOT NULL, job_id TEXT NOT NULL, event TEXT NOT NULL, PRIMARY KEY(run_id, job_id, event));
CREATE TABLE IF NOT EXISTS reports(run_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0);
"""

class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        columns={row[1] for row in self.db.execute("PRAGMA table_info(jobs)")}
        if "last_miss_date" not in columns:
            self.db.execute("ALTER TABLE jobs ADD COLUMN last_miss_date TEXT")
            self.db.commit()

    def has_success_on(self, date: str) -> bool:
        return self.latest_success_on(date) is not None

    def latest_success_on(self, date: str):
        rows=self.db.execute("SELECT * FROM runs WHERE status='success' ORDER BY id DESC").fetchall()
        row=next((r for r in rows if datetime.fromisoformat(r["completed_at"]).astimezone(ZoneInfo("Europe/Budapest")).date().isoformat()==date),None)
        if row is None: return None
        events=self.db.execute("SELECT job_id,event FROM run_events WHERE run_id=?",(row["id"],)).fetchall()
        return RunResult(row["id"],row["completed_at"],sorted(r["job_id"] for r in events if r["event"]=="new"),sorted(r["job_id"] for r in events if r["event"]=="expired"),row["active_count"],row["status"])

    def save_report(self, run_id: int, payload: dict):
        self.db.execute("INSERT INTO reports(run_id,payload) VALUES(?,?) ON CONFLICT(run_id) DO UPDATE SET payload=excluded.payload",(run_id,json.dumps(payload,ensure_ascii=False)))
        self.db.commit()

    def report_on(self, date: str):
        run=self.latest_success_on(date)
        if run is None: return None
        row=self.db.execute("SELECT payload FROM reports WHERE run_id=?",(run.run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def mark_published(self, run_id: int):
        self.db.execute("UPDATE reports SET published=1 WHERE run_id=?",(run_id,)); self.db.commit()

    def close(self): self.db.close()

    def record_successful_run(self, by_query: dict[str, list[Job]], expected_queries: int, observed_at: str | None = None) -> RunResult:
        if len(by_query) != expected_queries:
            return self.record_partial_run(by_query, expected_queries, observed_at)
        return self._record(by_query, expected_queries, observed_at)

    def record_partial_run(self, by_query: dict[str, list[Job]], expected_queries: int | None = None, observed_at: str | None = None) -> RunResult:
        now = observed_at or datetime.now(timezone.utc).isoformat()
        cur = self.db.execute("INSERT INTO runs(completed_at,status,expected_queries,completed_queries,active_count) VALUES(?,?,?,?,?)", (now,"partial",expected_queries or len(by_query),len(by_query),self.active_count()))
        self.db.commit()
        return RunResult(cur.lastrowid,now,[],[],self.active_count(),"partial")

    def _record(self, by_query, expected_queries, observed_at=None):
        now = observed_at or datetime.now(timezone.utc).isoformat()
        run_date = datetime.fromisoformat(now).astimezone(ZoneInfo("Europe/Budapest")).date().isoformat()
        status = "success"
        cur = self.db.execute("INSERT INTO runs(completed_at,status,expected_queries,completed_queries) VALUES(?,?,?,?)", (now,status,expected_queries,len(by_query)))
        run_id = cur.lastrowid
        existing = {r["job_id"]: dict(r) for r in self.db.execute("SELECT * FROM jobs")}
        seen: dict[str, Job] = {}
        new_ids: list[str] = []
        for query, jobs in by_query.items():
            for original in jobs:
                cls = classify_job(original.title, original.card_text)
                if not cls.relevant:
                    continue
                enriched = replace(original, family=cls.family, skills=tuple(extract_skills(original.card_text)), seniority=cls.seniority if cls.seniority != "unspecified" else original.seniority)
                seen[enriched.job_id] = enriched
                prior = existing.get(enriched.job_id)
                if prior is None or not prior["active"]:
                    new_ids.append(enriched.job_id)
                self.db.execute("""INSERT INTO jobs(job_id,url,title,company,location,seniority,work_mode,card_text,family,skills,first_seen,last_seen,active,miss_count)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,0)
                    ON CONFLICT(job_id) DO UPDATE SET url=excluded.url,title=excluded.title,company=excluded.company,location=excluded.location,seniority=excluded.seniority,work_mode=excluded.work_mode,card_text=excluded.card_text,family=excluded.family,skills=excluded.skills,last_seen=excluded.last_seen,active=1,miss_count=0,last_miss_date=NULL""",
                    (enriched.job_id,enriched.url,enriched.title,enriched.company,enriched.location,enriched.seniority,enriched.work_mode,enriched.card_text,enriched.family,"|".join(enriched.skills),now,now))
                self.db.execute("INSERT OR IGNORE INTO observations(run_id,job_id) VALUES(?,?)", (run_id,enriched.job_id))
                self.db.execute("INSERT OR IGNORE INTO job_queries(run_id,job_id,query) VALUES(?,?,?)", (run_id,enriched.job_id,query))
        expired: list[str] = []
        active_ids = [r[0] for r in self.db.execute("SELECT job_id FROM jobs WHERE active=1")]
        for job_id in active_ids:
            if job_id not in seen:
                prior_miss=self.db.execute("SELECT last_miss_date FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0]
                if prior_miss != run_date:
                    self.db.execute("UPDATE jobs SET miss_count=miss_count+1,last_miss_date=? WHERE job_id=?", (run_date,job_id))
                misses = self.db.execute("SELECT miss_count FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0]
                if misses >= 2:
                    self.db.execute("UPDATE jobs SET active=0 WHERE job_id=?", (job_id,))
                    expired.append(job_id)
        active = self.active_count()
        for job_id in set(new_ids): self.db.execute("INSERT OR IGNORE INTO run_events(run_id,job_id,event) VALUES(?,?,?)",(run_id,job_id,"new"))
        for job_id in expired: self.db.execute("INSERT OR IGNORE INTO run_events(run_id,job_id,event) VALUES(?,?,?)",(run_id,job_id,"expired"))
        self.db.execute("UPDATE runs SET active_count=?,new_count=?,expired_count=? WHERE id=?", (active,len(set(new_ids)),len(expired),run_id))
        self.db.commit()
        return RunResult(run_id,now,sorted(set(new_ids)),sorted(expired),active,status)

    def active_count(self): return self.db.execute("SELECT COUNT(*) FROM jobs WHERE active=1").fetchone()[0]
    def active_jobs(self): return [dict(r) for r in self.db.execute("SELECT * FROM jobs WHERE active=1 ORDER BY last_seen DESC,title")]
    def jobs_by_ids(self, ids):
        if not ids: return []
        marks=",".join("?" for _ in ids)
        return [dict(r) for r in self.db.execute(f"SELECT * FROM jobs WHERE job_id IN ({marks}) ORDER BY title", tuple(ids))]
    def history(self, days=30):
        return [dict(r) for r in self.db.execute("SELECT completed_at,status,active_count,new_count,expired_count FROM runs WHERE status='success' ORDER BY id DESC LIMIT ?", (days,))][::-1]

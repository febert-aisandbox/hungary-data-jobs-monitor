from dataclasses import dataclass, field

@dataclass(frozen=True)
class Job:
    job_id: str
    url: str
    title: str
    company: str
    location: str
    seniority: str
    work_mode: str
    card_text: str
    family: str = "other"
    skills: tuple[str, ...] = field(default_factory=tuple)

@dataclass(frozen=True)
class Classification:
    relevant: bool
    family: str
    seniority: str = "unspecified"
    reason: str = ""

@dataclass(frozen=True)
class ParseResult:
    jobs: list[Job]
    total_results: int

@dataclass(frozen=True)
class RunResult:
    run_id: int
    completed_at: str
    new_ids: list[str]
    expired_ids: list[str]
    active_total: int
    status: str = "success"

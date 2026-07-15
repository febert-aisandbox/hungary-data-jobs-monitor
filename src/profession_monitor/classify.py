import re
from .models import Classification

NEGATIVE = ("data entry", "adatrögzítő", "adatrogzito", "administrator")
FAMILIES = (
    ("data-science-ml", ("data scientist", "adattud", "machine learning", "ml engineer", "ai engineer")),
    ("data-engineering", ("data engineer", "analytics engineer", "etl developer", "adatbázis", "database engineer")),
    ("quant-risk", ("quantitative", "quant analyst", "risk analyst", "kockázati elemző", "fraud analyst", "actuar")),
    ("analyst-bi", ("data analyst", "adatelemző", "adatelemzo", "bi analyst", "business intelligence", "master data analyst", "reporting analyst", "data analytics")),
)
SKILLS = {
    "SQL": (r"\bsql\b",), "Python": (r"\bpython\b",), "Power BI": (r"power\s*bi",),
    "Tableau": (r"\btableau\b",), "Excel": (r"\bexcel\b",), "AWS": (r"\baws\b",),
    "Azure": (r"\bazure\b",), "GCP": (r"\bgcp\b", r"google cloud"), "Spark": (r"\bspark\b",),
    "dbt": (r"\bdbt\b",), "Docker": (r"\bdocker\b",), "Machine learning": (r"machine learning",),
    "Statistics": (r"statiszt", r"\bstatistics?\b"), "English": (r"\bangol\b", r"\benglish\b"),
}


def classify_job(title: str, text: str) -> Classification:
    value = f"{title} {text}".casefold()
    title_cf = title.casefold()
    if any(x in title_cf for x in NEGATIVE):
        return Classification(False, "other", reason="negative-title-pattern")
    for family, patterns in FAMILIES:
        if any(p in title_cf for p in patterns):
            seniority = "junior" if any(x in value for x in ("junior", "gyakornok", "intern", "pályakezd")) else "senior" if any(x in value for x in ("senior", "lead", "vezető")) else "unspecified"
            return Classification(True, family, seniority, "title-pattern")
    return Classification(False, "other", reason="no-data-role-title-pattern")


def extract_skills(text: str) -> list[str]:
    found = [name for name, patterns in SKILLS.items() if any(re.search(p, text, re.I) for p in patterns)]
    return sorted(found, key=str.casefold)

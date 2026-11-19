"""Open roles from public job boards (Ashby, Greenhouse, Lever) and YC job pages.

Job titles vary a lot ("support engineer", "customer engineer", "FDE"...), so roles are matched by regex
groups from config.json, and each job is tagged by where you can work from.
"""
from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor

from .sources import fetch, log

INDIA = re.compile(r"(?i:\b(india|bengaluru|bangalore|chennai|hyderabad|pune|mumbai|delhi|gurgaon|gurugram|noida)\b)|\bIN\b")
APAC = re.compile(r"\b(apac|asia|asia[- ]pacific)\b", re.I)
GLOBAL = re.compile(r"\b(anywhere|worldwide|global|international)\b", re.I)
US_ONLY = re.compile(r"\b(remote \(us\)|us only|united states only|us-based|must be (located|based) in the us)\b", re.I)
US_PLACE = re.compile(r"\b(US|USA|United States|CA|NY|NYC|San Francisco|New York|Seattle|Austin|Boston|Los Angeles|KY|TX|WA)\b")
OTHER_REGION = re.compile(r"\b(amer|americas|latam|emea|europe|uk|united kingdom|london|canada|toronto|ontario|australia|berlin|"
                          r"vienna|austria|prague|czech|sofia|bulgaria|germany|france|paris|amsterdam|dublin|ireland|"
                          r"spain|portugal|poland|japan|tokyo|singapore)\b", re.I)


def slugs(name: str, website: str = "") -> list[str]:
    """Likely job-board slugs: 'Agent 37' -> agent37, agent-37; website acme.ai -> acme."""
    base = name.split("/")[-1].strip().lower()
    out = [re.sub(r"[^a-z0-9]", "", base), re.sub(r"[^a-z0-9]+", "-", base).strip("-")]
    host = re.sub(r"^https?://(www\.)?", "", website or "").split("/")[0]
    if host:
        out.append(host.split(".")[0].lower())
    return [s for i, s in enumerate(out) if s and s not in out[:i]]


def _get_json(url: str):
    try:
        return json.loads(fetch(url))
    except Exception:
        return None


def ashby(slug: str) -> list[dict]:
    d = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    if not d or "jobs" not in d:
        return []
    return [{"title": j.get("title", ""),
             "location": ", ".join(filter(None, [j.get("location", "")] +
                                          [a.get("location", "") for a in j.get("secondaryLocations") or []])),
             "remote": bool(j.get("isRemote")) or (j.get("workplaceType") or "").lower() == "remote",
             "url": j.get("jobUrl", ""),
             "pay": (j.get("compensation") or {}).get("compensationTierSummary") or "",
             "visa": ""} for j in d["jobs"] if j.get("isListed", True)]


def greenhouse(slug: str) -> list[dict]:
    d = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    if not d or "jobs" not in d:
        return []
    return [{"title": j.get("title", ""), "location": (j.get("location") or {}).get("name", ""),
             "remote": "remote" in ((j.get("location") or {}).get("name", "")).lower(),
             "url": j.get("absolute_url", ""), "pay": "", "visa": ""} for j in d["jobs"]]


def lever(slug: str) -> list[dict]:
    d = _get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not isinstance(d, list):
        return []
    return [{"title": j.get("text", ""),
             "location": ", ".join((j.get("categories") or {}).get("allLocations") or
                                   [(j.get("categories") or {}).get("location", "")]),
             "remote": (j.get("workplaceType") or "").lower() == "remote",
             "url": j.get("hostedUrl", ""), "pay": "", "visa": ""} for j in d]


def yc_jobs(profile_url: str) -> list[dict]:
    try:
        page = fetch(profile_url.rstrip("/") + "/jobs")
        props = json.loads(html.unescape(re.search(r'data-page="([^"]+)"', page).group(1)))["props"]
    except Exception:
        return []
    out = []
    for j in props.get("jobPostings") or []:
        url = j.get("url") or ""
        out.append({"title": j.get("title", ""), "location": j.get("location", ""),
                    "remote": "remote" in (j.get("location") or "").lower(),
                    "url": ("https://www.ycombinator.com" + url) if url.startswith("/") else url,
                    "pay": j.get("salaryRange") or "", "visa": j.get("visa") or ""})
    return out


def board_for(company: dict) -> tuple[str, list[dict]]:
    """Return (board label, jobs) for the first ATS that answers for any slug guess."""
    jobs, label = [], ""
    if company.get("source") == "YC" and company.get("hiring") == "yes" and company.get("profile"):
        jobs, label = yc_jobs(company["profile"]), "YC"
    for s in slugs(company["name"], company.get("website", "")):
        for name, fn in (("ashby", ashby), ("greenhouse", greenhouse), ("lever", lever)):
            got = fn(s)
            if got:
                seen = {j["url"] for j in jobs}
                return f"{label}+{name}:{s}".lstrip("+"), jobs + [j for j in got if j["url"] not in seen]
    return label, jobs


def eligibility(job: dict) -> str:
    """india | remote-global | other-region | us-only | check"""
    loc, visa = job["location"] or "", (job.get("visa") or "").lower()
    if INDIA.search(loc):
        return "india"
    if "us citizen" in visa or US_ONLY.search(loc):
        return "us-only"
    remote = "remote" in loc.lower() or job.get("remote")
    if APAC.search(loc) or GLOBAL.search(loc):  # APAC includes India
        return "remote-global" if remote else "check"
    leftover = re.sub(r"[^a-z]+", " ", loc.lower().replace("remote", "")).strip()
    if remote and not leftover:  # just "Remote"
        return "remote-global"
    if OTHER_REGION.search(loc):
        return "other-region"
    if US_PLACE.search(loc):
        return "us-only"
    return "check"


def collect(companies: list[dict], role_re: re.Pattern, workers: int = 8) -> tuple[list[dict], dict]:
    boards: dict = {}

    def one(c):
        return c, board_for(c)

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for c, (label, jobs) in ex.map(one, companies):
            if label:
                boards[c["name"]] = label
            for j in jobs:
                if role_re.search(j["title"]):
                    j.update(company=c["name"], board=label, eligible=eligibility(j))
                    rows.append(j)
    log(f"  job boards found for {len(boards)} of {len(companies)} companies; {len(rows)} matching roles")
    return rows, boards

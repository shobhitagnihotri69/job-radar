"""Company sources: YC batches (yc-oss mirror) and a16z speedrun (latest cohort)."""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) job-radar"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def company(**kw) -> dict:
    base = {k: "" for k in ("source", "batch", "name", "one_liner", "description", "industries",
                            "location", "team_size", "hiring", "website", "profile")}
    base.update({k: ("" if v is None else v) for k, v in kw.items()})
    return base


def yc(batch: str) -> list[dict]:
    """batch is a yc-oss slug like 'winter-2027'. Unpublished batches 404 and return []."""
    try:
        data = json.loads(fetch(f"https://yc-oss.github.io/api/batches/{batch}.json"))
    except Exception as e:
        log(f"  yc {batch}: skipped ({e})")
        return []
    rows = [company(
        source="YC",
        batch=c.get("batch") or batch,
        name=c.get("name"),
        one_liner=c.get("one_liner"),
        description=(c.get("long_description") or "").replace("\n", " "),
        industries=", ".join(c.get("industries") or []),
        location=c.get("all_locations"),
        team_size=c.get("team_size"),
        hiring="yes" if c.get("isHiring") else "no",
        website=c.get("website"),
        profile=c.get("url"),
    ) for c in data]
    log(f"  yc {batch}: {len(rows)}")
    return rows


def speedrun() -> list[dict]:
    """a16z speedrun publishes its latest cohort in the page's __NEXT_DATA__ JSON."""
    try:
        page = fetch("https://speedrun.a16z.com/companies")
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
        data = json.loads(m.group(1))["props"]["pageProps"]["list"]["companies"]
    except Exception as e:
        log(f"  speedrun: failed ({e}); the page layout may have changed")
        return []
    rows = [company(
        source="a16z speedrun",
        batch=c.get("cohort"),
        name=c.get("name"),
        one_liner=c.get("oneLiner"),
        industries=", ".join(c.get("industries") or []),
        location=c.get("location"),
        team_size=c.get("teamSize"),
        hiring="unknown",
        profile=f"https://speedrun.a16z.com/companies/{c.get('slug', '')}",
    ) for c in data]
    log(f"  speedrun: {len(rows)}")
    return rows


def yc_profile(url: str) -> dict:
    """Founders, GitHub and social links from a YC company page (embedded data-page JSON)."""
    m = re.search(r'data-page="([^"]+)"', fetch(url))
    c = json.loads(html.unescape(m.group(1)))["props"]["company"]
    return {
        "github": c.get("github_url") or "",
        "x": c.get("twitter_url") or "",
        "linkedin": c.get("linkedin_url") or "",
        "founders": [{
            "name": f.get("full_name", ""),
            "title": f.get("title", ""),
            "linkedin": f.get("linkedin_url") or "",
            "x": f.get("twitter_url") or "",
            "bio": re.sub(r"\s+", " ", f.get("founder_bio") or "")[:240],
        } for f in c.get("founders", [])],
    }

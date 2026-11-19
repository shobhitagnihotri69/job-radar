"""Company sources: YC batches (yc-oss mirror) and a16z speedrun (latest cohort)."""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
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


HN_TITLE = re.compile(r"^(?:Launch|Show) HN:\s*(?P<name>.+?)\s*(?:\((?P<batch>YC [A-Z]\d{2})\))?\s*[–—:-]+\s*(?P<tag>.+)$")


def _since(days: int) -> int:
    import time
    return int(time.time()) - days * 86400


def hn(tag: str, days: int, min_points: int, query: str = "") -> list[dict]:
    """New launches on Hacker News. tag is 'launch_hn' (YC companies) or 'show_hn' (anyone)."""
    params = urllib.parse.urlencode({
        "tags": tag, "query": query, "hitsPerPage": 200,
        "numericFilters": f"created_at_i>{_since(days)},points>={min_points}",
    })
    try:
        hits = json.loads(fetch(f"https://hn.algolia.com/api/v1/search_by_date?{params}"))["hits"]
    except Exception as e:
        log(f"  hn {tag}: failed ({e})")
        return []
    rows = []
    for h in hits:
        m = HN_TITLE.match(h.get("title") or "")
        if not m:
            continue
        rows.append(company(
            source="Launch HN" if tag == "launch_hn" else "Show HN",
            batch=m.group("batch") or (h.get("created_at") or "")[:10],
            name=m.group("name"),
            one_liner=m.group("tag"),
            hiring="unknown",
            website=h.get("url") or "",
            profile=f"https://news.ycombinator.com/item?id={h['objectID']}",
            team_size="",
        ))
    log(f"  hn {tag}{' ' + query if query else ''}: {len(rows)}")
    return rows


def github_new(queries: list[str], days: int, min_stars: int) -> list[dict]:
    """Repos created in the last `days` days with traction - where open-source startups first appear."""
    import subprocess
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days)).isoformat()
    rows, seen = [], set()
    for q in queries:
        jq = '.items[] | {name: .full_name, desc: .description, stars: .stargazers_count, url: .html_url, home: .homepage, owner_type: .owner.type}'
        try:
            out = subprocess.run(
                ["gh", "api", "-X", "GET", "search/repositories",
                 "-f", f"q={q} created:>{since} stars:>={min_stars}", "-f", "sort=stars", "-f", "per_page=30",
                 "--jq", jq], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as e:
            log(f"  github '{q}': failed ({e})")
            continue
        for line in out.stdout.splitlines():
            r = json.loads(line)
            # startups publish from organizations; user-owned clones with farmed stars are a known malware pattern
            if r["name"] in seen or r["owner_type"] != "Organization":
                continue
            seen.add(r["name"])
            rows.append(company(
                source="GitHub new",
                batch=f'{r["stars"]} stars' + (" (org)" if r["owner_type"] == "Organization" else ""),
                name=r["name"],
                one_liner=r["desc"] or "",
                hiring="unknown",
                website=r["home"] or "",
                profile=r["url"],
            ))
    # identical descriptions across several repos = a spam cluster
    from collections import Counter
    dupes = Counter(r["one_liner"] for r in rows if r["one_liner"])
    rows = [r for r in rows if not r["one_liner"] or dupes[r["one_liner"]] < 2]
    log(f"  github new repos (orgs only): {len(rows)}")
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

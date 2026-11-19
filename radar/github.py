"""GitHub lookups through the authenticated `gh` CLI (avoids anonymous rate limits)."""
from __future__ import annotations

import base64
import json
import re
import subprocess


def open_issues(repo: str, days: int = 60, limit: int = 50) -> list[dict]:
    """Unclaimed issues: open, no assignee, created in the last `days` days.

    Uses the core issues API (5,000 req/hr), not search (30 req/min, easy to exhaust).
    Raises RuntimeError on API errors so a rate limit is never mistaken for "no issues".
    """
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days)).isoformat()
    jq = ('.[] | select(.pull_request|not) | select(.created_at >= "' + since + '") | '
          '{repo: "' + repo + '", number: .number, title: .title, url: .html_url, '
          'comments: .comments, created: .created_at[:10], labels: [.labels[].name]}')
    out = subprocess.run(
        ["gh", "api", f"repos/{repo}/issues?state=open&assignee=none&sort=created&direction=desc&per_page={limit}",
         "--jq", jq], capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip().splitlines()[-1] if out.stderr.strip() else "gh api failed")
    return [json.loads(line) for line in out.stdout.splitlines()]


CLOSED_PHRASES = re.compile(
    r"(do(es)? not|don't|doesn't|won't|will not|no longer|not) accept(ing)? (unsolicited |external |outside )?"
    r"(pull requests|prs|contributions|code contributions)", re.I)
INSIDERS = {"OWNER", "MEMBER", "COLLABORATOR"}


def _gh_json(path: str):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def pr_policy(repo: str, days: int = 30) -> dict:
    """Does the repo take outside PRs? Reads CONTRIBUTING and counts merged PRs from non-members.

    outside_merged is a lower bound: it only looks at the last 100 closed PRs.
    """
    from datetime import date, timedelta
    closed_text = ""
    for path in ("CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"):
        f = _gh_json(f"repos/{repo}/contents/{path}")
        if f and f.get("content"):
            text = base64.b64decode(f["content"]).decode("utf-8", "replace")
            m = CLOSED_PHRASES.search(text)
            if m:
                closed_text = m.group(0)
            break
    since = (date.today() - timedelta(days=days)).isoformat()
    pulls = _gh_json(f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100") or []
    merged = [p for p in pulls if p.get("merged_at") and p["merged_at"] >= since]
    # Org membership is often private, so core members show up as "CONTRIBUTOR". Count newcomers instead:
    # non-bot, non-member authors with at most 2 merged PRs in the window (the core team merges far more).
    from collections import Counter
    login = lambda p: (p.get("user") or {}).get("login", "")
    per_author = Counter(login(p) for p in merged)
    newcomers = [p for p in merged if p.get("author_association") not in INSIDERS
                 and not login(p).endswith("[bot]") and per_author[login(p)] <= 2]
    return {"closed": closed_text, "merged": len(merged), "outside_merged": len(newcomers),
            "newcomer_authors": len({login(p) for p in newcomers})}


def recent_repos(github_url: str, limit: int = 3) -> list[dict]:
    owner = github_url.rstrip("/").split("/")[-1] if "github.com/" in github_url else ""
    if not owner:
        return []
    jq = ('[.[] | select(.fork|not) | {name: .full_name, stars: .stargazers_count, '
          'issues: .open_issues_count, pushed: .pushed_at[:10], lang: .language}]')
    try:
        out = subprocess.run(["gh", "api", f"users/{owner}/repos?sort=pushed&per_page=10", "--jq", jq],
                             capture_output=True, text=True, timeout=30)
        return json.loads(out.stdout)[:limit] if out.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []

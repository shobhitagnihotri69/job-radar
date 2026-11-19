"""GitHub lookups through the authenticated `gh` CLI (avoids anonymous rate limits)."""
from __future__ import annotations

import json
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

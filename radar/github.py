"""GitHub lookups through the authenticated `gh` CLI (avoids anonymous rate limits)."""
from __future__ import annotations

import json
import subprocess


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

"""CLI: python3 -m radar scan | track | funnel"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import github, pipeline, report, sources
from .score import key, score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def scan(args, cfg: dict) -> None:
    out_dir = os.path.join(ROOT, cfg.get("output_dir", "out"))
    os.makedirs(out_dir, exist_ok=True)
    batches = args.yc or cfg["yc_batches"]

    sources.log("Fetching:")
    rows = [r for b in batches for r in sources.yc(b)]
    if cfg.get("speedrun", True) and not args.no_speedrun:
        rows += sources.speedrun()
    hn_cfg = cfg.get("hn", {})
    if hn_cfg and not args.no_hn:
        rows += sources.hn("launch_hn", hn_cfg["days"], hn_cfg["launch_min_points"])
        for q in hn_cfg.get("show_queries", []):
            rows += sources.hn("show_hn", hn_cfg["days"], hn_cfg["show_min_points"], q)
    gh_cfg = cfg.get("github_new", {})
    if gh_cfg and not args.no_github:
        rows += sources.github_new(gh_cfg["queries"], gh_cfg["days"], gh_cfg["min_stars"])

    # the same company can arrive from several sources (e.g. YC + Launch HN); keep the first
    uniq, names = [], set()
    for r in rows:
        n = r["name"].strip().lower()
        if n not in names:
            names.add(n)
            uniq.append(r)
    rows = uniq

    snap_path = os.path.join(out_dir, "snapshot.json")
    seen = set(json.load(open(snap_path))) if os.path.exists(snap_path) else set()
    first_run = not seen

    keywords = cfg["keywords"]
    for r in rows:
        r["score"], hits = score(r, keywords)
        r["matched"] = ", ".join(hits)
        r["remote"] = "yes" if "remote" in str(r["location"]).lower() else ""
        r["new"] = "" if first_run or key(r) in seen else "NEW"
    rows.sort(key=lambda r: (-r["score"], r["name"].lower()))

    min_score = args.min_score if args.min_score is not None else cfg["min_score"]
    label = (f"YC ({', '.join(batches)})" + ("" if args.no_speedrun else ", a16z speedrun")
             + ("" if args.no_hn else ", Launch HN / Show HN") + ("" if args.no_github else ", new GitHub repos"))
    report.write_csv(os.path.join(out_dir, "companies.csv"), rows)
    with open(os.path.join(out_dir, "REPORT.md"), "w") as f:
        f.write(report.report(rows, label, min_score, first_run, args.all))

    cards = []
    if args.enrich:
        sources.log("Enriching:")
        for r in [r for r in rows if r["score"] >= min_score and r["source"] == "YC"][:args.enrich]:
            try:
                p = sources.yc_profile(r["profile"])
            except Exception as e:
                sources.log(f"  {r['name']}: skipped ({e})")
                continue
            p["repos"] = github.recent_repos(p["github"])
            cards.append((r, p))
            sources.log(f"  {r['name']}: {len(p['founders'])} founders, {len(p['repos'])} repos")
        with open(os.path.join(out_dir, "ACTION_CARDS.md"), "w") as f:
            f.write(report.action_cards(cards))

    # remember which startup repos exist, for `radar issues`: enriched YC orgs + new GitHub startup repos
    repo_list = [{"company": r["name"], "repo": g["name"]} for r, p in cards for g in p["repos"]]
    repo_list += [{"company": r["name"].split("/")[0], "repo": r["name"]}
                  for r in rows if r["source"] == "GitHub new" and r["score"] >= min_score]
    if repo_list:
        with open(os.path.join(out_dir, "repos.json"), "w") as f:
            json.dump(repo_list, f)

    page = os.path.join(out_dir, "radar.html")
    with open(page, "w") as f:
        f.write(report.html_page(rows, cards, min_score))
    if args.open:
        import webbrowser
        webbrowser.open(f"file://{page}")

    with open(snap_path, "w") as f:
        json.dump(sorted(seen | {key(r) for r in rows}), f)

    n_match = sum(r["score"] >= min_score for r in rows)
    n_new = "first run" if first_run else f"{sum(bool(r['new']) for r in rows)} new"
    sources.log(f"\n{len(rows)} companies | {n_match} matches | "
                f"{sum(r['hiring'] == 'yes' for r in rows)} hiring | {n_new}")
    sources.log(f"-> {out_dir}/")


SKIP_LABELS = {"question", "discussion", "wontfix", "duplicate", "invalid", "rfc", "epic", "roadmap"}


def issues(args, cfg: dict) -> None:
    out_dir = os.path.join(ROOT, cfg.get("output_dir", "out"))
    repos = args.repo
    if not repos:
        path = os.path.join(out_dir, "repos.json")
        if not os.path.exists(path):
            sys.exit("No repos yet. Run: python3 -m radar scan --enrich 25   (or pass --repo owner/name)")
        repos = [x["repo"] for x in json.load(open(path))]
    found, skipped = [], []
    for repo in repos:
        policy = github.pr_policy(repo)
        if policy["closed"] and not args.include_closed:
            skipped.append(f'{repo} (CONTRIBUTING: "{policy["closed"]}")')
            sources.log(f"  {repo}: SKIPPED, does not accept outside PRs")
            continue
        try:
            got = github.open_issues(repo, days=args.days)
        except Exception as e:
            sources.log(f"  {repo}: ERROR {e}")
            continue
        for i in got:
            if not SKIP_LABELS & {l.lower() for l in i["labels"]}:
                i["outside_merged"] = policy["outside_merged"]
                found.append(i)
        sources.log(f"  {repo}: {sum(i['repo'] == repo for i in found)} unclaimed | "
                    f"newcomer PRs merged (30d): {policy['outside_merged']} of {policy['merged']}")
    # repos that actually merge outside PRs first, then bugs, then fewest comments, then newest
    found.sort(key=lambda i: (i["outside_merged"] == 0, not any("bug" in l.lower() for l in i["labels"]),
                              i["comments"], i["created"]))

    from html import escape as e
    rows = "".join(
        f'<tr><td>{e(i["repo"])}</td><td><a href="{e(i["url"])}" target="_blank" rel="noopener">#{i["number"]} {e(i["title"])}</a></td>'
        f'<td>{e(", ".join(i["labels"]))}</td><td>{i["comments"]}</td><td>{i["created"]}</td>'
        f'<td>{i["outside_merged"] or "<b>0</b>"}</td></tr>' for i in found)
    skipped_html = ("<p><b>Skipped (no outside PRs accepted):</b> " + e("; ".join(skipped)) + "</p>") if skipped else ""
    page = os.path.join(out_dir, "issues.html")
    with open(page, "w") as f:
        f.write(f"""<!doctype html><html><head><meta charset="utf-8"><title>Unclaimed issues</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--line:#e5e5e5;--link:#0b57d0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--fg:#e8e8e8;--line:#2c2c2c;--link:#8ab4f8}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.4 -apple-system,system-ui,sans-serif;margin:16px}}
table{{border-collapse:collapse;width:100%}} th,td{{text-align:left;padding:7px;border-bottom:1px solid var(--line);vertical-align:top}}
a{{color:var(--link);text-decoration:none}}</style></head><body>
<h2>Unclaimed issues ({len(found)})</h2>
<p>Open, no assignee, last {args.days} days. Before coding: reproduce it locally, then comment
that you are taking it. Aim for 50-100 lines. "Newcomer merges" = merged PRs (last 30 days) from authors with at most 2 merges, i.e. not the core team;
0 means newcomers rarely get merged there.</p>{skipped_html}
<table><tr><th>Repo</th><th>Issue</th><th>Labels</th><th>Comments</th><th>Opened</th><th>Newcomer merges</th></tr>{rows}</table></body></html>""")
    for i in found[:args.show]:
        print(f'{i["repo"]:<34} {i["url"]}  (newcomer merges 30d: {i["outside_merged"]})\n'
              f'    {i["title"][:90]}  [{", ".join(i["labels"])}]')
    for s in skipped:
        sources.log(f"  skipped: {s}")
    sources.log(f"\n{len(found)} unclaimed issues -> {page}")
    if args.open:
        import webbrowser
        webbrowser.open(f"file://{page}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="radar", description="Track newly funded startups and your outreach funnel.")
    ap.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="fetch companies, score them, write reports")
    s.add_argument("--yc", nargs="*", help="override yc batch slugs, e.g. winter-2027")
    s.add_argument("--no-speedrun", action="store_true")
    s.add_argument("--open", action="store_true", help="open out/radar.html in the browser when done")
    s.add_argument("--no-hn", action="store_true", help="skip Launch HN / Show HN")
    s.add_argument("--no-github", action="store_true", help="skip new GitHub repos")
    s.add_argument("--min-score", type=int)
    s.add_argument("--all", action="store_true", help="include non-matching companies in REPORT.md")
    s.add_argument("--enrich", type=int, default=0, metavar="N",
                   help="write ACTION_CARDS.md with founders and GitHub repos for the top N YC matches")

    t = sub.add_parser("track", help="set a company's pipeline stage")
    t.add_argument("company")
    t.add_argument("stage", choices=pipeline.STAGES)
    t.add_argument("--role", default="")
    t.add_argument("--channel", default="", help="e.g. referral, email, linkedin, x, pr, job-board")
    t.add_argument("--note", default="")

    sub.add_parser("funnel", help="show pipeline counts and reply rates")

    i = sub.add_parser("issues", help="unclaimed issues in the startups' public repos")
    i.add_argument("--repo", nargs="*", help="owner/name; default: repos found by the last scan --enrich")
    i.add_argument("--days", type=int, default=60)
    i.add_argument("--show", type=int, default=20, help="how many to print in the terminal")
    i.add_argument("--open", action="store_true", help="open out/issues.html in the browser")
    i.add_argument("--include-closed", action="store_true",
                   help="also list repos whose CONTRIBUTING says they do not accept outside PRs")

    args = ap.parse_args()
    cfg = load_config(args.config)
    pipe_path = os.path.join(ROOT, cfg.get("pipeline_file", "pipeline.csv"))

    if args.cmd == "scan":
        scan(args, cfg)
    elif args.cmd == "track":
        row = pipeline.track(pipe_path, args.company, args.stage, args.role, args.channel, args.note)
        print(f'{row["company"]}: {row["stage"]} ({row["updated"]})')
    elif args.cmd == "issues":
        issues(args, cfg)
    elif args.cmd == "funnel":
        print(pipeline.funnel(pipe_path))


if __name__ == "__main__":
    sys.exit(main())

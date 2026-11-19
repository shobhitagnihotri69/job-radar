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
    label = f"YC ({', '.join(batches)})" + ("" if args.no_speedrun else ", a16z speedrun (latest cohort)")
    report.write_csv(os.path.join(out_dir, "companies.csv"), rows)
    with open(os.path.join(out_dir, "REPORT.md"), "w") as f:
        f.write(report.report(rows, label, min_score, first_run, args.all))

    if args.enrich:
        sources.log("Enriching:")
        cards = []
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

    with open(snap_path, "w") as f:
        json.dump(sorted(seen | {key(r) for r in rows}), f)

    n_match = sum(r["score"] >= min_score for r in rows)
    n_new = "first run" if first_run else f"{sum(bool(r['new']) for r in rows)} new"
    sources.log(f"\n{len(rows)} companies | {n_match} matches | "
                f"{sum(r['hiring'] == 'yes' for r in rows)} hiring | {n_new}")
    sources.log(f"-> {out_dir}/")


def main() -> None:
    ap = argparse.ArgumentParser(prog="radar", description="Track newly funded startups and your outreach funnel.")
    ap.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="fetch companies, score them, write reports")
    s.add_argument("--yc", nargs="*", help="override yc batch slugs, e.g. winter-2027")
    s.add_argument("--no-speedrun", action="store_true")
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

    args = ap.parse_args()
    cfg = load_config(args.config)
    pipe_path = os.path.join(ROOT, cfg.get("pipeline_file", "pipeline.csv"))

    if args.cmd == "scan":
        scan(args, cfg)
    elif args.cmd == "track":
        row = pipeline.track(pipe_path, args.company, args.stage, args.role, args.channel, args.note)
        print(f'{row["company"]}: {row["stage"]} ({row["updated"]})')
    elif args.cmd == "funnel":
        print(pipeline.funnel(pipe_path))


if __name__ == "__main__":
    sys.exit(main())

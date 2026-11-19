"""Markdown/CSV writers."""
from __future__ import annotations

import csv
from datetime import date

FIELDS = ["new", "score", "source", "batch", "name", "one_liner", "industries", "location",
          "remote", "team_size", "hiring", "website", "profile", "matched", "description"]


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def table(rows: list[dict]) -> str:
    out = ["| Score | Company | Source / batch | What they build | Location | Team | Hiring |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        link = r["profile"] or r["website"]
        one = r["one_liner"].replace("|", "/")
        out.append(f'| {r["score"]} | [{r["name"]}]({link}) | {r["source"]} {r["batch"]} | {one} | '
                   f'{r["location"] or "-"} | {r["team_size"] or "-"} | {r["hiring"]} |')
    return "\n".join(out)


def report(rows: list[dict], sources: str, min_score: int, first_run: bool, show_all: bool) -> str:
    new = [r for r in rows if r["new"]]
    match = [r for r in rows if r["score"] >= min_score]
    hiring = [r for r in rows if r["hiring"] == "yes"]
    parts = [f"# Startup radar - {date.today()}", "", f"Sources: {sources}",
             f"Total: {len(rows)} | domain matches (score >= {min_score}): {len(match)} | "
             f"hiring now: {len(hiring)} | new since last run: {'first run' if first_run else len(new)}", ""]
    if new:
        parts += ["## New since last run", "", table(new), ""]
    parts += ["## Domain matches", "", table(match), ""]
    if hiring:
        parts += ["## Hiring now (any domain)", "", table(hiring), ""]
    if show_all:
        parts += ["## Everything else", "", table([r for r in rows if r["score"] < min_score]), ""]
    return "\n".join(parts)


def action_cards(cards: list[tuple[dict, dict]]) -> str:
    out = [f"# Action cards - {date.today()}", "",
           "See PLAYBOOK.md. Public repo -> one verified PR, then talk to the founder.",
           "No public repo -> use the product, send specific feedback, then talk to the founder.", ""]
    for r, p in cards:
        out += [f'## {r["name"]} ({r["batch"]}) - score {r["score"]}',
                f'{r["one_liner"]}  ',
                f'Location: {r["location"] or "-"} | team {r["team_size"] or "-"} | hiring: {r["hiring"]} | '
                f'[YC profile]({r["profile"]}) | [jobs]({r["profile"]}/jobs) | [site]({r["website"]})', ""]
        for f in p["founders"]:
            links = " ".join(f"[{k}]({v})" for k, v in (("LinkedIn", f["linkedin"]), ("X", f["x"])) if v)
            out.append(f'- **{f["name"]}** ({f["title"]}) {links}: {f["bio"]}')
        out.append("")
        if p["repos"]:
            out.append(f'GitHub: {p["github"]}')
            for g in p["repos"]:
                out.append(f'- [{g["name"]}](https://github.com/{g["name"]}) - {g["lang"]}, {g["stars"]} stars, '
                           f'{g["issues"]} open issues+PRs, last push {g["pushed"]} - '
                           f'[open bugs](https://github.com/{g["name"]}/issues?q=is%3Aopen+is%3Aissue+label%3Abug)')
        else:
            out.append("GitHub: no public repo. Route: product feedback, then founder conversation.")
        out.append("")
    return "\n".join(out)

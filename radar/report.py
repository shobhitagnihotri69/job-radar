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


def html_page(rows: list[dict], cards: list[tuple[dict, dict]], min_score: int) -> str:
    """Self-contained page with clickable links and a search box (no external assets)."""
    from html import escape as e

    def a(url: str, text: str) -> str:
        return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(text)}</a>' if url else e(text)

    by_name = {r["name"]: p for r, p in cards}
    trs = []
    for r in rows:
        if r["score"] < min_score and not r["new"]:
            continue
        p = by_name.get(r["name"])
        founders = ""
        if p:
            founders = "<br>".join(
                f'{e(f["name"])} '
                + " ".join(a(u, k) for k, u in (("in", f["linkedin"]), ("x", f["x"])) if u)
                for f in p["founders"])
            if p["github"]:
                founders += "<br>" + a(p["github"], "GitHub")
        links = " &middot; ".join(x for x in (a(r["profile"], "profile"), a(r["website"], "site")) if "<a" in x)
        trs.append(
            f'<tr><td>{"<b>NEW</b>" if r["new"] else ""}</td><td>{r["score"]}</td>'
            f'<td><b>{a(r["profile"] or r["website"], r["name"])}</b><div class="sub">{e(r["one_liner"])}</div></td>'
            f'<td>{e(r["source"])}<div class="sub">{e(str(r["batch"]))}</div></td>'
            f'<td>{e(str(r["location"]) or "-")}</td><td>{e(r["hiring"])}</td><td>{founders}</td><td>{links}</td></tr>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Startup radar {date.today()}</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--sub:#666;--line:#e5e5e5;--link:#0b57d0;--head:#f6f6f6}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--fg:#e8e8e8;--sub:#9a9a9a;--line:#2c2c2c;--link:#8ab4f8;--head:#1e1e1e}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.4 -apple-system,system-ui,sans-serif;margin:16px}}
h1{{font-size:20px;margin:0 0 4px}} .meta{{color:var(--sub);margin-bottom:12px}}
input{{width:100%;max-width:420px;padding:8px;font-size:14px;margin-bottom:12px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%}}
th,td{{text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid var(--line)}}
th{{background:var(--head);position:sticky;top:0}} .sub{{color:var(--sub);font-size:12px;margin-top:2px}}
a{{color:var(--link);text-decoration:none}} a:hover{{text-decoration:underline}}
</style></head><body>
<h1>Startup radar - {date.today()}</h1>
<div class="meta">{len(trs)} companies (domain score &ge; {min_score}, plus anything new). Click a name to open it.</div>
<input id="q" placeholder="Filter: name, keyword, source, location..." autofocus>
<div class="wrap"><table><thead><tr><th></th><th>Score</th><th>Company</th><th>Source</th><th>Location</th><th>Hiring</th><th>Founders</th><th>Links</th></tr></thead>
<tbody id="t">{"".join(trs)}</tbody></table></div>
<script>document.getElementById('q').addEventListener('input',function(){{var q=this.value.toLowerCase();
document.querySelectorAll('#t tr').forEach(function(r){{r.style.display=r.textContent.toLowerCase().indexOf(q)>-1?'':'none'}})}});</script>
</body></html>"""


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

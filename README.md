# job-radar

Find newly funded startups, see who founded them and whether they have public code,
and measure your outreach funnel until it turns into a paid role.

- **Sources:** YC batches (via the community [yc-oss](https://github.com/yc-oss/api) mirror, refreshed daily),
  the latest a16z speedrun cohort, Launch HN and Show HN posts (last 30 days), and new GitHub repos with traction
  (organization-owned only; star-farmed clone clusters are filtered out).
- **Scoring:** keyword weights in `config.json`. Edit them to match your domain.
- **Action cards:** founders (LinkedIn / X / bio) and the company's most active GitHub repos.
- **Jobs:** open roles from Ashby, Greenhouse, Lever and YC job pages for radar companies plus a watch list,
  matched by role type and tagged india / remote-global / other-region / us-only (only the first two shown by default).
- **Pipeline:** a CSV of companies moving through stages, with reply and call rates.

Python 3.9+, standard library only. Action cards need the [GitHub CLI](https://cli.github.com) logged in (`gh auth login`).

## Usage
```bash
python3 -m radar scan                    # fetch, score, write out/REPORT.md and out/companies.csv
python3 -m radar scan --enrich 25        # also write out/ACTION_CARDS.md for the top 25 YC matches
python3 -m radar scan --yc winter-2027   # just one batch
python3 -m radar scan --all              # include non-matching companies in the report
python3 -m radar scan --enrich 25 --open # also open out/radar.html (clickable, searchable) in the browser

python3 -m radar track "Superserve" contacted --channel x --role "support engineer"
python3 -m radar funnel                  # counts per stage, reply rate, call rate
python3 -m radar jobs --open             # support / solutions / FDE / intern roles you can apply to (India or global remote)
python3 -m radar issues --open           # unclaimed issues; skips repos that refuse outside PRs, ranks by newcomer merges
```

Stages: `found, pr_open, pr_merged, contacted, replied, call, trial, offer, rejected, dropped`.

Each `scan` remembers what it has seen (`out/snapshot.json`), so the next run marks new companies as **NEW**.
Run it weekly; most of a batch appears between acceptance and demo day.

## How to use the output
Read [PLAYBOOK.md](PLAYBOOK.md): pick a company, do one verified piece of work for it,
talk to the founder, and ask for paid work.

## Tests
```bash
python3 -m unittest discover -s tests -t .
```

## Notes
- The YC profile and speedrun parsers read data embedded in those pages. If either site changes layout,
  that source logs a warning and is skipped instead of crashing.
- `out/` and `pipeline.csv` are git-ignored because they hold your personal outreach data.

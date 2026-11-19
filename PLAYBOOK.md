# Playbook: from radar to a paid role

The radar finds companies. This file is the routine for turning one of them into a paid role.
Measure everything with `python3 -m radar funnel`; fix the stage where people drop off.

## 1. Pick (10 min per company)
Open `out/ACTION_CARDS.md` and pick companies where at least two are true:
- Raised in the last 6 months (current or last batch).
- Your proof matches what they build (robot data, agent sandboxes, RL environments, inference).
- They are hiring, or the team is 2-5 people (first hires happen soon).
- A founder is reachable (LinkedIn or X listed on the card).

`python3 -m radar track "Company" found`

## 2. Earn the right to talk (one piece of work, max 2-3 days)
**Public repo:** one PR that matters to them.
- Choose a bug a user reported, or a failure in their main use case. Skip typo or doc-only PRs.
- Reproduce it locally first. Paste the real failing output in the PR, then the real passing output after the fix.
  Never file anything you have not run yourself.
- One PR per company before talking. A second PR only comes after the conversation.

**No public repo:** use the product for an hour.
- Write down 3 specific findings (bug with reproduction steps, confusing onboarding step, missing integration).
- That list is your reason to talk.

`python3 -m radar track "Company" pr_open --channel pr`

## 3. Talk to the founder
Rules, not scripts (write the message yourself, in your own words):
- Lead with what you did for *their* product: the PR link or your 3 findings.
- One line of proof that matches them (e.g. 28 merged PRs on a robot-data pipeline, microVM work).
- A concrete, low-risk ask: a short paid trial with a defined deliverable, a contract, a support or
  solutions role, or an internship. Say you are open to non-engineering tech roles too.
- Keep it under 120 words. One follow-up after 5-7 days, then move on.
- Best channels, in order: warm intro from someone they know > reply on your merged PR > X DM > LinkedIn > email.

`python3 -m radar track "Company" contacted --channel x`

## 4. Convert
- Reply -> ask for a 15-minute call. `track ... replied`, then `track ... call`.
- Offer of free work -> counter with a 1-2 week paid trial at a fixed price. Free work stops here.
- Trial -> deliver early, write a short summary of what changed, ask about a monthly contract.

## Roles that count (any tech role)
Engineering (agent infra, ML, inference), technical support engineer, solutions / customer success engineer,
developer relations / community, forward deployed engineer, QA / eval engineer, AI training-data and
RL-environment contracting (Mercor, Turing, micro1, Outlier, Handshake AI).

## Weekly targets
| Activity | Target |
|---|---|
| New companies contacted with real work attached | 10 |
| Job-board applications (any tech role) | 10 |
| Referral asks (alumni, maintainers who merged your PRs) | 10 |
| Free PRs to companies with no hiring signal | 0 |

## Read the funnel every Sunday
- Contacted but no replies -> the message or the proof is the problem; change what you lead with.
- Replies but no calls -> the ask is unclear; make it smaller and paid.
- Calls but no trials/offers -> interview and pricing problem; practise and lower the trial size.

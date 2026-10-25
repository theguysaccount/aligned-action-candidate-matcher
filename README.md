# Who Votes Like Me

**Vote on the bills Congress actually voted on, then see which members voted your way.** A
nonpartisan quiz on real 2025–26 bills, each described by its official Congressional Research
Service summary, matched against every current member's roll-call votes, with every vote sourced.

**Live:** https://theguysaccount.github.io/aligned-action-candidate-matcher/

- **Records, not promises.** Members are matched on what they voted for. The quiz bills are chosen by a fixed, published rule, and no person or model picks the issues.
- **Private by design.** The quiz runs in the browser, and answers live only in the page address after the `#`.
- **Automated.** A GitHub Actions job rereads Voteview, GovInfo and the FEC, tests, rebuilds and publishes. No server, no keys, no cookies.

This repository is the "aligned-action candidate matcher" venture. It reuses the roll-call pipeline of
[Independents Tracker](https://github.com/theguysaccount/independents-win-tracker).

## Pages

| Page | What it answers |
|---|---|
| `/` | The quiz, then your matches by chamber and state, with a share link and a downloadable result card |
| `/bills/<bill>/` | One contested bill: the CRS summary, each chamber's result and party split, every member's vote |
| `/members/<member>/` | One member's vote on every contested bill, and whether they are on the 2026 ballot |
| `/states/<st>/` | A state's delegation on the quiz bills |
| `/issues/<area>/` | Contested votes by CRS policy area |
| `/methodology/`, `/data/`, `/about/` | The rules, CSV and JSON downloads, privacy and corrections |

## Run it locally

Needs Python 3.9 or later and nothing else. Chrome is optional, for the share image.

```bash
python3 -m matcher.refresh            # Voteview roll calls, GovInfo bill records, FEC 2026 candidates
python3 -m matcher.og --site _site    # build into _site/ and render the share card
python3 -m matcher.guard _site        # the checks the deploy runs
python3 -m http.server 8000 --directory _site
```

## Test

```bash
python3 -m unittest discover -s tests -v
```

## Deploy

A push to `main` builds and deploys to GitHub Pages through `.github/workflows/update.yml`, which
also runs every 6 hours. [OPERATIONS.md](OPERATIONS.md) lists each job, how it fails safely, and the keys a
human can turn later.

## Layout

```
matcher/   refresh.py · rollcalls.py (Voteview) · bills.py (GovInfo BILLSTATUS) · fec.py · select.py (quiz rule) · build.py · og.py · guard.py · indexnow.py · selftest.py
static/    quiz.js (the quiz and matching, in the browser) · app.js · style.css
config/    matcher.json (quiz size and caps) · indexnow-key.txt (public by design)
data/      committed snapshots: rollcalls.json, bills.json, candidates2026.json, status.json
```

Code: MIT. Data: public domain (CC0). Please credit Voteview, GovInfo/CRS, the FEC and the
congress-legislators project. Not affiliated with any party, campaign or PAC.

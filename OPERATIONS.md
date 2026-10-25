# OPERATIONS

Everything here runs on GitHub Actions in `theguysaccount/aligned-action-candidate-matcher`, and no
human needs to be involved. The live site is https://theguysaccount.github.io/aligned-action-candidate-matcher/.

## Automated jobs

| Workflow | When | What it does | How it fails safely |
|---|---|---|---|
| `update.yml` | Every 6 hours (04:41, 10:41, 16:41, 22:41 UTC), on every push to `main` (code), and by hand | `matcher.refresh` HEAD-checks the Voteview files and downloads them only when changed. It refetches GovInfo BILLSTATUS records that are new, have a new vote, or are older than 7 days, and refreshes the FEC candidate master when it changes. The job then runs the tests, builds the site and share card, runs `matcher.guard`, deploys to Pages, commits the `data/` snapshot, pings IndexNow (when pages change, and on Mondays), and runs the keep-alive. | Each source is read on its own. A failed source keeps its last good file, and `data/status.json` records the error. A bill whose record fails keeps its previous record, and the run fails over only if more than half fail. A failed test or guard stops before deploy, so the last good site stays live. IndexNow failures are ignored. |
| `selftest.yml` | Mondays 10:53 UTC, and by hand | Runs the tests. `matcher.refresh --check-fresh` fails if Voteview or GovInfo has not been read in 3 days, or the FEC in 4. `matcher.selftest` fetches every sitemap URL plus the quiz data, checks for 200s, checks bill pages carry their roll-call source, and checks the quiz vote strings match the member list. Then the keep-alive. | Read-only against the site. A failure only sends GitHub's failure email to the owner. |
| `test.yml` | Pull requests and pushes to other branches | Tests on Python 3.9 and 3.12, then build and guard | Never deploys |

**Keep-alive.** GitHub pauses scheduled workflows in public repositories after 60 days without
repository activity. Each scheduled run re-enables both workflows through the API. It also pushes an
empty `keep-alive` commit if the last commit is more than 45 days old. Normally the 6-hourly
`status.json` and weekly bill-record commits keep the repository active anyway.

## What to watch

- **Actions → "Update and deploy"**: a red run means the site was not updated that day. The previous site is still live. The failing step says why (Tests, Guard, which lists each problem, or Refresh).
- **`data/status.json`**: per source, `ok`, `last_success`, `error` and `note`.
- **Voteview lag**: votes arrive when Voteview publishes them. The footer and quiz show the date votes run through. If Voteview stops updating for more than a month while Congress is in session, the official Clerk and Senate XML feeds are the fallback to add (see "Keys", 5).
- **The 120th Congress (Jan. 3, 2027)**: set `CONGRESS = 120` in `matcher/rollcalls.py` and the BILLSTATUS congress in `matcher/bills.py`, or keep 119 as an archive. Until then, nothing changes on its own.

## Manual levers (all optional)

- **Run now:** Actions → Update and deploy → Run workflow (tick "force" to re-download everything).
- **Quiz size and caps:** `quiz.items`, `quiz.max_per_policy_area` and `quiz.max_disapprovals` in `config/matcher.json`.
- **Switch a source off:** `sources_enabled` in `config/matcher.json`.

## Keys a human can turn later

None of these is needed for the site to work.

1. **Custom domain.** `whovoteslikeme.com` was unregistered on 2026-10-25 (about $10/yr; buying it needs Jack's OK). `whovoteslikeme.org` is the fallback. Steps:
   1. Register the domain.
   2. DNS at the registrar: four `A` records `@` → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`, and `CNAME www` → `theguysaccount.github.io`.
   3. Repository Settings → Pages → Custom domain → enter it, then "Enforce HTTPS".
   4. Set the repository variable `SITE_URL=https://whovoteslikeme.com`, change `env.SITE_URL` in both workflows to `${{ vars.SITE_URL }}`, and run "Update and deploy".
   5. A root domain also lets crawlers read `robots.txt` and its Sitemap line.
2. **Money slot (upkeep only).** Set the repository variable `SUPPORT_URL` (a GitHub Sponsors or civic-grant page) and optionally `SUPPORT_LABEL`. The footer link appears on the next run. A Sponsors profile needs the account owner. Never link a candidate, party or PAC: that would end the site's neutrality and raise FEC coordination questions.
3. **Analytics (activation metric).** Create a free GoatCounter site and set the repository variable `GOATCOUNTER_URL=https://<code>.goatcounter.com/count`. The events `quiz-start`, `results-view`, `share`, `share-copy`, `card-download` and `source-*` start recording.
4. **Search Console.** Verify the domain with a DNS TXT record and submit `/sitemap.xml`. Bing and Yandex already get every page through IndexNow.
5. **Fresher votes (optional code change).** Add the House Clerk's `https://clerk.house.gov/evs/<year>/roll<NNN>.xml` and the Senate's LIS XML for votes newer than Voteview's latest. Both are keyless. That would close the few-weeks gap.
6. **Recurring written content (optional).** There is no AI key in Actions, and the site needs none. A scheduled Claude routine could open a weekly pull request adding a plain-language "what changed" note under `notes/`, citing roll-call URLs, for each newly added contested vote. Its input would be `data/rollcalls.json` from `main`.

## Costs

$0: public repository, GitHub-hosted runners (about 3–4 minutes a day), GitHub Pages and keyless public data.

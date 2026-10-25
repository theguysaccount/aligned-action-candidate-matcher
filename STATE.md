# STATE: 2026-10-25

**Before this session:** two short Apple Notes (Oct. 2025): "Here's what we predict your actions would be based on your values / Here's the candidate who's been taking the most aligned action" and "WHAT HAVE YOU DONE Not WHAT WILL YOU DO". There was no code and no data.

**Works now:**
- The live quiz: 24 rule-chosen contested bills from the 119th Congress with CRS summaries. Answers are matched to 433 House members and 100 senators, with a state filter and a 2026-ballot filter.
  - Ties are shown as ties.
  - Party averages are shown.
  - Every member can be expanded vote by vote.
  - Results can be shared as a link or a downloaded image.
- 206 bill pages, 555 member pages, 56 state pages and 29 issue pages, plus CSV and JSON downloads, a sitemap, IndexNow and a feed.
- A daily job (refresh, test, build, guard, deploy, commit snapshot), a weekly self-test, keep-alive, and 14 tests.

**Known gaps:**
- Roll calls arrive when Voteview publishes them (latest Sept. 30, 2026).
- No ZIP-to-district lookup; state choice only.
- Challengers without a voting record can't be matched.
- Google can't see the sitemap until there's a custom domain (same as the tracker).

**Worth reusing:** `matcher/bills.py` (keyless CRS summaries and titles from GovInfo BILLSTATUS), `matcher/select.py` (a neutral, rule-based way to pick votes) and `static/quiz.js` (client-side record matching with shareable answers in the URL fragment).

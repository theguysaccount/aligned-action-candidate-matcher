# LAUNCH

**Launch URL (live):** https://theguysaccount.github.io/aligned-action-candidate-matcher/. No DNS
change is needed. The domain steps and exact records are in [OPERATIONS.md](OPERATIONS.md#keys-a-human-can-turn-later).

This venture is machine-driven: nothing is posted as anyone and no outreach is drafted for a human to
send. Distribution runs on channels built into the product.

## Distribution built in

1. **The share loop.** Every result has a link that reopens the same comparison. The person who receives it sees the sharer's matches with a "Start my own quiz" button, and can download a 1200×630 result card for social posts. Native share, X and Bluesky intents are included, and nothing is posted automatically.
2. **Search pages for real queries.** Every result card links into the site's 848 indexable pages, built for these queries:
   - "who voted for <bill>" and "<bill> vote count": 206 bill pages
   - "<member> voting record": 555 member pages
   - "how did <state>'s representatives vote": 56 state pages
   - "<issue> votes in Congress": 29 issue pages
3. **Structured data**: WebApplication on the quiz, Legislation on bills, ProfilePage and Person on members, Dataset on /data, and BreadcrumbList everywhere.
4. **IndexNow** pings on every deploy that changes the page list, and weekly. A sitemap and canonical URLs are on every page.
5. **An Atom feed** of the latest contested votes (`/feed.xml`).
6. **Discoverability on GitHub**: topics, a description, and CC0 data that researchers can cite.

## First 1,000 visitors (no outreach)

- **Election week**: searches for members' voting records and "who votes like me". Every member page offers the quiz.
- **Shared result links and cards** from the people who take the quiz.
- **After the election**: bill pages are durable search answers, and new contested votes add pages automatically.

## Calendar (automatic)

| When | What happens without anyone |
|---|---|
| Every 6 hours (:41 UTC) | Sources rechecked, pages rebuilt and published, snapshot committed |
| When Voteview publishes | New contested votes added, and the quiz reselected by the rule |
| Weekly | Bill records refetched; IndexNow resubmission (Mondays) |
| Mondays | Self-test of every live URL and of the quiz data |
| Jan. 3, 2027 | 120th Congress begins (switch noted in OPERATIONS.md) |

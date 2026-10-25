# PRODUCT

**User.** Voters, especially independents, who distrust campaign promises and want to know which members of Congress actually vote the way they would. With Election Day on Nov. 3, 2026, that means checking their own representative and senators before voting. After the election, it serves anyone looking up "how did my representative vote on X".

**Painful job.** Issue quizzes like ISideWith match voters on stated positions. Voting records are public, but scattered across the House Clerk, the Senate, Congress.gov and Voteview, and nobody turns them into a "do they vote like me" answer.

**Promise.** Vote on real bills described in plain, official, nonpartisan language, and see in about two minutes which members voted your way, with every vote linked to its record.

**Wedge.**
1. The result is shareable: a link that reopens the comparison, and a downloadable image card.
2. Search pages answer "how did <member> vote", "who voted for <bill>" and "<state> delegation votes".
3. The 2026-ballot flag shows which matches voters can actually vote for or against now.

**Why now.** 433 House seats and 35 Senate seats are on the ballot on Nov. 3, and voters are deciding this week. The records are final for most of the 119th Congress.

**Activation metric.** A visitor answers at least 5 bills and opens their results (`results-view`). Supporting events are `quiz-start`, `share`, `share-copy`, `card-download` and `source-*`. They record once a GoatCounter endpoint is set (see OPERATIONS.md).

**First revenue event.** None in v1 (non-commercial on GitHub Pages). A footer slot (`SUPPORT_URL`) takes a GitHub Sponsors page or a civic-grant link, and it is never a donation link for a candidate.

**v1 deliberately won't:**
- Predict a voter's behavior from stated values. Machine-driven mode avoids AI political judgment, so the voter's own votes on real bills are the "actions".
- Rate or endorse anyone.
- Cover state legislatures.
- Look up districts from addresses.
- Store any answers.

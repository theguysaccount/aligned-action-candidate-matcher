# DECISIONS

D1. **The voter's votes are the "actions".** The note's step one ("what we predict your actions would be based on your values") would need someone, or a model, to map values onto bills. That is political judgment, and it would carry bias. Instead the visitor votes yea or nay on the real bills, and the comparison is pure arithmetic on the record. The note's thesis survives intact: "what have you done", not "what will you do".

D2. **Brand: "Who Votes Like Me".** An unrelated business already operates as "Aligned Action" (alignedaction.com), so using that name risked confusion. The repository keeps its required name. whovoteslikeme.com and .org were unregistered on 2026-10-25.

D3. **Votes are chosen by rule.** The quiz takes contested final votes on bills and joint resolutions, where the losing side had at least 10% of the votes cast.
- Bills need a CRS summary.
- Each bill scores 2 if both chambers voted, plus 2 × closeness, plus 1 if voted within 180 days, plus 0.5 if it became law.
- At most 3 bills per policy area and at most 5 Congressional Review Act disapprovals.

The rule is published on /methodology, and the quiz rebuilds itself as new votes arrive.

D4. **Descriptions are CRS text, verbatim.** Names come from official titles, and disapproval resolutions are named after the rule they overturn. The headline is the first sentence of the CRS summary, with the full summary one click away. Tallies appear only after the visitor answers, to avoid anchoring.

D5. **Matching.** Agreement is matched votes divided by votes both cast. A skip or a missed vote counts nowhere. House members are compared on House votes and senators on Senate votes. A national rank needs at least 5 shared votes. Ties are reported as ties, because party-line votes make many members identical.

D6. **Current members only in results.** Former members keep their pages, but are left out of matches.

D7. **Private by design.** Answers live in the URL fragment, which browsers never send to servers. There is no storage and there are no cookies. Analytics, if switched on, are GoatCounter (cookieless).

D8. **Reuse.** `matcher/rollcalls.py` is the tracker's Voteview pipeline (the same files, names and official-record links), extended to keep each member's vote on each kept roll call. The guard, share-card, IndexNow and self-test modules are the tracker's, adapted.

D9. **Keyless sources only.** Voteview, GovInfo BILLSTATUS bulk XML (rather than the Congress.gov API, which needs a key), the FEC candidate master and congress-legislators.

D10. **State, not ZIP.** A ZIP-to-district lookup needs a crosswalk that splits ZIPs across districts. Choosing a state, then reading your own member from the list, is exact and needs no data on the visitor.

## Open questions for Jack (none block v1)
1. Should this stay standalone and neutral, or become a feature of America.co or VoteUS? Standalone is recommended, so it can still be cited as neutral.
2. Register whovoteslikeme.com (~$10/yr)? The steps are in OPERATIONS.md.

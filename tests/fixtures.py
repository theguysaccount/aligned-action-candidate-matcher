"""Small synthetic inputs in the exact formats of the real sources."""
import json

H_MEMBERS = """congress,chamber,icpsr,state_icpsr,district_code,state_abbrev,party_code,occupancy,last_means,bioname,bioguide_id,born,died,nominate_dim1,nominate_dim2,nominate_log_likelihood,nominate_geo_mean_probability,nominate_number_of_votes,nominate_number_of_errors,conditional,nokken_poole_dim1,nokken_poole_dim2
119,President,99912,99,0,USA,200,0,0,"TRUMP, Donald John",,1946.0,,0.403,0.162,,,,,,,
119,House,1,1,1,AA,100,,,"ADAMS, Alice",A000001,1960.0,,-0.4,0,,,,,,,
119,House,2,1,2,AA,100,,,"BAKER, Bob",B000002,1960.0,,-0.3,0,,,,,,,
119,House,3,1,3,AA,200,,,"CRUZ, Carla",C000003,1960.0,,0.4,0,,,,,,,
119,House,4,2,1,BB,200,,,"DIAZ, Dan",D000004,1960.0,,0.5,0,,,,,,,
119,House,5,2,0,DC,100,,,"NORTH, Nell",N000005,1960.0,,-0.5,0,,,,,,,
"""
# 1 HR10 passage (contested 3-1), 2 HRES5 (simple resolution: dropped), 3 HR11 passage unanimous (dropped),
# 4 HR10 concur in Senate amendment (the last final House vote on HR10), 5 SJRES2 passage (contested).
H_ROLLCALLS = """congress,chamber,rollnumber,date,session,clerk_rollnumber,majority_requirement,yea_count,nay_count,nominate_mid_1,nominate_mid_2,nominate_spread_1,nominate_spread_2,nominate_log_likelihood,bill_number,vote_result,vote_desc,vote_question,dtl_desc
119,House,1,2025-02-01,1,10,1/2,3,1,0,0,0,0,0,HR10,Passed,Example Act,On Passage,
119,House,2,2025-02-02,1,11,1/2,2,2,0,0,0,0,0,HRES5,Passed,A rule,On Agreeing to the Resolution,
119,House,3,2025-02-03,1,12,1/2,4,0,0,0,0,0,0,HR11,Passed,A unanimous bill,On Passage,
119,House,4,2025-06-01,1,40,1/2,2,2,0,0,0,0,0,HR10,Passed,Example Act,On Motion to Concur in the Senate Amendment,
119,House,5,2026-03-01,2,7,1/2,2,2,0,0,0,0,0,SJRES2,Passed,Overturn a rule,On Passage,
"""
H_VOTES = """congress,chamber,rollnumber,icpsr,cast_code,prob
119,House,1,1,1,99
119,House,1,2,1,99
119,House,1,3,1,99
119,House,1,4,6,99
119,House,1,5,1,99
119,House,2,1,1,99
119,House,2,2,1,99
119,House,2,3,6,99
119,House,2,4,6,99
119,House,3,1,1,99
119,House,3,2,1,99
119,House,3,3,1,99
119,House,3,4,1,99
119,House,4,1,1,99
119,House,4,2,9,99
119,House,4,3,6,99
119,House,4,4,6,99
119,House,4,5,1,99
119,House,5,1,6,99
119,House,5,2,6,99
119,House,5,3,1,99
119,House,5,4,1,99
"""
S_MEMBERS = """congress,chamber,icpsr,state_icpsr,district_code,state_abbrev,party_code,occupancy,last_means,bioname,bioguide_id,born,died,nominate_dim1,nominate_dim2,nominate_log_likelihood,nominate_geo_mean_probability,nominate_number_of_votes,nominate_number_of_errors,conditional,nokken_poole_dim1,nokken_poole_dim2
119,Senate,11,1,0,AA,100,,,"FOX, Fay",F000011,1950.0,,-0.4,0,,,,,,,
119,Senate,12,1,0,AA,200,,,"GRAY, Gus",G000012,1950.0,,0.4,0,,,,,,,
119,Senate,13,2,0,BB,328,,,"HALE, Hal",H000013,1950.0,,-0.3,0,,,,,,,
"""
S_ROLLCALLS = """congress,chamber,rollnumber,date,session,clerk_rollnumber,majority_requirement,yea_count,nay_count,nominate_mid_1,nominate_mid_2,nominate_spread_1,nominate_spread_2,nominate_log_likelihood,bill_number,vote_result,vote_desc,vote_question,dtl_desc
119,Senate,1,2025-05-01,1,30,1/2,2,1,0,0,0,0,0,HR10,Passed,Example Act,On Passage of the Bill,
119,Senate,2,2025-05-02,1,31,1/2,2,1,0,0,0,0,0,PN9,Confirmed,A nominee,On the Nomination,
119,Senate,3,2026-02-01,2,5,1/2,2,1,0,0,0,0,0,SJRES2,Passed,Overturn a rule,On the Joint Resolution,
"""
S_VOTES = """congress,chamber,rollnumber,icpsr,cast_code,prob
119,Senate,1,11,6,99
119,Senate,1,12,1,99
119,Senate,1,13,1,99
119,Senate,2,11,1,99
119,Senate,2,12,1,99
119,Senate,2,13,6,99
119,Senate,3,11,6,99
119,Senate,3,12,1,99
119,Senate,3,13,1,99
"""
LEGISLATORS = [
    {"id": {"bioguide": "A000001", "fec": ["H6AA00001"]}, "name": {"first": "Alice", "last": "Adams"}, "terms": [{"type": "rep", "party": "Democrat"}]},
    {"id": {"bioguide": "B000002", "fec": []}, "name": {"first": "Robert", "nickname": "Bob", "last": "Baker"}, "terms": [{"type": "rep", "party": "Democrat"}]},
    {"id": {"bioguide": "C000003", "fec": []}, "name": {"first": "Carla", "last": "Cruz"}, "terms": [{"type": "rep", "party": "Republican"}]},
    {"id": {"bioguide": "D000004", "fec": []}, "name": {"first": "Dan", "last": "Diaz"}, "terms": [{"type": "rep", "party": "Republican"}]},
    {"id": {"bioguide": "N000005", "fec": []}, "name": {"first": "Nell", "last": "North"}, "terms": [{"type": "rep", "party": "Democrat"}]},
    {"id": {"bioguide": "F000011", "fec": []}, "name": {"first": "Fay", "last": "Fox"}, "terms": [{"type": "sen", "party": "Democrat"}]},
    {"id": {"bioguide": "G000012", "fec": []}, "name": {"first": "Gus", "last": "Gray"}, "terms": [{"type": "sen", "party": "Republican"}]},
    {"id": {"bioguide": "H000013", "fec": []}, "name": {"first": "Hal", "last": "Hale"}, "terms": [{"type": "sen", "party": "Independent", "caucus": "Democrat"}]},
]


def vote_texts():
    return {"H_members": H_MEMBERS, "H_rollcalls": H_ROLLCALLS, "H_votes": H_VOTES,
            "S_members": S_MEMBERS, "S_rollcalls": S_ROLLCALLS, "S_votes": S_VOTES, "legislators": json.dumps(LEGISLATORS)}


BILLSTATUS_HR10 = b"""<?xml version="1.0" encoding="utf-8"?>
<billStatus><bill><number>10</number><type>HR</type><congress>119</congress>
<introducedDate>2025-01-15</introducedDate>
<policyArea><name>Health</name></policyArea>
<sponsors><item><fullName>Rep. Adams, Alice [D-AA-1]</fullName></item></sponsors>
<summaries>
<summary><actionDesc>Introduced in House</actionDesc><actionDate>2025-01-15</actionDate><updateDate>2025-03-01T00:00:00Z</updateDate><text>&lt;p&gt;Example Act&lt;/p&gt;&lt;p&gt;This bill requires the U.S. Department of Health to publish prices. It also does other things.&lt;/p&gt;</text></summary>
<summary><actionDesc>Passed House</actionDesc><actionDate>2025-02-01</actionDate><updateDate>2025-02-20T00:00:00Z</updateDate><text>&lt;p&gt;Example Act&lt;/p&gt;&lt;p&gt;This bill requires the U.S. Department of Health to publish prices for No. 1 items. Second sentence.&lt;/p&gt;</text></summary>
</summaries>
<title>To require price publication, and for other purposes.</title>
<titles><item><titleType>Display Title</titleType><title>Example Act</title></item><item><titleType>Short Title(s) as Introduced</titleType><title>Example Act</title></item></titles>
<laws><item><type>Public Law</type><number>119-5</number></item></laws>
<latestAction><actionDate>2025-07-01</actionDate><text>Became Public Law No: 119-5.</text></latestAction>
<updateDate>2025-07-02T00:00:00Z</updateDate>
</bill></billStatus>"""

BILLSTATUS_SJRES2 = b"""<?xml version="1.0" encoding="utf-8"?>
<billStatus><bill><number>2</number><type>SJRES</type><congress>119</congress>
<policyArea><name>Energy</name></policyArea>
<summaries><summary><actionDesc>Introduced in Senate</actionDesc><actionDate>2025-01-10</actionDate><updateDate>2025-01-20T00:00:00Z</updateDate><text>&lt;p&gt;This joint resolution nullifies the rule issued by the Department of Energy titled Efficiency Standards for Widgets.&lt;/p&gt;</text></summary></summaries>
<title>Providing for congressional disapproval under chapter 8 of title 5, United States Code, of the rule submitted by the Department of Energy relating to "Energy Conservation Program: Efficiency Standards for Widgets".</title>
<titles><item><titleType>Display Title</titleType><title>Providing for congressional disapproval under chapter 8 of title 5, United States Code, of the rule submitted by the Department of Energy relating to "Energy Conservation Program: Efficiency Standards for Widgets".</title></item></titles>
</bill></billStatus>"""

CN_TEXT = "\n".join([
    "H6AA00001|ADAMS, ALICE|DEM|2026|AA|H|01|I|C|C001|123 PRIVATE ST||TOWN|AA|00000",
    "S8AA00001|FOX, FAY|DEM|2028|AA|S|00|I|C|C002|||||",
])

CFG = {
    "site": {"name": "Who Votes Like Me", "election_date": "2026-11-03", "default_url": "https://example.test/aligned-action-candidate-matcher",
             "repo": "example/aligned-action-candidate-matcher"},
    "quiz": {"items": 24, "max_per_policy_area": 3, "max_disapprovals": 5, "min_answers_for_results": 5, "min_shared_votes_for_rank": 5},
    "fec": {"cycle": 2026},
    "sources_enabled": {"voteview": True, "govinfo": True, "fec": True},
}

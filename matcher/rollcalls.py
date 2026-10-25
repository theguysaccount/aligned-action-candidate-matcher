"""Voteview roll calls -> data/rollcalls.json: every member's vote on each contested final vote on a bill.

Reuses the roll-call pipeline of the Independents Tracker (theguysaccount/independents-win-tracker,
tracker/votes.py): the same Voteview files, the same congress-legislators names, the same links to
the Clerk of the House and Senate records.

Sources (no key):
  Voteview  https://voteview.com/static/data/out/{members,rollcalls,votes}/{H,S}119_*.csv
  congress-legislators (public domain): display names, caucus, FEC ids of current members.

Kept roll calls: final votes on bills and joint resolutions (passage, suspension and passage,
concurring in the other chamber's amendment, conference reports, veto overrides) where the losing
side had at least 10% of the votes cast. Procedural votes, simple resolutions, nominations and
near-unanimous votes are left out: they say little about how a member differs from anyone else.
"""
import csv
import io
import json
import os
import re
from collections import Counter, defaultdict

from .common import DATA, http_get, iso, now_utc, person_name, read_json, slugify, write_json

CONGRESS = 119
VV = "https://voteview.com/static/data/out/{kind}/{ch}{congress}_{kind}.csv"
LEGISLATORS = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
OUT = os.path.join(DATA, "rollcalls.json")

YEA, NAY = {"1", "2", "3"}, {"4", "5", "6"}
PARTY = {"100": "D", "200": "R", "328": "I"}
PARTY_NAME = {"D": "Democrat", "R": "Republican", "I": "Independent"}
BILL_RE = re.compile(r"^(HR|S|HJRES|SJRES)(\d+)$")
FINAL_QUESTIONS = re.compile(
    r"^(On Passage|On Motion to Suspend the Rules and Pass|On Motion to Suspend the Rules and Concur|"
    r"On Agreeing to the Conference Report|On the Conference Report|On Motion to Concur|On Concurring|"
    r"On the Joint Resolution|On Passage of the Bill|On Overriding the Veto|On the Motion \(Motion to Concur|"
    r"On the Motion to Concur)", re.I)
MIN_MINORITY = 0.10


def sources(congress=CONGRESS):
    out = {}
    for ch in "HS":
        for kind in ("members", "rollcalls", "votes"):
            out[f"{ch}_{kind}"] = VV.format(kind=kind, ch=ch, congress=congress)
    out["legislators"] = LEGISLATORS
    return out


def remote_versions(congress=CONGRESS):
    out = {}
    for key, url in sources(congress).items():
        _, h = http_get(url, method="HEAD", timeout=30)
        out[key] = {"url": url, "last_modified": h.get("last-modified", ""), "etag": h.get("etag", "")}
    return out


def download(congress=CONGRESS):
    return {key: http_get(url, timeout=180)[0].decode("utf-8") for key, url in sources(congress).items()}


def _rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def official_url(chamber, date, session, clerk_roll, congress=CONGRESS):
    if not clerk_roll:
        return ""
    if chamber == "House":
        return f"https://clerk.house.gov/Votes/{date[:4]}{int(clerk_roll)}"
    return (f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/"
            f"vote_{congress}_{session}_{int(clerk_roll):05d}.htm")


_BILL_TYPES = [("HCONRES", "house-concurrent-resolution"), ("HJRES", "house-joint-resolution"),
               ("HRES", "house-resolution"), ("HR", "house-bill"),
               ("SCONRES", "senate-concurrent-resolution"), ("SJRES", "senate-joint-resolution"),
               ("SRES", "senate-resolution"), ("S", "senate-bill")]


def bill_url(bill, congress=CONGRESS):
    b = (bill or "").upper().replace(" ", "").replace(".", "")
    for prefix, path in _BILL_TYPES:
        m = re.fullmatch(prefix + r"(\d+)", b)
        if m:
            return f"https://www.congress.gov/bill/{congress}th-congress/{path}/{m.group(1)}"
    return ""


def bill_label(bill):
    b = (bill or "").upper().replace(" ", "")
    for prefix, label in [("HCONRES", "H.Con.Res."), ("HJRES", "H.J.Res."), ("HRES", "H.Res."), ("HR", "H.R."),
                          ("SCONRES", "S.Con.Res."), ("SJRES", "S.J.Res."), ("SRES", "S.Res."), ("S", "S.")]:
        if re.fullmatch(prefix + r"\d+", b):
            return label + " " + b[len(prefix):]
    return bill or ""


def legislator_index(legislators):
    idx = {}
    for x in legislators:
        n = x.get("name", {})
        first = n.get("nickname") or n.get("first", "")
        display = " ".join(p for p in [first, n.get("last", "")] if p)
        if n.get("suffix"):
            display += " " + n["suffix"]
        t = (x.get("terms") or [{}])[-1]
        idx[x["id"]["bioguide"]] = {"name": display, "official": n.get("official_full") or display,
                                    "party": t.get("party", ""), "caucus": t.get("caucus") or "",
                                    "fec": x["id"].get("fec", []), "type": t.get("type", ""),
                                    "url": t.get("url", "")}
    return idx


def is_final_bill_vote(r):
    return bool(BILL_RE.match((r.get("bill_number") or "").upper())) and bool(FINAL_QUESTIONS.match(r.get("vote_question") or ""))


def build(texts, congress=CONGRESS, versions=None):
    legis = legislator_index(json.loads(texts["legislators"])) if texts.get("legislators") else {}
    members, rollcalls, used = {}, {}, set()
    for ch, chamber in (("H", "House"), ("S", "Senate")):
        mrows = [m for m in _rows(texts[f"{ch}_members"]) if m["chamber"] == chamber]
        party_of = {m["icpsr"]: PARTY.get(m["party_code"], "O") for m in mrows}
        bio_of = {m["icpsr"]: (m["bioguide_id"] or f"icpsr{m['icpsr']}") for m in mrows}
        last_date = defaultdict(str)
        votes = defaultdict(dict)
        for v in _rows(texts[f"{ch}_votes"]):
            c = v["cast_code"]
            votes[v["rollnumber"]][v["icpsr"]] = "Y" if c in YEA else "N" if c in NAY else "P" if c in ("7", "8") else "9"
        dates = {}
        for r in _rows(texts[f"{ch}_rollcalls"]):
            rn = r["rollnumber"]
            dates[rn] = r["date"]
            for icpsr in votes.get(rn, {}):
                if r["date"] > last_date[icpsr]:
                    last_date[icpsr] = r["date"]
            if not is_final_bill_vote(r):
                continue
            vs = votes.get(rn, {})
            y = sum(1 for x in vs.values() if x == "Y")
            n = sum(1 for x in vs.values() if x == "N")
            if not y + n or min(y, n) / (y + n) < MIN_MINORITY:
                continue
            tally = Counter((party_of.get(i, "O"), x) for i, x in vs.items() if x in ("Y", "N"))
            key = f"{ch}-{rn}"
            rollcalls[key] = {
                "chamber": chamber, "rollnumber": int(rn), "clerk": r.get("clerk_rollnumber", ""),
                "session": r.get("session", ""), "date": r["date"], "bill": r["bill_number"].upper(),
                "bill_label": bill_label(r["bill_number"]), "question": (r.get("vote_question") or "").strip(),
                "result": (r.get("vote_result") or "").strip(), "desc": (r.get("vote_desc") or r.get("dtl_desc") or "").strip(),
                "yea": y, "nay": n,
                "party": {p: [tally[(p, "Y")], tally[(p, "N")]] for p in ("D", "R", "I") if tally[(p, "Y")] + tally[(p, "N")]},
                "url": official_url(chamber, r["date"], r.get("session", ""), r.get("clerk_rollnumber", ""), congress),
                "vv": f"https://voteview.com/rollcall/R{chamber[0]}{congress}{int(rn):04d}",
                "bill_url": bill_url(r["bill_number"], congress),
                "votes": {bio_of[i]: x for i, x in vs.items() if i in bio_of},
            }
        by_bio = defaultdict(list)
        for m in mrows:
            by_bio[bio_of[m["icpsr"]]].append(m)
        for bio, rows in by_bio.items():
            rows.sort(key=lambda m: last_date[m["icpsr"]])
            m0 = rows[-1]
            L = legis.get(bio, {})
            name = L.get("name") or person_name(m0["bioname"])
            slug = slugify(f"{name} {m0['state_abbrev']}")
            if slug in used:
                slug = slugify(f"{name} {m0['state_abbrev']} {chamber}")
            used.add(slug)
            members[bio] = {
                "bioguide": bio, "slug": slug, "name": name, "official": L.get("official") or person_name(m0["bioname"]),
                "chamber": chamber, "state": m0["state_abbrev"],
                "district": m0["district_code"] if chamber == "House" else "",
                "party": party_of[m0["icpsr"]], "party_now": PARTY_NAME.get(party_of[m0["icpsr"]], "Other"),
                "parties": sorted({party_of[m["icpsr"]] for m in rows}),
                "caucus": L.get("caucus", ""),
                "delegate": chamber == "House" and m0["state_abbrev"] in ("DC", "PR", "GU", "VI", "AS", "MP"),
                "current": bio in legis and L.get("type") == ("rep" if chamber == "House" else "sen"),
                "fec_ids": L.get("fec", []), "last_vote": max(last_date[m["icpsr"]] for m in rows),
                "voteview": f"https://voteview.com/person/{m0['icpsr']}",
                "congress_gov": f"https://www.congress.gov/member/{slugify(name)}/{bio}" if bio[:1].isalpha() and not bio.startswith("icpsr") else "",
            }
    return {"congress": congress, "source": versions or {}, "members": members, "rollcalls": rollcalls}


def refresh(cfg, force=False):
    prev = read_json(OUT, {})
    versions = remote_versions()
    unchanged = prev and all(prev.get("source", {}).get(k, {}).get("last_modified") == v["last_modified"]
                             for k, v in versions.items())
    if unchanged and not force:
        return {"changed": False, "note": "Voteview files unchanged"}
    out = build(download(), versions=versions)
    out["fetched_at"] = iso(now_utc())
    if len(out["members"]) < 400 or len(out["rollcalls"]) < 20:
        raise RuntimeError(f"Voteview parse produced {len(out['members'])} members and {len(out['rollcalls'])} roll calls; keeping the previous data")
    write_json(OUT, out, compact=True)
    return {"changed": True, "note": f"{len(out['members'])} members, {len(out['rollcalls'])} contested final votes on bills"}

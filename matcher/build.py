"""Render the static site from data/ into _site/.

  python3 -m matcher.build [--out _site] [--site-url URL]

The quiz runs in the browser from two prebuilt files (data/quiz.json, data/matrix.json). Every
other page is plain HTML: one per contested bill, per member, per state and per policy area.
Relative links throughout, so the build works on the GitHub Pages project path and on a domain.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from html import escape

from . import select
from .common import DATA, ROOT, STATES, iso, load_config, now_utc, ordinal, parse_iso, read_json, slugify

E = escape
PARTY_WORD = {"D": "Democrat", "R": "Republican", "I": "Independent"}
PARTY_PLURAL = {"D": "Democrats", "R": "Republicans", "I": "Independents"}
LOGO = ('<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="#0e7490"/>'
        '<path d="M8 16.5l5 5 11-11" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')
_AP_MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]


def fmt_date(d):
    if isinstance(d, str):
        if not d:
            return "unknown date"
        d = date.fromisoformat(d[:10])
    return f"{_AP_MONTHS[d.month - 1]} {d.day}, {d.year}"


def http_date_to_iso(s):
    try:
        return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return ""


def a_out(url, text, kind="link"):
    return f'<a href="{E(url)}" rel="noopener" data-out="{E(kind)}">{E(text)}</a>' if url else E(text)


def chip(p, text=None):
    return f'<span class="chip {p if p in ("D", "R", "I") else "plain"}">{E(text or p)}</span>'


def vote_word(v):
    return {"Y": '<span class="yea">Yea</span>', "N": '<span class="nay">Nay</span>', "P": "Present"}.get(v, '<span class="muted">Not voting</span>')


def where(m):
    if m["chamber"] == "Senate":
        return m["state"]
    d = m["district"]
    return f"{m['state']}-{'AL' if d in ('', '0', '00') else str(d).zfill(2)}"


# ---------------------------------------------------------------- model

class Model:
    def __init__(self, cfg, rc, bills, cands, status, now):
        self.cfg, self.rc, self.now = cfg, rc or {}, now
        self.status = status or {}
        self.bills = (bills or {}).get("bills", {})
        self.cands = (cands or {}).get("candidates", {})
        self.members = self.rc.get("members", {})
        self.items = select.items(self.rc, self.bills) if self.rc else {}
        self.quiz = select.choose_quiz(self.items, self.rc, cfg, now.date()) if self.items else []
        self.current = {b: m for b, m in self.members.items() if m.get("current") and not m.get("delegate")}
        dates = [r["date"] for r in self.rc.get("rollcalls", {}).values()]
        self.votes_through = max(dates) if dates else ""

    def on_ballot(self, m):
        """Office this member filed for in 2026, if any (FEC statutory candidate)."""
        for fid in m.get("fec_ids", []):
            c = self.cands.get(fid)
            if c:
                return "U.S. Senate" if c["office"] == "S" else "U.S. House"
        return ""

    def roll(self, key):
        return self.rc["rollcalls"][key]

    def member_votes(self, m):
        """[(item, rollcall key, vote)] for every contested bill vote in the member's chamber."""
        out = []
        for it in self.items.values():
            key = it["votes"].get(m["chamber"])
            if key:
                out.append((it, key, self.roll(key)["votes"].get(m["bioguide"])))
        out.sort(key=lambda x: self.roll(x[1])["date"], reverse=True)
        return out


# ---------------------------------------------------------------- shell

class Site:
    def __init__(self, out, site_url, cfg, model, env):
        self.out, self.url, self.cfg, self.m, self.env = out, site_url.rstrip("/"), cfg, model, env
        self.pages = []
        h = hashlib.sha1()
        for fn in ("style.css", "app.js", "quiz.js"):
            with open(os.path.join(ROOT, "static", fn), "rb") as f:
                h.update(f.read())
        self.ver = h.hexdigest()[:10]

    def abs(self, path):
        return f"{self.url}/{path}"

    def write(self, path, content):
        full = os.path.join(self.out, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)

    def page(self, path, title, desc, body, *, nav="", og="og/home.png", jsonld=None, crumbs=None, priority="0.6",
             index=True, scripts=""):
        depth = path.count("/")
        root = "../" * depth if depth else "./"
        if path == "404.html":
            from urllib.parse import urlparse
            root = urlparse(self.url).path.rstrip("/") + "/"
        canonical = self.abs(path)
        ld = list(jsonld or [])
        crumbs_html = ""
        if crumbs:
            parts = [f'<a href="{root}">Quiz</a>'] + [(f'<a href="{root}{p}">{E(t)}</a>' if p is not None else E(t)) for t, p in crumbs]
            crumbs_html = f'<div class="crumbs">{" › ".join(parts)}</div>'
            items = [{"@type": "ListItem", "position": 1, "name": "Who Votes Like Me", "item": self.abs("")}]
            for i, (t, p) in enumerate(crumbs, 2):
                items.append({"@type": "ListItem", "position": i, "name": t, "item": self.abs(p if p is not None else path)})
            ld.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items})
        ld_html = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)
        gc = self.env.get("GOATCOUNTER_URL", "").strip()
        gc_html = f'<script data-goatcounter="{E(gc)}" async src="https://gc.zgo.at/count.js"></script>' if gc.startswith("https://") else ""
        navs = [("", "Quiz"), ("bills/", "Key votes"), ("members/", "Members"), ("states/", "States"), ("methodology/", "Methodology"), ("about/", "About")]
        current = ' aria-current="page"'
        nav_html = "".join(f'<a href="{root}{p}"{current if nav == p else ""}>{t}</a>' for p, t in navs)
        html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
{'<link rel="canonical" href="' + E(canonical) + '">' if index else '<meta name="robots" content="noindex">'}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Who Votes Like Me">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(canonical)}">
<meta property="og:image" content="{E(self.abs(og))}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0e7490">
<link rel="icon" href="{root}static/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}static/style.css?v={self.ver}">
<link rel="alternate" type="application/atom+xml" title="Who Votes Like Me: new key votes" href="{root}feed.xml">
{ld_html}
{gc_html}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap">
<a class="brand" href="{root}">{LOGO}<span>Who Votes Like Me</span></a>
<nav class="main" aria-label="Main">{nav_html}</nav>
</div></header>
<main id="main"><div class="wrap">
{crumbs_html}
{body}
</div></main>
{self.footer(root)}
<script src="{root}static/app.js?v={self.ver}" defer></script>
{scripts.replace("{root}", root).replace("{ver}", self.ver)}
</body></html>
"""
        self.write(path + ("index.html" if path.endswith("/") or path == "" else ""), html)
        if index:
            self.pages.append((path, iso(self.m.now)[:10], priority))

    def footer(self, root):
        vv = http_date_to_iso(self.m.rc.get("source", {}).get("H_votes", {}).get("last_modified", ""))
        support = self.env.get("SUPPORT_URL", "").strip()
        label = self.env.get("SUPPORT_LABEL", "").strip() or "Support this project"
        support_html = (f'<p><a href="{E(support)}" rel="noopener sponsored">{E(label)}</a>. Upkeep only; not a political contribution and goes to no candidate.</p>'
                        if support.startswith("https://") else "")
        return f"""<footer class="site"><div class="wrap cols">
<div><strong>Who Votes Like Me</strong><p>Match yourself to Congress on what members actually voted for, not what they promise. Nonpartisan and automated: bills and summaries are official records, and every vote links to its roll call. Not affiliated with any party, campaign or PAC.</p>{support_html}</div>
<div><strong>Data</strong><p class="asof">Roll calls (Voteview) through {E(fmt_date(self.m.votes_through)) if self.m.votes_through else 'unknown'}{', files updated ' + E(fmt_date(vv)) if vv else ''}<br>Bill summaries: Congressional Research Service via GovInfo<br>2026 ballot: FEC candidate filings</p></div>
<div><strong>More</strong><p><a href="{root}methodology/">Methodology</a> · <a href="{root}data/">Download the data</a> · <a href="{root}about/">About and corrections</a> · <a href="{root}feed.xml">Feed</a> · <a href="https://github.com/{E(self.cfg['site']['repo'])}" rel="noopener">Source code</a></p>
<p class="tiny">Your quiz answers stay in your browser. Nothing here tells anyone how to vote.</p></div>
</div></footer>"""


# ---------------------------------------------------------------- client data

def quiz_data(site):
    m = site.m
    out = []
    for it in m.quiz:
        votes = {}
        for ch, key in sorted(it["votes"].items()):
            r = m.roll(key)
            votes[ch] = {"date": r["date"], "date_text": fmt_date(r["date"]), "result": r["result"], "yea": r["yea"], "nay": r["nay"],
                         "party": r["party"], "url": r["url"], "question": r["question"]}
        summary = it["summary"]
        if len(summary) > 1600:
            summary = summary[:1597].rsplit(" ", 1)[0] + "…"
        out.append({"id": it["id"], "label": it["label"], "title": it["title"], "headline": it["headline"], "summary": summary,
                    "policy_area": it["policy_area"], "congress_gov": it["congress_gov"], "page": f"bills/{it['slug']}/", "votes": votes})
    return {"generated": iso(m.now), "votes_through": m.votes_through, "items": out}


def matrix_data(site):
    """Per chamber: current members, and for each quiz bill a string with one character per member."""
    m = site.m
    out = {}
    for chamber in ("House", "Senate"):
        mems = sorted((x for x in m.current.values() if x["chamber"] == chamber), key=lambda x: (x["state"], x["name"]))
        rows = [[x["bioguide"], x["name"], x["party"], x["state"], "" if chamber == "Senate" else where(x).split("-")[1],
                 x["slug"], 1 if m.on_ballot(x) else 0] for x in mems]
        votes = {}
        for it in m.quiz:
            key = it["votes"].get(chamber)
            if not key:
                continue
            vs = m.roll(key)["votes"]
            votes[it["id"]] = "".join({"Y": "Y", "N": "N", "P": "P", "9": "-"}.get(vs.get(x["bioguide"]), ".") for x in mems)
        out[chamber] = {"members": rows, "votes": votes}
    return out


# ---------------------------------------------------------------- pages

def home_page(site):
    m, cfg = site.m, site.cfg
    eday = date.fromisoformat(cfg["site"]["election_date"])
    days = (eday - m.now.date()).days
    static_list = "".join(
        f'<li><a href="bills/{it["slug"]}/"><strong>{E(it["label"])}</strong> {E(it["title"])}</a><div class="small muted">{E(it["headline"])}</div></li>'
        for it in m.quiz)
    countdown = (f'<span class="countdown">Election Day, Tuesday, Nov. 3: <span data-countdown="{eday.isoformat()}">{days} days</span></span>'
                 if days >= 0 else "")
    title = "Who Votes Like Me: vote on real bills, see who in Congress voted your way"
    desc = (f"Vote yea or nay on {len(m.quiz)} bills Congress actually voted on, with official summaries, and see which members of the House and Senate "
            "voted the same way. Every vote linked to the roll call. Free, nonpartisan, nothing stored.")
    body = f"""<h1>Who in Congress votes like you?</h1>
<p class="lede">Judge them by what they did, not what they promise. Vote on {len(m.quiz)} bills Congress actually voted on, each described by its official nonpartisan summary, then see which of the {len([x for x in m.current.values() if x['chamber'] == 'House'])} House members and {len([x for x in m.current.values() if x['chamber'] == 'Senate'])} senators voted your way.</p>
{countdown}
<p class="small muted">Your answers stay in your browser; nothing is sent anywhere. Results appear after {cfg['quiz']['min_answers_for_results']} answers. Votes through {E(fmt_date(m.votes_through))}.</p>
<section id="quiz" hidden data-base="./data/" data-min="{cfg['quiz']['min_answers_for_results']}" data-minshared="{cfg['quiz']['min_shared_votes_for_rank']}" data-site="{E(site.abs(''))}">
<div class="q-progress"></div>
<article class="card q-card" aria-live="polite"></article>
<div class="q-nav"></div>
</section>
<section id="quiz-static">
<h2>The {len(m.quiz)} bills in the quiz</h2>
<ol>{static_list}</ol>
<p class="small muted">Turn on JavaScript to take the quiz; each bill page shows how every member voted.</p>
</section>
<section id="results" hidden>
<h2>Your matches</h2>
<p class="small muted">Based on your <span class="res-count">0</span> answers. Agreement counts only bills the member actually voted on.</p>
<div class="tabs" role="tablist"><button class="btn" role="tab" data-chamber="House" aria-selected="true">House</button><button class="btn" role="tab" data-chamber="Senate" aria-selected="false">Senate</button></div>
<div class="filters"><select data-state aria-label="State"><option value="">All states</option></select>
<label class="small"><input type="checkbox" data-ballot> Only members on the 2026 ballot</label></div>
<div class="res-body"></div>
<div class="share res-share"></div>
<div class="share res-fresh"></div>
<p class="small muted">Agreement is a count, not an endorsement: it says only how often a member's recorded votes matched yours on these bills. <a href="methodology/">How matching works</a>.</p>
</section>
<h2>How it works</h2>
<p>The bills are chosen by a fixed rule, not by anyone's opinion: contested final votes from the 119th Congress (2025–26), preferring bills both chambers voted on and close votes, with at most {cfg['quiz']['max_per_policy_area']} bills per policy area. Descriptions are the Congressional Research Service's own summaries. Votes come from <a href="https://voteview.com" rel="noopener">Voteview</a> and link to the Clerk of the House and the Senate. <a href="methodology/">Methodology</a> · <a href="bills/">All {len(m.items)} key votes</a> · <a href="states/">Your state's delegation</a></p>"""
    jsonld = [{"@context": "https://schema.org", "@type": "WebApplication", "name": "Who Votes Like Me", "url": site.abs(""),
               "applicationCategory": "ReferenceApplication", "operatingSystem": "Any", "description": desc,
               "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}]
    site.page("", title, desc, body, nav="", jsonld=jsonld, priority="1.0",
              scripts='<script src="{root}static/quiz.js?v={ver}" defer></script>')


def tally_text(r):
    return ", ".join(f"{PARTY_PLURAL[p]} {y}–{n}" for p, (y, n) in sorted(r["party"].items()))


def bill_page(site, it):
    m = site.m
    path = f"bills/{it['slug']}/"
    sections = []
    for ch in ("House", "Senate"):
        key = it["votes"].get(ch)
        if not key:
            continue
        r = m.roll(key)
        rows = []
        for bio, v in sorted(r["votes"].items(), key=lambda kv: (m.members.get(kv[0], {}).get("state", ""), m.members.get(kv[0], {}).get("name", ""))):
            mm = m.members.get(bio)
            if not mm:
                continue
            rows.append(f'<tr data-party="{mm["party"]}"><td><a href="../../members/{mm["slug"]}/">{E(mm["name"])}</a></td><td>{E(where(mm))}</td>'
                        f'<td>{chip(mm["party"])}</td><td data-v="{v}">{vote_word(v)}</td></tr>')
        tid = f"v-{ch.lower()}"
        sections.append(f"""<h2>{ch} vote</h2>
<div class="card"><p><strong>{E(r['result'])} {r['yea']}–{r['nay']}</strong> on {E(fmt_date(r['date']))} · {E(r['question'])}</p>
<p class="small">{E(tally_text(r))}</p>
<p class="src">Source: {a_out(r['url'], 'Official roll call', 'clerk')} · {a_out(r['vv'], 'Voteview', 'voteview')}</p></div>
<div class="filters"><input type="search" placeholder="Filter by name or state" data-filter="#{tid}" aria-label="Filter {ch} votes">
<select data-filter="#{tid}" data-key="party" aria-label="Party"><option value="">All parties</option><option value="D">Democrats</option><option value="R">Republicans</option><option value="I">Independents</option></select>
<span class="small muted"><span data-count="#{tid}">{len(rows)}</span> shown</span></div>
<div class="table-wrap"><table id="{tid}" data-sort><thead><tr><th><button>Member</button></th><th><button>State</button></th><th><button>Party</button></th><th><button>Vote</button></th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>""")
    in_quiz = any(q["id"] == it["id"] for q in m.quiz)
    summary_html = "".join(f"<p>{E(p)}</p>" for p in it["summary"].split("\n")) if it["summary"] else "<p class='muted'>No CRS summary has been published for this bill yet.</p>"
    first = [m.roll(k) for k in it["votes"].values()]
    title = f"{it['label']} {it['title']}: how every member of Congress voted | Who Votes Like Me"[:160]
    desc = f"{it['headline'] or it['official_title']} " + " ".join(f"{r['chamber']}: {r['result']} {r['yea']}–{r['nay']} ({fmt_date(r['date'])})." for r in first)
    jsonld = [{"@context": "https://schema.org", "@type": "Legislation", "name": it["title"], "legislationIdentifier": it["label"],
               "legislationJurisdiction": "United States", "url": it["congress_gov"], "description": it["headline"],
               "legislationLegalForce": "InForce" if it["law"] else "NotInForce"}]
    body = f"""<h1>{E(it['title'])}</h1>
<p class="lede">{E(it['label'])} · {E(it['policy_area'])}{' · ' + E(it['law']) if it['law'] else ''}</p>
{'<p><a class="btn primary" href="../../">This bill is in the quiz: how would you have voted?</a></p>' if in_quiz else ''}
<h2>What it does</h2>
<div class="card">{summary_html}<p class="src">Summary by the Congressional Research Service ({E(it['summary_version'] or 'latest version')}), via {a_out(it['source'], 'GovInfo BILLSTATUS', 'govinfo')}. {a_out(it['congress_gov'], 'Text, sponsors and history on Congress.gov', 'congress')}.{(' Sponsor: ' + E(it['sponsor']) + '.') if it['sponsor'] else ''}</p></div>
{''.join(sections)}
<p class="small muted"><a href="../">All key votes</a> · <a href="../../issues/{slugify(it['policy_area'])}/">More on {E(it['policy_area'])}</a> · <a href="https://github.com/{E(site.cfg['site']['repo'])}/issues/new?title={E('Correction: ' + it['label'])}" rel="noopener">Report a correction</a></p>"""
    site.page(path, title, desc[:300], body, nav="bills/", jsonld=jsonld, crumbs=[("Key votes", "bills/"), (it["label"], None)],
              priority="0.8" if in_quiz else "0.6")


def bills_index(site):
    m = site.m
    quiz_ids = {q["id"] for q in m.quiz}
    rows = []
    for it in sorted(m.items.values(), key=lambda x: x["last_vote"], reverse=True):
        res = " · ".join(f"{ch} {m.roll(k)['yea']}–{m.roll(k)['nay']}" for ch, k in sorted(it["votes"].items()))
        rows.append(f'<tr data-area="{E(slugify(it["policy_area"]))}"><td data-v="{it["last_vote"]}" class="nowrap">{E(fmt_date(it["last_vote"]))}</td>'
                    f'<td><a href="{it["slug"]}/"><strong>{E(it["label"])}</strong> {E(it["title"])}</a>{" <span class=chip>in quiz</span>" if it["id"] in quiz_ids else ""}</td>'
                    f'<td class="hide-sm">{E(it["policy_area"])}</td><td class="nowrap">{E(res)}</td></tr>')
    areas = sorted({it["policy_area"] for it in m.items.values()})
    opts = "".join(f'<option value="{E(slugify(a))}">{E(a)}</option>' for a in areas)
    body = f"""<h1>Key votes of the 119th Congress</h1>
<p class="lede">All {len(m.items)} bills and joint resolutions that reached a contested final vote in 2025–26, with how every member voted.</p>
<div class="filters"><input type="search" placeholder="Search bills" data-filter="#bills" aria-label="Search bills">
<select data-filter="#bills" data-key="area" aria-label="Policy area"><option value="">All policy areas</option>{opts}</select>
<span class="small muted"><span data-count="#bills">{len(rows)}</span> shown</span></div>
<div class="table-wrap"><table id="bills" data-sort><thead><tr><th><button>Last vote</button></th><th><button>Bill</button></th><th class="hide-sm"><button>Policy area</button></th><th>Result</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="src">Source: Voteview roll calls through {E(fmt_date(m.votes_through))}; titles and policy areas from GovInfo BILLSTATUS. A vote is contested when the losing side had at least 10% of the votes cast.</p>"""
    site.page("bills/", "Key votes in Congress 2025–2026: how every member voted | Who Votes Like Me",
              f"All {len(m.items)} contested final votes on bills in the 119th Congress, with official summaries and every member's vote.",
              body, nav="bills/", crumbs=[("Key votes", None)], priority="0.9")


def member_page(site, mm):
    m = site.m
    path = f"members/{mm['slug']}/"
    rows, same_party, counted = [], 0, 0
    p = mm["party"] if mm["party"] in ("D", "R") else ({"Democrat": "D", "Republican": "R"}.get(mm.get("caucus"), ""))
    for it, key, v in m.member_votes(mm):
        r = m.roll(key)
        pm = ""
        if p and p in r["party"]:
            y, n = r["party"][p]
            pm = "Y" if y > n else "N" if n > y else ""
        if v in ("Y", "N") and pm:
            counted += 1
            same_party += v == pm
        rows.append(f'<tr><td class="nowrap" data-v="{r["date"]}">{E(fmt_date(r["date"]))}</td><td><a href="../../bills/{it["slug"]}/"><strong>{E(it["label"])}</strong> {E(it["title"])}</a></td>'
                    f'<td data-v="{v or ""}">{vote_word(v)}</td><td class="hide-sm">{E(r["result"])} {r["yea"]}–{r["nay"]}</td>'
                    f'<td class="hide-sm">{("with " + PARTY_PLURAL.get(p, "") + " majority" if v == pm else "against " + PARTY_PLURAL.get(p, "") + " majority") if (v in ("Y", "N") and pm) else ""}</td></tr>')
    role = ("U.S. Representative" if mm["chamber"] == "House" else "U.S. Senator") if not mm.get("delegate") else "Delegate"
    ballot = m.on_ballot(mm)
    caucus = f", caucuses with {mm['caucus']}s" if mm["party"] == "I" and mm.get("caucus") else ""
    status = "" if mm.get("current") else " · former member"
    n_votes = sum(1 for _ in rows)
    title = f"{mm['name']} voting record on key bills, 2025–2026 ({mm['party']}-{where(mm)}) | Who Votes Like Me"
    desc = (f"How {mm['name']} ({PARTY_WORD.get(mm['party'], 'Other')}, {where(mm)}) voted on the {n_votes} contested bills of the 119th Congress, "
            f"each with its official summary and roll-call record. Compare with your own votes.")
    jsonld = [{"@context": "https://schema.org", "@type": "ProfilePage", "name": title, "url": site.abs(path),
               "mainEntity": {"@type": "Person", "name": mm["name"], "jobTitle": role,
                              "memberOf": {"@type": "GovernmentOrganization", "name": "United States " + ("House of Representatives" if mm["chamber"] == "House" else "Senate")}}}]
    party_line = (f"Voted with the {PARTY_WORD.get(p, '')} majority on {same_party} of these {counted} votes." if counted else "")
    body = f"""<h1>{E(mm['name'])}</h1>
<p class="lede">{E(role)}, {E(STATES.get(mm['state'], mm['state']))} ({E(where(mm))}) · {E(mm['party_now'])}{E(caucus)}{E(status)}</p>
<p>{'On the 2026 ballot for ' + E(ballot) + ' (FEC filing). ' if ballot else ''}{E(mm['name'])} cast votes on the {n_votes} contested bills below. {E(party_line)}</p>
<p><a class="btn primary" href="../../">Take the quiz: do you vote like {E(mm['name'])}?</a></p>
<div class="table-wrap"><table data-sort><thead><tr><th><button>Date</button></th><th><button>Bill</button></th><th><button>Vote</button></th><th class="hide-sm">Result</th><th class="hide-sm">Party</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="src">Source: Voteview roll calls through {E(fmt_date(m.votes_through))}, each linked from its bill page to the official record. {a_out(mm['voteview'], 'Voteview profile', 'voteview')}{' · ' + a_out(mm['congress_gov'], 'Congress.gov', 'congress') if mm.get('congress_gov') else ''}</p>"""
    site.page(path, title, desc, body, nav="members/", jsonld=jsonld, crumbs=[("Members", "members/"), (mm["name"], None)],
              priority="0.7" if mm.get("current") else "0.4")


def members_index(site):
    m = site.m
    rows = []
    for mm in sorted(m.members.values(), key=lambda x: (x["chamber"], x["state"], x["name"])):
        rows.append(f'<tr data-chamber="{mm["chamber"]}" data-party="{mm["party"]}"><td><a href="{mm["slug"]}/">{E(mm["name"])}</a>{"" if mm.get("current") else " <span class=tiny>(former)</span>"}</td>'
                    f'<td>{E(where(mm))}</td><td>{chip(mm["party"])}</td><td>{E(mm["chamber"])}</td><td class="hide-sm">{"yes" if m.on_ballot(mm) else ""}</td></tr>')
    body = f"""<h1>Members of the 119th Congress</h1>
<p class="lede">Each member's votes on every contested bill of 2025–26.</p>
<div class="filters"><input type="search" placeholder="Find a member or state" data-filter="#members" aria-label="Find a member">
<select data-filter="#members" data-key="chamber" aria-label="Chamber"><option value="">Both chambers</option><option value="House">House</option><option value="Senate">Senate</option></select>
<select data-filter="#members" data-key="party" aria-label="Party"><option value="">All parties</option><option value="D">Democrats</option><option value="R">Republicans</option><option value="I">Independents</option></select>
<span class="small muted"><span data-count="#members">{len(rows)}</span> shown</span></div>
<div class="table-wrap"><table id="members" data-sort><thead><tr><th><button>Member</button></th><th><button>Seat</button></th><th><button>Party</button></th><th><button>Chamber</button></th><th class="hide-sm"><button>2026 ballot</button></th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"""
    site.page("members/", "Voting records of every member of Congress, 2025–2026 | Who Votes Like Me",
              "Find any House member or senator and see how they voted on every contested bill of the 119th Congress.",
              body, nav="members/", crumbs=[("Members", None)], priority="0.8")


def state_page(site, st, mems):
    m = site.m
    path = f"states/{st.lower()}/"
    cols = m.quiz[:12]
    head = "".join(f'<th title="{E(it["title"])}"><a href="../../bills/{it["slug"]}/">{E(it["label"])}</a></th>' for it in cols)
    rows = []
    for mm in sorted(mems, key=lambda x: (x["chamber"] != "Senate", where(x))):
        cells = []
        for it in cols:
            key = it["votes"].get(mm["chamber"])
            v = m.roll(key)["votes"].get(mm["bioguide"]) if key else None
            cells.append(f"<td>{vote_word(v) if key else '<span class=tiny>—</span>'}</td>")
        rows.append(f'<tr><td><a href="../../members/{mm["slug"]}/">{E(mm["name"])}</a> {chip(mm["party"])}</td><td>{E(where(mm))}</td>{"".join(cells)}</tr>')
    name = STATES.get(st, st)
    body = f"""<h1>How {E(name)}'s members of Congress voted</h1>
<p class="lede">{len(mems)} current members from {E(name)}, and their votes on the first {len(cols)} bills of the quiz. A dash means that chamber did not vote on the bill.</p>
<p><a class="btn primary" href="../../">Take the quiz and pick {E(name)} to rank them against your votes</a></p>
<div class="table-wrap"><table class="wide-table"><thead><tr><th>Member</th><th>Seat</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="src">Source: Voteview roll calls through {E(fmt_date(m.votes_through))}. Bill names link to each bill's summary and full roll call.</p>"""
    site.page(path, f"How {name}'s congressional delegation voted on key bills, 2025–2026 | Who Votes Like Me",
              f"Votes of {name}'s {len(mems)} senators and representatives on the most contested bills of the 119th Congress, each linked to the roll call.",
              body, nav="states/", crumbs=[("States", "states/"), (name, None)], priority="0.7")


def states_index(site, by_state):
    links = "".join(f'<li><a href="{st.lower()}/">{E(STATES.get(st, st))}</a> <span class="tiny">({len(v)})</span></li>' for st, v in sorted(by_state.items(), key=lambda kv: STATES.get(kv[0], kv[0])))
    site.page("states/", "Congressional delegations by state: key votes | Who Votes Like Me",
              "Pick a state to see how its senators and representatives voted on the most contested bills of 2025–26.",
              f'<h1>Delegations by state</h1><p class="lede">How each state\'s members of Congress voted on the quiz bills.</p><ul style="columns:3 180px">{links}</ul>',
              nav="states/", crumbs=[("States", None)], priority="0.6")


def issue_pages(site):
    m = site.m
    by_area = defaultdict(list)
    for it in m.items.values():
        by_area[it["policy_area"]].append(it)
    links = []
    for area, its in sorted(by_area.items()):
        slug = slugify(area)
        rows = "".join(
            f'<tr><td class="nowrap">{E(fmt_date(it["last_vote"]))}</td><td><a href="../../bills/{it["slug"]}/"><strong>{E(it["label"])}</strong> {E(it["title"])}</a><div class="small muted">{E(it["headline"])}</div></td>'
            f'<td class="small">{"<br>".join(E(ch + ": " + tally_text(m.roll(k))) for ch, k in sorted(it["votes"].items()))}</td></tr>'
            for it in sorted(its, key=lambda x: x["last_vote"], reverse=True))
        body = f"""<h1>{E(area)}: how Congress voted</h1>
<p class="lede">{len(its)} contested final votes on {E(area.lower())} bills in the 119th Congress, with party breakdowns.</p>
<div class="table-wrap"><table><thead><tr><th>Last vote</th><th>Bill</th><th>By party</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="src">Policy areas are assigned by the Congressional Research Service. Source: GovInfo BILLSTATUS and Voteview.</p>"""
        site.page(f"issues/{slug}/", f"{area} votes in Congress, 2025–2026 | Who Votes Like Me",
                  f"How the House and Senate voted on {len(its)} contested {area.lower()} bills in 2025–26, with official summaries and roll calls.",
                  body, nav="bills/", crumbs=[("Issues", "issues/"), (area, None)], priority="0.6")
        links.append(f'<li><a href="{slug}/">{E(area)}</a> <span class="tiny">({len(its)})</span></li>')
    site.page("issues/", "Votes in Congress by issue | Who Votes Like Me", "Contested votes in the 119th Congress grouped by policy area.",
              f'<h1>Votes by issue</h1><ul style="columns:2 260px">{"".join(links)}</ul>', nav="bills/", crumbs=[("Issues", None)], priority="0.5")


def methodology_page(site):
    q = site.cfg["quiz"]
    body = f"""<h1>Methodology</h1>
<p class="lede">How the bills are chosen, where every fact comes from, and what a match means.</p>
<h2>Which votes count</h2>
<p>From every roll call of the 119th Congress (2025–26) published by <a href="https://voteview.com/data" rel="noopener">Voteview</a>, this site keeps final votes on bills and joint resolutions: passage, suspension and passage, concurring in the other chamber's changes, conference reports and veto overrides. It drops procedural votes, simple resolutions and nominations, and any vote where the losing side had less than 10% of the votes cast. When a bill had several final votes in one chamber, the last one counts.</p>
<h2 id="quiz">How the quiz is chosen</h2>
<p>A fixed rule picks {q['items']} bills, so no person or model decides which issues matter:</p>
<ol><li>Only bills with a Congressional Research Service summary.</li>
<li>Score: 2 points if both chambers voted on it, plus up to 2 points for how close the vote was (a tie scores 2), plus 1 point if the last vote was within 180 days, plus 0.5 if it became law.</li>
<li>Highest score first, with at most {q['max_per_policy_area']} bills per policy area and at most {q.get('max_disapprovals', 5)} Congressional Review Act disapproval resolutions.</li></ol>
<p>The quiz is rebuilt when new votes arrive, so it stays current. Shared result links keep working because each answer is stored with its bill's id.</p>
<h2>What the quiz shows you</h2>
<p>Each bill's name comes from its official title (popular or short title when there is one; for disapproval resolutions, the rule being overturned). The description is the first sentence of the CRS summary, and the full summary is one click away. How Congress voted appears only after you answer, so the tally can't anchor you.</p>
<h2 id="matching">How matching works</h2>
<ul><li>For each current member, agreement = bills where the member's recorded vote equals yours ÷ bills you both voted on. Skipped bills, and votes the member missed, are left out.</li>
<li>House members are compared on the House's votes and senators on the Senate's. Bills that only one chamber voted on compare only that chamber.</li>
<li>National lists rank members with at least {q['min_shared_votes_for_rank']} shared votes. Ties are shown as ties: on party-line votes many members vote identically.</li>
<li>“On the 2026 ballot” means the member's FEC candidate id (from the congress-legislators project) is a statutory 2026 House or Senate candidate in the FEC's candidate master file.</li></ul>
<h2>Limits</h2>
<ul><li>A yea or nay on a final vote compresses a lot: members sometimes vote against bills they support over a single provision, or for bills they dislike as part of a deal.</li>
<li>Only members' recorded votes in this Congress count, so challengers who hold no seat cannot be matched.</li>
<li>Roll calls arrive when Voteview publishes them, usually within a few weeks.</li></ul>
<h2>Sources</h2>
<ul><li>Roll calls: Voteview (Lewis, Poole, Rosenthal, Boche, Rudkin and Sonnet), with links to the Clerk of the House and the Senate.</li>
<li>Titles, policy areas and summaries: GovInfo BILLSTATUS bulk data (Library of Congress and CRS; public domain).</li>
<li>Names, caucus and FEC ids: the public-domain <a href="https://github.com/unitedstates/congress-legislators" rel="noopener">congress-legislators</a> project.</li>
<li>2026 candidates: the FEC candidate master file (cn26), without addresses.</li></ul>"""
    site.page("methodology/", "Methodology: how bills are chosen and matches computed | Who Votes Like Me",
              "How Who Votes Like Me chooses real bills for its quiz by a fixed rule, where the summaries and votes come from, and how agreement with members of Congress is computed.",
              body, nav="methodology/", crumbs=[("Methodology", None)], priority="0.5")


def about_page(site):
    body = f"""<h1>About</h1>
<p class="lede">Who Votes Like Me matches voters to members of Congress on their record, meaning the votes they cast, instead of their promises.</p>
<h2>Nonpartisan by construction</h2>
<ul><li>A fixed, published rule chooses the bills, and the descriptions are the Congressional Research Service's own summaries.</li>
<li>Every vote links to the official roll call.</li>
<li>No endorsements, no ratings, no "correct" answers.</li>
<li>Not affiliated with any party, candidate, campaign or PAC. Nothing here asks anyone to donate or vote a particular way.</li></ul>
<h2>Privacy</h2>
<p>The quiz runs entirely in your browser. Your answers are kept only in the page address after the “#”, which browsers do not send to servers, so they reach no one unless you share the link. There are no cookies and no accounts. If analytics are switched on, they are cookieless (GoatCounter) and count page views and button clicks only.</p>
<h2>Corrections</h2>
<p>Open an issue in the <a href="https://github.com/{E(site.cfg['site']['repo'])}/issues" rel="noopener">repository</a>.</p>
<h2>Licenses</h2>
<p>Code: MIT. Data derived from Voteview, GovInfo, the FEC and congress-legislators: public domain (CC0), with credit requested to the sources.</p>"""
    site.page("about/", "About Who Votes Like Me", "A nonpartisan, automated tool that matches voters to members of Congress on their actual votes.",
              body, nav="about/", crumbs=[("About", None)], priority="0.3")


def data_page(site):
    m = site.m
    full = os.path.join(site.out, "data")
    os.makedirs(full, exist_ok=True)
    keys = sorted({k for it in m.items.values() for k in it["votes"].values()}, key=lambda k: (k[0], int(k.split("-")[1])))
    bill_of = {k: it for it in m.items.values() for k in it["votes"].values()}
    with open(os.path.join(full, "rollcalls-119.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["roll_call", "chamber", "date", "bill", "title", "policy_area", "question", "result", "yea", "nay", "official_record", "bill_page"])
        for k in keys:
            r, it = m.roll(k), bill_of[k]
            w.writerow([k, r["chamber"], r["date"], it["label"], it["title"], it["policy_area"], r["question"], r["result"], r["yea"], r["nay"],
                        r["url"], site.abs(f"bills/{it['slug']}/")])
    with open(os.path.join(full, "votes-matrix-119.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["bioguide", "name", "party", "state", "district", "chamber"] + keys)
        for mm in sorted(m.members.values(), key=lambda x: (x["chamber"], x["state"], x["name"])):
            w.writerow([mm["bioguide"], mm["name"], mm["party"], mm["state"], mm["district"], mm["chamber"]] +
                       [m.roll(k)["votes"].get(mm["bioguide"], "") if m.roll(k)["chamber"] == mm["chamber"] else "" for k in keys])
    body = f"""<h1>Data</h1>
<p class="lede">Everything the site shows, as files. Public domain.</p>
<div class="grid two">
<div class="card"><h3><a href="votes-matrix-119.csv">votes-matrix-119.csv</a></h3><p class="small">One row per member, one column per contested final vote: Y (yea), N (nay), P (present), 9 (not voting), blank (not in that chamber). Columns are the roll-call ids in <a href="rollcalls-119.csv">rollcalls-119.csv</a>, which gives each vote's bill, title, policy area, date, result and official record.</p></div>
<div class="card"><h3><a href="quiz.json">quiz.json</a> and <a href="matrix.json">matrix.json</a></h3><p class="small">The quiz bills with summaries, and each current member's votes on them, exactly as the quiz uses them.</p></div>
</div>
<p>Snapshots are committed to the <a href="https://github.com/{E(site.cfg['site']['repo'])}/tree/main/data" rel="noopener">repository</a> on every change.</p>"""
    jsonld = [{"@context": "https://schema.org", "@type": "Dataset", "name": "Key roll-call votes of the 119th U.S. Congress",
               "description": "Every member's vote on each contested final vote on a bill or joint resolution in the 119th Congress, with CRS policy areas and roll-call links.",
               "url": site.abs("data/"), "license": "https://creativecommons.org/publicdomain/zero/1.0/",
               "creator": {"@type": "Organization", "name": "Who Votes Like Me"},
               "isBasedOn": ["https://voteview.com/data", "https://www.govinfo.gov/bulkdata/BILLSTATUS"],
               "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": site.abs("data/votes-matrix-119.csv")},
                                {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": site.abs("data/rollcalls-119.csv")}]}]
    site.page("data/", "Download: key votes of the 119th Congress | Who Votes Like Me", "CSV and JSON downloads of every member's vote on the contested bills of 2025–26. Public domain.",
              body, nav="", jsonld=jsonld, crumbs=[("Data", None)], priority="0.4")


def not_found(site):
    from urllib.parse import urlparse
    base = urlparse(site.url).path.rstrip("/") + "/"
    site.page("404.html", "Not found | Who Votes Like Me", "Page not found.",
              f'<h1>Page not found</h1><p><a class="btn" href="{E(base)}">Take the quiz</a> <a class="btn" href="{E(base)}bills/">Key votes</a> <a class="btn" href="{E(base)}members/">Members</a></p>',
              index=False)


def feed(site):
    m = site.m
    items = sorted(m.items.values(), key=lambda x: x["last_vote"], reverse=True)[:30]
    entries = "".join(f"""<entry><title>{E(it['label'] + ' ' + it['title'])}</title><id>tag:theguysaccount.github.io,2026:who-votes-like-me:{it['id']}</id>
<updated>{it['last_vote']}T23:59:59Z</updated><link href="{E(site.abs('bills/' + it['slug'] + '/'))}"/>
<content type="text">{E(it['headline'] + ' ' + ' '.join(ch + ': ' + m.roll(k)['result'] + ' ' + str(m.roll(k)['yea']) + '-' + str(m.roll(k)['nay']) + '.' for ch, k in sorted(it['votes'].items())))}</content></entry>""" for it in items)
    site.write("feed.xml", f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Who Votes Like Me: contested votes in Congress</title><id>{E(site.abs(''))}</id>
<link href="{E(site.abs(''))}"/><link rel="self" href="{E(site.abs('feed.xml'))}"/><updated>{iso(m.now)}</updated><author><name>Who Votes Like Me</name></author>
{entries}
</feed>
""")


def seo_files(site, key):
    urls = "".join(f"<url><loc>{E(site.abs(p))}</loc><lastmod>{lm}</lastmod><priority>{pr}</priority></url>\n" for p, lm, pr in site.pages)
    site.write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
    site.write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {site.abs('sitemap.xml')}\n")
    if key:
        site.write(f"{key}.txt", key)
    site.write("urls.txt", "\n".join(site.abs(p) for p, _, _ in site.pages) + "\n")
    site.write(".nojekyll", "")


def build(out=None, site_url=None, env=None, now=None, data_dir=DATA):
    env = dict(os.environ if env is None else env)
    cfg = load_config()
    out = out or os.path.join(ROOT, "_site")
    site_url = site_url or env.get("SITE_URL") or cfg["site"]["default_url"]
    now = now or now_utc()
    model = Model(cfg, read_json(os.path.join(data_dir, "rollcalls.json"), {}), read_json(os.path.join(data_dir, "bills.json"), {}),
                  read_json(os.path.join(data_dir, "candidates2026.json"), {}), read_json(os.path.join(data_dir, "status.json"), {}), now)
    saved = {}
    og_dir = os.path.join(out, "og")
    if os.path.isdir(og_dir):
        for fn in os.listdir(og_dir):
            with open(os.path.join(og_dir, fn), "rb") as f:
                saved[fn] = f.read()
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    shutil.copytree(os.path.join(ROOT, "static"), os.path.join(out, "static"))
    os.makedirs(og_dir, exist_ok=True)
    for fn, blob in saved.items():
        with open(os.path.join(og_dir, fn), "wb") as f:
            f.write(blob)
    if not os.path.exists(os.path.join(og_dir, "home.png")):
        shutil.copy(os.path.join(ROOT, "static", "og-default.png"), os.path.join(og_dir, "home.png"))
    site = Site(out, site_url, cfg, model, env)
    site.write("data/quiz.json", json.dumps(quiz_data(site), ensure_ascii=False, separators=(",", ":")))
    site.write("data/matrix.json", json.dumps(matrix_data(site), ensure_ascii=False, separators=(",", ":")))
    home_page(site)
    bills_index(site)
    for it in model.items.values():
        bill_page(site, it)
    members_index(site)
    for mm in model.members.values():
        member_page(site, mm)
    by_state = defaultdict(list)
    for mm in model.current.values():
        by_state[mm["state"]].append(mm)
    for st, mems in by_state.items():
        state_page(site, st, mems)
    states_index(site, by_state)
    issue_pages(site)
    methodology_page(site)
    about_page(site)
    data_page(site)
    not_found(site)
    feed(site)
    key_path = os.path.join(ROOT, "config", "indexnow-key.txt")
    key = ""
    if os.path.exists(key_path):
        with open(key_path) as f:
            key = f.read().strip()
    seo_files(site, key)
    return site


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--site-url", default=None)
    a = ap.parse_args(argv)
    site = build(out=a.out, site_url=a.site_url)
    print(f"built {len(site.pages)} pages into {site.out}")


if __name__ == "__main__":
    main()

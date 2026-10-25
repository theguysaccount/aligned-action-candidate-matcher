"""GovInfo BILLSTATUS -> data/bills.json: official titles, policy area and the CRS summary of each bill.

  https://www.govinfo.gov/bulkdata/BILLSTATUS/119/{type}/BILLSTATUS-119{type}{number}.xml  (no key)

Summaries are written by the Congressional Research Service, a nonpartisan office; like the titles
they are public domain. Only bills with a contested final vote are fetched (about 200), and each
one is refetched at most once a week, or sooner when a new roll call on it appears.
"""
import html
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import timedelta

from .common import DATA, http_get, iso, now_utc, parse_iso, read_json, write_json

OUT = os.path.join(DATA, "bills.json")
URL = "https://www.govinfo.gov/bulkdata/BILLSTATUS/{congress}/{type}/BILLSTATUS-{congress}{type}{number}.xml"
REFETCH = timedelta(days=7)
TYPE_PATH = {"HR": "house-bill", "S": "senate-bill", "HJRES": "house-joint-resolution", "SJRES": "senate-joint-resolution"}


def split_bill(bill):
    m = re.match(r"^(HR|S|HJRES|SJRES)(\d+)$", bill)
    return (m.group(1), m.group(2)) if m else (None, None)


def strip_html(s):
    s = re.sub(r"<\s*(br|/p|/li)\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in s.split("\n")]
    return "\n".join(x for x in lines if x)


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    b = root.find("bill")
    if b is None:
        raise ValueError("no <bill> element")
    titles = {}
    for t in b.findall("titles/item"):
        titles.setdefault(t.findtext("titleType") or "", t.findtext("title") or "")
    popular = next((v for k, v in titles.items() if k.startswith("Popular Title")), "")
    short = next((v for k, v in titles.items() if k.startswith("Short Title") and "portions" not in k), "")
    summaries = b.findall("summaries/summary")
    latest = summaries[-1] if summaries else None  # listed in legislative order; the last is the most advanced text
    summary = strip_html(latest.findtext("text")) if latest is not None else ""
    law = b.find("laws/item")
    return {
        "title": (b.findtext("title") or "").strip(),
        "popular_title": popular.strip(), "short_title": short.strip(),
        "policy_area": (b.findtext("policyArea/name") or "").strip(),
        "subjects": [x.findtext("name") for x in b.findall("subjects/legislativeSubjects/item")][:12],
        "summary": summary,
        "summary_version": (latest.findtext("actionDesc") or "") if latest is not None else "",
        "summary_date": (latest.findtext("actionDate") or "") if latest is not None else "",
        "introduced": b.findtext("introducedDate") or "",
        "sponsor": " ".join(x for x in [b.findtext("sponsors/item/fullName") or ""] if x),
        "latest_action": (b.findtext("latestAction/text") or "").strip(),
        "latest_action_date": b.findtext("latestAction/actionDate") or "",
        "law": f"Public Law {law.findtext('number')}" if law is not None and law.findtext("number") else "",
        "update_date": b.findtext("updateDate") or "",
    }


def display_title(b, bill_label):
    """The name people know: popular title, then short title, then the official title."""
    t = b.get("popular_title") or b.get("short_title") or b.get("title") or bill_label
    return t[:-1] if t.endswith(".") else t


def refresh(cfg, rollcalls, congress=119, force=False, now=None, pause=0.25):
    now = now or now_utc()
    prev = read_json(OUT, {}) or {}
    bills = dict(prev.get("bills", {}))
    wanted = {}
    for r in rollcalls.get("rollcalls", {}).values():
        wanted[r["bill"]] = max(wanted.get(r["bill"], ""), r["date"])
    fetched = failed = 0
    for bill, last_vote in sorted(wanted.items()):
        old = bills.get(bill)
        t = parse_iso(old.get("fetched_at")) if old else None
        stale = force or not old or t is None or now - t > REFETCH or last_vote > (old.get("fetched_for_vote") or "")
        if not stale:
            continue
        typ, num = split_bill(bill)
        if not typ:
            continue
        try:
            body, _ = http_get(URL.format(congress=congress, type=typ.lower(), number=num), timeout=90)
            rec = parse(body)
            rec.update(fetched_at=iso(now), fetched_for_vote=last_vote,
                       source=URL.format(congress=congress, type=typ.lower(), number=num),
                       congress_gov=f"https://www.congress.gov/bill/{congress}th-congress/{TYPE_PATH[typ]}/{num}")
            bills[bill] = rec
            fetched += 1
        except Exception as e:  # keep the previous record for this bill, if any
            failed += 1
            print(f"bills: {bill}: {e}")
        time.sleep(pause)
    if wanted and failed > max(10, len(wanted) // 2):
        raise RuntimeError(f"{failed} of {len(wanted)} bill records failed; keeping the previous data")
    out = {"congress": congress, "fetched_at": iso(now) if fetched else prev.get("fetched_at", iso(now)),
           "bills": {k: v for k, v in bills.items() if k in wanted}}
    write_json(OUT, out, compact=True)
    return {"changed": fetched > 0, "note": f"{fetched} bill records fetched, {failed} failed, {len(out['bills'])} kept"}

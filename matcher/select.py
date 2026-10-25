"""Turn roll calls and bill records into vote items, and choose the quiz.

An item is one bill with its final contested vote in each chamber that voted on it. The quiz is a
fixed, rule-based selection, so no person or model decides which issues "matter":
  1. only bills with a CRS summary;
  2. score = 2 if both chambers voted + 2 x closeness of the vote (1 = tied) + 1 if the last vote
     was within 180 days + 0.5 if the bill became law;
  3. highest score first, at most N bills per policy area and at most M Congressional Review Act
     disapproval resolutions, until the quiz has its size.
"""
import re
from datetime import date

from .bills import display_title
from .common import slugify

_DISAPPROVAL = re.compile(r"^(Providing (for )?congressional disapproval|A joint resolution (providing for congressional )?disapprov|"
                          r"Disapproving the action of the District of Columbia)", re.I)
_RULE = re.compile(r'rule submitted by (?:the )?(?P<agency>.+?) relat(?:ing|ed) to (?:"(?P<quoted>[^"]+)"|(?P<rule>.+?))\.?$', re.I)
_ABBREV = {"u.s", "d.c", "no", "sec", "mr", "ms", "mrs", "dr", "inc", "co", "st", "e.g", "i.e", "vs", "etc", "jr", "sr", "u.s.c", "pub", "l", "h.r", "s", "res", "con", "j"}


def is_disapproval(title):
    return bool(_DISAPPROVAL.match(title or ""))


def short_name(b, label):
    """A readable name: popular or short title; for Congressional Review Act resolutions, the rule."""
    if b.get("popular_title") or b.get("short_title"):
        return display_title(b, label)
    t = (b.get("title") or "").strip()
    m = _RULE.search(t)
    if is_disapproval(t) and m:
        rule = (m.group("quoted") or m.group("rule") or "").strip().rstrip(".")
        if len(rule) > 90:
            rule = rule[:87].rsplit(" ", 1)[0] + "…"
        return f"Overturn the {m.group('agency').strip()} rule “{rule}”"
    if t.startswith("Disapproving the action of the District of Columbia Council"):
        act = t.split(" in approving the ", 1)[1].strip().rstrip(".") if " in approving the " in t else ""
        return "Overturn the D.C. Council's " + act if act else "Overturn a D.C. Council act"
    t = t.rstrip(".")
    return t if len(t) <= 110 else t[:107].rsplit(" ", 1)[0] + "…"


def headline(summary, name=""):
    """The CRS summary's first sentence (skipping a first line that only repeats the bill's name)."""
    lines = [x.strip() for x in (summary or "").split("\n") if x.strip()]
    while lines and (not re.search(r"[.!?]$", lines[0]) or lines[0].lower().rstrip(".") == name.lower()) and len(lines) > 1 \
            and not lines[0].lower().startswith("this "):
        lines.pop(0)
    text = " ".join(lines)
    first = text
    for m in re.finditer(r"[.!?](?=\s+[A-Z(\"“]|$)", text):
        word = text[:m.start()].rsplit(" ", 1)[-1].lower().strip("(")
        if word in _ABBREV or re.fullmatch(r"(?:[a-z]\.)*[a-z]", word):
            continue  # "U.S." or "No." is not the end of a sentence
        first = text[:m.end()]
        break
    return first if len(first) <= 400 else first[:397].rsplit(" ", 1)[0] + "…"


def items(rc, bills):
    """bill id -> item, using the last final vote in each chamber."""
    by_bill = {}
    for key, r in sorted(rc.get("rollcalls", {}).items(), key=lambda kv: (kv[1]["date"], kv[1]["rollnumber"])):
        by_bill.setdefault(r["bill"], {})[r["chamber"]] = key
    out = {}
    used = set()
    for bill, chambers in by_bill.items():
        b = bills.get(bill, {})
        first = rc["rollcalls"][next(iter(chambers.values()))]
        label = first["bill_label"]
        title = short_name(b, label) if b else (first["desc"] or label)
        slug = slugify(f"{label} {title}")
        if len(slug) > 70:
            slug = slug[:70].rsplit("-", 1)[0]
        if slug in used:
            slug = slugify(label)
        used.add(slug)
        last = max(rc["rollcalls"][k]["date"] for k in chambers.values())
        out[bill] = {"id": bill.lower(), "bill": bill, "label": label, "title": title, "slug": slug,
                     "official_title": b.get("title", ""), "summary": b.get("summary", ""),
                     "headline": headline(b.get("summary", ""), title), "disapproval": is_disapproval(b.get("title", "")),
                     "summary_version": b.get("summary_version", ""), "policy_area": b.get("policy_area", "") or "Other",
                     "sponsor": b.get("sponsor", ""), "law": b.get("law", ""), "latest_action": b.get("latest_action", ""),
                     "congress_gov": b.get("congress_gov") or first["bill_url"], "source": b.get("source", ""),
                     "votes": dict(chambers), "last_vote": last}
    return out


def closeness(r):
    total = r["yea"] + r["nay"]
    return 1 - abs(r["yea"] - r["nay"]) / total if total else 0


def score(item, rc, today):
    rolls = [rc["rollcalls"][k] for k in item["votes"].values()]
    s = 2.0 if len(rolls) == 2 else 0.0
    s += 2.0 * sum(closeness(r) for r in rolls) / len(rolls)
    if (today - date.fromisoformat(item["last_vote"])).days <= 180:
        s += 1.0
    if item["law"]:
        s += 0.5
    return round(s, 4)


def choose_quiz(all_items, rc, cfg, today):
    """Highest score first (ties: latest vote first), capped per policy area and for disapproval resolutions."""
    size = cfg["quiz"]["items"]
    cap = cfg["quiz"]["max_per_policy_area"]
    cap_cra = cfg["quiz"].get("max_disapprovals", 5)
    pool = [it for it in all_items.values() if it["summary"]]
    pool.sort(key=lambda it: it["last_vote"], reverse=True)
    pool.sort(key=lambda it: score(it, rc, today), reverse=True)  # stable: equal scores stay newest first
    chosen, per_area, cra = [], {}, 0
    for it in pool:
        if per_area.get(it["policy_area"], 0) >= cap or (it["disapproval"] and cra >= cap_cra):
            continue
        chosen.append(it)
        per_area[it["policy_area"]] = per_area.get(it["policy_area"], 0) + 1
        cra += it["disapproval"]
        if len(chosen) >= size:
            break
    return chosen

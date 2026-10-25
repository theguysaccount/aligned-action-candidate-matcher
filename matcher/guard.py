"""Check a built site before it is published. Exit 1 (and publish nothing) if anything is off.

  python3 -m matcher.guard [_site]

Same checks as the Independents Tracker's guard: key pages exist, enough bill and member pages,
every bill page links its official roll call and summary source, every internal link resolves,
the quiz data parses and covers both chambers, and no advocacy language appears in our own text.
"""
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .common import ROOT

MIN_BILLS = 50
MIN_MEMBERS = 400
MIN_QUIZ = 10
BANNED = [r"\bvote for\b", r"\bdonate (?:to|now)\b", r"\bcontribute to\b", r"\bendors(?:e|es|ed|ing|ement)\b", r"\bchip in\b"]
ALLOWED = [r"no endorsements?", r"not an endorsement"]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.text, self._skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        for k in ("href", "src"):
            if a.get(k):
                self.links.append(a[k])

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def visible_text(html):
    p = Page()
    p.feed(html)
    return " ".join(p.text), p.links


def check(site_dir):
    errors = []
    for f in ["index.html", "bills/index.html", "members/index.html", "states/index.html", "issues/index.html", "methodology/index.html",
              "about/index.html", "data/index.html", "404.html", "sitemap.xml", "robots.txt", "feed.xml", "static/quiz.js",
              "static/style.css", "data/quiz.json", "data/matrix.json", "data/votes-matrix-119.csv", "og/home.png"]:
        if not os.path.exists(os.path.join(site_dir, f)):
            errors.append(f"missing {f}")
    def subdirs(d):
        p = os.path.join(site_dir, d)
        return [x for x in os.listdir(p) if os.path.isdir(os.path.join(p, x))] if os.path.isdir(p) else []
    bills, members = subdirs("bills"), subdirs("members")
    if len(bills) < MIN_BILLS:
        errors.append(f"only {len(bills)} bill pages (expected {MIN_BILLS}+)")
    if len(members) < MIN_MEMBERS:
        errors.append(f"only {len(members)} member pages (expected {MIN_MEMBERS}+)")
    try:
        quiz = json.loads(_read(os.path.join(site_dir, "data", "quiz.json")))
        matrix = json.loads(_read(os.path.join(site_dir, "data", "matrix.json")))
        if len(quiz["items"]) < MIN_QUIZ:
            errors.append(f"quiz has {len(quiz['items'])} bills (expected {MIN_QUIZ}+)")
        for it in quiz["items"]:
            if not it.get("headline") or not it.get("votes"):
                errors.append(f"quiz bill {it.get('id')} lacks a summary or a vote")
            for ch in it.get("votes", {}):
                s = matrix[ch]["votes"].get(it["id"], "")
                if len(s) != len(matrix[ch]["members"]):
                    errors.append(f"matrix {ch} {it['id']}: {len(s)} votes for {len(matrix[ch]['members'])} members")
        for ch in ("House", "Senate"):
            if len(matrix[ch]["members"]) < (400 if ch == "House" else 95):
                errors.append(f"matrix {ch} has {len(matrix[ch]['members'])} members")
    except Exception as e:
        errors.append(f"quiz data unreadable: {e}")
    sitemap = _read(os.path.join(site_dir, "sitemap.xml")) if os.path.exists(os.path.join(site_dir, "sitemap.xml")) else ""
    for d in bills:
        html = _read(os.path.join(site_dir, "bills", d, "index.html"))
        if "Official roll call" not in html or "Congressional Research Service" not in html:
            errors.append(f"bills/{d}: missing roll-call or summary source")
        if f"/bills/{d}/" not in sitemap:
            errors.append(f"bills/{d}: not in sitemap")
    banned = [re.compile(b, re.I) for b in BANNED]
    allowed = [re.compile(a, re.I) for a in ALLOWED]
    for dirpath, _, files in os.walk(site_dir):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, site_dir)
            text, links = visible_text(_read(path))
            # Bill titles and summaries are quoted from the official record; scan only our own pages' text.
            if not rel.startswith(("bills/", "members/", "states/", "issues/")) and rel != "index.html":
                for a in allowed:
                    text = a.sub(" ", text)
                for b in banned:
                    m = b.search(text)
                    if m:
                        errors.append(f"{rel}: advocacy phrase {m.group(0)!r}")
            if rel == "404.html":
                continue
            base = "file:///" + rel.replace(os.sep, "/")
            for link in links:
                u = urlparse(link)
                if u.scheme or link.startswith(("#", "mailto:", "data:", "//")):
                    continue
                target = urlparse(urljoin(base, u.path)).path.lstrip("/")
                full = os.path.join(site_dir, target)
                if target.endswith("/") or os.path.isdir(full):
                    full = os.path.join(full, "index.html")
                if not os.path.exists(full):
                    errors.append(f"{rel}: broken link {link}")
    return errors, {"bills": len(bills), "members": len(members)}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    site_dir = argv[0] if argv else os.path.join(ROOT, "_site")
    errors, counts = check(site_dir)
    for e in errors[:50]:
        print("GUARD", e)
    print(f"guard: {counts['bills']} bill pages, {counts['members']} member pages, {len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

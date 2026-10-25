"""Weekly self-test of the live site. Exit 1 if anything a visitor would notice is broken.

  python3 -m matcher.selftest --site-url https://theguysaccount.github.io/aligned-action-candidate-matcher

Fetches every URL in the live sitemap plus the quiz data, checks each answers 200, the quiz data
parses and matches the member list, and bill pages carry their sources.
"""
import argparse
import concurrent.futures
import json
import os
import re
import sys

from .common import ROOT, http_get, load_config


def fetch(url):
    try:
        body, _ = http_get(url, timeout=30, retries=2)
        return 200, body
    except Exception as e:
        return getattr(e, "code", 0), b""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-url", default=load_config()["site"]["default_url"])
    a = ap.parse_args(argv)
    base = a.site_url.rstrip("/")
    problems = []
    code, sm = fetch(base + "/sitemap.xml")
    urls = re.findall(r"<loc>([^<]+)</loc>", sm.decode("utf-8", "replace")) if code == 200 else []
    if len(urls) < 600:
        problems.append(f"sitemap lists {len(urls)} URLs (expected 600+), status {code}")
    with open(os.path.join(ROOT, "config", "indexnow-key.txt")) as f:
        key = f.read().strip()
    extra = [base + "/data/quiz.json", base + "/data/matrix.json", base + "/static/quiz.js", base + "/og/home.png",
             base + "/robots.txt", base + "/feed.xml", base + "/data/votes-matrix-119.csv", f"{base}/{key}.txt"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = dict(ex.map(lambda u: (u, fetch(u)), urls + extra))
    for u, (c, body) in results.items():
        if c != 200:
            problems.append(f"{u} answered {c}")
        elif "/bills/" in u and u.rstrip("/").count("/") > base.count("/") + 1 and b"Official roll call" not in body:
            problems.append(f"{u} lacks its roll-call source")
    try:
        quiz = json.loads(results[base + "/data/quiz.json"][1])
        matrix = json.loads(results[base + "/data/matrix.json"][1])
        for it in quiz["items"]:
            for ch in it["votes"]:
                if len(matrix[ch]["votes"].get(it["id"], "")) != len(matrix[ch]["members"]):
                    problems.append(f"quiz bill {it['id']}: {ch} vote string does not match the member list")
    except Exception as e:
        problems.append(f"quiz data unreadable on the live site: {e}")
    for p in problems[:40]:
        print("FAIL", p)
    print(f"selftest: {len(urls)} sitemap URLs and {len(extra)} assets checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

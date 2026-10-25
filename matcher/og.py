"""Open Graph share cards (1200x630 PNG) rendered with headless Chrome.

  python3 -m matcher.og [--site _site]   # build the site, then render the cards
  python3 -m matcher.og --default        # re-render static/og-default.png

Same approach as the Independents Tracker: Chrome on GitHub's runners, the macOS app locally, and a
copy of the committed default card when Chrome is missing, so no page points at a missing image.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from html import escape as E

from .common import ROOT

CHROMES = [os.environ.get("CHROME", ""), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
DEFAULT = os.path.join(ROOT, "static", "og-default.png")
CSS = """
*{box-sizing:border-box}html,body{margin:0;width:1200px;height:630px;overflow:hidden}
body{background:#0b1f26;color:#fff;font-family:"Inter","Segoe UI","Helvetica Neue",Arial,"DejaVu Sans",sans-serif;padding:56px 64px;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:14px;font-size:26px;font-weight:700;color:#8fe0ee}
.top i{display:inline-block;width:40px;height:40px;border-radius:9px;background:#0e7490}
h1{font-size:66px;line-height:1.05;letter-spacing:-1.5px;margin:34px 0 14px}
.sub{font-size:29px;color:#b9d4da;line-height:1.35}
.row{display:flex;gap:22px;margin-top:auto}
.box{flex:1;background:#12303a;border-radius:18px;padding:20px 24px;font-size:24px;color:#d7eef2}
.box b{display:block;font-size:44px;color:#fff;margin-bottom:4px}
"""


def find_chrome():
    for c in CHROMES:
        if c and (os.path.exists(c) or shutil.which(c)):
            return shutil.which(c) or c
    return None


def render(chrome, html, out_png):
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "card.html")
        with open(src, "w", encoding="utf-8") as f:
            f.write(f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html}</body></html>")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--mute-audio",
                        "--force-device-scale-factor=1", "--window-size=1200,630", f"--user-data-dir={os.path.join(d, 'profile')}",
                        f"--screenshot={out_png}", "file://" + src], check=True, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.exists(out_png) and os.path.getsize(out_png) > 1000


def card_home(n_bills, n_house, n_senate):
    return f"""<div class="top"><i></i>Who Votes Like Me</div>
<h1>Who in Congress votes like you?</h1>
<div class="sub">Vote yea or nay on {n_bills} real bills, described by their official summaries. See which members voted your way, every vote sourced.</div>
<div class="row"><div class="box"><b>{n_bills}</b>real bills</div><div class="box"><b>{n_house}</b>House members</div><div class="box"><b>{n_senate}</b>senators</div></div>"""


def run(site_dir, model):
    og = os.path.join(site_dir, "og")
    os.makedirs(og, exist_ok=True)
    n_h = sum(1 for x in model.current.values() if x["chamber"] == "House")
    n_s = sum(1 for x in model.current.values() if x["chamber"] == "Senate")
    jobs = [("home.png", card_home(len(model.quiz), n_h, n_s))]
    chrome = find_chrome()
    made = 0
    for name, html in jobs:
        out = os.path.join(og, name)
        ok = False
        if chrome:
            try:
                ok = render(chrome, html, out)
            except Exception as e:
                print(f"og: {name} failed: {e}", file=sys.stderr)
        if not ok:
            shutil.copy(DEFAULT, out)
        made += ok
    print(f"og: rendered {made} of {len(jobs)} cards" + ("" if chrome else " (no Chrome: copied the default card)"))
    return made


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=os.path.join(ROOT, "_site"))
    ap.add_argument("--default", action="store_true")
    a = ap.parse_args(argv)
    if a.default:
        chrome = find_chrome()
        if not chrome:
            sys.exit("Chrome not found")
        render(chrome, card_home(24, 435, 100), DEFAULT)
        print("wrote", DEFAULT)
        return
    from .build import build
    site = build(out=a.site)
    run(a.site, site.m)


if __name__ == "__main__":
    main()

"""Refresh every source that changed, each one on its own.

  python3 -m matcher.refresh                # what the daily job runs
  python3 -m matcher.refresh --force        # re-download everything
  python3 -m matcher.refresh --check-fresh  # exit 1 if a source has not been read successfully in time

A source that fails keeps its last good data file; data/status.json records the error and the time
of the last success, and every page prints the date its votes run through.
"""
import argparse
import sys
import traceback
from datetime import timedelta

from . import bills, fec, rollcalls
from .common import DATA, iso, load_config, now_utc, parse_iso, read_json, write_json

STATUS = DATA + "/status.json"
MAX_AGE = {"rollcalls": timedelta(days=3), "bills": timedelta(days=3), "fec": timedelta(days=4)}


def run(force=False, now=None):
    now = now or now_utc()
    cfg = load_config()
    status = read_json(STATUS, {}) or {}
    enabled = cfg.get("sources_enabled", {})

    def record(name, fn):
        st = status.get(name, {})
        st["checked_at"] = iso(now)
        try:
            res = fn()
            st.update(ok=True, last_success=iso(now), note=res.get("note", ""), error="")
            if res.get("changed"):
                st["last_changed"] = iso(now)
        except Exception as e:
            st.update(ok=False, error=f"{type(e).__name__}: {e}"[:500])
            traceback.print_exc()
        status[name] = st
        print(f"{name}: {'ok' if st.get('ok') else 'FAILED'} {st.get('note') if st.get('ok') else st.get('error')}")

    if enabled.get("voteview", True):
        record("rollcalls", lambda: rollcalls.refresh(cfg, force=force))
    rc = read_json(rollcalls.OUT, {})
    if enabled.get("govinfo", True) and rc:
        record("bills", lambda: bills.refresh(cfg, rc, force=force, now=now))
    if enabled.get("fec", True):
        record("fec", lambda: fec.refresh(cfg, force=force))
    write_json(STATUS, status)
    return status


def check_fresh(now=None):
    now = now or now_utc()
    status = read_json(STATUS, {}) or {}
    bad = []
    for name, age in MAX_AGE.items():
        last = parse_iso(status.get(name, {}).get("last_success"))
        if last is None or now - last > age:
            bad.append(f"{name}: last successful read {status.get(name, {}).get('last_success', 'never')}; "
                       f"last error: {status.get(name, {}).get('error', '')}")
    for b in bad:
        print("STALE", b)
    return not bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check-fresh", action="store_true")
    a = ap.parse_args(argv)
    if a.check_fresh:
        return 0 if check_fresh() else 1
    run(force=a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())

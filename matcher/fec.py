"""FEC candidate master (cn26.zip, no key) -> data/candidates2026.json: which sitting members are on
the 2026 ballot for federal office, matched through the FEC ids in congress-legislators.

Only the candidate id, office, state, district, party code and status are kept; the file's mailing
addresses are never read into the output.
"""
import io
import os
import zipfile

from .common import DATA, http_get, iso, now_utc, read_json, write_json

URL = "https://www.fec.gov/files/bulk-downloads/{cycle}/cn{yy}.zip"
OUT = os.path.join(DATA, "candidates2026.json")
CN = ["cand_id", "cand_name", "party", "election_yr", "state", "office", "district", "ici", "status", "pcc"]


def build(cn_text, cycle):
    out = {}
    for line in cn_text.splitlines():
        f = line.split("|")
        if len(f) < 10:
            continue
        r = dict(zip(CN, f[:10]))
        if r["election_yr"] == str(cycle) and r["status"] == "C" and r["office"] in ("H", "S"):
            out[r["cand_id"]] = {"office": r["office"], "state": r["state"], "district": r["district"],
                                 "party": r["party"], "ici": r["ici"]}
    return out


def refresh(cfg, force=False):
    cycle = cfg.get("fec", {}).get("cycle", 2026)
    url = URL.format(cycle=cycle, yy=str(cycle)[2:])
    prev = read_json(OUT, {}) or {}
    _, h = http_get(url, method="HEAD", timeout=30)
    lm = h.get("last-modified", "")
    if prev.get("last_modified") == lm and not force:
        return {"changed": False, "note": "FEC candidate master unchanged"}
    blob, _ = http_get(url, timeout=120)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        text = z.read([n for n in z.namelist() if n.endswith(".txt")][0]).decode("latin-1")
    cands = build(text, cycle)
    if len(cands) < 1000:
        raise RuntimeError(f"only {len(cands)} statutory {cycle} candidates parsed; keeping the previous data")
    write_json(OUT, {"cycle": cycle, "url": url, "last_modified": lm, "fetched_at": iso(now_utc()), "candidates": cands}, compact=True)
    return {"changed": True, "note": f"{len(cands)} statutory {cycle} House and Senate candidates"}

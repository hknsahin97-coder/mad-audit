#!/usr/bin/env python3
"""
MAD / MAST dataset audit — reproducible checks.

Audits the MAD dataset (HuggingFace `mcemri/MAST-Data`, CC-BY-4.0) published
alongside "Why Do Multi-Agent LLM Systems Fail?" (arXiv:2503.13657).

Every claim in README.md is produced by this script. Run:

    python audit.py                 # uses ./data, downloads if missing
    python audit.py --data DIR      # use an existing copy
    python audit.py --json out.json # also emit machine-readable results

No third-party dependencies. Network is used only to fetch the dataset
files and, for check F, three trace files from the MAST GitHub repo.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from difflib import SequenceMatcher

HF_BASE = "https://huggingface.co/datasets/mcemri/MAST-Data/resolve/main"
GH_RAW = "https://raw.githubusercontent.com/multi-agent-systems-failure-taxonomy/MAST/main"

# Minimum shared run of description text treated as "same mode, renumbered".
MIN_OVERLAP = 60

FILES = {
    "human": "MAD_human_labelled_dataset.json",
    "full": "MAD_full_dataset.json",
}

# Trace files compared in check F. HF record tag -> GitHub path under traces/.
TRACE_SAMPLES = [
    ("692c77d_1", "traces/AppWorld/692c77d_1.txt"),
    ("cf6abd2_1", "traces/AppWorld/cf6abd2_1.txt"),
    ("b119b1f_2", "traces/AppWorld/b119b1f_1.txt"),  # only _1 exists upstream
]

results = {}


def log(msg=""):
    print(msg, flush=True)


def rule(title):
    log()
    log("=" * 72)
    log(title)
    log("=" * 72)


def fetch(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    log(f"  downloading: {url}")
    with urllib.request.urlopen(url) as r, open(path, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def blockhash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


def parse_taxonomy(annotations):
    """annotations -> {code: (name, description)}"""
    out = {}
    for item in annotations:
        fm = item["failure mode"]
        code = fm.split()[0]
        name = fm.split("\n")[0].strip()
        desc = norm(" ".join(fm.split("\n")[1:]))
        out[code] = (name, desc)
    return out


# --------------------------------------------------------------------------
# A. provenance
# --------------------------------------------------------------------------
def check_provenance(paths):
    rule("A - File identity")
    prov = {}
    for key, path in paths.items():
        digest = sha256(path)
        size = os.path.getsize(path)
        prov[key] = {"file": os.path.basename(path), "sha256": digest, "bytes": size}
        log(f"  {os.path.basename(path):38} {size/1e6:8.1f} MB  sha256={digest[:16]}...")
    results["provenance"] = prov


# --------------------------------------------------------------------------
# B. taxonomy versions inside the human-labelled file
# --------------------------------------------------------------------------
def check_taxonomy_versions(human):
    rule("B - How many taxonomy versions are in the human-labelled file")
    by_round = Counter(r.get("round") for r in human)
    log("  round distribution:")
    for k, v in by_round.items():
        log(f"    {k:22} {v} records")

    versions = defaultdict(list)
    for r in human:
        codes = tuple(a["failure mode"].split()[0] for a in r["annotations"])
        versions[codes].append(r.get("round"))

    log()
    log(f"  distinct code sets: {len(versions)}")
    out = []
    for codes, rounds in versions.items():
        rs = sorted(set(rounds))
        log(f"    {len(codes):>2} modes | {len(rounds):>2} records | rounds: {rs}")
        out.append({"n_modes": len(codes), "n_records": len(rounds),
                    "rounds": rs, "codes": list(codes)})
    results["taxonomy_versions"] = out
    return versions


# --------------------------------------------------------------------------
# C. map each version onto MAST-14 by description identity
# --------------------------------------------------------------------------
def check_mapping(human):
    rule("C - Mapping each version onto MAST-14 (by description identity)")
    per_round = {}
    for r in human:
        per_round.setdefault(r["round"], r["annotations"])

    mast_round = next((k for k, v in per_round.items() if len(v) == 14), None)
    if mast_round is None:
        log("  no 14-mode version found - mapping skipped")
        return
    mast = parse_taxonomy(per_round[mast_round])
    log(f"  reference version: '{mast_round}' ({len(mast)} modes)")

    others = {k: parse_taxonomy(v) for k, v in per_round.items() if k != mast_round}
    # de-duplicate identical code sets (Round 2 and Round 3 share one)
    uniq, seen_sets = {}, {}
    for name, tax in others.items():
        key = tuple(sorted(tax))
        seen_sets.setdefault(key, []).append(name)
    for key, names in seen_sets.items():
        uniq["/".join(names)] = others[names[0]]

    def match(desc, tax):
        """Pick the code in `tax` sharing the longest common run of text with
        `desc`. Descriptions were carried over verbatim between taxonomy
        versions, so a long shared run is identity, not similarity. Both sides
        may carry extra text (MAST prepends the old mode name; earlier versions
        sometimes trail annotator scratch notes), which is why this compares
        longest common substring rather than a prefix."""
        best, best_len = None, 0
        for code, (_, d) in tax.items():
            if not d:
                continue
            m = SequenceMatcher(None, desc, d, autojunk=False).find_longest_match(
                0, len(desc), 0, len(d))
            if m.size > best_len:
                best, best_len = code, m.size
        return (best, best_len) if best_len >= MIN_OVERLAP else (None, best_len)

    header = f"  {'MAST-14':<40}" + "".join(f"{k:>18}" for k in uniq)
    log()
    log(header)
    log("  " + "-" * (len(header) - 2))

    table, agree = [], {k: 0 for k in uniq}
    for code in sorted(mast, key=lambda c: [int(x) for x in c.split(".")]):
        name, desc = mast[code]
        row = {"mast": code, "name": name}
        cells = ""
        for vname, tax in uniq.items():
            src, overlap = match(desc, tax)
            same = (src == code)
            agree[vname] += bool(same)
            row[vname] = {"code": src, "same_code": same, "overlap_chars": overlap}
            cells += f"{(src or '-') + (' =' if same else '  '):>18}"
        log(f"  {code + ' ' + name[4:]:<40}{cells}")
        table.append(row)

    log("  " + "-" * (len(header) - 2))
    for vname in uniq:
        log(f"  codes unchanged vs MAST-14 - {vname}: {agree[vname]}/{len(mast)}")

    # modes that did not survive into MAST-14
    log()
    for vname, tax in uniq.items():
        used = {row[vname]["code"] for row in table if row[vname]["code"]}
        dropped = [f"{c} {tax[c][0][4:]}" for c in sorted(tax) if c not in used]
        log(f"  {vname}: {len(dropped)} modes not carried into MAST-14")
        for d in dropped:
            log(f"     - {d}")

    results["mapping"] = {"reference_round": mast_round, "agreement": agree,
                          "rows": table}


# --------------------------------------------------------------------------
# D. duplicate annotation blocks in the human-labelled file
# --------------------------------------------------------------------------
def check_human_duplication(human):
    rule("D - Duplicate annotation blocks in the human-labelled file")
    by_block = defaultdict(list)
    for r in human:
        by_block[blockhash(r["annotations"])].append(
            (r.get("round"), r["mas_name"], r["trace_id"]))

    shared = sum(len(v) for v in by_block.values() if len(v) > 1)
    log(f"  records: {len(human)}   distinct annotation blocks: {len(by_block)}")
    log(f"  records sharing their block with another: {shared}")
    log()
    groups = []
    for h, members in sorted(by_block.items(), key=lambda kv: -len(kv[1])):
        if len(members) < 2:
            continue
        rounds = sorted({m[0] for m in members})
        frameworks = sorted({m[1] for m in members})
        log(f"    {h}  x{len(members)}  rounds={rounds}  frameworks={frameworks}")
        groups.append({"hash": h, "n": len(members), "rounds": rounds,
                       "frameworks": frameworks,
                       "members": [f"{m[1]}::{m[2]}" for m in members]})
    same_round = all(len(g["rounds"]) == 1 for g in groups)
    cross_fw = all(len(g["frameworks"]) > 1 for g in groups)
    log()
    log(f"  all duplicates within a single round: {same_round}")
    log(f"  all duplicates span multiple frameworks: {cross_fw}")
    results["human_duplication"] = {
        "n_records": len(human), "n_distinct_blocks": len(by_block),
        "n_sharing": shared, "all_within_round": same_round,
        "all_cross_framework": cross_fw, "groups": groups}


# --------------------------------------------------------------------------
# E. full dataset integrity
# --------------------------------------------------------------------------
def check_full(full):
    rule("E - Full dataset integrity")
    log(f"  records: {len(full)}")

    traces = Counter(blockhash(r.get("trace")) for r in full)
    repeated = sum(c for c in traces.values() if c > 1)
    log(f"  trace bodies: {len(traces)} distinct / {len(full)}   records in repeats: {repeated}")

    keys = Counter((r.get("mas_name"), r.get("llm_name"), r.get("trace_id")) for r in full)
    collisions = {k: c for k, c in keys.items() if c > 1}
    log(f"  (mas_name, llm_name, trace_id) distinct: {len(keys)} / {len(full)}")
    log(f"    colliding keys: {len(collisions)}  records covered: {sum(collisions.values())}")
    for k, c in list(collisions.items())[:3]:
        log(f"      example: {k} x{c}")

    blocks = defaultdict(list)
    nulls = 0
    for i, r in enumerate(full):
        a = r["mast_annotation"]
        blocks[blockhash(a)].append(i)
        if any(v is None for v in a.values()):
            nulls += 1
    biggest = max(blocks.values(), key=len)
    sample = full[biggest[0]]["mast_annotation"]
    flagged = sorted(k for k, v in sample.items() if v == 1)
    log(f"  mast_annotation: {len(blocks)} distinct blocks / {len(full)}")
    log(f"    largest block: {len(biggest)} records, flagged modes = "
        f"{flagged if flagged else 'NONE (all zero)'}")
    log(f"    -> label vector is {len(sample)}-bit; repetition is expected, "
        f"NOT a defect on its own")
    log(f"  records containing a null label: {nulls}")

    results["full_dataset"] = {
        "n_records": len(full),
        "distinct_traces": len(traces), "repeated_trace_records": repeated,
        "distinct_keys": len(keys), "colliding_keys": len(collisions),
        "records_in_collisions": sum(collisions.values()),
        "distinct_label_blocks": len(blocks),
        "largest_label_block": len(biggest),
        "largest_block_flagged_modes": flagged,
        "records_with_null_label": nulls,
    }


# --------------------------------------------------------------------------
# F. GitHub traces vs HF records
# --------------------------------------------------------------------------
def check_traces(human, data_dir):
    rule("F - GitHub traces/ vs HF records")
    by_tag = {}
    for r in human:
        t = r.get("trace")
        if not isinstance(t, str):
            continue
        m = re.search(r"Task \d+/\d+ \(([^)]+)\)", t)
        if m:
            by_tag[m.group(1)] = t

    rows = []
    for tag, gh_path in TRACE_SAMPLES:
        if tag not in by_tag:
            log(f"  {tag:12} no HF record found - skipped")
            continue
        local = os.path.join(data_dir, "gh", os.path.basename(gh_path))
        try:
            fetch(f"{GH_RAW}/{gh_path}", local)
        except Exception as exc:  # noqa: BLE001
            log(f"  {tag:12} could not fetch from GitHub: {exc}")
            continue
        with open(local, encoding="utf-8", errors="replace") as f:
            gh_text = f.read().strip()
        hf_text = by_tag[tag].strip()
        identical = hf_text == gh_text
        log(f"  {tag:12} vs {gh_path:34} "
            f"HF={len(hf_text):6} GH={len(gh_text):6}  identical={identical}")
        rows.append({"tag": tag, "github_path": gh_path,
                     "hf_len": len(hf_text), "gh_len": len(gh_text),
                     "identical": identical})
    results["trace_comparison"] = rows


# --------------------------------------------------------------------------
# G. GitHub definitions.txt drift
# --------------------------------------------------------------------------
def check_definitions(data_dir):
    rule("G - Repo definitions.txt vs the published taxonomy")
    local = os.path.join(data_dir, "gh", "definitions.txt")
    try:
        fetch(f"{GH_RAW}/taxonomy_definitions_examples/definitions.txt", local)
    except Exception as exc:  # noqa: BLE001
        log(f"  could not fetch: {exc}")
        return
    with open(local, encoding="utf-8", errors="replace") as f:
        text = f.read()
    found = {}
    for code in ["3.1", "3.2", "3.3"]:
        m = re.search(rf"^\s*{re.escape(code)}\s+([^:\n]+):", text, re.M)
        if m:
            found[code] = m.group(1).strip()
    published = {"3.1": "Premature Termination",
                 "3.2": "No or Incomplete Verification",
                 "3.3": "Incorrect Verification"}
    log(f"  {'code':6}{'definitions.txt':<38}{'published (paper / dataset card)'}")
    drift = []
    for code in ["3.1", "3.2", "3.3"]:
        a, b = found.get(code, "?"), published[code]
        same = a.lower().startswith(b.lower()[:12])
        log(f"  {code:6}{a:<38}{b}   {'match' if same else 'DIFFERS'}")
        if not same:
            drift.append({"code": code, "definitions_txt": a, "published": b})
    results["definitions_drift"] = drift


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--skip-full", action="store_true",
                    help="skip the 199 MB full dataset")
    args = ap.parse_args()

    os.makedirs(args.data, exist_ok=True)
    log("MAD / MAST dataset audit")
    log(f"data directory: {args.data}")

    paths = {}
    for key, name in FILES.items():
        if key == "full" and args.skip_full:
            continue
        paths[key] = fetch(f"{HF_BASE}/{name}", os.path.join(args.data, name))

    check_provenance(paths)

    with open(paths["human"], encoding="utf-8") as f:
        human = json.load(f)

    check_taxonomy_versions(human)
    check_mapping(human)
    check_human_duplication(human)
    check_traces(human, args.data)
    check_definitions(args.data)

    if "full" in paths:
        with open(paths["full"], encoding="utf-8") as f:
            full = json.load(f)
        check_full(full)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        log()
        log(f"machine-readable output: {args.json_out}")


if __name__ == "__main__":
    sys.exit(main())

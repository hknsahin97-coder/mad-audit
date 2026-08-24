#!/usr/bin/env python3
"""
Partial self-contained test of the audit's falsifiable prediction (README S3).

Prediction: repeating the issue #13 comparison with a round-aware remapping --
translating each human-file code to MAST-14 by description identity (finding 2)
before scoring -- should raise Cohen's kappa above the naive (literal-code)
value. If it does not rise, the mapping in finding 2 is wrong and findings 1-3
fall with it.

This runs the test WITHOUT re-running the llm_annotator.ipynb judge. Both sides
of kappa come from the released files:

  reference (MAST-14) : `mast_annotation` from MAD_full_dataset.json
  human labels        : MAD_human_labelled_dataset.json, per-mode annotator
                        majority, projected onto MAST-14 two ways --
                        naive (literal code number) vs remap (description match).

Two limits, both consequences of findings already in this audit:

  * The full set's (mas_name, benchmark_name, trace_id) key is not unique
    (finding 6) and traces share large boilerplate, so most human records
    cannot be reliably joined to a MAST-14 reference -- a join on that key
    pairs records whose trace bodies do not match. Only the AppWorld records
    carry a recoverable task tag (e.g. `692c77d_1`) that yields a clean 1:1
    join. That is 3 records, one per Round 1 / Round 2 / Round 3.
  * n = 3 is underpowered. The result is directional, not a confirmation.

Run:  python predict_kappa.py            # uses ./data
Stdlib only. Reuses the mapping helpers from audit.py so the remapping here is
identical to the one reported in finding 2.
"""

import json
import os
import re
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit import norm, parse_taxonomy, MIN_OVERLAP

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TAG = re.compile(r"\(([0-9a-f]{7}_\d+)\)")


def match_to_mast(desc, mast_tax):
    """MAST-14 code whose description shares the longest run of text with
    `desc`, if that run is >= MIN_OVERLAP chars (identity, not similarity).
    Same criterion as check_mapping() in audit.py."""
    best, best_len = None, 0
    for code, (_name, d) in mast_tax.items():
        if not d:
            continue
        m = SequenceMatcher(None, desc, d, autojunk=False).find_longest_match(
            0, len(desc), 0, len(d))
        if m.size > best_len:
            best, best_len = code, m.size
    return best if best_len >= MIN_OVERLAP else None


def present_modes(record, threshold=2):
    """Blocks the annotators mark present: votes >= threshold (2 = majority/3)."""
    out = []
    for item in record["annotations"]:
        votes = sum(bool(item.get(f"annotator_{i}")) for i in (1, 2, 3))
        if votes >= threshold:
            out.append(item)
    return out


def cohen_kappa(pairs):
    n = len(pairs)
    if not n:
        return float("nan"), float("nan")
    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n
    ay = sum(a for a, _ in pairs) / n
    by = sum(b for _, b in pairs) / n
    pe = ay * by + (1 - ay) * (1 - by)
    return ((po - pe) / (1 - pe) if (1 - pe) else float("nan")), po


def reliable_join(human, full):
    """Join human records to full-set MAST-14 labels by distinctive AppWorld
    task tag. Returns [(human_record, mast_annotation_dict), ...]."""
    by_tag = {}
    for r in full:
        tr = r.get("trace")
        txt = tr.get("trajectory") if isinstance(tr, dict) else (tr or "")
        ma = r.get("mast_annotation")
        if not isinstance(ma, dict):
            continue
        for tg in TAG.findall(txt):
            by_tag.setdefault(tg, []).append(ma)
    joined = []
    for rec in human:
        tags = set(TAG.findall(rec.get("trace", "")))
        hit = None
        for tg in tags:
            rows = by_tag.get(tg, [])
            if len(rows) == 1:          # unambiguous 1:1 match only
                hit = rows[0]
                break
        if hit is not None:
            joined.append((rec, hit))
    return joined


def main():
    human = json.load(open(os.path.join(DATA, "MAD_human_labelled_dataset.json"),
                           encoding="utf-8"))
    full = json.load(open(os.path.join(DATA, "MAD_full_dataset.json"),
                          encoding="utf-8"))

    mast_tax = parse_taxonomy(
        next(r for r in human if len(r["annotations"]) == 14)["annotations"])
    mast_codes = sorted(mast_tax, key=lambda c: [int(x) for x in c.split(".")])
    assert len(mast_codes) == 14

    joined = reliable_join(human, full)
    print(f"reliably joined records (AppWorld task tag): "
          f"{len(joined)} of {len(human)}")

    naive_pairs, remap_pairs = [], []
    for rec, ref in joined:
        ref_set = {c for c in mast_codes if int(ref.get(c, 0)) == 1}
        naive_set, remap_set = set(), set()
        for item in present_modes(rec):
            fm = item["failure mode"]
            code = fm.split()[0]
            desc = norm(" ".join(fm.split("\n")[1:]))
            if code in mast_tax:
                naive_set.add(code)
            m = match_to_mast(desc, mast_tax)
            if m:
                remap_set.add(m)
        print(f"\n  {rec['round']:16} {rec['mas_name']}/{rec['benchmark_name']}"
              f"/{rec['trace_id']}")
        print(f"    reference (MAST-14) present: {sorted(ref_set)}")
        print(f"    human naive             : {sorted(naive_set)}")
        print(f"    human remap             : {sorted(remap_set)}")
        for c in mast_codes:
            rb = 1 if c in ref_set else 0
            naive_pairs.append((1 if c in naive_set else 0, rb))
            remap_pairs.append((1 if c in remap_set else 0, rb))

    kn, pon = cohen_kappa(naive_pairs)
    kr, por = cohen_kappa(remap_pairs)
    print(f"\npooled over {len(joined)} records, {len(naive_pairs)} mode-cells")
    print(f"  kappa  naive (literal code) = {kn:+.3f}  (po={pon:.3f})")
    print(f"  kappa  remap (description)  = {kr:+.3f}  (po={por:.3f})")
    print(f"  delta                       = {kr - kn:+.3f}")
    print("\nInterpretation: remap raises kappa in the predicted direction, so "
          "the finding-2\nmapping is not refuted -- but n=3 and the gain is "
          "carried by a single Round 1\nrecord, so this is directional support, "
          "not confirmation. The strong test still\nneeds the llm_annotator.ipynb "
          "outputs this audit does not have.")


if __name__ == "__main__":
    main()

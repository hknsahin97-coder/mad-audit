# MAD dataset audit

An independent, reproducible audit of the **MAD** dataset
([`mcemri/MAST-Data`](https://huggingface.co/datasets/mcemri/MAST-Data), CC-BY-4.0),
published with *Why Do Multi-Agent LLM Systems Fail?* ([arXiv:2503.13657](https://arxiv.org/abs/2503.13657))
and its repo [`multi-agent-systems-failure-taxonomy/MAST`](https://github.com/multi-agent-systems-failure-taxonomy/MAST).

Every number below is produced by [`audit.py`](audit.py). Nothing is hand-entered.

Reported upstream: [MAST issue #18](https://github.com/multi-agent-systems-failure-taxonomy/MAST/issues/18)
· [dataset discussion #3](https://huggingface.co/datasets/mcemri/MAST-Data/discussions/3)

```bash
python audit.py                  # downloads to ./data if absent, prints the report
python audit.py --skip-full      # skip the 199 MB file (checks A–D, F, G)
python audit.py --json out.json  # machine-readable results
```

Stdlib only. Audited copy: `MAD_human_labelled_dataset.json` and
`MAD_full_dataset.json` as served on 2026-08-23, after the 2026-08-13 commit
*"Rebuild trace-label join; add Qwen/CodeLlama traces (1642 rows)"*.
SHA-256 of both files is printed by check A so any disagreement can be
localised to a version difference rather than a method difference:

| file | bytes | sha256 (first 16) |
|---|---|---|
| `MAD_human_labelled_dataset.json` | 2,662,908 | `30a0c4075078e9a1…` |
| `MAD_full_dataset.json` | 199,574,367 | `d636ac63dfc1c6af…` |

---

## Summary

| # | Finding | Status |
|---|---|---|
| 1 | `MAD_human_labelled_dataset.json` contains **three different taxonomy versions**, undocumented | open |
| 2 | Mode **codes were renumbered** between versions; 12/14 differ in Round 1, 7/14 in Rounds 2–3 | open |
| 3 | Consequence: pooled code-level comparison against MAST-14 is invalid for **15 of 19** records | open |
| 4 | 19 records carry only **8 distinct annotation blocks**; duplicates are within-round, cross-framework | open |
| 5 | Repo `definitions.txt` disagrees with the paper and dataset card on **3.2 / 3.3** | open |
| 6 | `(mas_name, llm_name, trace_id)` is **not unique** in the full set: 120 keys over 240 records | open |
| 7 | Trace-body replication in the full set | **resolved** by the 2026-08-13 rebuild |
| 8 | Repeated `mast_annotation` blocks in the full set | **not a defect** — see below |

Findings 1–3 are one problem seen from three sides. Finding 3 offers a simpler
explanation for the κ = 0.05 reported in
[issue #13](https://github.com/multi-agent-systems-failure-taxonomy/MAST/issues/13)
than the "different trace set" hypothesis raised there.

---

## 1. The human-labelled file mixes three taxonomy versions

`MAD_human_labelled_dataset.json` has 19 records over four `round` values.
Grouping records by the set of mode codes in their `annotations` array yields
**three distinct code sets**:

| `round` | records | modes | code range |
|---|---|---|---|
| Round 1 | 5 | **18** | 1.1–1.5, 2.1–2.6, 3.1–3.4, 4.1–4.3 |
| Round 2, Round 3 | 10 | **17** | 1.1–1.7, 2.1–2.7, 3.1–3.3 |
| `Generlazability` *(sic)* | 4 | **14** | 1.1–1.5, 2.1–2.6, 3.1–3.3 — the published MAST |

Only the last four records are natively annotated in the 14-mode taxonomy the
paper publishes. Neither the dataset card nor the repo README mentions that the
file spans several taxonomy generations, and `round` is not documented as a
schema-bearing field.

## 2. Codes were renumbered between versions

Mode **descriptions** were carried over verbatim across versions, so the
versions can be aligned without interpretation: `audit.py` matches modes by
longest common substring of their description text (threshold 60 characters;
observed overlaps are 100–400 characters, i.e. identity rather than
similarity).

| MAST-14 | Round 1 | Rounds 2–3 |
|---|---|---|
| 1.1 Disobey Task Specification | **1.1** | **1.1** |
| 1.2 Disobey Role Specification | 2.6 | 1.7 |
| 1.3 Step Repetition | 2.2 | 1.5 |
| 1.4 Loss of Conversation History | 2.3 | 1.6 |
| 1.5 Unaware of Termination Conditions | **1.5** | 1.3 |
| 2.1 Conversation Reset | 2.4 | **2.1** |
| 2.2 Fail to Ask for Clarification | 1.4 | **2.2** |
| 2.3 Task Derailment | 2.5 | **2.3** |
| 2.4 Information Withholding | 3.2 | 2.6 |
| 2.5 Ignored Other Agent's Input | 3.3 | 2.7 |
| 2.6 Reasoning-Action Mismatch | 1.2 | 1.2 |
| 3.1 Premature Termination | 4.1 | **3.1** |
| 3.2 No or Incomplete Verification | 4.3 | **3.2** |
| 3.3 Incorrect Verification | 4.2 | **3.3** |

Codes unchanged relative to MAST-14: **Round 1 → 2/14**, **Rounds 2–3 → 7/14**.

Modes that did not survive into MAST-14 — Round 1 drops four
(*Undetected conversation ambiguities and contradictions*, *Unbatched repetitive
execution*, *Disagreement induced inaction*, *Waiting for known information*);
Rounds 2–3 drop three (the same, minus *Waiting for known information*, which
they had already dropped). 18 − 4 = 14 and 17 − 3 = 14, so every mode is
accounted for.

Incidental: the Round 1 definition of `4.2 Lack of result verification` ends
with what reads as an editing note left in the published text —
`NEW: FUNCTION CORRECTNESS here 1. no verification in MAS 2. verification is designed to …`.

## 3. Consequence for code-level comparisons

Any procedure that reads `failure mode` codes from this file and compares them
to MAST-14 output — an LLM annotator, a detector, a κ computation — is
comparing different concepts for **15 of the 19 records**, unless it first
remaps by `round`.

This is a sufficient explanation for the result in issue #13 (Cohen's κ = 0.05
between `llm_annotator.ipynb` output and the published `failure_modes`, against
κ = 0.77 reported in the paper). The dataset need not be a different trace set;
the codes simply do not denote the same modes.

**This audit does not claim the paper's κ = 0.88 is wrong.** It claims that
κ cannot be recomputed from the published file without a round-aware remapping
that is not published.

### A falsifiable prediction

If this finding is correct, then repeating the comparison in issue #13 with a
**round-aware remapping** — translating Round 1 and Rounds 2–3 codes into
MAST-14 via the table in finding 2 before scoring — should raise Cohen's κ
substantially above 0.05.

If it does not rise, the mapping in finding 2 is wrong and findings 1–3 should
be discarded with it.

This audit deliberately does not run the full LLM-vs-human test: it does not
have the `llm_annotator.ipynb` outputs the issue was based on. The prediction is
stated so the claim can be **refuted** rather than argued about. Anyone holding
those outputs can settle it in an afternoon.

### Partial self-contained result (2026-08-24)

[`predict_kappa.py`](predict_kappa.py) runs a self-contained version of the test
that needs no LLM judge: it scores the human labels against the full set's own
`mast_annotation` (a MAST-14 0/1 vector), *naive* (literal code number) vs
*remap* (round-aware, via the finding-2 table).

The instrument is limited by two findings above. The `(mas_name,
benchmark_name, trace_id)` key is not unique (finding 6) and traces share large
boilerplate, so most human records cannot be reliably joined to a MAST-14
reference; a join on that key pairs records whose trace bodies do not match.
Only the **3 AppWorld records** carry a recoverable task tag (e.g. `692c77d_1`)
giving a clean 1:1 join — one per Round 1 / 2 / 3.

On those 3 records (42 mode-cells), pooled Cohen's κ:

| projection | κ |
|---|---|
| naive (literal code) | **+0.13** |
| round-aware remap | **+0.27** |

The remap raises κ, in the predicted direction, so the finding-2 mapping is
**not refuted**. But the entire gain comes from one Round 1 record (human code
`3.3` → MAST `2.5`, which the reference marks present); the Rounds 2–3 records
show no change. With n = 3 this is **directional support, not confirmation**.
The strong test — reproducing the issue #13 κ against `llm_annotator.ipynb`
output — still requires those judge outputs.

## 4. Duplicate annotation blocks

Hashing each record's full `annotations` array:

- 19 records → **8 distinct blocks**
- **18 of 19** records share their block with at least one other record
- every duplicate group is **within a single round** and **spans multiple MAS
  frameworks** (e.g. one block covers `AppWorld`, `HyperAgent` and `AG2`
  simultaneously)

Three annotators labelling three different systems' traces would not be
expected to produce byte-identical label arrays. The pattern is consistent with
a join that broadcast one annotation row across several traces. This
independently reproduces
[issue #16](https://github.com/multi-agent-systems-failure-taxonomy/MAST/issues/16)
on the post-rebuild file.

If inter-annotator agreement is computed over these records as if they were
independent, the effective number of distinct observations is 8, not 19.

## 5. `definitions.txt` disagrees with the published taxonomy

| code | repo `taxonomy_definitions_examples/definitions.txt` | paper & dataset card |
|---|---|---|
| 3.1 | Premature Termination | Premature Termination |
| 3.2 | **Weak Verification** | No or Incomplete Verification |
| 3.3 | **No or Incorrect Verification** | Incorrect Verification |

`llm_annotator.ipynb` feeds this file to the judge. This confirms
[issue #12](https://github.com/multi-agent-systems-failure-taxonomy/MAST/issues/12)
from a third source: the repo's definitions are a different taxonomy generation
than both the paper and the maintained dataset card.

## 6. Composite key is not unique in the full set

`MAD_full_dataset.json` has 1642 records but only **1522 distinct**
`(mas_name, llm_name, trace_id)` triples — **120 keys covering 240 records**
(e.g. `('ChatDev', 'GPT-4o', 0)` appears twice). Issue #14 used this triple as a
deduplication key; that assumption does not hold on the current file either.

**What the collisions are (check H, added 2026-08-27).** Comparing the trace
bodies of all 120 colliding pairs: **none are identical**, 15 share a long
prefix, 8 are near-duplicates, and **97 (80.8%) are unrelated traces**. The
cause is not duplication but an omitted field: in **120 of 120** colliding
pairs the records carry a *different* `trace["key"]` — the scenario id the
composite key leaves out (e.g. `ChatDev_ProgramDev_GPT4o` vs
`ChatDev_ProgramDev2_GPT4o`).

So the triple is not "unreliable"; it is **incomplete**. A consumer that needs
a unique key should use `(mas_name, llm_name, trace_id, trace["key"])`, which
is unique across the full set. This also explains why finding 7 holds — all
1642 trace bodies are distinct — without contradicting finding 6.

## 7. Resolved: trace-body replication

All **1642/1642** trace bodies in the full set are distinct — zero repeats. The
class of problem reported in
[issue #17](https://github.com/multi-agent-systems-failure-taxonomy/MAST/issues/17)
appears to have been addressed by the 2026-08-13 rebuild.

## 8. Not a defect: repeated `mast_annotation` blocks

The full set has only 453 distinct `mast_annotation` blocks across 1642
records, the largest covering 401. This looks like the full-set analogue of
finding 4, and it is not: the 401-record block is the **all-zero vector** (no
failure mode flagged), spread across all seven frameworks, and the next two
largest are ordinary co-occurrences (`1.3 + 1.5`; `1.1` alone).
`mast_annotation` is a 14-bit binary vector — repetition is expected.

Separately, 4 of the 1642 records carry at least one `null` label. The dataset
card documents `null` as "annotation unavailable", so this is expected; it is
noted here only because a consumer computing per-mode rates needs to decide
whether those are missing or negative.

The distinction matters: finding 4 is suspicious because human annotations of
different traces collided; this is just the arithmetic of a short label vector.

## Trace provenance (context, not a finding)

Where GitHub `traces/` and the HF records overlap they agree byte-for-byte
(`692c77d_1`, `cf6abd2_1`). GitHub is **not** a superset: HF record
`b119b1f_2` has no counterpart upstream (the repo has `b119b1f_1`, a different
task). GitHub carries 13,358 trace files against the dataset's 1642 records,
and filename-based alignment only works for AppWorld — other frameworks' trace
files carry no task tag.

---

## What this audit does not establish

- Whether any of this changes the paper's conclusions. That depends on how the
  files are used downstream, which the authors are better placed to judge.
- Whether the human-labelled file's version mixing is accidental or a
  deliberate record of the annotation process. A single sentence in the dataset
  card would settle it.
- The mapping in finding 2 is derived from description identity, not from an
  authors' statement. No official cross-version mapping appears to be published;
  that absence is part of the problem.
- Coverage: findings 4 and 6 are exhaustive over their files. The trace
  comparison samples three records, not all 19 — only AppWorld traces carry
  recoverable identifiers.

## Licence

The audited data is CC-BY-4.0. This audit's code is offered under the same
terms as the data it examines; attribution to the MAD authors is retained
throughout.

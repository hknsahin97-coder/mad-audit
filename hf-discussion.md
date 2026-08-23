<!--
POSTED 2026-08-23 as discussion #3:
https://huggingface.co/datasets/mcemri/MAST-Data/discussions/3

Kept here so the wording stays versioned alongside the findings it refers to.
-->

# Title

`MAD_human_labelled_dataset.json` spans three taxonomy versions — is this documented anywhere?

---

# Body

Thanks for keeping this dataset current — the 2026-08-13 *"Rebuild trace-label join"* update clearly did real work, and it's the reason I'm posting here rather than only on GitHub.

While computing inter-annotator agreement on `MAD_human_labelled_dataset.json` I found that its 19 records are not annotated in one taxonomy. Grouping records by the set of mode codes in their `annotations` array gives three distinct sets:

| `round` | records | modes |
|---|---|---|
| Round 1 | 5 | 18 |
| Round 2, Round 3 | 10 | 17 |
| `Generlazability` | 4 | 14 — the published MAST |

Mode descriptions were carried over verbatim between versions, so the versions can be aligned by description text. Doing that shows the code numbers were reassigned: only **2 of 14** codes are unchanged between Round 1 and MAST-14, and **7 of 14** between Rounds 2–3 and MAST-14. For example `2.2` is *Step Repetition* in Round 1 and *Fail to Ask for Clarification* in MAST-14.

Two things follow, and I'd like to check both with you rather than assume:

1. **The dataset card documents one schema.** It describes `trace` as `{key, index, trajectory}` and the label field as `mast_annotation`. That holds for `MAD_full_dataset.json`. In the human-labelled file `trace` is a plain string and the label field is `annotations` with a different, longer mode list. A reader following the card will mis-parse the second file.

2. **Code-level comparison against MAST-14 is invalid for 15 of the 19 records** unless remapped by `round`. This looks like a sufficient explanation for the κ = 0.05 reported in [MAST issue #13](https://github.com/multi-agent-systems-failure-taxonomy/MAST/issues/13), without needing the "different trace set" hypothesis raised there — and it is falsifiable: a round-aware remapping should raise that κ substantially. If it doesn't, my alignment is wrong.

Separately, and reproducing on the current file: the 19 records carry only **8 distinct** `annotations` blocks, with 18 of 19 sharing a byte-identical block with another record; every duplicate group is within a single round and spans multiple frameworks.

Full detail, the version mapping table, and a script that reproduces every number (stdlib only, downloads the files itself):

**https://github.com/hknsahin97-coder/mad-audit**

I also opened [MAST issue #18](https://github.com/multi-agent-systems-failure-taxonomy/MAST/issues/18) with the same findings, but the GitHub repo hasn't been pushed to since 2025-07, whereas this dataset is clearly maintained — so this is probably the better place to reach you.

If the version mixing is deliberate — a record of how the taxonomy developed rather than a packaging accident — a sentence in the card and a published cross-version code mapping would close it entirely. Happy to be told I'm misreading something.

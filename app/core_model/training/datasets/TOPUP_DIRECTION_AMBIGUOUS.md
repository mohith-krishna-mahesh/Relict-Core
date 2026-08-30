# Task: Top up direction_ambiguous category — sft_task1_final_v2.jsonl → v3

## Why
Post-dedup category proportions on the current 352-record file:
  standard_clear: 121 (34.4%)  — target 30%, over
  direction_ambiguous: 82 (23.3%) — target 30%, UNDER by 6.7pp
  fully_vague: 75 (21.3%) — target 20%, fine
  multi_goal_clear: 74 (21.0%) — target 20%, fine

direction_ambiguous is the category tied to the baseline's documented failure mode
(silent direction-guessing on compound-clause objectives). It took the largest
proportional hit from fuzzy dedup and needs to be brought back up. Do NOT generate
more of the other three categories — they're already at target.

## Step 1 — Generate raw batch
Run generate_task1.py targeting ONLY the direction_ambiguous category.
Generate 50 raw examples (buffer above the ~34 net-new needed, to absorb
near-duplicate rejection against the existing 352-record corpus).

Output: direction_ambiguous_batch_raw.jsonl

## Step 2 — Correct mislabels
KNOWN BUG: the generator mislabels direction_ambiguous as CLEAR by default in the
large majority of cases (it was ~93% wrong on the original batch). Every record in
this raw batch needs its ambiguity_status checked, not just a sample.

Process (same as the original 3-pass correction):
1. Apply your existing regex heuristics (the ones used to catch the first batch's
   mislabels) to auto-flag likely-CLEAR-mislabeled-as-CLEAR entries.
2. Manually review every remaining record — not just the flagged ones, since the
   heuristics are known to be imperfect (42 needed manual review out of the original
   batch even after 2 regex passes).
3. For every record confirmed direction_ambiguous: ambiguity_status =
   "CLARIFICATION_REQUIRED", and all 5 other expected_output fields = null (per the
   locked schema rule — no best-guess content on ambiguous objectives).

Output: direction_ambiguous_batch_corrected.jsonl

## Step 3 — Dedup against the FULL existing corpus (not just within the new batch)
This is different from the original dedup pass: the original dedup only checked new
examples against each other. This time, check every new record against ALL 352
existing records in sft_task1_final_v2.jsonl, using the same method as before
(SequenceMatcher ratio > 0.85, OR 50-character prefix exact match). Drop any new
record that matches an existing one. Log how many were dropped and why.

## Step 4 — Merge, validate, report
Use topup_merge_and_validate.py (provided separately) to:
- Merge the surviving corrected batch into sft_task1_final_v2.jsonl
- Validate every record's schema (6 keys, correct types, CLARIFICATION_REQUIRED
  records have all other fields null)
- Print final category counts and percentages
- Fail loudly (list the bad records) if anything doesn't validate — don't silently drop

Output: sft_task1_final_v3.jsonl

## Done when
- direction_ambiguous is at 28-32% of the new total (don't force exactly 30%,
  that's overfitting to a round number — the range matters, not the exact digit)
- 0 schema validation failures
- 0 remaining near-dup pairs against the full v3 file
- A printed summary: raw generated, mislabels corrected, near-dups dropped
  (batch-internal AND against existing corpus, reported separately), final counts
"""
Fixes app/core_model/training/datasets/sft_task1_raw_conservation.jsonl

Splits records into three outputs:
  1. sft_task1_raw_conservation.fixed.jsonl   - clean, auto-fixable records
  2. sft_task1_raw_conservation.needs_review.jsonl - fully-empty expected_output,
     cannot be auto-fixed, needs manual inspection or regeneration
  3. prints a summary + a duplicate-phrasing signal so you can eyeball whether
     the word bank is too narrow

Usage:
    python fix_schema_conservation.py <input.jsonl>
"""

import json
import re
import sys
from collections import Counter

EXPECTED_KEYS = {
    "target_phenotypes",
    "biological_processes",
    "desired_change",
    "relevant_concepts",
    "retrieval_targets",
    "ambiguity_status",
}


def fix_record(record, idx):
    """
    Returns (fixed_record, status) where status is one of:
      'ok'          - already valid, untouched
      'renamed'     - exactly one corrupted key found and renamed to retrieval_targets
      'needs_review'- expected_output missing multiple/all keys, no safe auto-fix
    """
    out = record.get("expected_output")
    if not isinstance(out, dict) or not out:
        return record, "needs_review"

    keys = set(out.keys())
    missing = EXPECTED_KEYS - keys
    unexpected = keys - EXPECTED_KEYS

    if not missing and not unexpected:
        return record, "ok"

    # The only safe auto-fix: exactly one field missing (retrieval_targets)
    # and exactly one unexpected key standing in for it. Multiple missing
    # fields (e.g. all six) means the generation itself failed - don't guess.
    if missing == {"retrieval_targets"} and len(unexpected) == 1:
        bad_key = next(iter(unexpected))
        out["retrieval_targets"] = out.pop(bad_key)
        record["expected_output"] = out
        return record, "renamed"

    return record, "needs_review"


def main():
    if len(sys.argv) != 2:
        print("Usage: python fix_schema_conservation.py <input.jsonl>")
        sys.exit(1)

    in_path = sys.argv[1]
    fixed_path = in_path.replace(".jsonl", ".fixed.jsonl")
    review_path = in_path.replace(".jsonl", ".needs_review.jsonl")

    counts = Counter()
    objective_words = Counter()

    with (
        open(in_path, encoding="utf-8") as f_in,
        open(fixed_path, "w", encoding="utf-8") as f_fixed,
        open(review_path, "w", encoding="utf-8") as f_review,
    ):
        for idx, line in enumerate(f_in, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            fixed, status = fix_record(record, idx)
            counts[status] += 1

            if status == "needs_review":
                f_review.write(json.dumps({"line": idx, **fixed}, ensure_ascii=False) + "\n")
            else:
                f_fixed.write(json.dumps(fixed, ensure_ascii=False) + "\n")

            # crude duplicate-phrasing signal: first 6 words of the objective,
            # species/numbers stripped
            obj = record.get("objective", "")
            skeleton = re.sub(r"\d+(\.\d+)?%?", "#", obj)
            skeleton = re.sub(r"[A-Z][a-z]+ [a-z]+", "SPECIES", skeleton)
            first_words = " ".join(skeleton.split()[:6])
            objective_words[first_words] += 1

    print(f"Processed: {sum(counts.values())} records")
    print(f"  ok:            {counts['ok']}")
    print(f"  renamed:       {counts['renamed']}  -> written to {fixed_path}")
    print(f"  needs_review:  {counts['needs_review']}  -> written to {review_path}")
    print()
    print("Top repeated 6-word openings (skeleton-normalized) - check for")
    print("word-bank narrowness if any count looks high relative to total:")
    for phrase, n in objective_words.most_common(10):
        if n > 1:
            print(f"  {n:>3}x  {phrase}")


if __name__ == "__main__":
    main()

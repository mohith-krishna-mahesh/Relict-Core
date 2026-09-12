"""
Merge a corrected direction_ambiguous top-up batch into sft_task1_final_v2.jsonl,
after deduping the new batch against the FULL existing corpus (not just internally).

Usage:
    python topup_merge_and_validate.py \
        --existing sft_task1_final_v2.jsonl \
        --new_batch direction_ambiguous_batch_corrected.jsonl \
        --output sft_task1_final_v3.jsonl \
        --dedup_threshold 0.85
"""

import json
import argparse
from collections import Counter
from difflib import SequenceMatcher

REQUIRED_KEYS = {
    "target_phenotypes",
    "biological_processes",
    "desired_change",
    "relevant_concepts",
    "retrieval_targets",
    "ambiguity_status",
}


def load_jsonl(path):
    recs = []
    with open(path) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path} line {i}: invalid JSON: {e}")
    return recs


def is_near_dup(text, existing_texts, threshold):
    prefix = text[:50]
    for other in existing_texts:
        if other[:50] == prefix:
            if SequenceMatcher(None, text, other).ratio() > threshold:
                return True
    return False


def validate_record(rec, idx):
    errors = []
    eo = rec.get("expected_output", {})
    keys = set(eo.keys())
    if keys != REQUIRED_KEYS:
        missing = REQUIRED_KEYS - keys
        extra = keys - REQUIRED_KEYS
        errors.append(f"key mismatch (missing={missing}, extra={extra})")
        return errors  # can't check further without correct keys

    status = eo.get("ambiguity_status")
    if status not in ("CLEAR", "CLARIFICATION_REQUIRED"):
        errors.append(f"invalid ambiguity_status: {status!r}")

    if status == "CLARIFICATION_REQUIRED":
        nonnull = {k: v for k, v in eo.items() if k != "ambiguity_status" and v is not None}
        if nonnull:
            errors.append(f"CLARIFICATION_REQUIRED but non-null fields present: {nonnull}")

    if (
        "objective" not in rec
        or not isinstance(rec["objective"], str)
        or not rec["objective"].strip()
    ):
        errors.append("missing or empty 'objective' field")

    if "category" not in rec:
        errors.append("missing 'category' field")

    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--existing", required=True)
    ap.add_argument("--new_batch", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--dedup_threshold", type=float, default=0.85)
    args = ap.parse_args()

    existing = load_jsonl(args.existing)
    new_batch = load_jsonl(args.new_batch)

    existing_texts = [r["objective"] for r in existing]

    # Dedup new batch against existing corpus
    kept, dropped_vs_existing = [], []
    for rec in new_batch:
        text = rec["objective"]
        if is_near_dup(text, existing_texts, args.dedup_threshold):
            dropped_vs_existing.append(text)
        else:
            kept.append(rec)

    # Dedup surviving new records against each other (in case the batch itself has dupes)
    final_new, dropped_internal = [], []
    kept_texts = []
    for rec in kept:
        text = rec["objective"]
        if is_near_dup(text, kept_texts, args.dedup_threshold):
            dropped_internal.append(text)
        else:
            final_new.append(rec)
            kept_texts.append(text)

    # Validate every surviving new record before merging
    bad_records = []
    for i, rec in enumerate(final_new):
        errs = validate_record(rec, i)
        if errs:
            bad_records.append((i, rec.get("objective", "<no objective>"), errs))

    if bad_records:
        print(f"VALIDATION FAILED — {len(bad_records)} record(s) did not pass schema checks:")
        for i, obj, errs in bad_records:
            print(f"  [{i}] {obj[:80]!r}")
            for e in errs:
                print(f"      - {e}")
        print("\nFix these before merging. No output file written.")
        return

    merged = existing + final_new

    with open(args.output, "w") as f:
        for rec in merged:
            f.write(json.dumps(rec) + "\n")

    cats = Counter(r["category"] for r in merged)
    total = len(merged)

    print(f"Raw new batch:              {len(new_batch)}")
    print(f"Dropped (dup of existing):  {len(dropped_vs_existing)}")
    print(f"Dropped (dup within batch): {len(dropped_internal)}")
    print(f"Net new records added:      {len(final_new)}")
    print(f"Final total:                {total}")
    print()
    print("Final category breakdown:")
    for c, n in cats.most_common():
        print(f"  {c}: {n} ({100 * n / total:.1f}%)")
    print()
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()

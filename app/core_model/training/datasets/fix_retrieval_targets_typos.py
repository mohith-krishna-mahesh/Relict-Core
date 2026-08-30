# fix_retrieval_targets_typos.py
import json

path = "app/core_model/training/datasets/sft_task1_raw.jsonl"
recs = [json.loads(l) for l in open(path, encoding="utf-8")]

REQUIRED_KEYS = {
    "target_phenotypes", "biological_processes", "desired_change",
    "relevant_concepts", "retrieval_targets", "ambiguity_status"
}

fixed = 0
for r in recs:
    out = r["expected_output"]
    if "retrieval_targets" not in out:
        extra_keys = set(out.keys()) - REQUIRED_KEYS
        if len(extra_keys) == 1:
            bad_key = extra_keys.pop()
            out["retrieval_targets"] = out.pop(bad_key)
            fixed += 1
        else:
            print(f"SKIPPED (ambiguous, {len(extra_keys)} extra keys): {r['objective'][:60]!r}")

with open(path, "w", encoding="utf-8") as f:
    for r in recs:
        f.write(json.dumps(r) + "\n")

print(f"Fixed {fixed} records")
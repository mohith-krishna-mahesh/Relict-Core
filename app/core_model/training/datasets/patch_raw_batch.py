import json

path = "app/core_model/training/datasets/sft_task1_raw.jsonl"
recs = [json.loads(l) for l in open(path, encoding="utf-8")]

for r in recs:
    if r["category"] == "fully_vague":
        out = r["expected_output"]
        for k in ["target_phenotypes", "biological_processes", "desired_change", "relevant_concepts", "retrieval_targets"]:
            out.setdefault(k, None)
        out.setdefault("ambiguity_status", "CLARIFICATION_REQUIRED")  # record 22 was missing this key entirely
    if r["category"] == "multi_goal_clear" and "retrie-than_targets" in r["expected_output"]:
        r["expected_output"]["retrieval_targets"] = r["expected_output"].pop("retrie-than_targets")

with open(path, "w", encoding="utf-8") as f:
    for r in recs:
        f.write(json.dumps(r) + "\n")

print("patched")
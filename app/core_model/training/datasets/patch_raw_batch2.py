import json

path = "app/core_model/training/datasets/sft_task1_raw.jsonl"
recs = [json.loads(l) for l in open(path, encoding="utf-8")]

for r in recs:
    out = r["expected_output"]
    if "ambiguitecture_status" in out:
        out.pop("ambiguitecture_status")

with open(path, "w", encoding="utf-8") as f:
    for r in recs:
        f.write(json.dumps(r) + "\n")

print("patched")
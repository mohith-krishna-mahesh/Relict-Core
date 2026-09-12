import json
import difflib
from collections import Counter

train = [
    json.loads(l)
    for l in open("app/core_model/training/datasets/active/sft_task1_train.jsonl", encoding="utf-8")
]
test = [
    json.loads(l)
    for l in open("app/core_model/training/datasets/active/sft_task1_test.jsonl", encoding="utf-8")
]

train_objs = [r["objective"] for r in train]

cat_matches = Counter()
cat_totals = Counter()

for r in test:
    cat = r.get("category", "unknown")
    cat_totals[cat] += 1
    obj = r["objective"]
    if any(difflib.SequenceMatcher(None, obj, tr).ratio() > 0.85 for tr in train_objs):
        cat_matches[cat] += 1

for cat in sorted(cat_totals):
    print(cat, cat_matches[cat], "/", cat_totals[cat])

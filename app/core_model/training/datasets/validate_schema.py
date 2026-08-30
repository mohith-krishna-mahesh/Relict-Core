import json, sys
from pathlib import Path

REQUIRED_KEYS = {
    "target_phenotypes",
    "biological_processes",
    "desired_change",
    "relevant_concepts",
    "retrieval_targets",
    "ambiguity_status",
}


def check_file(path):
    bad = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            rec = json.loads(line)
            out = rec.get("expected_output", {})
            missing = REQUIRED_KEYS - set(out.keys())
            extra = set(out.keys()) - REQUIRED_KEYS
            issues = []
            if missing:
                issues.append(f"missing: {missing}")
            if extra:
                issues.append(f"unexpected: {extra}")

            status = out.get("ambiguity_status")
            other_fields = {k: v for k, v in out.items() if k != "ambiguity_status"}
            if status == "CLARIFICATION_REQUIRED":
                non_null = {k: v for k, v in other_fields.items() if v is not None}
                if non_null:
                    issues.append(
                        f"CLARIFICATION_REQUIRED but non-null fields: {list(non_null.keys())}"
                    )
            elif status == "CLEAR":
                null_fields = {k for k, v in other_fields.items() if v is None}
                if null_fields:
                    issues.append(f"CLEAR but null fields: {null_fields}")

            cat = rec.get("category")
            expected_status = {
                "fully_vague": "CLARIFICATION_REQUIRED",
                "direction_ambiguous": "CLARIFICATION_REQUIRED",
                "standard_clear": "CLEAR",
                "multi_goal_clear": "CLEAR",
            }.get(cat)
            if expected_status and status != expected_status:
                issues.append(f"category={cat} implies {expected_status}, got {status}")

            if issues:
                bad.append((i, rec.get("objective", "")[:60], issues))

    if bad:
        print(f"{len(bad)} bad record(s) in {path}:")
        for i, obj, issues in bad:
            print(f"  [{i}] {obj!r} - {'; '.join(issues)}")
    else:
        print(f"{path}: all records pass schema + null-consistency + category checks.")


if __name__ == "__main__":
    check_file(sys.argv[1])

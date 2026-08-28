import json
from pathlib import Path

from app.core_model.objective_parser import resolve_objective

EVAL_SET_PATH = Path(__file__).parent / "datasets" / "eval_set.jsonl"


def load_eval_set() -> list[dict]:
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_eval() -> None:
    eval_set = load_eval_set()
    results = []

    for i, example in enumerate(eval_set):
        objective = example["objective"]
        expected = example["expected_output"]

        try:
            actual = resolve_objective(objective)
            actual_dict = actual.model_dump()
        except Exception as e:
            print(f"[{i}] FAILED TO PARSE: {objective!r}")
            print(f"    Error: {e}")
            results.append(
    {
        "index": i,
        "objective": objective,
        "status": "parse_error",
        "error": str(e),
    }
)
            continue

        status_match = actual_dict["ambiguity_status"] == expected["ambiguity_status"]

        print(f"[{i}] {objective}")
        print(f"    expected ambiguity_status: {expected['ambiguity_status']}")
        print(f"    actual   ambiguity_status: {actual_dict['ambiguity_status']}")
        print(f"    {'PASS' if status_match else 'FAIL'}")
        print()

        results.append({
            "index": i,
            "objective": objective,
            "expected": expected,
            "actual": actual_dict,
            "status_match": status_match,
        })

    total = len(results)
    passed = sum(1 for r in results if r.get("status_match"))
    errors = sum(1 for r in results if r.get("status") == "parse_error")

    print(f"\n{'='*50}")
    print(f"Total: {total} | Passed (ambiguity_status match): {passed} | Parse errors: {errors}")

    with open(Path(__file__).parent / "datasets" / "eval_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    run_eval()
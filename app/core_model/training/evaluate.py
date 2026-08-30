import json
from pathlib import Path

from app.core_model.objective_parser import _extract_json, _load_prompt_template, StructuredObjective
from app.core_model.inference.ollama import generate as baseline_generate
from app.core_model.training.merge_adapter import generate as finetuned_generate

EVAL_SET_PATH = Path(__file__).parent / "datasets" / "eval_set.jsonl"
RESULTS_PATH = Path(__file__).parent / "datasets" / "eval_results.json"


def load_eval_set() -> list[dict]:
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _resolve(generate_fn, prompt_template: str, objective_text: str) -> dict:
    prompt = prompt_template.format(objective=objective_text)
    raw_output = generate_fn(prompt)
    parsed = _extract_json(raw_output)
    return StructuredObjective(**parsed).model_dump()


def run_eval() -> None:
    eval_set = load_eval_set()
    prompt_template = _load_prompt_template()
    results = []

    for i, example in enumerate(eval_set):
        objective = example["objective"]
        expected = example["expected_output"]
        row = {"index": i, "objective": objective, "expected": expected}

        print(f"[{i}] {objective}")

        try:
            b_actual = _resolve(baseline_generate, prompt_template, objective)
            b_match = b_actual["ambiguity_status"] == expected["ambiguity_status"]
            row["baseline_actual"], row["baseline_match"] = b_actual, b_match
            print(f"    baseline   {b_actual['ambiguity_status']:<22} {'PASS' if b_match else 'FAIL'}")
        except Exception as e:
            row["baseline_error"] = str(e)
            print(f"    baseline   PARSE ERROR: {e}")

        try:
            f_actual = _resolve(finetuned_generate, prompt_template, objective)
            f_match = f_actual["ambiguity_status"] == expected["ambiguity_status"]
            row["finetuned_actual"], row["finetuned_match"] = f_actual, f_match
            print(f"    finetuned  {f_actual['ambiguity_status']:<22} {'PASS' if f_match else 'FAIL'}")
        except Exception as e:
            row["finetuned_error"] = str(e)
            print(f"    finetuned  PARSE ERROR: {e}")

        print()
        results.append(row)

    total = len(results)
    b_passed = sum(1 for r in results if r.get("baseline_match"))
    f_passed = sum(1 for r in results if r.get("finetuned_match"))
    b_errors = sum(1 for r in results if "baseline_error" in r)
    f_errors = sum(1 for r in results if "finetuned_error" in r)

    print(f"\n{'='*50}")
    print(f"Total: {total}")
    print(f"Baseline  — passed: {b_passed}/{total} | parse errors: {b_errors}")
    print(f"Finetuned — passed: {f_passed}/{total} | parse errors: {f_errors}")
    print(f"Delta: {f_passed - b_passed:+d}")

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nFull results written to {RESULTS_PATH}")


if __name__ == "__main__":
    run_eval()

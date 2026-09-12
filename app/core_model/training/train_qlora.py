"""
QLoRA fine-tuning for the Objective Resolution task (Core Model).

ASSUMPTIONS TO VERIFY BEFORE RUNNING — these will break the script if wrong:
1. MODEL_NAME must be the HF repo id for the safetensors weights, NOT the Ollama
   tag. Check model_manifest.json for the correct id and swap it in below.
2. build_prompt_completion() assumes app/core_model/prompts/objective_resolution.txt
   contains a `{objective}` placeholder you can .format() into. If the file uses a
   different placeholder name or structure, edit build_prompt_completion() to match
   it exactly — the model needs to train on the SAME prompt format it'll see at
   inference time, or the fine-tune won't transfer.
3. target_modules assumes a standard Llama/Qwen-style attention+MLP naming
   scheme. If model loading errors on "target module not found", print
   model.named_modules() and adjust the list.
"""

import json
import random
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

# --- CONFIG: verify against model_manifest.json before running ---
MODEL_NAME = "Qwen/Qwen3-4B-Instruct-2507"  # <-- CHECK model_manifest.json, this may be wrong

THIS_DIR = Path(__file__).parent
# sft_task1_final_v3.jsonl was the 412-record, agriculture-only pool that
# produced the regressed adapter — never point back at it.
# build_final_dataset.py now produces its own stratified train/val/test split
# (2,002/250/250 across all 6 domains) directly. Prefer those pre-split files
# over re-splitting here, since build_final_dataset.py's stratification is
# domain+category aware and this script's own stratified_split() below only
# knows about category. Fall back to splitting a merged pool only if the
# pre-split files aren't present (e.g. running against an older dataset).
TRAIN_PATH = THIS_DIR / "datasets" / "active" / "sft_task1_train.jsonl"
VAL_PATH = THIS_DIR / "datasets" / "active" / "sft_task1_val_clean.jsonl"
MERGED_FALLBACK_PATH = THIS_DIR / "datasets" / "active" / "sft_task1_merged_current.jsonl"
PROMPT_TEMPLATE_PATH = THIS_DIR.parent / "prompts" / "objective_resolution.txt"
OUTPUT_DIR = THIS_DIR / "checkpoints" / "objective_resolution_qlora"

SEED = 42
random.seed(SEED)


def load_records(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def stratified_split(records, train_frac=0.8, val_frac=0.1):
    """Split within each category so no split starves a category of examples."""
    by_cat = {}
    for r in records:
        by_cat.setdefault(r["category"], []).append(r)

    train, val, test = [], [], []
    for cat, items in by_cat.items():
        random.shuffle(items)
        n = len(items)
        n_train = int(n * train_frac)
        n_val = int(n * val_frac)
        train += items[:n_train]
        val += items[n_train : n_train + n_val]
        test += items[n_train + n_val :]
        print(f"  {cat}: {n} total -> train={n_train} val={n_val} test={n - n_train - n_val}")

    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)
    return train, val, test


def build_prompt_completion(rec, prompt_template):
    """Build a conversational prompt-completion pair, NOT a single rendered
    string. trl's SFTTrainer masks loss to the completion automatically when
    given this shape (completion_only_loss=True in SFTConfig below) — it
    determines the split from the dataset structure itself, not from
    string-matching a chat-template marker. This replaces an earlier attempt
    to do this with DataCollatorForCompletionOnlyLM, which trl has removed
    entirely from recent versions in favor of this dataset-shape approach.

    Do NOT pre-render this with tokenizer.apply_chat_template() — SFTTrainer
    applies the chat template itself when it sees separate prompt/completion
    message lists (pass the tokenizer as processing_class= below so it can).
    """
    user_prompt = prompt_template.format(objective=rec["objective"])
    assistant_response = json.dumps(rec["expected_output"])
    return {
        "prompt": [{"role": "user", "content": user_prompt}],
        "completion": [{"role": "assistant", "content": assistant_response}],
    }


def main():
    if TRAIN_PATH.exists() and VAL_PATH.exists():
        print(
            f"Loading pre-split train/val from {TRAIN_PATH.name} / {VAL_PATH.name} "
            f"(produced by build_final_dataset.py — not re-splitting here)."
        )
        train_recs = load_records(TRAIN_PATH)
        val_recs = load_records(VAL_PATH)
        print(f"train={len(train_recs)} val={len(val_recs)}\n")
    else:
        print(
            f"No pre-split files found at {TRAIN_PATH} — falling back to "
            f"loading {MERGED_FALLBACK_PATH.name} and splitting here."
        )
        if not MERGED_FALLBACK_PATH.exists():
            raise FileNotFoundError(
                f"Neither pre-split files ({TRAIN_PATH.name}/{VAL_PATH.name}) nor "
                f"the merged fallback ({MERGED_FALLBACK_PATH.name}) exist. Run "
                f"build_final_dataset.py first."
            )
        records = load_records(MERGED_FALLBACK_PATH)
        print(f"Loaded {len(records)} records\n")
        print("Stratified split by category:")
        train_recs, val_recs, test_recs = stratified_split(records)
        print(f"\nTotal: train={len(train_recs)} val={len(val_recs)} test={len(test_recs)}")

        # Save splits so evaluate.py can reuse the exact same test set later
        for name, recs in [("train", train_recs), ("val", val_recs), ("test", test_recs)]:
            out_path = MERGED_FALLBACK_PATH.parent / f"sft_task1_{name}.jsonl"
            with open(out_path, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(json.dumps(r) + "\n")
            print(f"Wrote {out_path}")

    # save_total_limit=2 only rotates checkpoints made WITHIN this run — it
    # will not clean up an adapter left over from a prior run (e.g. the
    # regressed v3 adapter). Never silently train into that same directory;
    # move it aside so it's still available to compare against if needed.
    if OUTPUT_DIR.exists():
        import shutil
        from datetime import datetime

        backup_dir = OUTPUT_DIR.parent / f"{OUTPUT_DIR.name}_prev_{datetime.now():%Y%m%d_%H%M%S}"
        print(
            f"Existing checkpoint dir found at {OUTPUT_DIR} — moving to {backup_dir} "
            f"before starting a new run."
        )
        shutil.move(str(OUTPUT_DIR), str(backup_dir))

    if not PROMPT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"{PROMPT_TEMPLATE_PATH} not found — training prompt format must match "
            f"inference-time prompt format, cannot proceed without it."
        )
    prompt_template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    print(f"\nLoading tokenizer + model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
    )
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    train_ds = Dataset.from_list([build_prompt_completion(r, prompt_template) for r in train_recs])
    val_ds = Dataset.from_list([build_prompt_completion(r, prompt_template) for r in val_recs])

    training_args = SFTConfig(
        output_dir=str(OUTPUT_DIR),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=3,
        learning_rate=2e-4,
        logging_steps=5,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        gradient_checkpointing=True,
        bf16=True,
        report_to="none",
        max_length=1024,  # was max_seq_length
        completion_only_loss=True,  # loss computed only on the target JSON, not the instruction prompt
        seed=SEED,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tokenizer,  # needed so trl can apply the chat template to prompt/completion itself
    )

    print("\nStarting training...")
    trainer.train()

    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print(f"\nDone. Adapter saved to {OUTPUT_DIR}")
    print(
        "Next: run evaluate.py against sft_task1_test.jsonl and compare to baseline eval numbers."
    )


if __name__ == "__main__":
    main()

bad_val = {58, 109, 119, 132, 138, 141, 229, 233}

def filter_file(in_path, out_path, bad_indices):
    kept = 0
    dropped = 0
    with open(in_path, encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as out:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            if i in bad_indices:
                dropped += 1
                continue
            out.write(line)
            kept += 1
    print(f"{in_path} -> {out_path}: kept {kept}, dropped {dropped}")

filter_file("app/core_model/training/datasets/sft_task1_val.jsonl",
            "app/core_model/training/datasets/sft_task1_val_clean.jsonl", bad_val)

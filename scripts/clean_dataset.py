import os
import json
import collections
import sys
from difflib import SequenceMatcher

def load_data(filepath):
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def save_data(filepath, records):
    with open(filepath, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

def validate_record(record, idx):
    expected_keys = {
        "target_phenotypes",
        "biological_processes",
        "desired_change",
        "relevant_concepts",
        "retrieval_targets",
        "ambiguity_status"
    }
    
    eo = record.get("expected_output")
    if not isinstance(eo, dict):
        return f"Line {idx+1}: expected_output is not a dict"
        
    keys = set(eo.keys())
    if keys != expected_keys:
        return f"Line {idx+1}: Keys mismatch. Expected {expected_keys}, got {keys}"
        
    # target_phenotypes: list[str] | None
    tp = eo.get("target_phenotypes")
    if tp is not None and (not isinstance(tp, list) or not all(isinstance(x, str) for x in tp)):
        return f"Line {idx+1}: target_phenotypes invalid type or content: {type(tp)}"
        
    # biological_processes: list[str] | None
    bp = eo.get("biological_processes")
    if bp is not None and (not isinstance(bp, list) or not all(isinstance(x, str) for x in bp)):
        return f"Line {idx+1}: biological_processes invalid type or content: {type(bp)}"
        
    # desired_change: str | None
    dc = eo.get("desired_change")
    if dc is not None and not isinstance(dc, str):
        return f"Line {idx+1}: desired_change invalid type: {type(dc)}"
        
    # relevant_concepts: list[str] | None
    rc = eo.get("relevant_concepts")
    if rc is not None and (not isinstance(rc, list) or not all(isinstance(x, str) for x in rc)):
        return f"Line {idx+1}: relevant_concepts invalid type or content: {type(rc)}"
        
    # retrieval_targets: list[str] | None
    rt = eo.get("retrieval_targets")
    if rt is not None and (not isinstance(rt, list) or not all(isinstance(x, str) for x in rt)):
        return f"Line {idx+1}: retrieval_targets invalid type or content: {type(rt)}"
        
    # ambiguity_status: "CLEAR" | "CLARIFICATION_REQUIRED"
    as_val = eo.get("ambiguity_status")
    if as_val not in ("CLEAR", "CLARIFICATION_REQUIRED"):
        return f"Line {idx+1}: ambiguity_status invalid value: {as_val}"
        
    return None

def main():
    # Fix console encoding for Windows output to handle Unicode characters (like beta) safely
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    input_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app', 'core_model', 'training', 'datasets', 'sft_task1_final.jsonl'))
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app', 'core_model', 'training', 'datasets', 'sft_task1_final_v2.jsonl'))
    
    print(f"Loading raw dataset from: {input_path}")
    records = load_data(input_path)
    print(f"Loaded {len(records)} records.")
    
    fixed_count = 0
    relabeled_count = 0
    
    # Step 1 & 2: Record fixes
    for i, r in enumerate(records):
        obj = r.get("objective", "")
        cat = r.get("category", "")
        
        # 1. OsMYB10 example in multi_goal_clear
        if "OsMYB10" in obj:
            print(f"\n[FIX 1] Found OsMYB10 record at line {i+1}.")
            # Restore expected_output
            r["expected_output"] = {
                "target_phenotypes": [
                    "higher anthocyanin concentration in seeds",
                    "improved seed pigmentation"
                ],
                "biological_processes": [
                    "flavonoid biosynthesis",
                    "seed-specific gene expression"
                ],
                "desired_change": "2-fold increase in seed anthocyanin levels",
                "relevant_concepts": [
                    "OsMYB10 gene function",
                    "synthetic promoters in rice",
                    "anthocyanin biosynthesis pathway"
                ],
                "retrieval_targets": [
                    "OsMYB10 expression in rice seeds",
                    "synthetic promoter driving OsMYB10",
                    "flavonoid biosynthesis pathway in rice"
                ],
                "ambiguity_status": "CLEAR"
            }
            fixed_count += 1
            print("Successfully updated OsMYB10 expected_output structure and ambiguity_status.")
            
        # 2. Category/label contradiction (Bt cotton)
        if "Design a gene drive system to spread a trait for reduced pesticide sensitivity in Bt cotton populations." in obj:
            print(f"\n[FIX 2] Found Bt cotton contradiction record at line {i+1}.")
            eo = r.get("expected_output", {})
            eo["ambiguity_status"] = "CLEAR"
            relabeled_count += 1
            print("Successfully relabeled ambiguity_status to CLEAR.")
            
    # Step 3: Fuzzy similarity dedup
    print("\n[DEDUP] Starting fuzzy similarity deduplication...")
    deduped_records = []
    removed_counts = collections.defaultdict(int)
    clusters_by_category = collections.defaultdict(list) # category -> list of clusters (each is list of records)
    
    for idx, r in enumerate(records):
        cat = r.get("category")
        obj = r.get("objective", "")
        
        # Find matching cluster
        found_cluster = None
        for cluster in clusters_by_category[cat]:
            rep_r = cluster[0]
            rep_obj = rep_r.get("objective", "")
            
            # Match condition: SequenceMatcher ratio > 0.85 OR first 50 chars match exactly
            if (len(obj) >= 50 and len(rep_obj) >= 50 and obj[:50] == rep_obj[:50]) or \
               SequenceMatcher(None, obj, rep_obj).ratio() > 0.85:
                found_cluster = cluster
                break
                
        if found_cluster is not None:
            # We already have a representative for this cluster, so discard it
            removed_counts[cat] += 1
        else:
            # First of its kind, create a new cluster and keep this record
            clusters_by_category[cat].append([r])
            deduped_records.append(r)
            
    print("Deduplication Summary:")
    total_removed = 0
    for cat, count in removed_counts.items():
        print(f"  Category '{cat}': Removed {count} near-duplicates")
        total_removed += count
    print(f"Total near-duplicates removed: {total_removed}")
    
    # Step 4: Schema validation pass on final output records
    print("\n[VALIDATION] Performing schema validation pass on output records...")
    validation_failures = 0
    for i, r in enumerate(deduped_records):
        error_msg = validate_record(r, i)
        if error_msg:
            print(f"!!! SCHEMA FAILURE: {error_msg}")
            validation_failures += 1
            
    if validation_failures == 0:
        print("Schema validation passed! 0 errors detected.")
    else:
        print(f"Schema validation FAILED with {validation_failures} errors! Check output logs.")
        
    # Save the output file
    print(f"\nSaving cleaned dataset to: {output_path}")
    save_data(output_path, deduped_records)
    print(f"Successfully wrote {len(deduped_records)} records to {os.path.basename(output_path)}")
    
    # Final overall summary
    print("\n" + "="*40)
    print("CLEANING WORKFLOW RUN COMPLETED")
    print(f"Total input records: {len(records)}")
    print(f"Records fixed: {fixed_count}")
    print(f"Records relabeled: {relabeled_count}")
    print(f"Duplicates removed: {total_removed}")
    print(f"Validation failures flagged: {validation_failures}")
    print(f"Total output records: {len(deduped_records)}")
    print("="*40)

if __name__ == '__main__':
    main()

"""
direction_ambiguous_generator.py, patched again: fixes the still-live
mid-sentence capitalization bug (verb.capitalize() applied unconditionally
even though 2 of 5 templates don't put the verb sentence-first). Verified
against the uploaded domain files: 41-49% of records had a mid-sentence
capital before this fix.

Fix: render with the LOWERCASE verb, then capitalize only the first
character of the whole rendered sentence. Everything else (trait
interpolation fix, dedup guard, lockstep-walk fix) is unchanged from the
version already confirmed working (125/125 unique on all 6 domains).
"""
import json
import random
from itertools import product

DIRECTIONAL_VERBS = ["increase","decrease","improve","reduce","enhance","boost","lower","raise","strengthen","diminish"]
NON_DIRECTIONAL_VERBS = ["modify","alter","adjust","optimize","change","tune","engineer","regulate","influence","shift"]

TEMPLATES = [
    "{verb} the {parameter} linked to {trait} in {species}.",
    "{verb} {species_short}'s {parameter} tied to {trait}.",
    "we want to {verb} the {parameter} associated with {trait} in {species}.",
    "{verb} the {parameter} in the {trait} pathway of {species}.",
    "please {verb} {species_short}'s {parameter} related to {trait}.",
]

def _species_short(species_entry):
    if "(" in species_entry and species_entry.endswith(")"):
        return species_entry.rsplit("(", 1)[1][:-1]
    return species_entry

def _null_output():
    return {"target_phenotypes": None, "biological_processes": None, "desired_change": None,
            "relevant_concepts": None, "retrieval_targets": None, "ambiguity_status": "CLARIFICATION_REQUIRED"}

def _combo_pool(domain_config):
    species_list = domain_config["species"]
    params = domain_config["ambiguous_parameters"]
    traits = domain_config["genes_traits"] + domain_config["phenotypes"]
    pool = list(product(TEMPLATES, species_list, params, traits))
    random.shuffle(pool)
    return pool

def _render(template, verb, species, parameter, trait):
    text = template.format(verb=verb, species=species, species_short=_species_short(species),
                            parameter=parameter, trait=trait)
    return text[0].upper() + text[1:] if text else text

def generate_direction_ambiguous(domain_config, n, seed=None):
    if seed is not None:
        random.seed(seed)
    pool = _combo_pool(domain_config)
    capacity = len(pool) * len(NON_DIRECTIONAL_VERBS)
    if n > capacity:
        raise ValueError(f"Requested {n} but capacity is only {capacity}.")
    records, seen = [], set()
    combo_idx = verb_idx = draws = 0
    verb_cycle = list(NON_DIRECTIONAL_VERBS); random.shuffle(verb_cycle)
    max_draws = capacity * 3
    while len(records) < n:
        draws += 1
        if draws > max_draws:
            raise RuntimeError(f"Could not draw {n} unique renders after {max_draws} attempts.")
        template, species, parameter, trait = pool[combo_idx % len(pool)]; combo_idx += 1
        verb = verb_cycle[verb_idx % len(verb_cycle)]; verb_idx += 1
        objective_text = _render(template, verb, species, parameter, trait)
        if objective_text in seen:
            continue
        seen.add(objective_text)
        records.append({"objective": objective_text, "expected_output": _null_output(), "category": "direction_ambiguous"})
    return records

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/mnt/user-data/uploads")
    from domain_configs import DOMAINS, DEFAULT_CATEGORY_TARGETS
    import re

    for domain in sorted(DOMAINS):
        recs = generate_direction_ambiguous(DOMAINS[domain], 125, seed=42)
        objs = [r["objective"] for r in recs]
        caps_issues = sum(1 for o in objs if re.search(r'\b(want to|Please|please) [A-Z][a-z]+', o))
        print(f"{domain}: {len(objs)} generated, {len(set(objs))} unique, mid-sentence-caps issues: {caps_issues}")
        with open(f"direction_ambiguous_{domain}_v2.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

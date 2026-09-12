"""
Loads the base Qwen3-4B-Instruct-2507 model with the QLoRA adapter attached,
for running inference with the fine-tuned Objective Resolution model.

This does NOT merge LoRA weights into a single checkpoint on disk. Merging
into a 4-bit (bitsandbytes) quantized base isn't a clean algebraic operation
without dequantizing first, and you don't need a merged checkpoint to
evaluate correctness — loading the 4-bit base once and keeping the adapter
active during generation is functionally equivalent for this purpose. A real
merge-and-export step can be added later if you need a single deployable
checkpoint; it is not required to answer "did fine-tuning help."

BASE_MODEL_NAME below MUST stay in sync with MODEL_NAME in train_qlora.py —
if you change one, change both. There's no shared constant between them
right now; that's a real drift risk if either file gets edited later.
"""

import torch
from pathlib import Path

from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

BASE_MODEL_NAME = "Qwen/Qwen3-4B-Instruct-2507"  # must match train_qlora.py's MODEL_NAME
from app.config import settings
_LOCAL_ADAPTER_DIR = Path(__file__).parent / "checkpoints" / "objective_resolution_qlora"
ADAPTER_SOURCE = str(_LOCAL_ADAPTER_DIR) if _LOCAL_ADAPTER_DIR.exists() else settings.adapter_repo_id

_model = None
_tokenizer = None


def _load() -> tuple[PeftModel, AutoTokenizer]:
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer



    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    print(f"Loading base model {BASE_MODEL_NAME} in 4-bit...")
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
    )

    print(f"Attaching adapter from {ADAPTER_SOURCE}...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_SOURCE)
    model.eval()

    # Load the tokenizer FROM THE ADAPTER DIR, not the base repo. train_qlora.py
    # saved the tokenizer alongside the adapter, and training logged a PAD/BOS/EOS
    # token adjustment ("pad_token_id: 151643") — reloading a fresh tokenizer from
    # the base model could silently mismatch what the model actually trained on.
    tokenizer = AutoTokenizer.from_pretrained(ADAPTER_SOURCE)

    _model, _tokenizer = model, tokenizer
    return _model, _tokenizer


def generate(prompt: str, max_new_tokens: int = 512) -> str:
    """Generate a completion from the fine-tuned (base + adapter) model.

    `prompt` is the fully-formatted user prompt (same string objective_parser.py
    builds from objective_resolution.txt) — this wraps it in the same chat
    template used at training time, with add_generation_prompt=True so the
    model completes the assistant turn instead of being shown it.
    """
    model, tokenizer = _load()

    messages = [{"role": "user", "content": prompt}]
    input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,  # deterministic — you're checking correctness, not creativity
            pad_token_id=tokenizer.pad_token_id,
        )

    generated_tokens = output_ids[0][inputs["input_ids"].shape[1] :]
    return tokenizer.decode(generated_tokens, skip_special_tokens=True)
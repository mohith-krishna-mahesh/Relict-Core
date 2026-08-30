"""NOT used or tested for tonight's eval. Needs a GGUF export that doesn't
exist in this repo. Included only so the ModelClient interface has a name
for it; do not wire this in under time pressure."""

from pathlib import Path
from llama_cpp import Llama
from app.core_model.inference.base import ModelClient


class LlamaCppClient(ModelClient):
    def __init__(self, model_path: str, n_ctx: int = 4096, n_gpu_layers: int = -1):
        if not Path(model_path).exists():
            raise FileNotFoundError(f"GGUF model not found at {model_path}")
        self._llm = Llama(
            model_path=model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers, verbose=False
        )

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        result = self._llm(prompt, max_tokens=max_tokens, echo=False)
        return result["choices"][0]["text"]

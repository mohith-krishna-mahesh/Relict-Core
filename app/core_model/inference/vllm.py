"""NOT used or tested for tonight's eval. vLLM needs its own server process
and GPU memory reservation — don't spin this up alongside your training/eval
scripts under deadline pressure. Included for interface completeness only."""

from vllm import LLM, SamplingParams
from app.core_model.inference.base import ModelClient


class VLLMClient(ModelClient):
    def __init__(self, model_name: str, **engine_kwargs):
        self._llm = LLM(model=model_name, **engine_kwargs)

    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.0) -> str:
        params = SamplingParams(max_tokens=max_tokens, temperature=temperature)
        outputs = self._llm.generate([prompt], params)
        return outputs[0].outputs[0].text
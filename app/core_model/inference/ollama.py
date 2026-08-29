from typing import Any
import ollama

MODEL_NAME = "qwen3:4b-instruct"


def generate(prompt: str, model: str = MODEL_NAME) -> str:
    response: Any = ollama.generate(model=model, prompt=prompt, stream=False)  # type: ignore
    return str(response["response"])
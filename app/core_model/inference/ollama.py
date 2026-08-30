from typing import Any

MODEL_NAME = "qwen3:4b-instruct"


def generate(prompt: str, model: str = MODEL_NAME, temperature: float = 0.0) -> str:
    try:
        import ollama
    except ImportError as e:
        raise RuntimeError("ollama package is not installed.") from e

    response: Any = ollama.generate(
        model=model, prompt=prompt, stream=False, options={"temperature": temperature}
    )  # type: ignore
    return str(response["response"])

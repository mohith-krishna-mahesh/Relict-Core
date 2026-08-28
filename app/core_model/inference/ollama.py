import ollama

MODEL_NAME = "qwen3:4b-instruct"


def generate(prompt: str, model: str = MODEL_NAME) -> str:
    response = ollama.generate(model=model, prompt=prompt, stream=False)
    return response["response"]
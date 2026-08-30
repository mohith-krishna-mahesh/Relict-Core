import ollama

MODEL_NAME = "qwen3:4b-instruct"

# ollama.py
def generate(prompt: str, model: str = MODEL_NAME, temperature: float = 0.0) -> str:
    response = ollama.generate(model=model, prompt=prompt, stream=False, options={"temperature": temperature})
    return response["response"]
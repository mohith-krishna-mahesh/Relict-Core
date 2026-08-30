"""
Provider-agnostic interface for the Core Model.

Each concrete client (Ollama, llama.cpp, vLLM, or the local PEFT-adapter
client in merge_adapter.py) implements generate(prompt) -> str. Code that
needs a completion should depend on this interface, not import a specific
provider directly, except at the one place a client is constructed.
"""

from abc import ABC, abstractmethod


class ModelClient(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return the raw text completion for a given prompt."""
        raise NotImplementedError

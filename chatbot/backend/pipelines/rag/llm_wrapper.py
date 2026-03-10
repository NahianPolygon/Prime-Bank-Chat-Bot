"""
Shared LLM wrapper for Ollama API calls.
"""

import os
import re
import requests
from typing import Dict, Any


class OllamaLLM:
    """Wrapper for Ollama API with timeout and error handling."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # Use environment variable if set (for Docker), otherwise use config
        self.base_url = os.getenv("OLLAMA_HOST", config["base_url"]).rstrip("/")
        self.model = config["model_name"]
        self.timeout = config.get("timeout", 120)
        self.temp = config.get("temperature", 0.3)
        self.top_p = config.get("top_p", 0.9)

        if not self._ping():
            raise RuntimeError(
                f"Ollama not available at {self.base_url}. Run: ollama serve"
            )
        print(f"✓ Connected to Ollama at {self.base_url}")

    def _ping(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/api/tags", timeout=5).status_code == 200
        except Exception:
            return False

    def generate(
        self, prompt: str, temperature: float = None, max_tokens: int = 800
    ) -> str:
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature if temperature is not None else self.temp,
                        "top_p": self.top_p,
                        "num_predict": max_tokens,
                    },
                    "think": False,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            return _clean(text)
        except requests.Timeout:
            raise RuntimeError("Ollama timeout")
        except Exception as e:
            raise RuntimeError(f"Ollama error: {e}")


def _clean(text: str) -> str:
    """Strip <think> blocks and leaked template labels."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"\*\*\[.*?\]\*\*\s*\n?", "", text)
    text = re.sub(r"\[[^\]]*[—\-][^\]]*\]\s*\n?", "", text)
    text = re.sub(
        r"\[(Opening|Closing|Instructions?|Rules?)[^\]]*\]\s*\n?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^\s*---\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

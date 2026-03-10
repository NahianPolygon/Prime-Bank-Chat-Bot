"""
Ollama API utilities for LLM interactions.
Provides simple wrappers for calling Ollama and parsing JSON responses.
"""

import os
import json
import re
import requests
from typing import Optional, Dict, Any


def ollama_chat(
    system: str,
    user: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    """
    Call Ollama API with system and user prompts.
    
    Args:
        system: System prompt/instructions
        user: User message/query
        temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
        max_tokens: Maximum tokens in response
        
    Returns:
        Raw response text from Ollama
        
    Raises:
        RuntimeError: If Ollama is unavailable or request fails
    """
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_k_m")
    
    # Format prompt with system instructions
    prompt = f"{system}\n\n{user}"
    
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": 0.9,
                    "num_predict": max_tokens,
                },
            },
            timeout=180,
        )
        response.raise_for_status()
        
        result = response.json().get("response", "").strip()
        return _clean_response(result)
        
    except requests.Timeout:
        raise RuntimeError(f"Ollama timeout at {ollama_host}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"Cannot connect to Ollama at {ollama_host}")
    except requests.RequestException as e:
        raise RuntimeError(f"Ollama error: {e}")
    except Exception as e:
        raise RuntimeError(f"Ollama request failed: {e}")


def parse_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract and parse JSON from text.
    
    Attempts to find and parse JSON object from the given text.
    Handles cases where JSON is embedded in other text.
    
    Args:
        text: Text potentially containing JSON
        
    Returns:
        Parsed JSON as dict, or None if no valid JSON found
    """
    if not text:
        return None
    
    # Try to find JSON object in the text
    # Look for content between { and }
    matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    # If no match found, try parsing the entire text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _clean_response(text: str) -> str:
    """
    Clean LLM output by removing model thinking markers and formatting artifacts.
    
    Args:
        text: Raw LLM response
        
    Returns:
        Cleaned text
    """
    # Remove <think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    
    # Remove template labels
    text = re.sub(r"\*\*\[.*?\]\*\*\s*\n?", "", text)
    text = re.sub(r"\[[^\]]*[—\-][^\]]*\]\s*\n?", "", text)
    text = re.sub(
        r"\[(Opening|Closing|Instructions?|Rules?)[^\]]*\]\s*\n?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    
    # Remove standalone dashes
    text = re.sub(r"^\s*---\s*$", "", text, flags=re.MULTILINE)
    
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text.strip()


__all__ = ["ollama_chat", "parse_json"]

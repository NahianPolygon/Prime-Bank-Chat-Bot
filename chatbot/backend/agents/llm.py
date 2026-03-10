"""
LLM configuration for CrewAI agents using Ollama.
"""

import os
from crewai import LLM


def get_ollama_llm():
    """
    Create and return an Ollama LLM instance compatible with CrewAI.
    
    Uses CrewAI's LLM class with Ollama backend for proper integration.
    
    Configuration:
    - Model: qwen2.5:7b-instruct-q4_k_m (7 billion parameter model)
    - Host: From OLLAMA_HOST env var or http://192.168.12.41:11434
    - Temperature: 0.3 (low variance for consistent outputs)
    
    Returns:
        LLM: Configured LLM instance for use in CrewAI agents
    """
    ollama_host = os.getenv("OLLAMA_HOST", "http://192.168.12.41:11434")
    ollama_host = ollama_host.rstrip("/")
    
    # Use CrewAI's LLM class with Ollama model format
    return LLM(
        model="ollama/qwen2.5:7b-instruct-q4_k_m",
        base_url=ollama_host,
        temperature=0.3,
    )


__all__ = ["get_ollama_llm"]

"""Agents module for bank chatbot."""

from .llm import get_ollama_llm
from .retriever import product_retriever_agent
from .eligibility import eligibility_analyzer_agent
from .comparator import feature_comparator_agent
from .formatter import response_formatter_agent
from .recommender import alternative_product_recommender_agent

# Note: existing_cardholder_agent is imported lazily in orchestrator
# due to potential import issues; we don't import it here

__all__ = [
    "get_ollama_llm",
    "product_retriever_agent",
    "eligibility_analyzer_agent",
    "feature_comparator_agent",
    "response_formatter_agent",
    "alternative_product_recommender_agent",
]


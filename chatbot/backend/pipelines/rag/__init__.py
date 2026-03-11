"""RAG (Retrieval Augmented Generation) pipeline."""

from .search import rag_search_tool, rag_search_impl, initialize_rag_tool, NO_PRODUCTS_SENTINEL
from .retrieval import DynamicRAGPipeline
from .llm_wrapper import OllamaLLM

RAGPipeline = DynamicRAGPipeline

__all__ = [
    "rag_search_tool",
    "rag_search_impl",
    "initialize_rag_tool",
    "NO_PRODUCTS_SENTINEL",
    "RAGPipeline",
    "DynamicRAGPipeline",
    "OllamaLLM",
]

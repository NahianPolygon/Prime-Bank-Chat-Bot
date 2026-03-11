"""
Pipelines Module.
Contains RAG and CrewAI pipelines for processing queries.
"""

from .rag import DynamicRAGPipeline, initialize_rag_tool, rag_search_tool
from .crew import CrewPipeline

RAGPipeline = DynamicRAGPipeline

__all__ = ['CrewPipeline', 'RAGPipeline', 'DynamicRAGPipeline', 'initialize_rag_tool', 'rag_search_tool']

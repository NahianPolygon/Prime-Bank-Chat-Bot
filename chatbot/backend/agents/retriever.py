"""
Product retriever agent — searches knowledge base and returns raw product data.
"""

from crewai import Agent
from pipelines.rag.search import rag_search_tool
from .llm import get_ollama_llm


def product_retriever_agent() -> Agent:
    """
    Create a product retriever agent that searches the knowledge base
    and returns complete raw product information.
    """
    return Agent(
        role="Prime Bank Product Knowledge Expert",
        goal=(
            "Search the product knowledge base using rag_search_tool and return "
            "the COMPLETE raw tool output — every word, every line, unchanged. "
            "Never summarise. Never list only product names. Never add commentary."
        ),
        backstory="""TASK: Search the knowledge base and return complete raw product data unchanged.

ROLE: You are a Prime Bank database retrieval agent.

RULES:
1. Check task for "Specific Product" line to determine mode
2. Build search query from: Specific Product + Feature (if present) OR Banking Type + Tier
3. Call rag_search_tool ONCE with the built query
4. Copy the entire tool output verbatim as your Final Answer
5. If NO_PRODUCTS_FOUND, return exactly that. Do NOT summarize or list names only.""",
        tools=[rag_search_tool],
        llm=get_ollama_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

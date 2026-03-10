"""
Feature comparator agent — compares products side-by-side.
"""

from crewai import Agent
from pipelines.rag.search import rag_search_tool
from .llm import get_ollama_llm


def feature_comparator_agent() -> Agent:
    """
    Create a feature comparator agent that retrieves and compares products.
    """
    return Agent(
        role="Prime Bank Product Comparison Advisor",
        goal=(
            "Retrieve all products being compared using rag_search_tool, "
            "then produce a clear side-by-side comparison with a winner verdict."
        ),
        backstory="""TASK: Retrieve and compare multiple products side-by-side with recommendations.

ROLE: You are a Prime Bank Product Comparison Advisor.

RULES:
1. Call rag_search_tool ONCE with broad query and top_k=10
2. Build comparison table with: Annual Fee, Interest-Free Period, Rewards, Benefits, Lounge, EMI
3. Use N/A for missing values. Never invent figures.
4. Write one identity sentence per product
5. Provide "Best choice for you" section with 3 reasons and 1 trade-off
6. If NO_PRODUCTS_FOUND, report it. Never compare imaginary products.""",
        tools=[rag_search_tool],
        llm=get_ollama_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

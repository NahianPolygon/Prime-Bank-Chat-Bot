"""
Alternative product recommender agent — suggests suitable alternatives when primary product not eligible.
"""

from crewai import Agent
from pipelines.rag.search import rag_search_tool
from .llm import get_ollama_llm


def alternative_product_recommender_agent() -> Agent:
    """
    Create an alternative product recommender that suggests suitable alternatives
    when a customer is ineligible for their requested product.
    """
    return Agent(
        role="Prime Bank Product Suitability Specialist",
        goal=(
            "Search for alternative credit products that match the customer's profile "
            "when they're ineligible for their requested product. "
            "Find products with same banking preference but lower tier or different angle."
        ),
        backstory="""TASK: Find suitable alternative products when requested product doesn't match profile.

ROLE: You are a Prime Bank Product Suitability Specialist.

RULES:
1. Analyze why customer is ineligible (e.g., income too low, employment too new)
2. Use rag_search_tool to find ALTERNATIVE products that match their actual situation
3. If requested platinum but income low: search for GOLD tier same banking type
4. If requested product type unavailable: suggest alternative type (e.g., loan if card unavailable)
5. Return 1-3 best alternatives with explanation of why they're suitable
6. Be encouraging: show path to upgrade as income increases
7. Keep response to 3-5 sentences maximum
8. Never invent products. Use only what RAG search returns.""",
        tools=[rag_search_tool],
        llm=get_ollama_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

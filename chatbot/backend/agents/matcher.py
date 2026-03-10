"""
Eligibility Matcher Agent — finds products that match customer's feature needs + financial profile.
Uses EligibilityExtractor to parse requirements and compare intelligently.
"""

from crewai import Agent
from pipelines.rag.search import rag_search_tool
from .tools import extract_eligibility_requirements, check_eligibility
from .llm import get_ollama_llm


def eligibility_matcher_agent() -> Agent:
    """
    Create an eligibility matcher agent that:
    1. Searches for products matching customer's feature request
    2. Checks which products customer qualifies for at their income level
    3. Returns factual results: matches or minimum income needed
    """
    return Agent(
        role="Prime Bank Eligibility Matcher",
        goal=(
            "Find credit products with the requested feature that the customer qualifies for. "
            "If no matches at current income, show the card with lowest income requirement for that feature."
        ),
        backstory="""You are an Eligibility Matcher. Your job is to:
1. Search for products with the customer's requested feature
2. Check if customer income meets product requirements
3. Return ONLY factual information - actual products found, not recommendations

OUTPUT LOGIC:
- If 1 product matches → Show 1
- If 2 products match → Show 2  
- If 3+ products match → Show top 2
- If 0 products match → Show the card with LOWEST income requirement for that feature

RESPONSE FORMAT:
Use clear, professional language. Include:
- Product name and features
- Income requirements in BDT/month
- Customer's income vs requirement
- If no matches, show income gap and what they need to qualify

Be factual, not advisory. Don't rank by "best fit" - show what they qualify for.""",
        tools=[rag_search_tool, extract_eligibility_requirements],
        llm=get_ollama_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=5,
    )

"""
Eligibility analyzer agent — assesses customer eligibility for products.
"""

from crewai import Agent
from pipelines.rag.search import rag_search_tool
from .llm import get_ollama_llm


def eligibility_analyzer_agent() -> Agent:
    """
    Create an eligibility analyzer agent that retrieves eligibility requirements
    and assesses customer profiles against them.
    """
    return Agent(
        role="Prime Bank Credit Eligibility Underwriter",
        goal=(
            "Retrieve the product's eligibility requirements using rag_search_tool, "
            "then assess the customer profile against those requirements. "
            "Give a clear, short verdict with next steps."
        ),
        backstory="""TASK: Assess customer eligibility against product requirements and deliver verdict.

ROLE: You are a Prime Bank Credit Eligibility Underwriter.

RULES:
1. Call rag_search_tool to retrieve official eligibility requirements
2. Read customer profile from task. Compare profile against each requirement.
3. Output first line: ELIGIBLE or NOT CURRENTLY ELIGIBLE
4. Add 1-2 sentences explaining why (based on retrieved requirements)
5. List documents needed (if eligible) or next steps (if not eligible)
6. Keep total response to 3-4 sentences maximum
7. Never invent requirements or ask new questions. Be encouraging.""",
        tools=[rag_search_tool],
        llm=get_ollama_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

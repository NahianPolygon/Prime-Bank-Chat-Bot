"""
Eligibility Matching Crew — orchestrates the eligibility matching workflow.
Takes customer profile + feature request, returns ranked matching products.
"""

from crewai import Crew
from agents.matcher import eligibility_matcher_agent
from agents.tasks.eligibility_matching import create_eligibility_matching_task
from pipelines.rag.feature_expansion import expand_feature_query


def create_eligibility_matching_crew(
    customer_age: int,
    customer_annual_income: float,
    customer_tenure_months: int,
    requested_feature: str,
) -> Crew:
    """
    Create a crew for finding matching credit products based on customer profile.
    
    Args:
        customer_age: Age in years
        customer_annual_income: Annual income in BDT
        customer_tenure_months: Banking tenure in months
        requested_feature: Feature requested (e.g., "lounge_access", "airport_benefits")
    
    Returns:
        Crew configured with matcher agent and task
    """
    task = create_eligibility_matching_task(
        customer_age=customer_age,
        customer_annual_income=customer_annual_income,
        customer_tenure_months=customer_tenure_months,
        requested_feature=requested_feature,
    )
    
    crew = Crew(
        agents=[eligibility_matcher_agent()],
        tasks=[task],
        verbose=False,
        max_iter=5,
    )
    
    return crew


def run_eligibility_matching(
    customer_age: int,
    customer_annual_income: float,
    customer_tenure_months: int,
    requested_feature: str,
    banking_type: str = "",
) -> dict:
    """
    Run eligibility matching workflow.
    
    Args:
        customer_age: Age in years
        customer_annual_income: Annual income in BDT
        customer_tenure_months: Banking tenure in months
        requested_feature: Feature requested (e.g., "travel", "dining", "rewards")
        banking_type: "conventional" or "islamic" or "" (optional for feature expansion)
    
    Returns:
        Dictionary with:
        - result: String with ranked products and eligibility analysis
        - matching_products: List of dicts with product info and fit level
    """
    # Expand feature to RAG-optimized keywords (e.g., "travel" → "lounge airport flight booking")
    expanded_feature = expand_feature_query(
        [requested_feature],
        banking_type=banking_type if banking_type else None,
    )
    
    # If expansion returns keywords, use expanded version for search; otherwise use original
    search_feature = expanded_feature if expanded_feature else requested_feature
    
    crew = create_eligibility_matching_crew(
        customer_age=customer_age,
        customer_annual_income=customer_annual_income,
        customer_tenure_months=customer_tenure_months,
        requested_feature=search_feature,
    )
    
    result = crew.kickoff(inputs={})
    
    return {
        "result": str(result),
        "customer_profile": {
            "age": customer_age,
            "annual_income": customer_annual_income,
            "tenure_months": customer_tenure_months,
        },
        "requested_feature": requested_feature,
    }

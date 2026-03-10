"""
Eligibility Matching Task — finds credit products matching customer needs.
Input: Customer profile (age, income, tenure) + feature request
Output: Ranked products with eligibility analysis (best fit first)
"""

from crewai import Task
from agents.matcher import eligibility_matcher_agent


def create_eligibility_matching_task(
    customer_age: int,
    customer_annual_income: float,
    customer_tenure_months: int,
    requested_feature: str,
) -> Task:
    """
    Create an eligibility matching task that shows cards matching customer's criteria.
    
    Args:
        customer_age: Age in years
        customer_annual_income: Annual income in BDT
        customer_tenure_months: Banking tenure in months
        requested_feature: Feature requested (e.g., "lounge_access", "airport_benefits")
    
    Returns:
        Task for finding products matching customer criteria
    """
    customer_monthly_income = customer_annual_income / 12
    
    description = f"""Find credit cards with {requested_feature} that match this customer's income:

CUSTOMER CRITERIA:
- Monthly Income: BDT {customer_monthly_income:,.0f}
- Annual Income: BDT {customer_annual_income:,.0f}
- Requested Feature: {requested_feature}

LOGIC:
- 1 product qualifies → Show 1
- 2 products qualify → Show 2
- 3+ products qualify → Show top 2
- 0 products qualify → Show card with LOWEST income requirement for that feature

TASK:
1. Search for products with '{requested_feature}'
2. Extract income requirement for each
3. Check which ones customer qualifies for
4. Return:
   - If 1 qualifies: Show 1 product they can apply for
   - If 2 qualify: Show 2 products they can apply for
   - If 3+ qualify: Show top 2 products
   - If none qualify: Show card with LOWEST income requirement + income gap

For each product show:
- Product name and feature
- Minimum monthly income requirement
- Income gap if any (in BDT/month)

CRITICAL: Factual only. Show what they found, not predictions."""

    return Task(
        description=description,
        expected_output=(
            "Cards matching customer's feature request:\n"
            "- If 1 product qualifies: Show 1 product\n"
            "- If 2 products qualify: Show 2 products\n"
            "- If 3+ products qualify: Show top 2 products\n"
            "- If 0 products qualify: Show card with LOWEST income requirement + gap\n"
            "- For each: name, income requirement (BDT/month), income gap if any\n"
        ),
        agent=eligibility_matcher_agent(),
        tools=[],  # Agent has its own tools
    )

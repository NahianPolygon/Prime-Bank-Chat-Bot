"""
Eligibility analysis task — instructs eligibility agent to assess customer fit.
"""

from crewai import Task


def analyze_eligibility_task(
    agent,
    customer_profile: str,
    product_info: str,
) -> Task:
    """
    Create a task that instructs the eligibility agent to assess whether
    a customer qualifies for a product based on retrieved requirements.
    """
    return Task(
        description=(
            f"TASK: Assess customer eligibility against product requirements.\n\n"
            f"CUSTOMER PROFILE:\n{customer_profile}\n\n"
            f"PRODUCT INFORMATION:\n{product_info}\n\n"
            f"RULES:\n"
            f"1. Retrieve official eligibility requirements\n"
            f"2. Compare customer profile against each requirement\n"
            f"3. Output verdict on first line: ELIGIBLE or NOT CURRENTLY ELIGIBLE\n"
            f"4. Then 1-2 sentences explanation with documents/next steps\n"
            f"5. Keep total to 3-4 sentences. Be encouraging."
        ),
        expected_output=(
            "First line: ELIGIBLE or NOT CURRENTLY ELIGIBLE\n"
            "Next 1-2 sentences: explanation based on requirements and profile\n"
            "Next line: documents needed (if eligible) or steps to qualify (if not)\n"
            "Keep total response to 3-4 sentences."
        ),
        agent=agent,
    )

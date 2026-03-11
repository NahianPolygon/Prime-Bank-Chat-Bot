"""
Alternative product recommendation task — instructs agent to suggest suitable alternatives.
"""

from crewai import Task


def recommend_alternatives_task(
    agent,
    customer_profile: str,
    requested_product: str,
    ineligibility_reason: str,
    retrieved_products: str = None,
) -> Task:
    """
    Create a task that instructs the recommender agent to find suitable alternative
    products based on the customer's actual profile and why they were ineligible.
    
    Args:
        agent: The recommender agent
        customer_profile: Customer's financial/demographic profile
        requested_product: The product they wanted
        ineligibility_reason: Why they were ineligible
        retrieved_products: ACTUAL product data from Chroma DB (RAG results) - REQUIRED
    """
    
    # If retrieved products provided, constrain alternatives to only those products
    constraint_msg = ""
    if retrieved_products:
        constraint_msg = (
            f"\n\nACTUAL PRODUCTS AVAILABLE (from Prime Bank knowledge base):\n"
            f"{retrieved_products}\n\n"
            f"!!!CRITICAL!!!\n"
            f"- You MUST recommend ONLY from the products listed above\n"
            f"- Do NOT invent products like HSBC, Standard Chartered, etc.\n"
            f"- Use ONLY the products shown in the section above\n"
            f"- Each product MUST be listed ONCE only (no duplicates)\n"
            f"- If no suitable product exists, explain why"
        )
    else:
        constraint_msg = (
            "\n\nWARNING: No product data available. "
            "Recommend checking with the bank for available options."
        )
    
    return Task(
        description=(
            f"TASK: Find suitable alternative products for this customer.\n\n"
            f"CUSTOMER PROFILE:\n{customer_profile}\n\n"
            f"ORIGINALLY REQUESTED:\n{requested_product}\n\n"
            f"INELIGIBILITY REASON:\n{ineligibility_reason}\n\n"
            f"RULES:\n"
            f"1. Analyze the customer's actual situation (income, employment, age)\n"
            f"2. Find alternative products that MATCH their actual profile\n"
            f"3. If Platinum requested but income low: suggest GOLD tier in same banking type\n"
            f"4. Return 1-3 suitable alternatives with clear explanation\n"
            f"5. Each product in the list should appear EXACTLY ONCE (no repeats)\n"
            f"6. Show why these alternatives work and path to upgrade\n"
            f"7. Be encouraging and practical\n"
            f"{constraint_msg}"
        ),
        expected_output=(
            "List of 1-3 suitable alternative products (each product name appears ONCE ONLY)\n"
            "For each: product name, key features, and why it's suitable\n"
            "Only recommend products from the available list above\n"
            "Encouraging note about path to upgrade as situation improves\n"
            "Keep response warm and practical (3-5 sentences per alternative)"
        ),
        agent=agent,
    )

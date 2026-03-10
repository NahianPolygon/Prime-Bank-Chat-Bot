"""
Product retrieval task — instructs retriever agent to search the knowledge base.
"""

from crewai import Task


def retrieve_products_task(
    agent,
    search_context: str,
) -> Task:
    """
    Create a task that instructs the retriever agent to search products
    based on banking type, tier, and/or specific product/feature.
    """
    return Task(
        description=(
            f"TASK: Search knowledge base and return complete raw product output.\n\n"
            f"CRITERIA:\n{search_context}\n\n"
            f"RULES:\n"
            f"1. Call rag_search_tool ONCE\n"
            f"2. Return the COMPLETE output verbatim, every line unchanged\n"
            f"3. Do not summarize, list names only, or add commentary\n"
            f"4. If NO_PRODUCTS_FOUND, return that exactly."
        ),
        expected_output=(
            "Raw product data from the knowledge base in this format:\n"
            "============================================================\n"
            "PRODUCT: [Product Name]\n"
            "============================================================\n"
            "[Full product content from knowledge base]\n\n"
            "Repeat for each product found, or return: NO_PRODUCTS_FOUND"
        ),
        agent=agent,
    )

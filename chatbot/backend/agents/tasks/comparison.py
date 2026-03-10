"""
Feature comparison task — instructs comparator agent to compare products side-by-side.
"""

from crewai import Task


def compare_features_task(
    agent,
    comparison_context: str,
    search_criteria: str,
) -> Task:
    """
    Create a task that instructs the comparator agent to retrieve and compare
    multiple products side-by-side using a CONCISE TABLE format.
    """
    return Task(
        description=(
            f"TASK: Compare products using CONCISE TABLE ONLY. NO LONG NARRATIVES.\n\n"
            f"CONTEXT:\n{comparison_context}\n\n"
            f"CRITERIA:\n{search_criteria}\n\n"
            f"FORMAT (MANDATORY):\n"
            f"1. Markdown table: | Product | Annual Fee | Interest-Free | Rewards | Lounge Access | Best For |\n"
            f"2. ONE sentence per product (identity)\n"
            f"3. ONE paragraph (2-3 sentences) for 'Your Best Choice' with specific reason\n"
            f"4. TOTAL: Fewer than 10 lines\n"
            f"\n"
            f"CRITICAL:\n"
            f"- Table rows MUST match retrieved products exactly\n"
            f"- Use ONLY values from retrieval, never invent fees/features\n"
            f"- NO repeated descriptions, NO detailed sections\n"
            f"- Explain which card is better FOR THEIR SPECIFIC INCOME (600k annual)"
        ),
        expected_output=(
            "Markdown comparison table with 2-3 columns\n"
            "One identity sentence per product\n"
            "One short paragraph (3-4 sentences max) explaining which is better and why\n"
            "Total response: <15 lines (table + minimal explanation)"
        ),
        agent=agent,
    )

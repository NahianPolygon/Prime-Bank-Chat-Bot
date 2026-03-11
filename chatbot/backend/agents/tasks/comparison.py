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
    multiple products side-by-side using a CONCISE TABLE format ONLY.
    """
    return Task(
        description=(
            f"TASK: OUTPUT ONLY A MARKDOWN COMPARISON TABLE. NOTHING ELSE.\n\n"
            f"!!!DO NOT include any sections, headers, or long descriptions!!!\n"
            f"!!!ONLY output: TABLE + ONE sentence per product + ONE short paragraph!!!\n\n"
            f"CONTEXT:\n{comparison_context}\n\n"
            f"REQUIRED FORMAT (must follow exactly):\n"
            f"1. START with markdown table: | Product | Annual Fee | Interest-Free | Rewards | Lounge Access | Best For |\n"
            f"2. Fill table with product data - ONE ROW per product\n"
            f"3. After table ONLY: ONE sentence per product identifying it (e.g., 'JCB Platinum Credit Card offers premium JCB benefits with Balaka VIP lounge.')\n"
            f"4. After that ONLY: ONE paragraph (2-3 sentences max) titled 'Your Best Choice:' explaining WHICH CARD IS BETTER FOR THEIR SPECIFIC PROFILE and WHY\n"
            f"5. TOTAL OUTPUT: TABLE + 3-4 sentences ONLY (less than 10 lines)\n\n"
            f"!!!CRITICAL RULES (MUST FOLLOW)!!!\n"
            f"- NO [Key Features], [Overview], or section headers\n"
            f"- NO bullet points or detailed feature lists\n"
            f"- NO repeated information\n"
            f"- NO lengthy explanations\n"
            f"- Use ONLY values from retrieved data - NEVER invent fees/rates\n"
            f"- Explain why one card is better FOR THEIR ACTUAL INCOME/USE CASE\n"
            f"- If customer mentioned dining focus + BDT 2.4M annual income, explain which card suits that better\n\n"
            f"If you output anything other than TABLE + minimal sentences, the output is WRONG."
        ),
        expected_output=(
            "ONLY one markdown table (4-6 rows: header + 2-4 product rows)\n"
            "ONLY 1 sentence per product (max 50 words each)\n"
            "ONLY 1 paragraph (2-3 sentences) for 'Your Best Choice' (max 100 words)\n"
            "NOTHING ELSE - NO sections, NO bullets, NO descriptions, NO long text\n"
            "Total: table (4-6 lines) + 5-8 sentences (5-10 lines) = <15 lines total"
        ),
        agent=agent,
    )

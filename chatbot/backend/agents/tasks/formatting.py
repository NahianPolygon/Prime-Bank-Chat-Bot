"""
Response formatting task — instructs formatter agent to create the final response.
"""

from crewai import Task


def format_response_task(
    agent,
    raw_outputs: str,
    customer_message: str,
) -> Task:
    """
    Create a task that instructs the formatter agent to turn technical
    outputs into a warm, natural customer response.
    """
    return Task(
        description=(
            f"TASK: Format retrieved product data into a warm, natural customer response.\n\n"
            f"CUSTOMER ASKED: {customer_message}\n\n"
            f"RETRIEVED PRODUCT DATA (use ONLY these facts, NEVER invent):\n{raw_outputs}\n\n"
            f"CRITICAL RULES:\n"
            f"1. Extract product NAMES from data above and use EXACTLY as written\n"
            f"2. Extract product FEATURES from data above ONLY\n"
            f"3. If a feature is not in the data, DO NOT mention it\n"
            f"4. Never invent product names, fees, rates, limits, or features\n"
            f"5. No section labels like [Opening] or [Closing]\n"
            f"6. Plain language, warm tone, knowledgeable banker style\n"
            f"7. For discovery: list products found with their features from data\n"
            f"8. For feature questions: answer using ONLY features in data\n"
            f"9. For comparison: compare ONLY what's in the data"
        ),
        expected_output=(
            "A warm customer response using ONLY facts from the product data above:\n"
            "- Product names exactly as they appear in data\n"
            "- Product features from the data only, no invented details\n"
            "- Natural, friendly tone\n"
            "- Plain language, no section labels"
        ),
        agent=agent,
    )

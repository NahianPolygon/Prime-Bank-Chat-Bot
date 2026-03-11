"""
Helper functions for greeting, small talk, and context building.
"""

from utils.ollama import ollama_chat


def greet(query: str, history: list) -> str:
    """Generate a warm greeting response."""
    recent = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-3:])
    prefix = ("Recent conversation:\n" + recent + "\n") if recent else ""
    return (
        ollama_chat(
            system=(
                "You are a friendly Prime Bank assistant. "
                "Write 2 natural sentences. No bullet lists. No formal headers."
            ),
            user=(
                prefix
                + f'Customer says: "{query}"\n\n'
                "Greet them warmly and invite them to ask about credit cards, loans, or savings. "
                "Sound like a real person, not a chatbot."
            ),
            temperature=0.7,
            max_tokens=100,
        )
        or "Welcome to Prime Bank! 👋 How can I help you today?"
    )


def chat(query: str, history: list, state=None) -> str:
    """
    Handle small talk and steer back to banking help with context awareness.
    Tracks off-topic interactions and offers escalation if confused.
    """
    # Track confusion if enabled
    if state:
        state.increment_confusion()
    
    # Extract context from recent conversation
    recent = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-3:])
    prefix = ("Recent:\n" + recent + "\n") if recent else ""
    
    # Generate context-aware response
    response = (
        ollama_chat(
            system=(
                "You are a Prime Bank assistant. "
                "Reply briefly to small talk, reference their banking interest if mentioned, "
                "then naturally steer back to banking help. 2 sentences maximum. "
                "Be warm, not robotic."
            ),
            user=(
                prefix + 
                f'Customer: "{query}"\n' 
                "Give a brief human reply acknowledging their comment, then offer relevant banking help. "
                "If they seem confused or we're going in circles, suggest speaking with support."
            ),
            temperature=0.7,
            max_tokens=100,
        )
        or "Happy to chat! Is there anything I can help you with at Prime Bank today?"
    )
    
    # Check if we should offer escalation due to repeated off-topic
    if state and state.confusion_counter > 3 and not state.escalation_offered:
        response += (
            "\n\nI notice we're having fun with other topics! 😊 "
            "Would it help to speak with one of our support specialists? They can guide you better."
        )
        state.escalation_offered = True
    
    return response


def build_context_block(
    query: str, history: list, intent: dict, state
) -> str:
    """
    Build the enriched context string the agents receive.
    Contains the customer's question and all understood intent fields.
    For feature_query: also includes the specific product and feature so
    the retriever can search precisely instead of broadly.
    """
    lines = [f'Customer Query: "{query}"']

    field_map = {
        "product_type": "Product Type",
        "banking_type": "Banking Type",
        "tier": "Tier",
        "use_case": "Use Case",
        "employment": "Employment",
    }
    for field, label in field_map.items():
        val = intent.get(field, "unknown")
        if val and val != "unknown":
            lines.append(f"{label}: {val}")

    # Feature query: inject specific product + feature so retriever is precise
    if intent.get("intent_type") == "feature_query":
        if intent.get("specific_product"):
            lines.append(f"Specific Product: {intent['specific_product']}")
        if intent.get("specific_feature"):
            lines.append(f"Specific Feature: {intent['specific_feature']}")

    if history:
        lines.append("\nRecent conversation:")
        for m in history[-4:]:
            lines.append(f"  {m['role'].upper()}: {m['content']}")

    return "\n".join(lines)

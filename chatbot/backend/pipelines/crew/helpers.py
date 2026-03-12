from utils.ollama import ollama_chat


def greet(query: str, history: list) -> str:
    return ollama_chat(
        system="Warm Prime Bank assistant. Mention Prime Bank by name. Max 2 sentences.",
        user=f'Customer: "{query}"\nGreet warmly and offer help with credit cards/banking.',
        temperature=0.7, max_tokens=60,
    ) or "Hello! Welcome to Prime Bank — how can I help you with our credit cards today?"


def chat(query: str, history: list, state=None) -> str:
    if state:
        state.increment_confusion()
    response = ollama_chat(
        system="Warm Prime Bank assistant. Acknowledge briefly, steer back to banking. Max 2 sentences.",
        user=f'Customer: "{query}"\nAcknowledge warmly then offer Prime Bank banking help.',
        temperature=0.7, max_tokens=70,
    ) or "Happy to chat! Is there anything I can help you with at Prime Bank today?"
    if state and state.confusion_counter > 3 and not state.escalation_offered:
        response += "\n\nWould it help to speak with one of our Prime Bank specialists?"
        state.escalation_offered = True
    return response


def build_context_block(query: str, history: list, intent: dict, state) -> str:
    """
    Build enriched context string for orchestrator/agents.
    Normalises customer_income → annual_income so needs_clarification() finds it.
    """
    lines = [f'Customer Query: "{query}"']

    fields = ["intent_type", "banking_type", "tier", "preferred_tier", "card_brand",
              "specific_product", "primary_use_case", "use_case"]
    for f in fields:
        v = intent.get(f)
        if v and v != "unknown":
            lines.append(f"{f.replace('_', ' ').title()}: {v}")

    # Normalise income — write both keys so all downstream checks find it
    income = intent.get("customer_income") or intent.get("annual_income")
    if income:
        lines.append(f"Monthly Income (BDT): {income}")
        annual = income * 12 if income < 500000 else income
        lines.append(f"Annual Income (BDT): {annual}")
        intent["annual_income"] = annual  # mutate so main.py checks work

    features = intent.get("specific_features")
    if features:
        lines.append(f"Requested Features: {', '.join(features) if isinstance(features, list) else features}")

    if state and getattr(state, "recommended_product", None):
        lines.append(f"Currently Shown: {state.recommended_product}")
    if state and getattr(state, "alternative_products", None):
        lines.append(f"Alternatives Shown: {', '.join(state.alternative_products)}")

    if history:
        lines.append("\nRecent conversation:")
        for m in history[-4:]:
            lines.append(f"  {m['role'].upper()}: {m['content']}")

    return "\n".join(lines)
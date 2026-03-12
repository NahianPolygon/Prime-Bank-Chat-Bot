from core import SessionState
from utils.ollama import ollama_chat, parse_json

REQUIRED_FIELDS = ["age", "employment_type", "tenure", "monthly_income", "has_etin"]


def start_eligibility_collection(intent: dict, state: SessionState) -> str:
    state.eligibility_active = True
    state._confirmed_fields = {}

    if intent.get("specific_product"):
        state.eligibility_product = intent["specific_product"]
    else:
        tier = intent.get("tier", "")
        banking = intent.get("banking_type", "conventional")
        state.eligibility_product = f"{tier} credit card ({banking})".strip()

    question = ollama_chat(
        system="You are a warm Prime Bank assistant. Max 2 sentences.",
        user=f'Customer wants eligibility check for: {state.eligibility_product}\nAcknowledge warmly and ask for their age only.',
        temperature=0.6, max_tokens=60,
    ) or f"I'd love to help check your eligibility for the {state.eligibility_product}! Could you share your age?"

    state.eligibility_chat.append({"role": "assistant", "content": question})
    return question


def get_next_pending_field(state: SessionState) -> str | None:
    confirmed = getattr(state, '_confirmed_fields', {})
    for field in REQUIRED_FIELDS:
        if field not in confirmed:
            return field
    return None


def _extract_single_field(field: str, user_input: str, collected: dict):
    """Pure LLM extraction — one short prompt per field type."""
    prompts = {
        "age": f'Age from: "{user_input}". JSON: {{"value": <number 15-80 or null>}}',
        "employment_type": f'Employment from: "{user_input}". Options: salaried/self_employed/business_owner/student. JSON: {{"value": "<option or null>"}}',
        "tenure": f'Job tenure from: "{user_input}". JSON: {{"value": "<e.g. 3 years, 8 months, or null>"}}',
        "monthly_income": f'Monthly income in BDT from: "{user_input}". 300k=300000, 2 lakh=200000. JSON: {{"value": <number or null>}}',
        "has_etin": f'Has E-TIN from: "{user_input}". yes/have/confirm=true, no/don\'t have=false. JSON: {{"value": <true|false|null>}}',
    }
    raw = ollama_chat(
        system="Extract one value. Return ONLY JSON with a single 'value' key. No markdown.",
        user=prompts[field],
        temperature=0.0, max_tokens=40,
    )
    parsed = parse_json(raw)
    if not parsed:
        return None
    value = parsed.get("value")
    return value if value is not None else None


def _build_confirmation(field: str, value) -> str:
    if field == "age":
        return f"✓ Age: **{value}**"
    if field == "employment_type":
        return f"✓ Employment: **{str(value).replace('_', ' ').title()}**"
    if field == "tenure":
        return f"✓ Tenure: **{value}**"
    if field == "monthly_income":
        try:
            return f"✓ Monthly Income: **BDT {int(value):,}**"
        except:
            return f"✓ Monthly Income: **{value}**"
    if field == "has_etin":
        return f"✓ E-TIN: **{'Yes' if value else 'No'}**"
    return f"✓ {field}: **{value}**"


def _ask_field_question(field: str, collected: dict, state: SessionState) -> str:
    confirmed = ", ".join(f"{k}={v}" for k, v in collected.items() if v is not None) or "none yet"
    hints = {
        "age": "their age in years",
        "employment_type": "employment type: salaried / self-employed / business owner / student",
        "tenure": "how long in current job or business",
        "monthly_income": "monthly income in BDT (they can say '50k', '2 lakh', etc.)",
        "has_etin": "whether they have an E-TIN (tax ID) — briefly explain it's required",
    }
    return ollama_chat(
        system="You are a warm Prime Bank eligibility assistant. One question, max 2 sentences.",
        user=f"Card: {state.eligibility_product or 'credit card'}\nConfirmed so far: {confirmed}\nAsk for: {hints.get(field, field)}",
        temperature=0.5, max_tokens=60,
    ) or f"Could you share your {field.replace('_', ' ')}?"


def ask_for_next_field(field: str, collected: dict, state: SessionState, last_user_input: str = None) -> str:
    if not last_user_input:
        return _ask_field_question(field, collected, state)
    extracted = _extract_single_field(field, last_user_input, collected)
    if extracted is None:
        return _ask_field_question(field, collected, state)
    if not hasattr(state, '_confirmed_fields'):
        state._confirmed_fields = {}
    state._confirmed_fields[field] = extracted
    state.confirm_field_value(field, extracted, str(extracted))
    confirmation = _build_confirmation(field, extracted)
    remaining = [f for f in REQUIRED_FIELDS if f not in state._confirmed_fields]
    if remaining:
        return f"{confirmation}\n\n{_ask_field_question(remaining[0], collected, state)}"
    state._all_fields_confirmed = True
    return f"{confirmation}\n\n✨ Thank you! Checking your eligibility now..."


def check_eligibility_completeness(state: SessionState) -> dict:
    confirmed = getattr(state, '_confirmed_fields', {})
    complete = all(confirmed.get(f) is not None for f in REQUIRED_FIELDS)
    next_field = next((f for f in REQUIRED_FIELDS if confirmed.get(f) is None), None)
    return {"complete": complete, "next_field": next_field, "collected": dict(confirmed)}


def build_eligibility_profile(state: SessionState) -> str:
    confirmed = getattr(state, '_confirmed_fields', {})
    if confirmed:
        parts = []
        if confirmed.get("age"):        parts.append(f"Age: {confirmed['age']}")
        if confirmed.get("employment_type"): parts.append(f"Employment: {confirmed['employment_type']}")
        if confirmed.get("tenure"):     parts.append(f"Tenure: {confirmed['tenure']}")
        if confirmed.get("monthly_income"): parts.append(f"Monthly Income: BDT {int(confirmed['monthly_income']):,}")
        if confirmed.get("has_etin") is not None: parts.append(f"E-TIN: {'Yes' if confirmed['has_etin'] else 'No'}")
        return f"Card: {state.eligibility_product}\n" + " | ".join(parts)
    # fallback if confirmed is somehow empty
    history = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in state.eligibility_chat)
    return ollama_chat(
        system="Summarise in one line. Output: Age/Employment/Tenure/Income/ETIN only.",
        user=history, temperature=0.0, max_tokens=80,
    ) or history
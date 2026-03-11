
from core import SessionState
from utils.ollama import ollama_chat, parse_json
from pipelines.crew.validation import DynamicInputValidator

_validator = DynamicInputValidator()


def start_eligibility_collection(intent: dict, state: SessionState) -> str:
    """Start the eligibility collection multi-turn flow."""
    state.eligibility_active = True

    
    if intent.get("specific_product"):
        state.eligibility_product = intent.get("specific_product")
        print(f"✅ Eligibility check for specific product: {state.eligibility_product}")
    else:
        tier = intent.get("tier", "unknown")
        product = intent.get("product_type", "credit card").replace("_", " ")
        banking = intent.get("banking_type", "conventional")
        tier_str = f"{tier} " if tier != "unknown" else ""
        state.eligibility_product = f"{tier_str}{product} ({banking} banking)"
        print(f"ℹ️  Generic eligibility check: {state.eligibility_product}")

    question = (
        ollama_chat(
            system="You are a warm Prime Bank eligibility assistant. Write 1-2 natural sentences.",
            user=(
                f"A customer wants to check eligibility for: {state.eligibility_product}\n"
                "Warmly acknowledge this and ask for their age only. Nothing else yet."
            ),
            temperature=0.6,
            max_tokens=80,
        )
        or (
            f"I'd be happy to help you check your eligibility for the "
            f"{state.eligibility_product}! To get started, could you tell me your age?"
        )
    )

    state.eligibility_chat.append({"role": "assistant", "content": question})
    return question


def check_eligibility_completeness(state: SessionState) -> dict:
    """
    LLM reads the eligibility conversation and tells us:
    - What fields we have collected
    - Whether we have all required fields
    - What to ask for next
    """
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in state.eligibility_chat
    )

    raw = ollama_chat(
        system="You are a data extraction system. Output only JSON. CRITICAL: Extract ALL required fields.",
        user=f"""Read this eligibility conversation and extract what the customer has told us.

Conversation:
{history_text}

REQUIRED FIELDS (ALL MUST be provided - none can be skipped):
1. age - customer's age (number)
2. employment_type - salaried, self_employed, business_owner, student
3. tenure - how long in current job (e.g., "2 years", "8 years")
4. monthly_income - income in BDT (e.g., "BDT 150000")
5. has_etin - REQUIRED - true if HAS E-TIN, false if NO E-TIN, null if NOT YET ASKED

CRITICAL EXTRACTION RULES:
- If customer mentions job type, extract it
- If customer mentions employment years/duration, that is tenure
- If E-TIN is mentioned (Tax ID, E-TIN, employer number), set has_etin=true
- If customer says they DON'T have E-TIN, set has_etin=false
- If E-TIN NOT mentioned in conversation yet, set has_etin=null
- DO NOT assume has_etin=true. Only true if customer actually confirmed they have it.

Output JSON (exactly this format):
{{
  "collected": {{
    "age": <number or null>,
    "employment_type": <"salaried"|"self_employed"|"business_owner"|"student"|null>,
    "tenure": <string like "2 years" or null>,
    "monthly_income": <string like "BDT 150000" or null>,
    "has_etin": <true|false|null>,
    "credit_history": <string or null>
  }},
  "complete": <true ONLY if age AND employment_type AND tenure AND monthly_income AND has_etin are ALL non-null>,
  "next_field": <missing field to ask next: "age"|"employment_type"|"tenure"|"monthly_income"|"has_etin", or null if complete>
}}

IMPORTANT: If any field is null, complete=false. Return the first null field as next_field.
Output ONLY the JSON. Do not add explanation.""",
        temperature=0.0,
        max_tokens=300,
    )

    parsed = parse_json(raw)
    if not parsed:
        return {"complete": False, "next_field": "age", "collected": {}}

    
    collected = parsed.get("collected", {})
    if collected.get("has_etin") is None:
        parsed["complete"] = False
        if not parsed.get("next_field"):
            parsed["next_field"] = "has_etin"

    return {
        "complete": bool(parsed.get("complete", False)),
        "next_field": parsed.get("next_field"),
        "collected": parsed.get("collected", {}),
    }


def ask_for_next_field(field: str, collected: dict, state: SessionState, last_user_input: str = None) -> str:
    """
    Ask for next field with validation, confirmation, and simple question flow.
    
    Flow:
    1. Ask for the current field
    2. When user provides input, validate it matches the field
    3. If valid, show a simple confirmation and ask for the next field
    4. If invalid, ask again with a helpful note (not accusatory)
    """
    
    if not last_user_input:
        # First time asking for this field
        return _ask_field_question(field, collected, state)
    
    # Validate the input based on field type
    validation_result = _validator.validate_with_context(
        user_input=last_user_input,
        field_name=field,
        conversation_context=dict(collected),
        previous_attempts=getattr(state, '_previous_invalid_attempts', [])
    )
    
    if not validation_result.get("valid", False):
        # Invalid input - ask for the same field again with a gentle prompt
        attempts = state.increment_invalid_attempts()
        if not hasattr(state, '_previous_invalid_attempts'):
            state._previous_invalid_attempts = []
        state._previous_invalid_attempts.append(last_user_input)
        
        # Gentle re-ask instead of accusatory message
        simple_question = _ask_field_question(field, collected, state)
        if attempts > 1:
            simple_question = f"Let me try that again. {simple_question}"
        
        return simple_question
    
    # Valid input - simple confirmation and move to next field
    extracted_value = validation_result.get("extracted_value")
    confidence = validation_result.get("confidence", 0)
    
    # Build simple, positive confirmation
    confirmation_msg = ""
    if extracted_value and confidence > 0.7:
        if isinstance(extracted_value, dict):
            if "age_years" in extracted_value:
                confirmation_msg = f"✓ Got it - **{extracted_value['age_years']} years old**"
            elif "monthly_bdt" in extracted_value:
                monthly = extracted_value["monthly_bdt"]
                annual = extracted_value.get("annual_bdt", monthly * 12)
                confirmation_msg = f"✓ Got it - **BDT {monthly:,}/month**"
            elif "category" in extracted_value:
                confirmation_msg = f"✓ Got it - **{extracted_value['category']}**"
            elif "tenure_months" in extracted_value:
                display = extracted_value.get("tenure_display", f"{extracted_value['tenure_months']} months")
                confirmation_msg = f"✓ Got it - **{display}**"
            elif "has_etin" in extracted_value:
                etin_status = "Yes" if extracted_value["has_etin"] else "No"
                confirmation_msg = f"✓ Got it - **{etin_status}**"
            else:
                confirmation_msg = f"✓ Got it - **{extracted_value}**"
        else:
            confirmation_msg = f"✓ **{extracted_value}**"
    else:
        confirmation_msg = "✓ Confirmed"
    
    # Reset invalid attempts since this field is valid
    state.invalid_attempt_count = 0
    if hasattr(state, '_previous_invalid_attempts'):
        state._previous_invalid_attempts = []
    
    # Track confirmed value
    if extracted_value:
        state.confirm_field_value(field, extracted_value, confirmation_msg)
    
    # Move to next field
    next_field_map = ["age", "employment_type", "tenure", "monthly_income", "has_etin"]
    try:
        current_idx = next_field_map.index(field)
        remaining_fields = [f for f in next_field_map[current_idx + 1:] if collected.get(f) is None]
        
        if remaining_fields:
            next_field = remaining_fields[0]
            next_question = _ask_field_question(next_field, collected, state)
            return f"{confirmation_msg}\n\n{next_question}"
        else:
            return f"{confirmation_msg}\n\n✨ Great! I have all the information I need."
    except (ValueError, IndexError):
        return confirmation_msg or _ask_field_question(field, collected, state)


def _ask_field_question(field: str, collected: dict, state: SessionState) -> str:
    """Generate a natural question for the specified field with context awareness."""
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in state.eligibility_chat[-6:]
    )
    collected_summary = (
        ", ".join(f"{k}={v}" for k, v in collected.items() if v is not None)
        or "nothing yet"
    )

    # Special handling for E-TIN question
    if field == "has_etin":
        return (
            ollama_chat(
                system=(
                    "You are a warm Prime Bank eligibility assistant. "
                    "Ask about E-TIN clearly but naturally (also called Tax ID, employer tax number, or registration). "
                    "Max 2 sentences."
                ),
                user=(
                    f"Customer profile so far:\n{collected_summary}\n\n"
                    "Ask if they have an E-TIN (Employer's Tax Identification Number). "
                    "This is needed for eligibility verification. Be warm and explain briefly why."
                ),
                temperature=0.5,
                max_tokens=100,
            )
            or "Do you have an E-TIN (Employer's Tax Identification Number) or tax registration? This helps us verify employment."
        )
    
    # For other fields, ask naturally with context
    return (
        ollama_chat(
            system=(
                f"You are a warm Prime Bank eligibility assistant helping a customer apply for: "
                f"{state.eligibility_product or 'a credit card'}. "
                "Ask for ONE piece of information at a time. Be brief and natural. Max 2 sentences. "
                "Reference what they've already shared."
            ),
            user=(
                f"Conversation so far:\n{history_text}\n\n"
                f"We have collected: {collected_summary}\n"
                f"Next, we need to know: {field}\n\n"
                "Write the next question naturally, referencing earlier context if relevant."
            ),
            temperature=0.5,
            max_tokens=90,
        )
        or f"Could you also share your {field.replace('_', ' ')}?"
    )


def build_eligibility_profile(state: SessionState) -> str:
    """All fields collected — build profile summary."""
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in state.eligibility_chat
    )

    return (
        ollama_chat(
            system="Summarize customer data concisely. Output a short paragraph.",
            user=(
                f"Summarize this customer's eligibility profile from the conversation:\n"
                f"{history_text}\n\n"
                "Include: age, employment type, job tenure, monthly income, E-TIN status (has/doesn't have). "
                "Be factual and concise. One paragraph."
            ),
            temperature=0.0,
            max_tokens=150,
        )
        or history_text
    )

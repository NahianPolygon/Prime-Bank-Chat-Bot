from core import SessionState
from utils.ollama import ollama_chat, parse_json

REQUIRED_FIELDS = ["age", "employment_type", "tenure", "monthly_income", "has_etin"]


def start_eligibility_collection(intent: dict, state: SessionState) -> str:
    state.eligibility_active = True
    state._confirmed_fields = {}

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
    # Only read USER turns to prevent LLM hallucinating from assistant questions
    user_turns = [m for m in state.eligibility_chat if m["role"] == "user"]
    history_text = "\n".join(
        f"CUSTOMER: {m['content']}" for m in user_turns
    )

    raw = ollama_chat(
        system="You are a data extraction system. Output only JSON. Extract ALL required fields.",
        user=f"""Read this eligibility conversation and extract what the customer has told us.

Conversation:
{history_text}

REQUIRED FIELDS:
1. age - customer's age (number)
2. employment_type - salaried, self_employed, business_owner, student
3. tenure - how long in current job (e.g., "2 years", "8 years")
4. monthly_income - income in BDT (e.g., "BDT 150000")
5. has_etin - true if HAS E-TIN, false if NO E-TIN, null if NOT YET ASKED

EXTRACTION RULES (only extract from USER turns, never infer from ASSISTANT messages):
- employment_type: ONLY if customer explicitly stated job type. "full time", "full-time", "employed", "salaried", "office job" → "salaried". If not stated by customer → null
- tenure: ONLY if customer stated years/months in current job. If not stated → null
- monthly_income: "300k", "300 k" per month → "BDT 300000". ONLY from customer input. If not stated → null
- has_etin: "yes", "yes i have", "i have it" → true. "no", "don't have" → false. Not yet asked/answered → null
- CRITICAL: Set null for ANY field the customer has not explicitly answered yet. Never assume or infer.

Output JSON:
{{
  "collected": {{
    "age": <number or null>,
    "employment_type": <string or null>,
    "tenure": <string or null>,
    "monthly_income": <string or null>,
    "has_etin": <true|false|null>
  }},
  "complete": <true ONLY if ALL five fields are non-null>,
  "next_field": <first null field name, or null if complete>
}}

Output ONLY JSON.""",
        temperature=0.0,
        max_tokens=300,
    )

    parsed = parse_json(raw)
    if not parsed:
        return {"complete": False, "next_field": "age", "collected": {}}

    collected = parsed.get("collected", {})

    # Merge in already-confirmed fields so LLM extraction gaps don't cause re-asking
    confirmed = getattr(state, '_confirmed_fields', {})
    for field, value in confirmed.items():
        if collected.get(field) is None and value is not None:
            collected[field] = value

    # Recompute completeness after merge
    complete = all(collected.get(f) is not None for f in REQUIRED_FIELDS)
    next_field = None
    if not complete:
        for f in REQUIRED_FIELDS:
            if collected.get(f) is None:
                next_field = f
                break

    return {
        "complete": complete,
        "next_field": next_field,
        "collected": collected,
    }


def ask_for_next_field(field: str, collected: dict, state: SessionState, last_user_input: str = None) -> str:
    """
    Ask for next field. No external validator — check_eligibility_completeness handles extraction.
    Only re-asks if the LLM genuinely could not extract the field from the user's input.
    """
    if not last_user_input:
        return _ask_field_question(field, collected, state)

    # Check if the field was successfully extracted from this latest user input
    # by running a quick targeted extraction instead of the full validator
    extracted = _extract_single_field(field, last_user_input, collected)

    if extracted is None:
        # Could not extract — ask again once with a gentle re-prompt
        state.invalid_attempt_count = (state.invalid_attempt_count or 0) + 1
        question = _ask_field_question(field, collected, state)
        if state.invalid_attempt_count > 1:
            question = f"Let me try that again. {question}"
        return question

    # Successfully extracted — store in confirmed fields
    if not hasattr(state, '_confirmed_fields'):
        state._confirmed_fields = {}
    state._confirmed_fields[field] = extracted
    state.invalid_attempt_count = 0
    state.confirm_field_value(field, extracted, str(extracted))

    # Build confirmation text
    confirmation = _build_confirmation(field, extracted)

    # Determine next field using confirmed fields as ground truth
    confirmed_keys = set(state._confirmed_fields.keys())
    remaining = [f for f in REQUIRED_FIELDS if f not in confirmed_keys and collected.get(f) is None]

    if remaining:
        next_field = remaining[0]
        next_question = _ask_field_question(next_field, collected, state)
        return f"{confirmation}\n\n{next_question}"
    else:
        # All fields collected — signal completion
        state._all_fields_confirmed = True
        return f"{confirmation}\n\n✨ Thank you! I have everything I need to check your eligibility."


def _extract_single_field(field: str, user_input: str, collected: dict):
    """
    Hybrid extraction: regex first for reliable patterns, LLM fallback for ambiguous input.
    Regex handles 95% of cases instantly. LLM only runs when regex finds nothing.
    """
    import re
    text = user_input.strip().lower()

    # ── REGEX LAYER ──────────────────────────────────────────────────────────

    if field == "age":
        m = re.search(r'\b(\d{1,3})\s*(?:years?\s*old|yr|yrs)?\b', text)
        if m:
            age = int(m.group(1))
            if 15 <= age <= 80:
                return age

    elif field == "employment_type":
        salaried_kw = [r"full.?time", r"salaried", r"\bemployee\b", r"\bemployed\b",
                       r"\boffice\b", r"\bjob\b", r"\bservice\b", r"software", r"engineer",
                       r"banker", r"teacher", r"doctor", r"manager", r"executive",
                       r"\bstaff\b", r"\bworker\b", r"govt", r"government"]
        self_emp_kw = [r"self.?employ", r"freelanc", r"\bconsultant\b", r"\bcontractor\b"]
        business_kw = [r"\bbusiness\b", r"\bowner\b", r"entrepreneur", r"\bshop\b", r"\bfirm\b"]
        student_kw  = [r"\bstudent\b", r"studying", r"university", r"college"]
        for kw in salaried_kw:
            if re.search(kw, text):
                return "salaried"
        for kw in self_emp_kw:
            if re.search(kw, text):
                return "self_employed"
        for kw in business_kw:
            if re.search(kw, text):
                return "business_owner"
        for kw in student_kw:
            if re.search(kw, text):
                return "student"

    elif field == "tenure":
        m = re.search(r'(\d+)\s*(?:years?|yrs?)', text)
        if m:
            return f"{m.group(1)} years"
        m = re.search(r'(\d+)\s*months?', text)
        if m:
            return f"{m.group(1)} months"
        m = re.search(r'since\s+(\d{4})', text)
        if m:
            import datetime
            years = datetime.datetime.now().year - int(m.group(1))
            return f"{years} years"

    elif field == "monthly_income":
        m = re.search(r'(\d[\d,]*\.?\d*)\s*k\b', text)
        if m:
            return int(float(m.group(1).replace(",", "")) * 1000)
        m = re.search(r'(\d[\d,]*\.?\d*)\s*lakh', text)
        if m:
            return int(float(m.group(1).replace(",", "")) * 100000)
        m = re.search(r'(\d[\d,]*\.?\d*)\s*crore', text)
        if m:
            return int(float(m.group(1).replace(",", "")) * 10000000)
        m = re.search(r'\b(\d{4,})\b', text)
        if m:
            return int(m.group(1).replace(",", ""))

    elif field == "has_etin":
        yes_kw = [r'\byes\b', r'\bi have\b', r'\bi do\b', r'\bhave it\b',
                  r'\byep\b', r'\byeah\b', r'\bconfirm\b', r'\bsure\b']
        no_kw  = [r"\bno\b", r"\bdon't have\b", r"\bnot have\b",
                  r"\bdo not have\b", r"\bnope\b", r"\bhavent\b", r"\bwithout\b"]
        for kw in yes_kw:
            if re.search(kw, text):
                return True
        for kw in no_kw:
            if re.search(kw, text):
                return False

    # ── LLM FALLBACK — only runs if regex found nothing ──────────────────────
    field_prompts = {
        "age": f'What age is mentioned in: "{user_input}"? Return only: {{"value": <number or null>}}',
        "employment_type": (
            f'Classify employment from: "{user_input}". '
            f'Options: salaried, self_employed, business_owner, student. '
            f'Return only: {{"value": "<category or null>"}}'
        ),
        "tenure": f'How long in current job from: "{user_input}"? Return only: {{"value": "<e.g. 3 years or null>"}}',
        "monthly_income": (
            f'Extract monthly income amount in BDT from: "{user_input}". '
            f'"300k"=300000, "2 lakh"=200000. Return only: {{"value": <number or null>}}'
        ),
        "has_etin": (
            f'Does "{user_input}" confirm having E-TIN/tax ID? '
            f'yes/have/confirm=true, no/don\'t have=false, unclear=null. '
            f'Return only: {{"value": <true|false|null>}}'
        ),
    }

    prompt = field_prompts.get(field)
    if not prompt:
        return None

    print(f"🔄 Regex failed for '{field}', trying LLM fallback on: '{user_input[:40]}'")
    raw = ollama_chat(
        system="Extract one data point. Return ONLY a JSON object with a single 'value' key. No explanation, no markdown.",
        user=prompt,
        temperature=0.0,
        max_tokens=30,
    )

    parsed = parse_json(raw)
    if not parsed:
        return None

    value = parsed.get("value")
    return value if value is not None else None


def _build_confirmation(field: str, value: any) -> str:
    confirmations = {
        "age": f"✓ Age: **{value}**",
        "employment_type": f"✓ Employment: **{value}**",
        "tenure": f"✓ Tenure: **{value}**",
        "monthly_income": lambda v: f"✓ Income: **BDT {int(v):,}/month**" if isinstance(v, (int, float)) else f"✓ Income: **{v}**",
        "has_etin": f"✓ E-TIN: **{'Yes' if value else 'No'}**",
    }
    conf = confirmations.get(field, f"✓ {field}: **{value}**")
    return conf(value) if callable(conf) else conf


def _ask_field_question(field: str, collected: dict, state: SessionState) -> str:
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in state.eligibility_chat[-6:]
    )
    collected_summary = (
        ", ".join(f"{k}={v}" for k, v in collected.items() if v is not None)
        or "nothing yet"
    )

    if field == "has_etin":
        return (
            ollama_chat(
                system="You are a warm Prime Bank eligibility assistant. Max 2 sentences.",
                user=(
                    f"Customer profile so far: {collected_summary}\n"
                    "Ask if they have an E-TIN (Employer's Tax Identification Number / tax registration). "
                    "Explain briefly why it's needed. Be warm."
                ),
                temperature=0.5,
                max_tokens=80,
            )
            or "Do you have an E-TIN (Employer's Tax Identification Number)? This helps us verify your eligibility."
        )

    return (
        ollama_chat(
            system=(
                f"You are a warm Prime Bank eligibility assistant for: "
                f"{state.eligibility_product or 'a credit card'}. "
                "Ask for ONE piece of info. Max 2 sentences. Reference prior context briefly."
            ),
            user=(
                f"Conversation so far:\n{history_text}\n\n"
                f"Already collected: {collected_summary}\n"
                f"Ask for: {field}\n\n"
                "Write the next question naturally."
            ),
            temperature=0.5,
            max_tokens=80,
        )
        or f"Could you share your {field.replace('_', ' ')}?"
    )


def get_next_pending_field(state: SessionState) -> str | None:
    """
    Return the next field that has NOT been confirmed yet, using _confirmed_fields
    as the authoritative source of truth. Never relies on LLM extraction.
    Returns None if all fields are collected.
    """
    confirmed = getattr(state, '_confirmed_fields', {})
    for field in REQUIRED_FIELDS:
        if field not in confirmed:
            return field
    return None


def build_eligibility_profile(state: SessionState) -> str:
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in state.eligibility_chat
    )

    # Also include confirmed fields as a reliable fallback
    confirmed = getattr(state, '_confirmed_fields', {})
    confirmed_summary = ", ".join(f"{k}={v}" for k, v in confirmed.items()) if confirmed else ""

    return (
        ollama_chat(
            system="Summarize customer data concisely. Output a short paragraph.",
            user=(
                f"Summarize this customer's eligibility profile.\n\n"
                f"Conversation:\n{history_text}\n\n"
                f"Confirmed fields: {confirmed_summary}\n\n"
                "Include: age, employment type, job tenure, monthly income, E-TIN status. "
                "Be factual and concise. One paragraph."
            ),
            temperature=0.0,
            max_tokens=150,
        )
        or history_text
    )

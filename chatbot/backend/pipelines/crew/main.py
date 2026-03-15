from core import SessionState
from intent import IntentClassifier
from pipelines.crew.orchestrator import BankChatbotCrew, _format_products
from pipelines.crew.clarification import DynamicClarificationBuilder
from pipelines.crew.comparator import ProductComparator
from pipelines.crew.eligibility import (
    start_eligibility_collection,
    ask_for_next_field,
    build_eligibility_profile,
)
from pipelines.crew.helpers import greet, chat, build_context_block
from pipelines.crew.eligibility_matching import run_eligibility_matching, run_eligibility_info
from pipelines.rag.search import rag_search_impl, resolve_product_name, get_all_product_names
from utils.ollama import ollama_chat, parse_json

_clarification_builder = DynamicClarificationBuilder()
_comparator = ProductComparator()


def _extract_comparison_products(query: str, intent: dict) -> list[str]:
    """
    Extract two product names from a comparison query, then resolve each
    to the canonical ChromaDB product_name via semantic search.
    No hardcoded product names — all lookups go through the vector DB.
    """
    # Intent classifier may already have parsed names
    if intent.get("comparison_products") and len(intent["comparison_products"]) >= 2:
        return [resolve_product_name(p) for p in intent["comparison_products"][:2]]

    # LLM extracts fuzzy names from the query text
    raw = ollama_chat(
        system='Extract two credit card names. JSON: {"p1": "...", "p2": "..."}. null if not found.',
        user=f'Query: "{query}"',
        temperature=0.0, max_tokens=40,
    )
    parsed = parse_json(raw) or {}
    p1, p2 = parsed.get("p1"), parsed.get("p2")
    if p1 and p2:
        # resolve_product_name does a top_k=1 RAG search → returns metadata.product_name
        return [resolve_product_name(p1), resolve_product_name(p2)]
    return []


def _get_how_to_apply(product_name: str, state: SessionState) -> str:
    """RAG search for application process, then LLM formats the result."""
    raw = rag_search_impl(
        query=f"{product_name} how to apply required documents application process eligibility",
        banking_type="islami" if "hasanah" in product_name.lower() else "",
        top_k=6,
    )
    if not raw or raw.strip() == "NO_PRODUCTS_FOUND":
        raw = rag_search_impl(query=f"{product_name} apply", top_k=6)

    if not raw or raw.strip() == "NO_PRODUCTS_FOUND":
        # Last resort: generic LLM response (no hardcoded text)
        return ollama_chat(
            system="You are a Prime Bank assistant. Be helpful and accurate.",
            user=f"Describe the general credit card application process at Prime Bank for the {product_name}. Include documents needed, eligibility, and contact info.",
            temperature=0.3, max_tokens=300,
        ) or f"Please visit a Prime Bank branch or call 09666770101 to apply for the {product_name}."

    return ollama_chat(
        system="Prime Bank assistant. Use only the product data given. Be concise and structured.",
        user=f"Product data:\n{raw}\n\nDescribe how to apply for the {product_name}. Include: steps, required documents, eligibility criteria, approval timeline.",
        temperature=0.2, max_tokens=400,
    ) or raw


class CrewPipeline:

    def __init__(self):
        self.crew = BankChatbotCrew()
        self.sessions: dict[str, SessionState] = {}
        self.clarification_builder = _clarification_builder

    def _get_state(self, session_id: str) -> SessionState:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState()
        return self.sessions[session_id]

    def run(self, query, conversation_history=None, session_id=None, customer_info=None):
        history = conversation_history or []
        session_id = session_id or "default"
        state = self._get_state(session_id)

        if state.eligibility_active:
            return self._eligibility_turn(query, state, history)

        # ── Profiling collection ──────────────────────────────────────────────
        if state.profiling_needed:
            self._collect_profile_info(query, state)
            if not state.missing_profile_fields:
                matched_cards = self.clarification_builder.find_matching_cards(
                    banking_type=state.collected_profile.get("banking_type"),
                    use_case=state.collected_profile.get("primary_use_case"),
                    annual_income=state.collected_profile.get("annual_income"),
                    employment_type=state.collected_profile.get("employment_type"),
                    preferred_tier=state.preferred_tier,
                )
                if matched_cards:
                    state.products_text = matched_cards
                    state.profiling_needed = False
                    self._store_products(matched_cards, state)
                    formatted = _format_products(matched_cards, query, "product_info")
                    return self._respond(f"Based on your profile, here are the best cards for you:\n\n{formatted}", ["Smart Profiler", "RAG"], state.intent)
            else:
                # Ask one field at a time — first missing field only
                next_field = state.missing_profile_fields[0]
                msg = self.clarification_builder.generate_contextual_question(
                    next_field, state.collected_profile
                )
                return self._respond(msg, ["Smart Profiler"], state.intent, needs_clarification=True)

        # ── Numeric selection (structural, not semantic — OK as-is) ──────────
        query_stripped = query.strip()
        if query_stripped in ("1", "2", "3") and (state.recommended_product or state.alternative_products):
            idx = int(query_stripped) - 1
            all_products = [state.recommended_product] + (state.alternative_products or [])
            if 0 <= idx < len(all_products):
                result = _get_how_to_apply(all_products[idx], state)
                return self._respond(result, ["Product Info", "Formatter"], {"intent_type": "product_info"})

        # ── Intent classification ─────────────────────────────────────────────
        intent = IntentClassifier.classify(query, history, state.intent)
        intent_type = intent["intent_type"]
        print(f"📋 Intent: {intent_type} | banking={intent.get('banking_type')} | features={intent.get('specific_features')} | income={intent.get('customer_income')}")

        # ── Off-topic ────────────────────────────────────────────────────────
        if intent.get("is_off_topic") or intent.get("relevance_score", 100) < 55:
            state.increment_confusion()
            reply = ollama_chat(
                system="Warm Prime Bank assistant. Max 2 sentences.",
                user=f'Customer: "{query[:100]}"\nAcknowledge briefly, redirect to Prime Bank credit cards.',
                temperature=0.6, max_tokens=80,
            ) or "Happy to chat! How can I help you with Prime Bank today?"
            if state.confusion_counter > 3 and not state.escalation_offered:
                reply += "\n\nWould you like to speak with one of our support team members?"
                state.escalation_offered = True
            return self._respond(reply, [], intent)

        if intent["category"] == "greeting":
            return self._respond(greet(query, history), [], intent)
        if intent["category"] == "small_talk":
            return self._respond(chat(query, history, state), [], intent)

        if state.has_products() and intent.get("preferences_changed"):
            state.reset_products()

        # NOTE: do NOT short-circuit on intent["needs_clarification"] here.
        # The intent classifier's needs_clarification flag is unreliable for product_info.
        # All profiling decisions are made by clarification_builder.needs_clarification() below.

        state.intent = intent
        if intent.get("preferred_tier") and intent.get("preferred_tier") != "unknown":
            state.preferred_tier = intent["preferred_tier"]
        if intent.get("card_brand") and intent.get("card_brand") != "unknown":
            state.card_brand = intent["card_brand"]

        # Detect "how to apply" from query — used in multiple checks below
        _is_apply_query = any(s in query.lower() for s in
            ("apply", "application", "how to get", "sign up", "sign-up", "register", "enroll"))

        # ── How-to-apply: intent classifier already detects this as product_info
        # with a how-to-apply flavour via specific_product. We check the LLM intent
        # rather than keyword-scanning the query.
        if intent_type == "product_info" and (intent.get("is_how_to_apply") or _is_apply_query):
            product = intent.get("specific_product") or state.recommended_product
            if not product and state.alternative_products:
                # Multiple products shown — ask which one
                opts = [state.recommended_product] + state.alternative_products
                choices = "\n".join(f"{i+1}. **{p}**" for i, p in enumerate(opts))
                return self._respond(f"Which card would you like to apply for?\n\n{choices}", ["Intent Classifier"], intent, needs_clarification=True)
            if product:
                result = _get_how_to_apply(resolve_product_name(product), state)
                return self._respond(result, ["RAG", "Formatter"], intent)

        # After eligibility → how to apply
        if state.eligibility_done and state.recommended_product and _is_apply_query:
            state.eligibility_done = False
            result = _get_how_to_apply(state.recommended_product, state)
            return self._respond(result, ["RAG", "Formatter"], intent)

        # ── Category browse (show all Mastercards, gold cards, etc.) ────────
        if intent_type == "search_by_category":
            enriched = build_context_block(query, history, intent, state)
            response, retrieved = self.crew.run_agents(enriched_query=enriched, intent_type="search_by_category", intent=intent, state=state)
            if retrieved:
                state.products_text = retrieved
                self._store_products(retrieved, state)
            return self._respond(response, ["Category Search", "RAG"], intent)

        # ── Feature inquiry ───────────────────────────────────────────────────
        if intent_type == "feature_inquiry":
            enriched = build_context_block(query, history, intent, state)
            response, retrieved = self.crew.run_agents(enriched_query=enriched, intent_type="feature_inquiry", intent=intent, state=state)
            if retrieved:
                state.products_text = retrieved
                self._store_products(retrieved, state)
            return self._respond(response, ["Feature Search", "RAG"], intent)

        # ── Income search ─────────────────────────────────────────────────────
        if intent_type == "product_search_by_income":
            enriched = build_context_block(query, history, intent, state)
            response, retrieved = self.crew.run_agents(enriched_query=enriched, intent_type="product_search_by_income", intent=intent, state=state)
            if retrieved:
                state.products_text = retrieved
                self._store_products(retrieved, state)
            return self._respond(response, ["Income Search", "RAG"], intent)

        # ── Cold-start comparison ─────────────────────────────────────────────
        if intent_type == "comparison" and not state.recommended_product:
            products = _extract_comparison_products(query, intent)
            if len(products) == 2:
                return self._respond(self._fetch_and_compare(products, intent, state), ["Comparison", "Comparator"], intent)
            return self._respond(
                ollama_chat(
                    system="Prime Bank assistant. Max 1 sentence.",
                    user=f"Customer wants to compare cards but didn't specify which. Available: {', '.join(get_all_product_names()[:4])}. Ask them to specify two cards to compare.",
                    temperature=0.5, max_tokens=60,
                ) or "Which two cards would you like to compare? Please name them both.",
                ["Intent Classifier"], intent, needs_clarification=True,
            )

        # ── Warm comparison ───────────────────────────────────────────────────
        if intent_type == "comparison" and state.recommended_product and state.alternative_products:
            products_list = self._extract_product_blocks(state.products_text) if state.products_text else []
            if len(products_list) >= 2:
                table = _comparator.build_comparison_table(products_list[:2], customer_profile=state.collected_profile)
                rec = _comparator.extract_recommended_product(table)
                if rec:
                    state.recommended_product = rec
                return self._respond(table, ["Comparator"], intent)

        # ── Direct how-to-apply (first message or mid-conversation) ─────────
        if _is_apply_query and intent.get("specific_product"):
            result = _get_how_to_apply(resolve_product_name(intent["specific_product"]), state)
            return self._respond(result, ["RAG", "Formatter"], intent)

        # ── Vague → profiling ─────────────────────────────────────────────────
        is_vague, missing = self.clarification_builder.needs_clarification(intent_type, intent, conversation_context={"query": query})
        if is_vague:
            if (state.preferred_tier and state.preferred_tier != "unknown") or (state.card_brand and state.card_brand != "unknown"):
                q = " ".join(filter(None, [state.card_brand, state.preferred_tier, "credit card"]))
                cards = rag_search_impl(query=q, banking_type=intent.get("banking_type") or "", tier=state.preferred_tier or "", top_k=15)
                if cards and cards != "NO_PRODUCTS_FOUND":
                    state.products_text = cards
                    self._store_products(cards, state)
                    formatted = _format_products(cards, query, "product_info")
                    return self._respond(formatted, ["Brand/Tier RAG"], intent)
            state.profiling_needed = True
            state.missing_profile_fields = missing
            # Ask only the first missing field to keep conversation natural
            first_field = missing[0]
            msg = self.clarification_builder.generate_contextual_question(first_field, state.collected_profile)
            return self._respond(msg, ["Smart Profiler"], intent, needs_clarification=True)

        # ── Eligibility check ─────────────────────────────────────────────────
        if intent.get("specific_product") and ("eligible" in query.lower() or "qualify" in query.lower()):
            intent["intent_type"] = "eligibility_check"
            intent_type = "eligibility_check"
        elif ("eligible" in query.lower() or "qualify" in query.lower()) and not intent.get("specific_product"):
            if state.recommended_product:
                intent["specific_product"] = state.recommended_product
                intent["intent_type"] = intent_type = "eligibility_check"
            elif state.products_text:
                for line in state.products_text.split('\n'):
                    if line.startswith('PRODUCT:'):
                        intent["specific_product"] = line.replace('PRODUCT:', '').strip()
                        intent["intent_type"] = intent_type = "eligibility_check"
                        break

        if intent_type == "eligibility_check":
            # Distinguish two sub-modes:
            # 1. "What are the requirements for X?" → info query, answer directly
            # 2. "Am I eligible?" / "Do I qualify?" → personal check, start collection
            q_lower = query.lower()
            is_personal_check = any(w in q_lower for w in (
                "am i", "do i", "can i", "will i", "would i", "i qualify", "i eligible",
                "my eligibility", "check my", "for me"
            ))
            specific_product = intent.get("specific_product", "")
            if not is_personal_check and specific_product:
                # Info query — fetch requirements and present them directly
                result = run_eligibility_info(
                    product_name=specific_product,
                    banking_type=intent.get("banking_type", ""),
                )
                return self._respond(result["result"], ["Eligibility", "RAG"], intent)
            # Personal eligibility check — start multi-turn collection
            question = start_eligibility_collection(intent, state)
            state._current_field = "age"
            return self._respond(question, ["Eligibility"], intent, needs_clarification=True)

        # ── Eligibility matching ──────────────────────────────────────────────
        if intent_type == "eligibility_matching":
            income = intent.get("customer_income")
            features = intent.get("specific_features", [])
            if not (income and features):
                msg = "To find matching products, I need:\n"
                if not income:    msg += "- Your monthly or annual income (BDT)\n"
                if not features:  msg += "- A specific feature (lounge, dining, rewards, EMI, etc.)\n"
                return self._respond(msg, ["Intent Classifier"], intent, needs_clarification=True)
            if income < 50000:
                income *= 12
            result = run_eligibility_matching(
                customer_age=int(intent.get("customer_age") or 25),
                customer_annual_income=int(income),
                customer_tenure_months=int(intent.get("customer_tenure_months") or 6),
                requested_feature=str(features[0] if isinstance(features, list) else features),
                banking_type=intent.get("banking_type", ""),
            )
            return self._respond(result["result"], ["Eligibility Matcher", "RAG"], intent)

        # ── Fallback: RAG + Crew ──────────────────────────────────────────────
        enriched = build_context_block(query, history, intent, state)
        response, retrieved = self.crew.run_agents(enriched_query=enriched, intent_type=intent_type, intent=intent, state=state)
        if retrieved:
            state.products_text = retrieved
            if intent_type == "comparison":
                state.comparison_done = True
        return self._respond(response, self._chain_label(intent_type), intent)

    # ── Eligibility turns ─────────────────────────────────────────────────────

    def _eligibility_turn(self, query, state, history):
        from pipelines.crew.eligibility import _extract_single_field, _build_confirmation, _ask_field_question, get_next_pending_field

        if not hasattr(state, '_confirmed_fields') or state._confirmed_fields is None:
            state._confirmed_fields = {}

        state.eligibility_chat.append({"role": "user", "content": query})
        current_field = getattr(state, '_current_field', None) or get_next_pending_field(state)

        if current_field:
            extracted = _extract_single_field(current_field, query, state._confirmed_fields)
            if extracted is not None:
                state._confirmed_fields[current_field] = extracted
                state.invalid_attempt_count = 0
                state.confirm_field_value(current_field, extracted, str(extracted))
                confirmation = _build_confirmation(current_field, extracted)
                print(f"✓ {current_field}={extracted}")

                next_field = get_next_pending_field(state)
                if next_field is None:
                    state._current_field = None
                    state.eligibility_chat.append({"role": "assistant", "content": f"{confirmation}\n\n✨ Checking eligibility now..."})
                    return self._run_eligibility_assessment(state)

                state._current_field = next_field
                reply = f"{confirmation}\n\n{_ask_field_question(next_field, dict(state._confirmed_fields), state)}"
            else:
                state.invalid_attempt_count = (state.invalid_attempt_count or 0) + 1
                print(f"⚠️ Could not extract '{current_field}' from: '{query[:50]}'")
                q = _ask_field_question(current_field, dict(state._confirmed_fields), state)
                reply = f"I didn't quite catch that. {q}" if state.invalid_attempt_count == 1 else q
                state._current_field = current_field
        else:
            return self._run_eligibility_assessment(state)

        state.eligibility_chat.append({"role": "assistant", "content": reply})
        return self._respond(reply, ["Eligibility"], state.intent, needs_clarification=True)

    def _run_eligibility_assessment(self, state):
        profile = build_eligibility_profile(state)
        enriched = f"Customer Query: Check eligibility for {state.eligibility_product}\nCustomer Profile:\n{profile}"
        response, retrieved = self.crew.run_agents(
            enriched_query=enriched, intent_type="eligibility_check",
            intent=state.intent, state=state, customer_profile=profile,
        )
        if retrieved:
            state.products_text = retrieved
        if state.eligibility_product:
            state.recommended_product = state.eligibility_product
        state.eligibility_done = True
        state.reset_eligibility()

        follow_up = (
            "\n\n**Next Steps:** Would you like to:\n1. Proceed with the application?\n2. Check eligibility for another card?\n3. Explore other options?"
            if ("eligible" in response.lower() or "qualify" in response.lower())
            else "\n\n**What would you like to do next?**\n1. Explore cards with different criteria\n2. Check eligibility for another card\n3. Learn how to become eligible"
        )
        return self._respond(response + follow_up, ["Eligibility Analyzer", "Formatter"], state.intent)

    # ── Profile collection ────────────────────────────────────────────────────

    def _collect_profile_info(self, query, state):
        known_parts = [f"{k}={v}" for k, v in state.collected_profile.items() if v not in (None, "")]
        known = ", ".join(known_parts) or "nothing yet"
        missing = ", ".join(state.missing_profile_fields)
        raw = ollama_chat(
            system="Extract profile data from the customer message. Return ONLY JSON, no markdown.",
            user=(
                f'Customer said: "{query}"\n'
                f'Already known: {known}\n'
                f'Need to extract: {missing}\n\n'
                "Extract ONLY what the customer mentioned. Map to these values:\n"
                "- banking_type: \'conventional\' or \'islami\' or null\n"
                "- primary_use_case: \'travel\'/\'dining\'/\'shopping\'/\'business\'/\'rewards\'/\'lifestyle\' or null\n"
                "  everyday/general/normal use → \'shopping\'\n"
                "  ummm maybe shopping → \'shopping\'\n"
                "- annual_income: integer BDT. If monthly multiply by 12. null if not mentioned\n""  Examples: 200k monthly=2400000, 100k monthly=1200000, 300k monthly=3600000\n"
                "- employment_type: \'salaried\'/\'business_owner\'/\'self_employed\'/\'student\' or null\n"
                "Return only the fields listed in \'Need to extract\' above.\n"
                "Example: {\"primary_use_case\": \"shopping\", \"annual_income\": null}"
            ),
            temperature=0.0, max_tokens=120,
        )
        extracted = parse_json(raw) or {}
        print(f"📊 Profile extracted: {extracted}")
        for field in list(state.missing_profile_fields):
            val = extracted.get(field)
            if val is not None and val != "null" and val != "":
                state.collected_profile[field] = val
                state.missing_profile_fields.remove(field)
                print(f"✓ Collected {field}={val}, remaining: {state.missing_profile_fields}")

    # ── Comparison helpers ────────────────────────────────────────────────────

    def _fetch_and_compare(self, product_names, intent, state):
        r1 = rag_search_impl(query=product_names[0], banking_type=intent.get("banking_type", ""), top_k=5)
        r2 = rag_search_impl(query=product_names[1], banking_type=intent.get("banking_type", ""), top_k=5)
        if not r1 or "NO_PRODUCTS_FOUND" in r1:
            return f"❌ Could not find '{product_names[0]}' in our database."
        if not r2 or "NO_PRODUCTS_FOUND" in r2:
            return f"❌ Could not find '{product_names[1]}' in our database."
        b1 = self._extract_product_blocks(r1)
        b2 = self._extract_product_blocks(r2)
        if not b1 or not b2:
            return "❌ Could not extract product data for comparison."
        state.products_text = r1 + "\n---\n" + r2
        state.recommended_product = product_names[0]
        state.alternative_products = [product_names[1]]
        state.comparison_done = True
        return _comparator.build_comparison_table([b1[0], b2[0]], customer_profile=state.collected_profile)

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _store_products(self, products_text, state):
        names = [l.replace('PRODUCT:', '').strip() for l in products_text.split('\n') if l.startswith('PRODUCT:') and l.replace('PRODUCT:', '').strip()]
        if names:
            state.recommended_product = names[0]
            state.alternative_products = names[1:] if len(names) > 1 else []
            state.shown_products_context = products_text

    def _extract_product_blocks(self, products_text):
        products, current = [], []
        for line in products_text.split('\n'):
            if line.startswith('PRODUCT:'):
                if current: products.append('\n'.join(current))
                current = [line]
            elif current:
                current.append(line)
        if current: products.append('\n'.join(current))
        return products

    def _chain_label(self, intent_type):
        return {
            "eligibility_matching":      ["Eligibility Matcher", "RAG"],
            "comparison":                ["RAG", "Comparator"],
            "feature_inquiry":           ["RAG", "Feature Analyst"],
            "product_search_by_income":  ["RAG", "Income Filter"],
            "eligibility_check":         ["Eligibility Analyzer"],
        }.get(intent_type, ["RAG", "Product Analyst"])

    def _respond(self, response, agent_chain, intent, needs_clarification=False):
        return {"response": response, "agent_chain": agent_chain, "needs_clarification": needs_clarification, "detected_intent": intent}
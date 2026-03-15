"""
Clarification builder for Prime Bank Chatbot
=============================================
Fixes applied:
- Tier bypass: checks both "preferred_tier" and "tier" keys, also checks intent dict directly
- Process query bypass: LLM detects FAQ/process queries (how to apply, approval time, documents,
  fees, minimum payment) and skips profiling — answers directly from RAG
- Brand bypass already present, kept as-is
"""

from typing import Optional, Dict, List, Tuple
from pipelines.rag.search import rag_search_impl
from utils.ollama import ollama_chat, parse_json


def _is_process_query(query: str) -> bool:
    """
    Use LLM to detect if the query is a process/FAQ question that should
    be answered directly without profiling the customer.
    Process queries: how to apply, approval timeline, required documents,
    fees & charges, minimum payment, interest rate, cash advance procedure, etc.
    """
    raw = ollama_chat(
        system="You are a classifier. Answer only yes or no.",
        user=f"""Does this query ask about a SPECIFIC FACT or procedure that applies to all cards equally,
with a single definitive answer from the knowledge base?

Query: "{query}"

Answer YES if the query asks about:
- How to apply (steps, process)
- Required documents (NID, E-TIN, salary slip)
- Approval timeline ("how long does it take")
- Fees and charges (annual fee, cash advance fee, late payment fee)
- Fee waiver conditions ("annual fee waiver", "how to waive fee")
- Minimum payment amount or calculation
- Interest rates or grace period mechanics
- Cash advance facility (how it works, fees)
- How reward points work or how to redeem
- How EMI works
- General terms that are the same across all/most cards

Answer NO if the query asks:
- Which card to get / recommend
- What cards are available
- Cards for a specific income level
- Cards with specific features
- Comparison between cards
- Anything requiring knowledge of customer's preferences

Answer only: yes or no""",
        temperature=0.0,
        max_tokens=5,
    )
    return raw.strip().lower().startswith("yes")


class DynamicClarificationBuilder:

    def needs_clarification(
        self,
        intent_type: str,
        extracted_profile: Dict,
        conversation_context: Optional[Dict] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Decide if profiling is needed before answering.

        Bypass rules (never ask profiling):
        - feature_inquiry          → feature already in intent
        - comparison               → products already in intent
        - product_info + specific_product named → answer directly
        - product_info + tier or brand present  → filter RAG, answer directly
        - product_search_by_income + income present → search directly
        - process/FAQ queries      → answer from RAG directly
        - eligibility_check        → eligibility flow handles its own collection
        - existing_cardholder      → cardholder agent handles it

        Ask profiling only for:
        - truly vague product_info (no product, no tier, no brand, no banking type)
        """

        # These intents manage their own flows
        if intent_type in ("feature_inquiry", "comparison", "eligibility_check", "existing_cardholder"):
            return False, []

        if intent_type == "product_search_by_income":
            income = extracted_profile.get("customer_income") or extracted_profile.get("annual_income")
            return (False, []) if income else (True, ["annual_income"])

        if intent_type == "product_info":
            # Named product → answer directly
            if extracted_profile.get("specific_product"):
                return False, []

            # Process / FAQ query → answer directly from RAG (high priority - bypass all profiling)
            query_text = (conversation_context or {}).get("query", "") or extracted_profile.get("query", "")
            if query_text and _is_process_query(query_text):
                return False, []

            # Tier present → filter by tier, answer directly
            tier = (extracted_profile.get("preferred_tier")
                    or extracted_profile.get("tier")
                    or (conversation_context or {}).get("preferred_tier", ""))
            if tier and tier not in ("unknown", ""):
                return False, []

            # Brand present → filter by brand, answer directly
            brand = (extracted_profile.get("card_brand")
                     or extracted_profile.get("brand")
                     or (conversation_context or {}).get("card_brand", ""))
            if brand and brand not in ("unknown", ""):
                return False, []

            # Banking type alone is NOT enough to skip profiling.
            # Customer still needs to tell us use case and income for a good recommendation.
            # Only skip if banking_type + at least one other signal present.
            banking = extracted_profile.get("banking_type", "unknown")
            banking_known = banking and banking not in ("unknown", "")
            use_case_known = bool(extracted_profile.get("primary_use_case"))
            income_known = bool(
                extracted_profile.get("customer_income")
                or extracted_profile.get("annual_income")
            )
            if banking_known and (use_case_known or income_known):
                return False, []

            # Truly vague → collect profile
            # Only ask for what we don't know yet
            missing = []
            if not banking_known:
                missing.append("banking_type")
            if not use_case_known:
                missing.append("primary_use_case")
            if not income_known:
                missing.append("annual_income")
            return (len(missing) > 0, missing)

        return False, []

    def get_dynamic_clarification_message(
        self,
        missing_fields: List[str],
        collected_profile: Dict,
        intent_type: str,
        conversation_context: Optional[Dict] = None,
        max_questions: int = 3,
    ) -> str:
        if not missing_fields:
            return ""

        known = ", ".join(f"{k}={v}" for k, v in collected_profile.items() if v and v != "unknown") or "nothing yet"
        field_hints = {
            "banking_type":       "conventional or Islamic (Shariah) banking preference",
            "primary_use_case":   "main card use (travel, dining, shopping, business, etc.)",
            "annual_income":      "monthly or annual income in BDT",
            "employment_type":    "employment type (salaried, self-employed, business owner, student)",
        }
        ask_about = "; ".join(field_hints.get(f, f) for f in missing_fields[:max_questions])

        return ollama_chat(
            system="You are a Prime Bank assistant. Ask clearly and warmly. Max 3 sentences.",
            user=f"Known about customer: {known}\nNeed to know: {ask_about}\nWrite a natural clarification message.",
            temperature=0.6, max_tokens=120,
        ) or f"To recommend the best card, could you share: {ask_about}?"

    def generate_contextual_question(self, field: str, collected_profile: Dict, conversation_context: Optional[Dict] = None) -> str:
        known = ", ".join(f"{k}={v}" for k, v in collected_profile.items() if v and v != "unknown") or "none"
        hints = {
            "banking_type":     "Do they prefer conventional or Islamic banking?",
            "primary_use_case": "What will they primarily use the card for? (travel, dining, shopping, business, etc.)",
            "annual_income":    "What's their monthly or annual income in BDT?",
            "employment_type":  "What's their employment type? (salaried, self-employed, business owner, student, etc.)",
        }
        return ollama_chat(
            system="Prime Bank assistant. Ask one natural, conversational question in 1-2 sentences. Be casual and friendly.",
            user=f"Known: {known}\nAsk about: {hints.get(field, field)}",
            temperature=0.6, max_tokens=60,
        ) or f"Could you share your {field.replace('_', ' ')}?"

    def find_matching_cards(
        self,
        banking_type: Optional[str] = None,
        use_case: Optional[str] = None,
        annual_income: Optional[int] = None,
        employment_type: Optional[str] = None,
        age: Optional[int] = None,
        preferred_tier: Optional[str] = None,
        top_n: int = 2,
    ) -> Optional[str]:
        parts = [p for p in [use_case, employment_type, preferred_tier] if p]
        if annual_income:
            parts.append("platinum" if annual_income >= 1500000 else "gold")
        if not parts:
            parts = ["credit card benefits rewards"]

        tier = preferred_tier or ("platinum" if (annual_income or 0) >= 1500000 else "gold")

        try:
            results = rag_search_impl(
                query=" ".join(parts),
                banking_type=banking_type or "",
                tier=tier,
                top_k=15,
                customer_income=annual_income,
            )
        except Exception as e:
            print(f"⚠️ find_matching_cards failed: {e}")
            return None

        if not results or results == "NO_PRODUCTS_FOUND":
            return None

        return self._top_n(results, top_n)

    def _top_n(self, results: str, n: int) -> str:
        products, current = [], []
        for line in results.split('\n'):
            if line.startswith('PRODUCT:'):
                if current:
                    products.append(current)
                current = [line]
            elif current:
                current.append(line)
        if current:
            products.append(current)
        return '\n'.join('\n'.join(p) for p in products[:n])

    # Kept for import compatibility
    def determine_question_sequence(self, missing_fields, collected_profile, intent_type):
        return missing_fields

    def should_skip_field(self, field, collected_profile, conversation_context=None):
        return False, None
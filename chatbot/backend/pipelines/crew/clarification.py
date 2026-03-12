from typing import Optional, Dict, List, Tuple
from pipelines.rag.search import rag_search_impl
from utils.ollama import ollama_chat, parse_json


class DynamicClarificationBuilder:

    def needs_clarification(
        self,
        intent_type: str,
        extracted_profile: Dict,
        conversation_context: Optional[Dict] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Decide if profiling is needed.

        Rules:
        - feature_inquiry          → never (feature already in intent)
        - product_search_by_income → never if income present; ask income only if missing
        - product_info + specific_product named → never
        - product_info truly vague → ask banking_type + use_case (+ income if missing)
        - comparison               → never
        - everything else          → never
        """
        if intent_type == "feature_inquiry":
            return False, []

        if intent_type == "product_search_by_income":
            income = extracted_profile.get("customer_income") or extracted_profile.get("annual_income")
            return (False, []) if income else (True, ["annual_income"])

        if intent_type == "product_info":
            if extracted_profile.get("specific_product"):
                return False, []
            # Customer already narrowed down by brand or tier — search directly, no profiling needed
            tier = extracted_profile.get("preferred_tier") or extracted_profile.get("tier")
            brand = extracted_profile.get("card_brand")
            if (tier and tier not in ("unknown", "")) or (brand and brand not in ("unknown", "")):
                return False, []
            missing = []
            if not extracted_profile.get("banking_type") or extracted_profile.get("banking_type") == "unknown":
                missing.append("banking_type")
            if not extracted_profile.get("primary_use_case"):
                missing.append("primary_use_case")
            if not (extracted_profile.get("customer_income") or extracted_profile.get("annual_income")):
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
            "banking_type":     "conventional or Islamic banking preference",
            "primary_use_case": "main use: travel, dining, shopping, business, etc.",
            "annual_income":    "monthly or annual income in BDT",
            "employment_type":  "salaried / self-employed / business owner / student",
        }
        return ollama_chat(
            system="Prime Bank assistant. One question, 1-2 sentences.",
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

    # ── Unused but kept for import compatibility ─────────────────────────────
    def determine_question_sequence(self, missing_fields, collected_profile, intent_type):
        return missing_fields

    def should_skip_field(self, field, collected_profile, conversation_context=None):
        return False, None
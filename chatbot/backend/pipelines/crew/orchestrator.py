from crewai import Crew
from agents import (
    eligibility_analyzer_agent,
    feature_comparator_agent,
    response_formatter_agent,
    alternative_product_recommender_agent,
)
from agents.cardholder_agent import existing_cardholder_agent
from agents.tasks import (
    analyze_eligibility_task,
    compare_features_task,
    format_response_task,
    recommend_alternatives_task,
    cardholder_service_task,
)
from pipelines.rag.search import rag_search_impl
from pipelines.rag.feature_expansion import expand_feature_query
from core import SessionState
from utils.cleanup import clean_response
from utils.ollama import ollama_chat


def _format_products(raw: str, query: str, intent_type: str) -> str:
    """Convert raw RAG text to clean customer-facing response."""

    # Trim raw to avoid token overflow while keeping key sections
    raw_trimmed = raw[:3500] if len(raw) > 3500 else raw

    instructions = {
        "search_by_category": (
            "The customer wants to see ALL cards in a category (brand, tier, or banking type). "
            "List EVERY product found in the data. For each: write its exact name as after 'PRODUCT:', "
            "then give credit limit, annual fee, and 2-3 key highlights in one line. "
            "Show ALL products — do not skip any. "
            "End by asking: Would you like full details on any of these cards?"
        ),
        "product_info": (
            "Present each PRODUCT found in the data above. "
            "For each: state its exact name as written after 'PRODUCT:', "
            "then list credit limit (exact BDT figure), annual fee, interest-free period, "
            "and top 3-4 benefits using the exact names and numbers from the data. "
            "If the data says BDT 700,000 write BDT 700,000 — never round or change. "
            "End by asking: Would you like details on any of these cards?"
        ),
        "feature_inquiry": (
            "The customer asked about a specific feature. "
            "List ONLY the cards in the data that have this feature. "
            "For each card: write its exact name, then quote the exact benefit description "
            "including numbers (e.g. '2 points per BDT 50', 'up to 36 months', "
            "'BDT 700,000 unsecured', 'Balaka VIP + 2 companions'). "
            "Copy numbers directly from the data — never paraphrase or omit them. "
            "End by asking: Would you like to know more about any of these cards?"
        ),
        "product_search_by_income": (
            "Based on the customer's income, show which cards they qualify for. "
            "For each card in the data: exact name, exact unsecured credit limit in BDT, "
            "annual fee (and waiver condition), interest-free period, and top 3 benefits "
            "with specific numbers from the data. "
            "End by asking: Would you like to apply for or learn more about any of these?"
        ),
    }

    rule = instructions.get(intent_type, instructions["product_info"])

    system = (
        "You are a Prime Bank product specialist. "
        "CRITICAL: Your response must be grounded 100% in the PRODUCT DATA below. "
        "If a number appears in the data, reproduce it exactly. "
        "If a product name appears after 'PRODUCT:', use that exact name. "
        "NEVER say 'not specified' or 'not mentioned' if the data contains the value. "
        "NEVER invent numbers, limits, or features not in the data. "
        "NEVER ignore a product that appears in the data."
    )

    user = (
        f"PRODUCT DATA (ground truth — use only this):\n"
        f"{raw_trimmed}\n\n"
        f"---\n"
        f"Customer asked: \"{query}\"\n\n"
        f"Task: {rule}"
    )

    return ollama_chat(
        system=system,
        user=user,
        temperature=0.1,
        max_tokens=800,
    ) or raw


class BankChatbotCrew:

    def run_agents(
        self,
        enriched_query: str,
        intent_type: str,
        state: SessionState,
        intent: dict | None = None,
        customer_profile: str = "",
    ) -> tuple[str, str | None]:
        intent = intent or {}
        needs_comparison  = intent_type == "comparison"
        needs_eligibility = intent_type == "eligibility_check"
        print(f"\n🎯 intent={intent_type}")

        # ── Cardholder service ───────────────────────────────────────────────
        if intent_type == "existing_cardholder":
            agent = existing_cardholder_agent()
            task  = cardholder_service_task(agent, enriched_query)
            result = clean_response(str(Crew(agents=[agent], tasks=[task], verbose=True, max_iter=3, memory=False).kickoff()))
            return result, None

        # ── Retrieve products ────────────────────────────────────────────────
        raw = ""
        product_types = ("product_info", "comparison", "feature_inquiry", "product_search_by_income", "search_by_category")

        if intent_type in product_types:
            if intent_type == "comparison" and state.has_products():
                raw = state.products_text or ""
            else:
                search_q = enriched_query
                if intent_type == "search_by_category":
                    # Build focused query from category signals
                    brand = intent.get("card_brand", "")
                    tier  = intent.get("preferred_tier", "")
                    bt    = intent.get("banking_type", "")
                    bt_str = "islami hasanah" if bt == "islami" else ("conventional" if bt == "conventional" else "")
                    brand_str = "" if brand in ("unknown", "") else brand
                    tier_str  = "" if tier  in ("unknown", "") else tier
                    search_q = " ".join(filter(None, [brand_str, tier_str, bt_str, "credit card overview features"]))

                elif intent_type == "feature_inquiry":
                    features = intent.get("specific_features", [])
                    if features:
                        # Use short focused query: feature names + card type
                        # Avoid over-expanded queries that confuse the embedder
                        feature_str = " ".join(features)
                        bt = intent.get("banking_type", "")
                        bt_str = "islami hasanah" if bt == "islami" else ("conventional" if bt == "conventional" else "")
                        tier_str = intent.get("preferred_tier", "") if intent.get("preferred_tier") not in ("unknown", "") else ""
                        search_q = " ".join(filter(None, [feature_str, bt_str, tier_str, "credit card"]))
                try:
                    raw = rag_search_impl(
                        query=search_q,
                        banking_type=intent.get("banking_type", ""),
                        tier=intent.get("preferred_tier") or intent.get("tier", ""),
                        top_k=15 if intent_type == "search_by_category" else (10 if needs_comparison else 6),
                        customer_income=intent.get("customer_income"),
                    )
                except Exception as e:
                    print(f"⚠️ RAG failed: {e}")

        if needs_eligibility:
            try:
                raw = rag_search_impl(
                    query=f"{enriched_query} eligibility requirements",
                    banking_type=intent.get("banking_type", ""),
                    tier=intent.get("preferred_tier") or intent.get("tier", ""),
                    top_k=6,
                )
            except Exception as e:
                print(f"⚠️ RAG eligibility failed: {e}")

        # ── Post-filter for search_by_category ──────────────────────────────
        # RAG embeddings don't respect brand — filter blocks by product_name
        if intent_type == "search_by_category" and raw and raw.strip() != "NO_PRODUCTS_FOUND":
            brand  = (intent.get("card_brand") or "").lower().strip()
            tier   = (intent.get("preferred_tier") or "").lower().strip()

            # brand aliases: "mastercard" matches "Mastercard World", "Mastercard Platinum"
            # tier aliases: "gold" matches "Visa Gold", "JCB Gold", "Visa Hasanah Gold"
            # combined: brand="visa" + tier="platinum" → only "Visa Platinum Credit Card"
            brand_map = {"mastercard": "mastercard", "visa": "visa", "jcb": "jcb"}
            tier_map  = {"gold": "gold", "platinum": "platinum", "world": "world", "silver": "silver"}

            brand_kw = brand_map.get(brand, "")
            tier_kw  = tier_map.get(tier, "")

            if brand_kw or tier_kw:
                # Split raw into per-product blocks and keep only matching ones
                blocks, current = [], []
                for line in raw.split("\n"):
                    if line.startswith("PRODUCT:"):
                        if current:
                            blocks.append("\n".join(current))
                        current = [line]
                    elif current:
                        current.append(line)
                if current:
                    blocks.append("\n".join(current))

                def _matches(block: str) -> bool:
                    # Extract product name from first line: "PRODUCT: Mastercard World Credit Card"
                    first = block.split("\n")[0].replace("PRODUCT:", "").strip().lower()
                    brand_ok = (not brand_kw) or (brand_kw in first)
                    tier_ok  = (not tier_kw)  or (tier_kw  in first)
                    return brand_ok and tier_ok

                filtered = [b for b in blocks if _matches(b)]
                raw = "\n\n".join(filtered) if filtered else raw

        cleaned = clean_response(raw) if raw else ""

        # ── Direct LLM format for simple product display ─────────────────────
        if intent_type in ("product_info", "feature_inquiry", "product_search_by_income", "search_by_category"):
            if not raw or not raw.strip():
                return "I couldn't find matching products. Could you rephrase or tell me more about what you're looking for?", None
            # Extract original customer question from enriched block
            customer_q = next(
                (l.replace("Customer Query:", "").strip().strip('"') for l in enriched_query.split("\n") if l.startswith("Customer Query:")),
                enriched_query
            )
            return _format_products(raw, customer_q, intent_type), cleaned or None

        # ── CrewAI for comparison / eligibility ──────────────────────────────
        agents, tasks = [], []

        comp_task = elig_task = rec_task = None

        if needs_comparison:
            comp = feature_comparator_agent()
            comp_task = compare_features_task(comp, enriched_query, "")
            agents.append(comp); tasks.append(comp_task)

        if needs_eligibility:
            elig = eligibility_analyzer_agent()
            elig_task = analyze_eligibility_task(elig, customer_profile=customer_profile or "No profile.", product_info=enriched_query)
            agents.append(elig); tasks.append(elig_task)

            rec = alternative_product_recommender_agent()
            rec_task = recommend_alternatives_task(rec, customer_profile=customer_profile or "No profile.", requested_product=enriched_query, ineligibility_reason="", retrieved_products=raw)
            agents.append(rec); tasks.append(rec_task)

        formatter = response_formatter_agent()
        fmt_task  = format_response_task(formatter, raw_outputs=cleaned or enriched_query, customer_message=enriched_query)
        agents.append(formatter); tasks.append(fmt_task)

        print(f"CrewAI: {[a.role for a in agents]}")
        result = clean_response(str(Crew(agents=agents, tasks=tasks, verbose=True, max_iter=5, memory=False).kickoff()))
        return result, cleaned or None
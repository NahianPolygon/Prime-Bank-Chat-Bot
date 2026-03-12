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
    instructions = {
        "product_info":              "Present each card with name, key features, BDT amounts. Bullet points.",
        "feature_inquiry":           "Name cards offering the feature. For each, describe exactly how it works with specific details and numbers.",
        "product_search_by_income":  "Show which cards the customer qualifies for. Include credit limit, annual fee, key benefits.",
        "comparison":                "Markdown table: Credit Limit | Annual Fee | Interest-Free | Lounge | Rewards | EMI. Fill every cell from the data.",
        "eligibility_check":         "State eligible or not, why, requirements met/missed, next steps.",
    }
    rule = instructions.get(intent_type, "Present the product information clearly with all features and BDT amounts.")
    return ollama_chat(
        system="You are a Prime Bank specialist. Use only the product data given. Include specific numbers and named features. No vague placeholders.",
        user=f'Customer asked: "{query}"\n\nProduct data:\n{raw}\n\nTask: {rule}\n\nEnd with 2-3 "What would you like to do?" options.',
        temperature=0.3, max_tokens=700,
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
        product_types = ("product_info", "comparison", "feature_inquiry", "product_search_by_income")

        if intent_type in product_types:
            if intent_type == "comparison" and state.has_products():
                raw = state.products_text or ""
            else:
                search_q = enriched_query
                if intent_type == "feature_inquiry":
                    features = intent.get("specific_features", [])
                    if features:
                        expanded = expand_feature_query(features, banking_type=intent.get("banking_type"))
                        if expanded:
                            search_q = expanded
                try:
                    raw = rag_search_impl(
                        query=search_q,
                        banking_type=intent.get("banking_type", ""),
                        tier=intent.get("tier", ""),
                        top_k=10 if needs_comparison else 6,
                        customer_income=intent.get("customer_income"),
                    )
                except Exception as e:
                    print(f"⚠️ RAG failed: {e}")

        if needs_eligibility:
            try:
                raw = rag_search_impl(
                    query=f"{enriched_query} eligibility requirements",
                    banking_type=intent.get("banking_type", ""),
                    tier=intent.get("tier", ""),
                    top_k=6,
                )
            except Exception as e:
                print(f"⚠️ RAG eligibility failed: {e}")

        cleaned = clean_response(raw) if raw else ""

        # ── Direct LLM format for simple product display ─────────────────────
        if intent_type in ("product_info", "feature_inquiry", "product_search_by_income"):
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
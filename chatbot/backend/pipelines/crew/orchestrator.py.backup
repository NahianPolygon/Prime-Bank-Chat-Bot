"""
Crew orchestrator — builds and runs agent chains.
"""

from crewai import Crew
from agents import (
    product_retriever_agent,
    eligibility_analyzer_agent,
    feature_comparator_agent,
    response_formatter_agent,
    alternative_product_recommender_agent,
)
from agents.cardholder_agent import existing_cardholder_agent
from agents.tasks import (
    retrieve_products_task,
    analyze_eligibility_task,
    compare_features_task,
    format_response_task,
    recommend_alternatives_task,
    cardholder_service_task,
)
from pipelines.rag.search import rag_search_tool, rag_search_impl
from pipelines.rag.feature_expansion import expand_feature_query
from core import SessionState
from utils.cleanup import clean_response


class BankChatbotCrew:
    """
    Orchestrates retriever, eligibility, comparison, and formatter agents.
    """

    def run_agents(
        self,
        enriched_query: str,
        intent_type: str,
        state: SessionState,
        intent: dict | None = None,
        customer_profile: str = "",
    ) -> tuple[str, str | None]:
        """
        Build and run the right agent chain. Returns (response, retrieved_products).

        ARCHITECTURAL FIX: Retrieve products directly in Python using rag_search_tool,
        then pass raw results to agents as context. This bypasses the 1.5B model's
        tendency to summarise product data into just names.
        """
        intent = intent or {}
        needs_comparison = intent_type == "comparison"
        needs_eligibility = intent_type == "eligibility_check"

        print(
            f"\n🎯 intent={intent_type} | comparison={needs_comparison} "
            f"| eligibility={needs_eligibility}"
        )

        # === CARDHOLDER SERVICE FLOW (existing cardholders) ===
        if intent_type == "existing_cardholder":
            print(f"🆔 Routing to cardholder service agent")
            cardholder_agent = existing_cardholder_agent()
            cardholder_task = cardholder_service_task(cardholder_agent, enriched_query)
            
            crew = Crew(
                agents=[cardholder_agent],
                tasks=[cardholder_task],
                verbose=True,
                max_iter=3,
                memory=False,
            )
            
            result = clean_response(str(crew.kickoff()))
            return result, None  # Cardholder queries don't store retrieved_products in session

        agent_list = []
        task_list = []

        # --- DIRECT PYTHON CALL: Retrieve products without using retriever agent ---
        # This ensures we get raw, complete product data instead of the 1.5B model
        # summarizing it into just product names
        retrieved_raw = ""
        retrieved_clean = ""

        if intent_type in ("product_info", "comparison", "feature_inquiry", "product_search_by_income"):
            print(f"📦 Calling rag_search_tool directly (no agent summarization)")
            
            # For comparisons of previously shown products, use session state products
            search_query = enriched_query
            if intent_type == "comparison" and state.has_products():
                print(f"  Using previously shown products for comparison")
                retrieved_raw = state.products_text
                retrieved_clean = clean_response(retrieved_raw) if retrieved_raw else ""
            else:
                # For feature_inquiry, use feature-optimized search query
                search_query = enriched_query
                if intent_type == "feature_inquiry":
                    features = intent.get("specific_features", [])
                    if features:
                        feature_optimized = expand_feature_query(
                            features,
                            banking_type=intent.get("banking_type"),
                            tier=intent.get("tier")
                        )
                        if feature_optimized:
                            print(f"  Feature-optimized query: {feature_optimized}")
                            search_query = feature_optimized
                
                try:
                    retrieved_raw = rag_search_impl(
                        query=search_query,
                        banking_type=intent.get("banking_type", ""),
                        tier=intent.get("tier", ""),
                        top_k=10 if needs_comparison else 6,
                        customer_income=intent.get("customer_income"),
                    )
                    retrieved_clean = clean_response(retrieved_raw) if retrieved_raw else ""
                    print(f"✓ Retrieved {len(retrieved_raw)} chars of raw product data")
                except Exception as e:
                    print(f"⚠️ Direct rag_search_tool call failed: {e}")
                    retrieved_raw = ""
                    retrieved_clean = ""

        # For eligibility, fetch requirements directly
        if needs_eligibility:
            print(f"📦 Calling rag_search_tool for eligibility requirements")
            try:
                retrieved_raw = rag_search_impl(
                    query=f"{enriched_query} eligibility requirements documents",
                    banking_type=intent.get("banking_type", ""),
                    tier=intent.get("tier", ""),
                    top_k=6,
                    customer_income=intent.get("customer_income"),
                )
                retrieved_clean = clean_response(retrieved_raw) if retrieved_raw else ""
                print(f"✓ Retrieved {len(retrieved_raw)} chars of eligibility data")
            except Exception as e:
                print(f"⚠️ Direct rag_search_tool call for eligibility failed: {e}")
                retrieved_raw = ""
                retrieved_clean = ""

        # === Build Agent Chain (WITHOUT retriever for product flows) ===
        # For product_info, comparison, feature_query: skip retriever agent entirely
        # These flows get the raw data passed to formatter/comparator

        # Comparator if needed (for comparison intent)
        comparison_task = None
        if needs_comparison:
            comparator = feature_comparator_agent()
            comparison_task = compare_features_task(comparator, enriched_query, "")
            agent_list.append(comparator)
            task_list.append(comparison_task)

        # Eligibility analyzer if needed
        eligibility_task = None
        recommender_task = None
        if needs_eligibility:
            elig_agent = eligibility_analyzer_agent()
            eligibility_task = analyze_eligibility_task(
                elig_agent,
                customer_profile=customer_profile or "No profile collected yet.",
                product_info=enriched_query,
            )
            agent_list.append(elig_agent)
            task_list.append(eligibility_task)
            
            # If ineligible for requested product, recommend alternatives
            # Extract ineligibility reason from customer profile and request
            ineligibility_reason = (
                f"Customer requested {intent.get('tier', 'unknown')} "
                f"{intent.get('banking_type', 'conventional')} card. "
                f"Eligibility check will determine if profile matches requirements."
            )
            
            recommender = alternative_product_recommender_agent()
            recommender_task = recommend_alternatives_task(
                recommender,
                customer_profile=customer_profile or "No profile collected yet.",
                requested_product=enriched_query,
                ineligibility_reason=ineligibility_reason,
                retrieved_products=retrieved_raw,  # Pass actual products from Chroma DB
            )
            agent_list.append(recommender)
            task_list.append(recommender_task)

        # Formatter always last — receives all previous task outputs via context=
        context_tasks = [t for t in [comparison_task, eligibility_task, recommender_task] if t]
        formatter = response_formatter_agent()
        formatter_task = format_response_task(
            formatter,
            raw_outputs=retrieved_clean or enriched_query,
            customer_message=enriched_query,
        )
        agent_list.append(formatter)
        task_list.append(formatter_task)

        print(f"Running: {[a.role for a in agent_list]}")

        crew = Crew(
            agents=agent_list,
            tasks=task_list,
            verbose=True,
            max_iter=5,
            memory=False,
        )

        result = clean_response(str(crew.kickoff()))

        # Return both the formatted response and the raw retrieved data
        return result, retrieved_clean if retrieved_clean else None

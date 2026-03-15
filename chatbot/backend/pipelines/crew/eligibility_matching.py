from pipelines.rag.search import rag_search_impl
from pipelines.rag.feature_expansion import expand_feature_query
from utils.ollama import ollama_chat


def run_eligibility_matching(
    customer_age: int,
    customer_annual_income: float,
    customer_tenure_months: int,
    requested_feature: str,
    banking_type: str = "",
) -> dict:
    expanded = expand_feature_query([requested_feature], banking_type=banking_type or None)
    search_q = expanded if expanded else requested_feature

    try:
        raw = rag_search_impl(query=search_q, banking_type=banking_type or "", tier="", top_k=10, customer_income=customer_annual_income)
    except Exception as e:
        raw = ""
        print(f"⚠️ RAG failed in eligibility matching: {e}")

    if not raw or raw.strip() == "NO_PRODUCTS_FOUND":
        return {
            "result": f"I couldn't find cards with '{requested_feature}'. Would you like to see all Prime Bank credit cards?",
            "customer_profile": {"age": customer_age, "annual_income": customer_annual_income, "tenure_months": customer_tenure_months},
            "requested_feature": requested_feature,
        }

    result = ollama_chat(
        system="Prime Bank eligibility specialist. Use only the product data given. Include specific feature details and BDT amounts.",
        user=(
            f"Customer: age {customer_age}, annual income BDT {customer_annual_income:,.0f}, "
            f"tenure {customer_tenure_months} months, wants: {requested_feature}\n\n"
            f"Product data:\n{raw}\n\n"
            "For each card: 1) Does it offer the feature? (specific details) "
            "2) Is customer eligible by income? (state the requirement) "
            "3) Recommend the best match. Give next steps."
        ),
        temperature=0.2, max_tokens=600,
    ) or f"Based on your profile, please visit a Prime Bank branch to confirm eligibility for {requested_feature} cards."

    return {
        "result": result,
        "customer_profile": {"age": customer_age, "annual_income": customer_annual_income, "tenure_months": customer_tenure_months},
        "requested_feature": requested_feature,
    }


def run_eligibility_info(product_name: str, banking_type: str = "") -> dict:
    """
    Fetch eligibility information for a specific product from RAG.
    Used for info queries like "What are the eligibility requirements for X card?"
    """
    search_query = f"eligibility requirements {product_name}"
    
    try:
        raw = rag_search_impl(
            query=search_query,
            banking_type=banking_type or "",
            tier="",
            top_k=5
        )
    except Exception as e:
        raw = ""
        print(f"⚠️ RAG failed in eligibility info: {e}")
    
    if not raw or raw.strip() == "NO_PRODUCTS_FOUND":
        return {
            "result": f"I couldn't find detailed eligibility information for {product_name}. Please visit a Prime Bank branch or contact our customer service for specific requirements.",
            "product": product_name,
        }
    
    result = ollama_chat(
        system="Prime Bank eligibility specialist. Extract and present only the eligibility requirements and criteria from the product information.",
        user=(
            f"For the {product_name} card, provide the eligibility requirements including:\n"
            f"- Minimum age\n"
            f"- Minimum annual income\n"
            f"- Employment requirements\n"
            f"- Tenure or credit history requirements\n"
            f"- Any other key eligibility criteria\n\n"
            f"Product information:\n{raw}"
        ),
        temperature=0.2,
        max_tokens=400,
    ) or f"Please contact Prime Bank directly for specific eligibility requirements of {product_name}."
    
    return {
        "result": result,
        "product": product_name,
    }


# Stub for import compatibility
def create_eligibility_matching_crew(*args, **kwargs):
    return None
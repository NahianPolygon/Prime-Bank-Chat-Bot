"""
RAG search tool for CrewAI agents.
"""

from typing import Dict, List, Any, Optional
from crewai.tools import tool

NO_PRODUCTS_SENTINEL = "NO_PRODUCTS_FOUND"

# Global state
_vector_db = None
_llm_config = None


def initialize_rag_tool(vector_db, llm_config: Dict[str, Any] = None) -> None:
    """
    Called once at startup. Injects the vector DB (and optionally LLM config)
    so both rag_search_tool and RAGPipeline can use them.

    Example in main.py:
        from rag_pipeline import initialize_rag_tool
        initialize_rag_tool(vector_db, config["llm"])
    """
    global _vector_db, _llm_config
    _vector_db = vector_db
    _llm_config = llm_config
    print("✓ RAG tool initialized")


@tool("rag_search_tool")
def rag_search_tool(
    query: str, 
    banking_type: str = "", 
    tier: str = "", 
    top_k: int = 6,
    customer_income: float = None
) -> str:
    """
    Search Prime Bank's product knowledge base and return COMPLETE product data.

    Call this tool ONCE. It handles searching, filtering, and formatting internally.

    Args:
        query:            What the customer is looking for, e.g. "conventional platinum credit card"
        banking_type:     "conventional" | "islami" | "" (no filter)
        tier:             "platinum" | "gold" | "silver" | "" (no filter)
        top_k:            Number of chunks to retrieve (default 6, use 8-10 for comparison)
        customer_income:  Customer's annual income in BDT (optional, used to rank/filter products)

    Returns:
        Complete product data grouped by product name, or NO_PRODUCTS_FOUND.
    """
    return rag_search_impl(query, banking_type, tier, top_k, customer_income)


def rag_search_impl(
    query: str, banking_type: str = "", tier: str = "", top_k: int = 6, customer_income: float = None
) -> str:
    """Direct callable implementation for Python code (bypasses @tool decorator)."""
    global _vector_db
    if _vector_db is None:
        return "ERROR: Vector DB not initialized. Call initialize_rag_tool() at startup."

    try:
        bt = (banking_type or "").strip().lower() or None
        if bt in ("unknown", "none", ""):
            bt = None
        if bt == "islamic":
            bt = "islami"

        t = (tier or "").strip().lower() or None
        if t in ("unknown", "none", ""):
            t = None

        # If customer income provided, add it to the query naturally
        # NO hardcoded income brackets - let semantic embeddings learn what products match each income level
        # This is fully dynamic: the KB chunks contain income-related language and embeddings will rank appropriately
        enriched_query = query
        if customer_income and customer_income > 0:
            # Pass raw annual income value to query - let embeddings find relevant products
            enriched_query = f"{query} annual income BDT {int(customer_income):,}"

        print(f"🔍 rag_search_tool: query='{enriched_query}' bt={bt} tier={t} top_k={top_k} income={customer_income}")

        # Build Chroma $and/$eq filter from bt/tier
        filter_parts = []
        if bt:
            filter_parts.append({"banking_type": {"$eq": bt}})
        if t:
            filter_parts.append({"tier": {"$eq": t}})
        chroma_filter = None
        if len(filter_parts) == 1:
            chroma_filter = filter_parts[0]
        elif len(filter_parts) == 2:
            chroma_filter = {"$and": filter_parts}

        results = _vector_db.search(enriched_query, top_k=top_k, filters=chroma_filter)

        if not results:
            print("🔍 rag_search_tool: no results")
            return NO_PRODUCTS_SENTINEL

        # Group by product name so each product appears as a clean block
        groups: Dict[str, List] = {}
        for r in results:
            name = r["metadata"].get("product_name", "Unknown Product")
            groups.setdefault(name, []).append(r)

        blocks = []
        for product_name, chunks in groups.items():
            lines = ["=" * 60, f"PRODUCT: {product_name}", "=" * 60]
            for chunk in chunks:
                section = chunk["metadata"].get("section", "General")
                lines += [f"\n[{section}]", chunk["content"]]
            blocks.append("\n".join(lines))

        print(f"🔍 rag_search_tool: {len(groups)} product(s): {list(groups.keys())}")
        return "\n\n".join(blocks)

    except Exception as e:
        print(f"🔍 rag_search_tool error: {e}")
        return f"ERROR: {e}"

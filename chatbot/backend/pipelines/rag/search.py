"""
RAG search tool for CrewAI agents.
"""

from typing import Dict, List, Any, Optional
from crewai.tools import tool

NO_PRODUCTS_SENTINEL = "NO_PRODUCTS_FOUND"

# Global state
_vector_db = None
_llm_config = None
_product_names_cache: list[str] | None = None


def initialize_rag_tool(vector_db, llm_config: Dict[str, Any] = None) -> None:
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

        enriched_query = query
        if customer_income and customer_income > 0:
            enriched_query = f"{query} annual income BDT {int(customer_income):,}"

        print(f"🔍 rag_search: query='{enriched_query}' bt={bt} tier={t} top_k={top_k} income={customer_income}")

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
            print("🔍 rag_search: no results")
            return NO_PRODUCTS_SENTINEL

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

        print(f"🔍 rag_search: {len(groups)} product(s): {list(groups.keys())}")
        return "\n\n".join(blocks)

    except Exception as e:
        print(f"🔍 rag_search error: {e}")
        return f"ERROR: {e}"


def get_all_product_names() -> list[str]:
    """
    Return all unique product names stored in ChromaDB.
    Cached after first call — safe to call repeatedly.
    """
    global _vector_db, _product_names_cache
    if _product_names_cache is not None:
        return _product_names_cache
    if _vector_db is None:
        return []
    try:
        result = _vector_db.collection.get(include=["metadatas"])
        names = sorted({m["product_name"] for m in result["metadatas"] if m.get("product_name")})
        _product_names_cache = names
        print(f"📦 {len(names)} products in ChromaDB: {names}")
        return names
    except Exception as e:
        print(f"⚠️ get_all_product_names failed: {e}")
        return []


def resolve_product_name(fuzzy_name: str, banking_type: str = "") -> str:
    """
    Resolve a fuzzy/partial product name to the canonical ChromaDB product_name.
    Does a top_k=1 semantic search — the closest match's metadata.product_name
    is the canonical name. No hardcoded product list.
    """
    global _vector_db
    if _vector_db is None:
        return fuzzy_name
    try:
        bt = (banking_type or "").strip().lower() or None
        if bt in ("unknown", "none", ""):
            bt = None
        if bt == "islamic":
            bt = "islami"
        chroma_filter = {"banking_type": {"$eq": bt}} if bt else None
        results = _vector_db.search(fuzzy_name, top_k=1, filters=chroma_filter)
        if results:
            canonical = results[0]["metadata"]["product_name"]
            print(f"🔍 Resolved '{fuzzy_name}' → '{canonical}'")
            return canonical
    except Exception as e:
        print(f"⚠️ resolve_product_name failed: {e}")
    return fuzzy_name
# tools/search_tools.py
from typing import Optional
from crewai.tools import tool

# Module-level DB reference - injected at startup
_vector_db = None

def set_vector_db(db):
    """Called once at startup to inject the shared VectorDB instance."""
    global _vector_db
    _vector_db = db


class SearchTools:

    @tool("search_products")
    def search_products(query: str, banking_type: Optional[str] = None, tier: Optional[str] = None) -> str:
        """
        Search for bank products based on query.

        Args:
            query: Search query
            banking_type: 'islami' or 'conventional'
            tier: 'gold', 'platinum', 'silver'

        Returns:
            Formatted product information
        """
        try:
            if _vector_db is None:
                return "Search unavailable: database not initialized."

            # Build Chroma-compatible where filter
            conditions = []
            if banking_type:
                conditions.append({"banking_type": {"$eq": banking_type.lower()}})
            if tier:
                conditions.append({"tier": {"$eq": tier.lower()}})

            if len(conditions) == 0:
                where_filter = None
            elif len(conditions) == 1:
                where_filter = conditions[0]
            else:
                where_filter = {"$and": conditions}

            results = _vector_db.search(query, filters=where_filter, top_k=3)

            if not results:
                return "No products found matching criteria."

            formatted = "Found Products:\n"
            for i, result in enumerate(results, 1):
                formatted += f"\n{i}. {result.get('product_name', 'Unknown')}\n"
                formatted += f"   Content: {result.get('content', 'N/A')[:200]}...\n"
            return formatted
        except Exception as e:
            return f"Search error: {str(e)}"

    @tool("get_product_details")
    def get_product_details(product_name: str) -> str:
        """
        Get detailed information about a specific product.

        Args:
            product_name: Name of the product

        Returns:
            Detailed product information
        """
        try:
            if _vector_db is None:
                return "Search unavailable: database not initialized."
            results = _vector_db.search(product_name, top_k=5)
            if not results:
                return f"No details found for {product_name}"
            details = f"Details for {product_name}:\n"
            for result in results:
                details += f"\n{result.get('section', 'Section')}\n"
                details += f"{result.get('content', 'N/A')}\n"
            return details
        except Exception as e:
            return f"Error retrieving details: {str(e)}"

    @tool("list_available_products")
    def list_available_products(banking_type: Optional[str] = None) -> str:
        """
        List all available products.

        Args:
            banking_type: Optional filter for 'islami' or 'conventional'

        Returns:
            List of available products
        """
        try:
            if _vector_db is None:
                return "Search unavailable: database not initialized."

            where_filter = {"banking_type": {"$eq": banking_type.lower()}} if banking_type else None

            results = _vector_db.search("credit card loan savings", filters=where_filter, top_k=50)
            products = sorted(set(r.get('product_name') for r in results if r.get('product_name')))

            if not products:
                return "No products available."
            return "Available Products:\n" + "\n".join(f"- {p}" for p in products)
        except Exception as e:
            return f"Error listing products: {str(e)}"

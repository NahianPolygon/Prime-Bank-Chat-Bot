"""Comparison and formatting tools for bank chatbot agents."""

from crewai.tools import tool
from typing import List, Dict, Any

# Module-level DB reference - injected at startup
_vector_db = None

def set_vector_db_for_comparison(db):
    """Called once at startup to inject the shared VectorDB instance."""
    global _vector_db
    _vector_db = db


class ComparisonTools:
    """Tools for comparing products and formatting responses."""
    
    @staticmethod
    def _extract_feature_value(content: str, feature_keywords: List[str]) -> str:
        """Extract feature value from product content."""
        content_lower = content.lower()
        for keyword in feature_keywords:
            if keyword.lower() in content_lower:
                # Try to find the sentence containing the keyword
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        # Return first 60 chars of the sentence
                        return sentence.strip()[:60]
        return "Not specified"
    
    @staticmethod
    def _get_product_details(product_name: str) -> Dict[str, Any]:
        """Fetch detailed information about a product from vector DB."""
        if _vector_db is None:
            return {}
        
        try:
            # Search for product details
            results = _vector_db.search(product_name, top_k=10)
            if not results:
                return {}
            
            # Aggregate product information
            product_info = {
                'product_name': product_name,
                'banking_type': results[0].get('banking_type', 'Unknown'),
                'product_type': results[0].get('product_type', 'Unknown'),
                'tier': results[0].get('tier', 'Unknown'),
                'use_cases': results[0].get('use_cases', ''),
                'employment_suitable': results[0].get('employment_suitable', ''),
                'features': {},
                'full_content': '\n'.join([r.get('content', '') for r in results])
            }
            
            # Extract common features from content
            feature_keywords = {
                'Interest Rate': ['interest rate', 'apr', '%'],
                'Annual Fee': ['annual fee', 'yearly fee', '$'],
                'Credit Limit': ['credit limit', '$'],
                'Rewards': ['reward', 'cashback', 'points'],
                'Insurance': ['insurance', 'coverage', 'protection'],
                'Support': ['24/7', 'support', 'customer service'],
                'Travel Benefits': ['travel', 'lounge', 'insurance'],
                'Flexibility': ['flexible', 'customizable']
            }
            
            for feature, keywords in feature_keywords.items():
                value = ComparisonTools._extract_feature_value(product_info['full_content'], keywords)
                product_info['features'][feature] = value
            
            return product_info
        except Exception as e:
            print(f"Error fetching product details: {str(e)}")
            return {}
    
    @tool("compare_products")
    def compare_products(product_names: List[str]) -> str:
        """
        Compare features between multiple products dynamically.
        
        Args:
            product_names: List of product names to compare
            
        Returns:
            Detailed comparison table
        """
        if not product_names:
            return "No products to compare."
        
        # Fetch product details
        products = {}
        for name in product_names:
            products[name] = ComparisonTools._get_product_details(name)
        
        if not products:
            return "Could not retrieve product details for comparison."
        
        # Build comparison table
        comparison = "## Product Comparison\n\n"
        
        # Feature matrix table
        all_features = set()
        for product_info in products.values():
            all_features.update(product_info.get('features', {}).keys())
        
        all_features = sorted(list(all_features))
        
        # Create markdown table
        comparison += "| Feature | " + " | ".join(product_names) + " |\n"
        comparison += "|---------|" + "|".join(["------" for _ in product_names]) + "|\n"
        
        for feature in all_features:
            comparison += f"| {feature} |"
            for name in product_names:
                value = products[name].get('features', {}).get(feature, "N/A")
                comparison += f" {value} |"
            comparison += "\n"
        
        # Add metadata summary
        comparison += "\n### Product Details Summary\n"
        for name in product_names:
            info = products[name]
            comparison += f"\n**{name}**\n"
            comparison += f"- Banking Type: {info.get('banking_type', 'N/A')}\n"
            comparison += f"- Product Type: {info.get('product_type', 'N/A')}\n"
            comparison += f"- Tier: {info.get('tier', 'N/A')}\n"
            if info.get('use_cases'):
                comparison += f"- Use Cases: {info.get('use_cases')}\n"
            if info.get('employment_suitable'):
                comparison += f"- Suitable For: {info.get('employment_suitable')}\n"
        
        return comparison
    
    @tool("create_comparison_table")
    def create_comparison_table(products: Dict[str, Dict[str, Any]]) -> str:
        """
        Create a detailed comparison table from product data.
        
        Args:
            products: Dictionary of products with their features
            
        Returns:
            Formatted comparison table
        """
        if not products:
            return "No products to compare."
        
        # If products dict has product names as keys, fetch details
        if isinstance(products, dict) and all(isinstance(v, str) for v in products.values()):
            # This is a dict of product names
            product_names = list(products.values())
            product_details = {}
            for name in product_names:
                product_details[name] = ComparisonTools._get_product_details(name)
            return ComparisonTools.compare_products(product_names)
        
        table = "## Product Comparison\n\n"
        table += "| Feature | " + " | ".join(products.keys()) + " |\n"
        table += "|---------|" + "|".join(["-" * 15 for _ in products.keys()]) + "|\n"
        
        all_features = set()
        for product_data in products.values():
            if isinstance(product_data, dict):
                all_features.update(product_data.keys())
        
        for feature in sorted(all_features):
            table += f"| {feature} |"
            for product_data in products.values():
                if isinstance(product_data, dict):
                    value = str(product_data.get(feature, "N/A"))[:40]
                else:
                    value = "N/A"
                table += f" {value} |"
            table += "\n"
        
        return table
    
    @tool("format_product_recommendation")
    def format_product_recommendation(product_name: str, 
                                     reason: str, 
                                     benefits: List[str]) -> str:
        """
        Format a product recommendation with dynamic details.
        
        Args:
            product_name: Name of recommended product
            reason: Why it's recommended
            benefits: List of key benefits
            
        Returns:
            Formatted recommendation
        """
        # Get product details
        product_info = ComparisonTools._get_product_details(product_name)
        
        recommendation = f"## Recommendation: {product_name}\n\n"
        recommendation += f"**Why this product?**\n{reason}\n\n"
        
        recommendation += "**Key Benefits:**\n"
        for benefit in benefits:
            recommendation += f"- {benefit}\n"
        
        # Add dynamic details
        if product_info:
            recommendation += "\n**Product Details:**\n"
            recommendation += f"- Banking Type: {product_info.get('banking_type', 'N/A')}\n"
            recommendation += f"- Tier: {product_info.get('tier', 'N/A')}\n"
            if product_info.get('employment_suitable'):
                recommendation += f"- Suitable For: {product_info.get('employment_suitable')}\n"
        
        return recommendation
    
    @tool("create_pros_cons_table")
    def create_pros_cons_table(product_name: str, 
                               pros: List[str] = None, 
                               cons: List[str] = None) -> str:
        """
        Create a pros and cons comparison with dynamic extraction.
        
        Args:
            product_name: Name of product
            pros: Optional list of advantages
            cons: Optional list of disadvantages
            
        Returns:
            Formatted pros/cons table
        """
        # Fetch product details
        product_info = ComparisonTools._get_product_details(product_name)
        
        # If pros/cons not provided, extract from features
        if not pros:
            pros = []
            if product_info.get('features'):
                for feature, value in product_info['features'].items():
                    if value and value != "Not specified":
                        pros.append(f"{feature}: {value}")
        
        if not cons:
            cons = ["Additional information not available in knowledge base"]
        
        table = f"## {product_name} - Pros & Cons\n\n"
        table += "| Advantages | Considerations |\n"
        table += "|-----------|----------------|\n"
        
        max_len = max(len(pros), len(cons)) if pros or cons else 1
        for i in range(max_len):
            pro = pros[i][:50] if i < len(pros) else "-"
            con = cons[i][:50] if i < len(cons) else "-"
            table += f"| {pro} | {con} |\n"
        
        return table

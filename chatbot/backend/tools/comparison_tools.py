"""Comparison and formatting tools for bank chatbot agents."""

from crewai.tools import tool
from typing import List, Dict, Any


class ComparisonTools:
    """Tools for comparing products and formatting responses."""
    
    @tool("compare_products")
    def compare_products(product_names: List[str]) -> str:
        """
        Compare features between multiple products.
        
        Args:
            product_names: List of product names to compare
            
        Returns:
            Comparison table
        """
        comparison = "Product Comparison:\n"
        comparison += "=" * 60 + "\n"
        comparison += f"{'Feature':<20} | {' | '.join(p[:15] for p in product_names)}\n"
        comparison += "-" * 60 + "\n"
        
        features = ['Interest Rate', 'Credit Limit', 'Annual Fee', 'Rewards', 'Insurance']
        
        for feature in features:
            comparison += f"{feature:<20} | "
            for product in product_names:
                comparison += f"{'TBD':<15} | "
            comparison += "\n"
        
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
        
        table = "## Product Comparison\n\n"
        table += "| Feature | " + " | ".join(products.keys()) + " |\n"
        table += "|---------|" + "|".join(["-" * (len(k) + 2) for k in products.keys()]) + "|\n"
        
        all_features = set()
        for product_data in products.values():
            all_features.update(product_data.keys())
        
        for feature in sorted(all_features):
            table += f"| {feature} |"
            for product_data in products.values():
                value = product_data.get(feature, "N/A")
                table += f" {value} |"
            table += "\n"
        
        return table
    
    @tool("format_product_recommendation")
    def format_product_recommendation(product_name: str, 
                                     reason: str, 
                                     benefits: List[str]) -> str:
        """
        Format a product recommendation.
        
        Args:
            product_name: Name of recommended product
            reason: Why it's recommended
            benefits: List of key benefits
            
        Returns:
            Formatted recommendation
        """
        recommendation = f"## Recommendation: {product_name}\n\n"
        recommendation += f"**Why this product?**\n{reason}\n\n"
        recommendation += "**Key Benefits:**\n"
        for benefit in benefits:
            recommendation += f"- {benefit}\n"
        
        return recommendation
    
    @tool("create_pros_cons_table")
    def create_pros_cons_table(product_name: str, 
                               pros: List[str], 
                               cons: List[str]) -> str:
        """
        Create a pros and cons comparison.
        
        Args:
            product_name: Name of product
            pros: List of advantages
            cons: List of disadvantages
            
        Returns:
            Formatted pros/cons table
        """
        table = f"## {product_name} - Pros & Cons\n\n"
        table += "| Pros | Cons |\n"
        table += "|------|------|\n"
        
        max_len = max(len(pros), len(cons))
        for i in range(max_len):
            pro = pros[i] if i < len(pros) else "-"
            con = cons[i] if i < len(cons) else "-"
            table += f"| {pro} | {con} |\n"
        
        return table

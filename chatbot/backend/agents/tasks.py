"""CrewAI Task definitions for bank chatbot."""

from crewai import Task
from textwrap import dedent
from typing import Any


class BankTasks:
    """Bank chatbot tasks using CrewAI."""
    
    def classify_intent_task(self, agent: Any, user_query: str) -> Task:
        """
        Task 1: Classify user intent and extract parameters.
        """
        return Task(
            description=dedent(f"""
                Analyze the customer's query and identify their intent and preferences.
                
                Extract the following information if present:
                - Intent: product_info, comparison, eligibility_check, or feature_query
                - Banking Type: Islamic (Shariah-compliant) or Conventional
                - Product Tier: Gold, Platinum, or Silver
                - Product Type: Credit Card, Debit Card, Savings Account, Loan, etc.
                - Use Cases: Shopping, Travel, Dining, Lifestyle, Business, Rewards, etc.
                
                Customer Query: "{user_query}"
                
                Provide a structured analysis of the intent and parameters.
                This information will guide product retrieval and recommendations.
            """),
            agent=agent,
            expected_output="Structured intent analysis with banking type, tier, and use cases identified"
        )
    
    def retrieve_products_task(self, agent: Any, intent: str, criteria: str) -> Task:
        """
        Task 2: Retrieve relevant products.
        """
        return Task(
            description=dedent(f"""
                Search for bank products that match the customer's needs.
                
                Search Criteria: {criteria}
                Intent: {intent}
                
                Steps:
                1. Use multiple search queries to find relevant products
                2. Filter by banking type (Islamic/Conventional) if specified
                3. Filter by tier (Gold/Platinum/Silver) if specified
                4. Retrieve detailed information for top 3-5 products
                5. Sort by relevance to the customer's needs
                
                For each product found, retrieve:
                - Product name
                - Key features
                - Interest rates / fees
                - Eligibility requirements
                - Special benefits
                
                Return a comprehensive list of matching products with details.
            """),
            agent=agent,
            expected_output="List of 3-5 relevant products with complete details and features"
        )
    
    def analyze_eligibility_task(self, agent: Any, products: str, customer_profile: str) -> Task:
        """
        Task 3: Analyze customer eligibility.
        """
        return Task(
            description=dedent(f"""
                Analyze whether the customer qualifies for the recommended products.
                
                Recommended Products: {products}
                
                Customer Profile: {customer_profile}
                
                Evaluation Criteria:
                1. Employment Type Compatibility
                2. Credit Score Requirements
                3. Income Requirements
                4. Document Requirements
                5. Age and Residency Requirements (if applicable)
                
                For each product, provide:
                - Eligibility Status (Eligible / Likely Eligible / Not Eligible)
                - Reasoning
                - Required Documents
                - Next Steps if not fully eligible
                
                Be honest but encouraging. If they don't qualify for premium products,
                suggest alternatives they might be eligible for.
            """),
            agent=agent,
            expected_output="Eligibility assessment for each product with requirements and next steps"
        )
    
    def compare_features_task(self, agent: Any, products: str) -> Task:
        """
        Task 4: Compare product features.
        """
        return Task(
            description=dedent(f"""
                Create a detailed comparison of the candidate products.
                
                Products to Compare: {products}
                
                Create comprehensive comparisons including:
                1. Interest Rates & Fees
                2. Credit Limits
                3. Reward Programs
                4. Additional Benefits (Insurance, Lounge Access, etc.)
                5. Processing Time
                6. Customer Support Quality
                7. Unique Features
                
                Format:
                - Create a comparison table for easy reading
                - Highlight key differences
                - Create pros and cons for each product
                - Indicate which product is best for which use case
                
                Make the comparison easy for customers to understand and compare options.
            """),
            agent=agent,
            expected_output="Detailed product comparison with tables, pros/cons, and use case matching"
        )
    
    def format_response_task(self, agent: Any, 
                            products_info: str,
                            eligibility_info: str,
                            comparison_info: str,
                            original_query: str) -> Task:
        """
        Task 5: Format final response for frontend.
        Takes output from all previous agents and formats into a clean, user-friendly response.
        """
        # Build description based on what information is available
        format_instructions = """
        Take the outputs from the previous agents and create a FINAL FORMATTED RESPONSE for the frontend.
        
        The response should be:
        - Clear and well-structured
        - Friendly and professional in tone
        - Easy to read with proper formatting
        - Actionable with next steps
        - Include all relevant information from previous agents
        """
        
        if eligibility_info != "not_requested":
            format_instructions += """
        Since eligibility analysis was performed:
        - Show which products the customer qualifies for
        - Highlight eligibility status clearly
        - Explain any requirements or next steps
        """
        
        if comparison_info != "not_requested":
            format_instructions += """
        Since feature comparison was performed:
        - Highlight key differences between products
        - Show which product is best for their use case
        - Include pros/cons or comparison table
        """
        
        format_instructions += f"""
        Original Customer Query: "{original_query}"
        
        Format the response as follows:
        1. **Summary**: Brief answer to their question
        2. **Recommended Products**: Top 1-3 products with WHY they're recommended
        3. **Key Features/Benefits**: What makes these products suitable
        4. {'4. **Eligibility Status**: Which products they qualify for' if eligibility_info != 'not_requested' else ''}
        5. {'4. **Product Comparison**: Key differences' if comparison_info != 'not_requested' else ''}
        6. **Next Steps**: How to apply, what documents needed, contact info
        
        Make it friendly, not robotic. Empower the customer to make a decision.
        """
        
        return Task(
            description=dedent(format_instructions),
            agent=agent,
            expected_output="Professional, well-formatted customer response ready for frontend display"
        )

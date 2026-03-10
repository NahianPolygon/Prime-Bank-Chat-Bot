"""
Vector DB-based clarification question builder and smart profiling.
Uses knowledge base metadata to understand customer needs and recommend cards.
"""

from typing import Optional, Dict, List, Tuple
from pipelines.rag.search import rag_search_impl
from utils.ollama import ollama_chat


class ClarificationBuilder:
    """
    Manages clarification questions for vague queries.
    Builds customer profile dynamically from vector DB and LLM.
    All questions are generated via LLM for natural, context-aware conversations.
    """
    
    # Fields needed for smart recommendation (in priority order)
    PROFILE_FIELDS_PRIORITY = ["banking_type", "primary_use_case", "annual_income", "employment_type"]
    
    @staticmethod
    def generate_clarification_question(field: str, collected_profile: Dict = None) -> str:
        """
        Generate a single clarification question dynamically using LLM based on context.
        
        Args:
            field: Which field to ask about (banking_type, primary_use_case, etc.)
            collected_profile: Profile data already collected
            
        Returns:
            Natural language question for the customer
        """
        collected_profile = collected_profile or {}
        
        # Build context about what we know already
        context_parts = []
        if collected_profile.get("primary_use_case"):
            context_parts.append(f"primary use case: {collected_profile['primary_use_case']}")
        if collected_profile.get("banking_type"):
            context_parts.append(f"banking preference: {collected_profile['banking_type']}")
        if collected_profile.get("annual_income"):
            context_parts.append(f"annual income: BDT {collected_profile['annual_income']:,}")
        
        context_str = "\n".join(context_parts) if context_parts else "no info collected yet"
        
        # Field-specific prompts
        field_prompts = {
            "banking_type": "Ask the customer if they prefer conventional banking or Shariah-compliant Islamic (Hasanah) cards. Be concise.",
            "primary_use_case": "Ask the customer what they primarily use their credit card for (e.g., travel, dining, business, rewards, lifestyle). Keep it to 1-2 sentences.",
            "annual_income": "Ask the customer for their annual income or monthly salary in BDT. Be specific about the unit. 1-2 sentences.",
            "employment_type": "Ask if they are salaried, self-employed, or a business owner. Keep it brief.",
        }
        
        prompt = field_prompts.get(field, f"Ask about {field}.")
        
        response = ollama_chat(
            system="You are a warm Prime Bank customer service assistant. Generate natural, concise questions to collect customer info.",
            user=f"""
Customer Profile So Far:
{context_str}

Question to Generate:
{prompt}

Write the question as you would ask it naturally. Max 2 sentences. NO explanations, just the question.""",
            temperature=0.6,
            max_tokens=100,
        )
        
        return response.strip() if response else f"Could you tell me about your {field.replace('_', ' ')}?"
    
    @staticmethod
    def get_clarification_questions(missing_fields: List[str], collected_profile: Dict = None) -> str:
        """Build clarification message with dynamically generated questions."""
        if not missing_fields:
            return ""
        
        collected_profile = collected_profile or {}
        
        # Prioritize banking_type first - it's critical for filtering
        prioritized = []
        if "banking_type" in missing_fields:
            prioritized.append("banking_type")
        
        for field in ClarificationBuilder.PROFILE_FIELDS_PRIORITY:
            if field in missing_fields and field != "banking_type":
                prioritized.append(field)
        
        # Generate questions dynamically
        questions = []
        for field in prioritized:
            q = ClarificationBuilder.generate_clarification_question(field, collected_profile)
            questions.append(q)
        
        if len(questions) == 1:
            return f"To recommend the best card for you:\n\n{questions[0]}"
        else:
            return f"To recommend the best card for you, I'd like to know:\n\n" + \
                   "\n\n".join([f"{i}. {q}" for i, q in enumerate(questions, 1)])

    @staticmethod
    def find_matching_cards(
        banking_type: Optional[str] = None,
        use_case: Optional[str] = None,
        annual_income: Optional[int] = None,
        employment_type: Optional[str] = None,
    ) -> str:
        """
        Query vector DB to find cards matching the customer profile.
        Returns raw product data from KB - LIMITED TO TOP 2 PRODUCTS.
        
        Income-aware tier mapping: Pass actual tier filter based on income level.
        
        Args:
            banking_type: "conventional" or "islamic"
            use_case: "travel", "dining", "business", etc.
            annual_income: Annual income in BDT (raw value)
            employment_type: "salaried" or "business_owner"
        
        Returns:
            Product data from KB as string (top 2 products only)
        """
        
        # Build search query based on profile
        search_parts = []
        
        if use_case:
            search_parts.append(use_case)
        
        if employment_type:
            search_parts.append(employment_type)
        
        # Determine tier based on income (for KB filtering)
        tier = ""
        if annual_income and annual_income > 0:
            if annual_income < 600000:
                tier = "gold"  # Entry-level: Gold cards
                search_parts.append("accessible entry-level beginner")
            elif annual_income < 1500000:
                tier = "gold"  # Mid-tier: Still Gold (can upgrade to Platinum based on features)
                search_parts.append("mid-tier standard suitable")
            else:
                tier = "platinum"  # Premium: Platinum cards
                search_parts.append("premium elite luxury")
        
        if not search_parts:
            search_parts.append("best credit card")
        
        search_query = " ".join(search_parts)
        
        # Search KB with profile
        try:
            results = rag_search_impl(
                query=search_query,
                banking_type=banking_type or "",
                tier=tier,  # Pass tier filter to RAG
                top_k=10,  # Retrieve more chunks to identify top products
                customer_income=annual_income,  # Also pass raw income to RAG for context
            )
            
            if not results or results == "NO_PRODUCTS_FOUND":
                return None
            
            # Parse results to extract unique products and limit to top 2
            # Format: "======\nPRODUCT: Name\n======\n[Section]\nContent\n\n"
            products = []
            current_product = None
            lines = results.split('\n')
            
            for i, line in enumerate(lines):
                if line.startswith('PRODUCT:'):
                    product_name = line.replace('PRODUCT:', '').strip()
                    if current_product:
                        products.append(current_product)
                    current_product = {'name': product_name, 'lines': ['=' * 60, line, '=' * 60]}
                elif current_product is not None:
                    current_product['lines'].append(line)
            
            # Add last product
            if current_product:
                products.append(current_product)
            
            # Limit to top 2 products
            top_2_products = products[:2]
            
            if not top_2_products:
                return None
            
            # Reassemble output with only top 2 products
            output_lines = []
            for product in top_2_products:
                output_lines.extend(product['lines'])
                output_lines.append('')  # Separator
            
            result = '\n'.join(output_lines).strip()
            tier_info = f"tier={tier}" if tier else "no tier"
            income_info = f"(yearly: BDT {annual_income:,})" if annual_income else ""
            print(f"🎯 Profiler: Found {len(products)} {tier_info} products, showing top 2: {[p['name'] for p in top_2_products]} {income_info}")
            return result
            
        except Exception as e:
            print(f"⚠️ Profile search failed: {e}")
            return None

    @staticmethod
    def needs_clarification(
        intent_type: str,
        extracted_profile: Dict,
    ) -> Tuple[bool, List[str]]:
        """
        Determine if clarification is needed for vague queries.
        
        Returns:
            (needs_clarification: bool, missing_fields: List[str])
        """
        
        # These intents might need clarification if vague
        vague_intents = ["product_info", "product_search_by_income"]
        
        if intent_type not in vague_intents:
            return False, []
        
        # Check what's already extracted
        missing = []
        
        # ALWAYS ask banking_type first - it's critical for recommendations
        banking_type = extracted_profile.get("banking_type", "").lower().strip()
        if not banking_type or banking_type == "unknown":
            missing.append("banking_type")
        
        # Check for income (can be stored as customer_income or annual_income)
        has_income = extracted_profile.get("customer_income") or extracted_profile.get("annual_income")
        
        # For product_search_by_income, must have income
        if intent_type == "product_search_by_income":
            if not has_income:
                missing.append("annual_income")
        
        # For generic product_info, check if very vague
        if intent_type == "product_info":
            # If no features and no income mentioned, need more info
            features = extracted_profile.get("specific_features", [])
            
            if not features and not has_income:
                # User just said "i want a card, which is best for me?"
                # Need: banking_type (already added), primary_use_case, income
                if "primary_use_case" not in missing:
                    missing.append("primary_use_case")
                if "annual_income" not in missing:
                    missing.append("annual_income")
        
        return len(missing) > 0, missing

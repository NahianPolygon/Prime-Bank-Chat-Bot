
from typing import Optional, Dict, List, Tuple
from pipelines.rag.search import rag_search_impl
from utils.ollama import ollama_chat, parse_json


class DynamicClarificationBuilder:
    """
    Context-aware clarification system that adapts to customer profile.
    
    Key features:
    1. Adaptive questioning based on demographics
    2. Intelligent field sequencing
    3. Skip redundant questions
    4. Reference previous answers naturally
    5. Tone adjustment by customer segment
    """
    
    def __init__(self):
        # Define field importance for different scenarios
        self.field_importance = {
            "product_search_by_income": ["banking_type", "annual_income", "primary_use_case"],
            "product_info": ["banking_type", "primary_use_case", "annual_income", "employment_type"],
            "comparison": ["banking_type", "primary_use_case"],
            "eligibility": ["annual_income", "employment_type", "banking_type"],
        }
    
    def generate_contextual_question(
        self,
        field: str,
        collected_profile: Dict,
        conversation_context: Optional[Dict] = None
    ) -> str:
        """
        Generate a fully dynamic question that adapts to everything we know.
        
        Args:
            field: Field to ask about
            collected_profile: All data collected so far
            conversation_context: Additional context (tone, urgency, etc.)
        
        Returns:
            Natural, contextual question
        """
        
        # Build rich context for LLM
        context_prompt = self._build_context_for_question(
            field=field,
            collected_profile=collected_profile,
            conversation_context=conversation_context or {}
        )
        
        # Generate question using LLM with full awareness
        prompt = f"""{context_prompt}

TASK: Generate a natural, contextual question to ask for: **{field}**

CRITICAL REQUIREMENTS:
1. Reference what you already know when relevant
2. Match the customer's demographic (age, employment affect phrasing)
3. Use appropriate examples for their segment
4. Keep it conversational (1-2 sentences max)
5. Don't repeat information they've already provided

FIELD-SPECIFIC GUIDANCE:
{self._get_field_guidance(field, collected_profile)}

OUTPUT: Just the question text. No preamble, no explanation."""

        response = ollama_chat(
            system="You are a skilled conversational AI that asks natural, contextual questions. Adapt your language to the customer's profile.",
            user=prompt,
            temperature=0.7,  # Higher for natural variety
            max_tokens=150,
        )
        
        return response.strip() if response else self._fallback_question(field)
    
    def _build_context_for_question(
        self,
        field: str,
        collected_profile: Dict,
        conversation_context: Dict
    ) -> str:
        """
        Build comprehensive context about the customer for question generation.
        """
        
        context_parts = ["CUSTOMER PROFILE:"]
        
        # Demographics
        age = collected_profile.get("age")
        if age:
            age_bracket = self._get_age_bracket(age)
            context_parts.append(f"- Age: {age} ({age_bracket})")
        
        employment = collected_profile.get("employment_type")
        if employment:
            context_parts.append(f"- Employment: {employment}")
        
        income = collected_profile.get("annual_income") or collected_profile.get("customer_income")
        if income:
            segment = self._get_income_segment(income)
            context_parts.append(f"- Income: BDT {income:,}/year ({segment})")
        
        # Banking preferences
        banking_type = collected_profile.get("banking_type")
        if banking_type and banking_type != "unknown":
            context_parts.append(f"- Banking preference: {banking_type}")
        
        # Use cases
        use_case = collected_profile.get("primary_use_case")
        if use_case:
            context_parts.append(f"- Primary use case: {use_case}")
        
        features = collected_profile.get("specific_features", [])
        if features:
            context_parts.append(f"- Interested in: {', '.join(features)}")
        
        # If no data collected yet
        if len(context_parts) == 1:
            context_parts.append("- (No information collected yet)")
        
        # Add conversation context
        if conversation_context:
            context_parts.append("\nCONVERSATION CONTEXT:")
            
            if conversation_context.get("tone"):
                context_parts.append(f"- Customer tone: {conversation_context['tone']}")
            
            if conversation_context.get("urgency"):
                context_parts.append(f"- Urgency level: {conversation_context['urgency']}")
            
            if conversation_context.get("previous_questions"):
                context_parts.append(f"- Previous questions asked: {', '.join(conversation_context['previous_questions'])}")
        
        return '\n'.join(context_parts)
    
    def _get_field_guidance(self, field: str, collected_profile: Dict) -> str:
        """
        Generate dynamic guidance for each field based on what we know.
        NOT hardcoded templates - context-aware instructions.
        """
        
        age = collected_profile.get("age")
        employment = collected_profile.get("employment_type")
        income = collected_profile.get("annual_income") or collected_profile.get("customer_income")
        
        # Build dynamic guidance
        guidance_parts = []
        
        if field == "banking_type":
            guidance_parts.append("Ask if they prefer conventional or Islamic (Shariah-compliant/Hasanah) banking.")
            
            if age and age < 30:
                guidance_parts.append("Younger customers: Keep it simple, 'conventional or Islamic banking?'")
            elif age and age > 50:
                guidance_parts.append("Older customers: May appreciate brief explanation of Islamic banking option.")
            
            if employment == "business_owner":
                guidance_parts.append("Business owners: Might care about Shariah compliance for business ethics.")
        
        elif field == "primary_use_case":
            guidance_parts.append("Ask what they'll mainly use the card for (travel, dining, shopping, business, etc.)")
            
            if employment == "salaried":
                guidance_parts.append("Salaried: Examples like 'daily expenses, dining, online shopping'")
            elif employment == "business_owner":
                guidance_parts.append("Business owner: Examples like 'business expenses, travel, supplier payments'")
            elif employment == "student":
                guidance_parts.append("Student: Examples like 'online shopping, dining, subscriptions'")
            
            if income and income > 1500000:
                guidance_parts.append("High earners: Mention premium options like 'travel, fine dining, luxury shopping'")
            elif income and income < 600000:
                guidance_parts.append("Budget conscious: Mention 'everyday shopping, groceries, bills'")
        
        elif field == "annual_income":
            guidance_parts.append("Ask for annual income or monthly salary in BDT.")
            
            if employment == "salaried":
                guidance_parts.append("Salaried: Ask for 'monthly salary' - more natural than annual")
            elif employment == "self_employed" or employment == "business_owner":
                guidance_parts.append("Self-employed/Business: Ask for 'annual income' - more appropriate")
            
            if age and age < 25:
                guidance_parts.append("Young customers: Might be entry-level, ask gently")
        
        elif field == "employment_type":
            guidance_parts.append("Ask if they're salaried, self-employed, business owner, or student.")
            
            if age and age < 25:
                guidance_parts.append("Young: More likely student or early career salaried")
            elif age and age > 40:
                guidance_parts.append("Mature: More likely established salaried or business owner")
        
        elif field == "tenure":
            guidance_parts.append("Ask how long they've been in current employment.")
            
            if employment == "business_owner":
                guidance_parts.append("Business owner: Ask 'how long have you been running your business?'")
            elif employment == "salaried":
                guidance_parts.append("Salaried: Ask 'how long have you been with your current employer?'")
        
        return '\n'.join(guidance_parts) if guidance_parts else f"Ask about their {field.replace('_', ' ')}."
    
    def _get_age_bracket(self, age: int) -> str:
        """Categorize age for context."""
        if age < 25:
            return "young professional/student"
        elif age < 35:
            return "young professional"
        elif age < 50:
            return "established professional"
        else:
            return "senior professional"
    
    def _get_income_segment(self, annual_income: int) -> str:
        """Categorize income for context."""
        if annual_income < 600000:
            return "entry-level"
        elif annual_income < 1500000:
            return "mid-tier"
        else:
            return "premium"
    
    def _fallback_question(self, field: str) -> str:
        """Simple fallback if generation fails."""
        fallbacks = {
            "banking_type": "Do you prefer conventional or Islamic banking?",
            "primary_use_case": "What will you primarily use the card for?",
            "annual_income": "What's your annual income in BDT?",
            "employment_type": "Are you salaried, self-employed, or a business owner?",
            "tenure": "How long have you been in your current job?",
        }
        return fallbacks.get(field, f"Could you tell me about your {field.replace('_', ' ')}?")
    
    def determine_question_sequence(
        self,
        missing_fields: List[str],
        collected_profile: Dict,
        intent_type: str
    ) -> List[str]:
        """
        Intelligently order questions based on context.
        
        Rules:
        1. Banking type almost always comes first (critical filter)
        2. Income comes early if intent is income-based
        3. Employment before tenure (tenure depends on employment)
        4. Use case adapts based on what's known
        
        Args:
            missing_fields: Fields we need to ask about
            collected_profile: What we already know
            intent_type: Type of query (affects priority)
        
        Returns:
            Ordered list of fields to ask about
        """
        
        # Get importance ranking for this intent
        importance = self.field_importance.get(
            intent_type,
            ["banking_type", "primary_use_case", "annual_income", "employment_type"]
        )
        
        # Filter to only missing fields, maintain importance order
        sequence = [f for f in importance if f in missing_fields]
        
        # Add any remaining missing fields not in importance list
        for field in missing_fields:
            if field not in sequence:
                sequence.append(field)
        
        # Apply contextual reordering
        sequence = self._apply_contextual_reordering(sequence, collected_profile, intent_type)
        
        return sequence
    
    def _apply_contextual_reordering(
        self,
        sequence: List[str],
        collected_profile: Dict,
        intent_type: str
    ) -> List[str]:
        """
        Reorder questions based on context for natural flow.
        """
        
        # Rule 1: Banking type almost always first (critical filter)
        if "banking_type" in sequence:
            sequence.remove("banking_type")
            sequence.insert(0, "banking_type")
        
        # Rule 2: For income-based searches, prioritize income early
        if intent_type == "product_search_by_income" and "annual_income" in sequence:
            # Move income to position 1 (after banking_type if present)
            sequence.remove("annual_income")
            insert_pos = 1 if "banking_type" in sequence else 0
            sequence.insert(insert_pos, "annual_income")
        
        # Rule 3: Employment before tenure (tenure depends on employment context)
        if "employment_type" in sequence and "tenure" in sequence:
            emp_idx = sequence.index("employment_type")
            ten_idx = sequence.index("tenure")
            if ten_idx < emp_idx:
                # Swap them
                sequence.remove("tenure")
                sequence.insert(emp_idx, "tenure")
        
        # Rule 4: If they mentioned business/employment in use case, skip employment question
        use_case = collected_profile.get("primary_use_case", "").lower()
        if "business" in use_case and "employment_type" in sequence:
            # Infer they're business owner
            collected_profile["employment_type"] = "business_owner"
            sequence.remove("employment_type")
        
        # Rule 5: If income is very high, skip tier-related questions
        income = collected_profile.get("annual_income") or collected_profile.get("customer_income")
        if income and income > 2000000:
            # They can afford any card, no need to ask about budget concerns
            if "tier_preference" in sequence:
                sequence.remove("tier_preference")
        
        return sequence
    
    def get_dynamic_clarification_message(
        self,
        missing_fields: List[str],
        collected_profile: Dict,
        intent_type: str,
        conversation_context: Optional[Dict] = None,
        max_questions: int = 3
    ) -> str:
        """
        Build a dynamic clarification message with context-aware questions.
        
        Args:
            missing_fields: Fields we need
            collected_profile: What we know
            intent_type: Query type
            conversation_context: Conversation state
            max_questions: Max questions to ask at once
        
        Returns:
            Natural clarification message
        """
        
        if not missing_fields:
            return ""
        
        # Determine intelligent question sequence
        sequence = self.determine_question_sequence(
            missing_fields=missing_fields,
            collected_profile=collected_profile,
            intent_type=intent_type
        )
        
        # Limit to max_questions to avoid overwhelming
        sequence = sequence[:max_questions]
        
        # Generate dynamic questions
        questions = []
        for field in sequence:
            question = self.generate_contextual_question(
                field=field,
                collected_profile=collected_profile,
                conversation_context=conversation_context
            )
            questions.append(question)
        
        # Build message with adaptive tone
        return self._format_clarification_message(
            questions=questions,
            collected_profile=collected_profile,
            conversation_context=conversation_context
        )
    
    def _format_clarification_message(
        self,
        questions: List[str],
        collected_profile: Dict,
        conversation_context: Optional[Dict]
    ) -> str:
        """
        Format the clarification message with adaptive tone.
        """
        
        if not questions:
            return ""
        
        # Determine tone based on profile
        age = collected_profile.get("age")
        employment = collected_profile.get("employment_type")
        
        # Choose intro based on context
        if age and age < 25:
            intro = "To find the perfect card for you, I'd like to know:"
        elif employment == "business_owner":
            intro = "To recommend the best card for your business needs:"
        else:
            intro = "To recommend the best card for you:"
        
        # Single question - direct
        if len(questions) == 1:
            return f"{intro}\n\n{questions[0]}"
        
        # Multiple questions - numbered or natural flow
        if len(questions) == 2:
            # Natural conjunction for 2 questions
            return f"{intro}\n\n{questions[0]}\n\nAnd {questions[1].lower()}"
        else:
            # Numbered list for 3+
            numbered = "\n\n".join([f"{i}. {q}" for i, q in enumerate(questions, 1)])
            return f"{intro}\n\n{numbered}"
    
    def should_skip_field(
        self,
        field: str,
        collected_profile: Dict,
        conversation_context: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Intelligently determine if a field can be skipped/inferred.
        
        Returns:
            (should_skip: bool, inferred_value: Optional[str])
        """
        
        # Check for implicit information
        use_case = collected_profile.get("primary_use_case", "").lower()
        age = collected_profile.get("age")
        
        # Skip employment if we can infer
        if field == "employment_type":
            if age and age < 22:
                return True, "student"
            if "business" in use_case or "company" in use_case:
                return True, "business_owner"
            if age and age > 65:
                return True, "retired"
        
        # Skip banking_type if they mentioned Islamic/Shariah/Hasanah
        if field == "banking_type":
            query = conversation_context.get("original_query", "").lower() if conversation_context else ""
            if any(word in query for word in ["islamic", "shariah", "hasanah", "halal"]):
                return True, "islamic"
            if any(word in query for word in ["conventional", "regular", "standard"]):
                return True, "conventional"
        
        # Skip tier if income is known (we can infer)
        if field == "tier":
            income = collected_profile.get("annual_income") or collected_profile.get("customer_income")
            if income:
                if income < 600000:
                    return True, "gold"
                elif income < 1500000:
                    return True, "gold"  # Can upgrade based on features
                else:
                    return True, "platinum"
        
        return False, None
    
    def needs_clarification(
        self,
        intent_type: str,
        extracted_profile: Dict,
        conversation_context: Optional[Dict] = None
    ) -> Tuple[bool, List[str]]:
        """
        Determine if clarification is needed with intelligent field detection.
        
        Returns:
            (needs_clarification: bool, missing_fields: List[str])
        """
        
        # Define all fields we'd like to collect per intent (prioritized)
        # First tier: minimally required
        # Additional tiers: ask for better recommendations
        all_fields_by_intent = {
            "product_info": ["banking_type", "primary_use_case", "annual_income"],
            "product_search_by_income": ["banking_type", "annual_income", "primary_use_case"],
            "comparison": ["banking_type", "primary_use_case"],
            "eligibility": ["annual_income", "employment_type"],
        }
        
        target_fields = all_fields_by_intent.get(intent_type, ["banking_type"])
        
        # Check what's missing
        missing = []
        for field in target_fields:
            value = extracted_profile.get(field)
            
            # Special handling for banking_type
            if field == "banking_type":
                if not value or value == "unknown" or value == "":
                    should_skip, inferred = self.should_skip_field(
                        field, extracted_profile, conversation_context
                    )
                    if should_skip:
                        extracted_profile[field] = inferred
                        continue
                    missing.append(field)
            
            # Special handling for income
            elif field == "annual_income":
                income = extracted_profile.get("customer_income") or extracted_profile.get("annual_income")
                if not income:
                    missing.append(field)
            
            # Generic check for other fields
            elif not value:
                should_skip, inferred = self.should_skip_field(
                    field, extracted_profile, conversation_context
                )
                if should_skip:
                    extracted_profile[field] = inferred
                    continue
                missing.append(field)
        
        return len(missing) > 0, missing
    
    def find_matching_cards(
        self,
        banking_type: Optional[str] = None,
        use_case: Optional[str] = None,
        annual_income: Optional[int] = None,
        employment_type: Optional[str] = None,
        age: Optional[int] = None,
        preferred_tier: Optional[str] = None,
        top_n: int = 2
    ) -> Optional[str]:
        """
        Enhanced card matching with demographic awareness.
        
        Args:
            banking_type: conventional or islamic
            use_case: travel, dining, business, etc.
            annual_income: Annual income in BDT
            employment_type: salaried, self_employed, business_owner
            age: Customer age (affects search emphasis)
            preferred_tier: "gold", "platinum", "silver" (if customer specified)
            top_n: Number of products to return
        
        Returns:
            Product data string with top N products
        """
        
        # Build search query with demographic awareness
        search_parts = []
        
        # Primary use case
        if use_case:
            search_parts.append(use_case)
        
        # Employment context
        if employment_type:
            search_parts.append(employment_type)
        
        # Age-based keywords
        if age:
            if age < 25:
                search_parts.append("student youth beginner entry-level")
            elif age < 35:
                search_parts.append("professional lifestyle modern")
            elif age > 50:
                search_parts.append("premium established exclusive")
        
        # Determine tier: prefer explicit preference, fallback to income-based
        tier = ""
        if preferred_tier and preferred_tier != "unknown":
            # User explicitly specified tier (e.g., "I want a platinum card")
            tier = preferred_tier
            search_parts.append(f"{preferred_tier} premium elite luxury exclusive concierge")
        elif annual_income:
            # Derive tier from income if no explicit preference
            if annual_income < 600000:
                tier = "gold"
                search_parts.append("affordable accessible entry-level value")
            elif annual_income < 1500000:
                tier = "gold"
                search_parts.append("mid-tier balanced standard rewards")
            else:
                tier = "platinum"
                search_parts.append("premium elite luxury exclusive concierge")
        
        if not search_parts:
            search_parts.append("best credit card benefits rewards")
        
        search_query = " ".join(search_parts)
        
        # Search with profile
        try:
            results = rag_search_impl(
                query=search_query,
                banking_type=banking_type or "",
                tier=tier,
                top_k=15,  # Get more to ensure variety
                customer_income=annual_income,
            )
            
            if not results or results == "NO_PRODUCTS_FOUND":
                return None
            
            # Parse and limit to top N
            products = self._parse_products(results)
            top_products = products[:top_n]
            
            if not top_products:
                return None
            
            # Reassemble
            output = self._format_products(top_products)
            
            income_str = f"{annual_income:,}" if annual_income else "unknown"
            age_str = str(age) if age else "unknown"
            print(f"🎯 Found {len(products)} products (tier={tier}), showing top {top_n}: "
                  f"{[p['name'] for p in top_products]} | "
                  f"income={income_str} BDT/year, age={age_str}")
            
            return output
            
        except Exception as e:
            print(f"⚠️ Card matching failed: {e}")
            return None
    
    def _parse_products(self, results: str) -> List[Dict]:
        """Parse product results into structured format."""
        products = []
        current_product = None
        
        for line in results.split('\n'):
            if line.startswith('PRODUCT:'):
                if current_product:
                    products.append(current_product)
                product_name = line.replace('PRODUCT:', '').strip()
                current_product = {'name': product_name, 'lines': ['=' * 60, line, '=' * 60]}
            elif current_product is not None:
                current_product['lines'].append(line)
        
        if current_product:
            products.append(current_product)
        
        return products
    
    def _format_products(self, products: List[Dict]) -> str:
        """Format products for output."""
        output_lines = []
        for product in products:
            output_lines.extend(product['lines'])
            output_lines.append('')
        return '\n'.join(output_lines).strip()


# ==================== USAGE EXAMPLE ====================

if __name__ == "__main__":
    """Example usage"""
    
    builder = DynamicClarificationBuilder()
    
    # Example 1: Young professional
    print("=" * 70)
    print("EXAMPLE 1: Young Professional (25, Salaried)")
    print("=" * 70)
    
    profile = {
        "age": 25,
        "employment_type": "salaried",
    }
    
    question = builder.generate_contextual_question(
        field="primary_use_case",
        collected_profile=profile,
        conversation_context={}
    )
    print(f"Question: {question}\n")
    
    # Example 2: Business Owner
    print("=" * 70)
    print("EXAMPLE 2: Business Owner (45, High Income)")
    print("=" * 70)
    
    profile = {
        "age": 45,
        "employment_type": "business_owner",
        "annual_income": 2500000,
    }
    
    question = builder.generate_contextual_question(
        field="banking_type",
        collected_profile=profile,
        conversation_context={}
    )
    print(f"Question: {question}\n")
    
    # Example 3: Full clarification message
    print("=" * 70)
    print("EXAMPLE 3: Multiple Missing Fields")
    print("=" * 70)
    
    profile = {
        "age": 30,
    }
    
    message = builder.get_dynamic_clarification_message(
        missing_fields=["banking_type", "primary_use_case", "annual_income"],
        collected_profile=profile,
        intent_type="product_info",
        max_questions=3
    )
    print(f"Clarification Message:\n{message}\n")
    
    # Example 4: Smart field skipping
    print("=" * 70)
    print("EXAMPLE 4: Smart Field Inference")
    print("=" * 70)
    
    profile = {
        "age": 21,
        "primary_use_case": "online shopping and food delivery",
    }
    
    should_skip, inferred = builder.should_skip_field(
        field="employment_type",
        collected_profile=profile,
        conversation_context={}
    )
    
    print(f"Should skip 'employment_type'? {should_skip}")
    print(f"Inferred value: {inferred}")
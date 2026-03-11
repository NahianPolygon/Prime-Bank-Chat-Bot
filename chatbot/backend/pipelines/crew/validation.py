from utils.ollama import ollama_chat, parse_json
from typing import Tuple, Dict, Any, Optional, List
from datetime import datetime


class DynamicInputValidator:
    
    def __init__(self, business_context: Optional[Dict[str, Any]] = None):
        """
        Initialize validator with optional business context.
        
        Args:
            business_context: Domain-specific rules, e.g.:
                {
                    "min_age_for_credit": 18,
                    "max_age_for_credit": 70,
                    "min_monthly_income_bdt": 25000,
                    "currencies_accepted": ["BDT", "USD"],
                    "employment_types": ["salaried", "self_employed", "business_owner", "student"],
                    "min_employment_months": 6
                }
        """
        self.business_context = business_context or self._default_business_context()
    
    @staticmethod
    def _default_business_context() -> Dict[str, Any]:
        """Default business rules for Prime Bank credit cards."""
        return {
            "product_type": "credit_cards",
            "bank_name": "Prime Bank Bangladesh",
            "min_age": 18,
            "max_age": 70,
            "min_monthly_income_bdt": 25000,
            "preferred_currency": "BDT",
            "employment_categories": ["salaried", "self_employed", "business_owner", "student", "retired"],
            "min_employment_duration_months": 6,
            "requires_tax_id": True,
            "country": "Bangladesh"
        }
    
    def validate_with_context(
        self,
        user_input: str,
        field_name: str,
        conversation_context: Optional[Dict[str, Any]] = None,
        previous_attempts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Universal validation method with full context awareness.
        
        Args:
            user_input: What the user said
            field_name: What we're validating (age, income, employment, etc.)
            conversation_context: Previous collected data and conversation state
            previous_attempts: List of previous invalid inputs (for better coaching)
        
        Returns:
            {
                "valid": bool,
                "extracted_value": Any,  # Structured data
                "confidence": float,  # 0.0 to 1.0
                "reasoning": str,  # Why LLM made this decision
                "coaching_message": str,  # What to tell the user
                "suggested_clarification": str,  # Optional follow-up question
                "metadata": dict  # Additional context for downstream processing
            }
        """
        conversation_context = conversation_context or {}
        previous_attempts = previous_attempts or []
        
        
        prompt = self._build_validation_prompt(
            user_input=user_input,
            field_name=field_name,
            conversation_context=conversation_context,
            previous_attempts=previous_attempts
        )
        
        
        raw_response = ollama_chat(
            system=self._get_system_prompt(field_name),
            user=prompt,
            temperature=0.1,  
            max_tokens=500,
        )
        
        
        parsed = parse_json(raw_response)
        
        if not parsed:
            return self._fallback_response(field_name, user_input)
        
        
        return self._enrich_validation_result(parsed, field_name, user_input, conversation_context)
    
    def _get_system_prompt(self, field_name: str) -> str:
        """
        Generate field-specific system prompt that teaches LLM the validation task.
        """
        return f"""You are an intelligent input validation assistant for {self.business_context['bank_name']}.

YOUR ROLE:
- Validate customer input for {field_name} in a {self.business_context['product_type']} application
- Make decisions based on business context, not rigid rules
- Provide warm, helpful coaching when input is unclear or invalid
- Extract structured data that can be used downstream

BUSINESS CONTEXT:
{self._format_business_context()}

VALIDATION PHILOSOPHY:
1. **Intent over format**: Understand what the user MEANS, not just what they wrote
2. **Contextual reasoning**: Use conversation history to disambiguate
3. **Graceful handling**: Never reject without explaining why and how to fix
4. **Cultural awareness**: Understand local expressions, currencies, and norms
5. **Progressive disclosure**: Ask for clarification incrementally, not all at once

OUTPUT REQUIREMENTS:
- Always return valid JSON
- Be definitive when confident, tentative when uncertain
- Provide specific, actionable coaching messages
- Include reasoning for transparency

Remember: You're helping real customers apply for financial products. Be helpful, patient, and clear."""

    def _format_business_context(self) -> str:
        """Format business context in a readable way for LLM."""
        lines = []
        for key, value in self.business_context.items():
            formatted_key = key.replace('_', ' ').title()
            lines.append(f"- {formatted_key}: {value}")
        return '\n'.join(lines)
    
    def _build_validation_prompt(
        self,
        user_input: str,
        field_name: str,
        conversation_context: Dict[str, Any],
        previous_attempts: List[str]
    ) -> str:
        """
        Build a rich, contextual validation prompt.
        This is where the magic happens - no hardcoded rules!
        """
        
        
        prompt_parts = [
            f"FIELD TO VALIDATE: {field_name}",
            f"USER INPUT: \"{user_input}\"",
            "",
            "CONVERSATION CONTEXT:",
        ]
        
        
        if conversation_context:
            for key, value in conversation_context.items():
                prompt_parts.append(f"- {key}: {value}")
        else:
            prompt_parts.append("- (No prior context)")
        
        prompt_parts.append("")
        
        
        if previous_attempts:
            prompt_parts.append("PREVIOUS INVALID ATTEMPTS:")
            for i, attempt in enumerate(previous_attempts, 1):
                prompt_parts.append(f"{i}. \"{attempt}\"")
            prompt_parts.append("")
            prompt_parts.append("NOTE: User has tried before. Be extra helpful and specific in your coaching.")
            prompt_parts.append("")
        
        
        field_guidance = self._get_field_guidance(field_name, conversation_context)
        prompt_parts.append(field_guidance)
        
        prompt_parts.append("")
        prompt_parts.append("OUTPUT FORMAT (valid JSON only):")
        prompt_parts.append(self._get_output_schema(field_name))
        
        return '\n'.join(prompt_parts)
    
    def _get_field_guidance(self, field_name: str, context: Dict[str, Any]) -> str:
        """
        Provide field-specific guidance to the LLM.
        This is NOT hardcoded rules - it's teaching the LLM what to think about.
        """
        
        guidance_templates = {
            "age": """
WHAT TO CONSIDER FOR AGE:
- Is this a number representing years old?
- Does it fall within reasonable bounds for credit applications ({min_age}-{max_age})?
- Did they mention something irrelevant (like their child's age)?
- Can you extract a number from words like "thirty-five" or "mid-forties"?
- If ambiguous, what clarification would help?

COMMON PATTERNS:
- Direct: "30", "thirty", "35 years old"
- Vague: "middle-aged", "in my 40s" → needs clarification
- Irrelevant: "my kid is 5" → clearly not their age
- Edge cases: "18" (barely eligible), "71" (over limit)
""".format(**self.business_context),
            
            "income": """
WHAT TO CONSIDER FOR INCOME:
- What currency? Assume {preferred_currency} unless stated otherwise
- Is this monthly or annual? Look for keywords or infer from amount
- Can you convert from common formats: "200k", "2 lakh", "BDT 50,000/month"?
- Is the amount reasonable for {country}? (Too low/high might be a typo)
- Do you need to ask for clarification about monthly vs annual?

COMMON PATTERNS:
- Clear: "200,000 BDT per month", "2.4 million annual", "50k monthly"
- Needs conversion: "5 lakh annual" → calculate monthly equivalent
- Ambiguous: "200k" → monthly or annual? Amount suggests monthly in {country}
- Invalid: "a lot", "enough", "varies" → needs specific number

BUSINESS LOGIC:
- Minimum acceptable: {min_monthly_income_bdt} BDT/month
- If annual given, divide by 12 for monthly
- If only number given, assume monthly unless unreasonably high
""".format(**self.business_context),
            
            "employment": """
WHAT TO CONSIDER FOR EMPLOYMENT:
- What category best describes their work situation?
- Valid categories: {employment_categories}
- Can you map their description to one of these categories?
- If unclear, what specific question would clarify?

COMMON PATTERNS:
- Clear: "full-time job" → salaried, "run my own business" → business_owner
- Needs mapping: "freelancer" → self_employed, "contractor" → self_employed
- Multiple categories: "part-time job + freelance" → ask which is primary
- Unclear: "between jobs", "taking a break" → needs clarification

CONTEXT AWARENESS:
- Previous context may hint at employment (e.g., they mentioned "office")
- Student status might have been mentioned earlier
- Look for consistency with other answers
""".format(**self.business_context),
            
            "tenure": """
WHAT TO CONSIDER FOR JOB TENURE:
- How long in current employment?
- Can you parse various formats: "2 years", "18 months", "since 2020"?
- Minimum required: {min_employment_duration_months} months
- Calculate total months from years + months if given separately

COMMON PATTERNS:
- Direct: "2 years", "18 months", "2 years 3 months"
- Needs calculation: "since Jan 2022" → calculate from today ({current_date})
- Unclear: "a while", "long time" → needs specific timeframe
- Edge case: "3 months" → valid input but below minimum, note this

CONTEXT AWARENESS:
- If they're self-employed/business owner, tenure = business age
- If student, tenure might not apply (note this)
- Cross-reference with employment type from context
""".format(
                min_employment_duration_months=self.business_context['min_employment_duration_months'],
                current_date=datetime.now().strftime("%B %Y")
            ),
            
            "tax_id": """
WHAT TO CONSIDER FOR TAX ID/E-TIN:
- Do they have it? (yes/no question)
- Can you interpret various ways of saying yes/no?
- If unclear, ask directly

COMMON PATTERNS:
- Yes: "yes", "have it", "i do", "already got one"
- No: "no", "don't have", "never got", "haven't"
- Unclear: "not sure", "maybe", "i think so" → needs verification

CONTEXT AWARENESS:
- If salaried → likely has E-TIN (employer issued)
- If self-employed/business → should have (required for tax filing)
- If student → probably doesn't have
""",
        }
        
        return guidance_templates.get(field_name, f"Validate the {field_name} field based on business context and common sense.")
    
    def _get_output_schema(self, field_name: str) -> str:
        """Define expected JSON output schema for each field type."""
        
        base_schema = """
{
  "valid": <boolean>,
  "confidence": <float 0.0-1.0>,
  "extracted_value": <structured data based on field type>,
  "reasoning": "<why you made this decision>",
  "coaching_message": "<what to tell user if invalid or uncertain>",
  "suggested_clarification": "<optional follow-up question>",
  "metadata": {
    "requires_confirmation": <boolean>,
    "severity": "info"|"warning"|"error",
    "alternative_interpretations": [<list of possible meanings>]
  }
}"""
        
        field_specific_examples = {
            "age": """
EXAMPLE for "thirty-five":
{
  "valid": true,
  "confidence": 0.95,
  "extracted_value": {"age_years": 35},
  "reasoning": "User clearly stated age as 'thirty-five', which is within acceptable range (18-70)",
  "coaching_message": "",
  "suggested_clarification": null,
  "metadata": {"requires_confirmation": false, "severity": "info"}
}

EXAMPLE for "in my 40s":
{
  "valid": false,
  "confidence": 0.6,
  "extracted_value": {"age_range": [40, 49], "age_years": null},
  "reasoning": "User gave age range, not specific age. Need exact number for application.",
  "coaching_message": "I see you're in your 40s. Could you give me your exact age? For example, are you 42, 45, or 48?",
  "suggested_clarification": "What's your exact age?",
  "metadata": {"requires_confirmation": true, "severity": "warning", "alternative_interpretations": ["Could be 40-49"]}
}""",
            
            "income": """
EXAMPLE for "200k per month":
{
  "valid": true,
  "confidence": 0.95,
  "extracted_value": {
    "monthly_bdt": 200000,
    "annual_bdt": 2400000,
    "currency": "BDT",
    "frequency": "monthly"
  },
  "reasoning": "Clear monthly income stated with 'k' suffix. Converted to full amount and calculated annual.",
  "coaching_message": "",
  "suggested_clarification": null,
  "metadata": {"requires_confirmation": true, "severity": "info"}
}

EXAMPLE for "5 lakh annual":
{
  "valid": true,
  "confidence": 0.9,
  "extracted_value": {
    "monthly_bdt": 41667,
    "annual_bdt": 500000,
    "currency": "BDT",
    "frequency": "annual",
    "conversion_applied": true
  },
  "reasoning": "Annual income in lakhs. Converted to BDT (1 lakh = 100,000) and calculated monthly (÷12).",
  "coaching_message": "Got it - your annual income is BDT 5 lakh (500,000). That's about BDT 41,667 per month. Is that correct?",
  "suggested_clarification": "Please confirm this is correct",
  "metadata": {"requires_confirmation": true, "severity": "info"}
}""",
            
            "employment": """
EXAMPLE for "full-time office job":
{
  "valid": true,
  "confidence": 0.95,
  "extracted_value": {
    "category": "salaried",
    "description": "full-time office job",
    "employment_type_confidence": "high"
  },
  "reasoning": "Clear indication of salaried employment with 'full-time' and 'office job'",
  "coaching_message": "",
  "suggested_clarification": null,
  "metadata": {"requires_confirmation": false, "severity": "info"}
}""",
        }
        
        return base_schema + "\n\n" + field_specific_examples.get(field_name, "")
    
    def _enrich_validation_result(
        self,
        parsed_result: Dict[str, Any],
        field_name: str,
        user_input: str,
        conversation_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enrich LLM response with additional metadata and safety checks.
        """
        
        enriched = {
            "valid": parsed_result.get("valid", False),
            "confidence": parsed_result.get("confidence", 0.0),
            "extracted_value": parsed_result.get("extracted_value"),
            "reasoning": parsed_result.get("reasoning", ""),
            "coaching_message": parsed_result.get("coaching_message", ""),
            "suggested_clarification": parsed_result.get("suggested_clarification"),
            "metadata": parsed_result.get("metadata", {}),
            
            
            "field_name": field_name,
            "original_input": user_input,
            "timestamp": datetime.now().isoformat(),
            "validation_version": "2.0_dynamic",
        }
        
        
        enriched["metadata"].update({
            "has_conversation_context": bool(conversation_context),
            "context_keys": list(conversation_context.keys()) if conversation_context else [],
        })
        
        return enriched
    
    def _fallback_response(self, field_name: str, user_input: str) -> Dict[str, Any]:
        """Graceful fallback when LLM fails to respond properly."""
        return {
            "valid": False,
            "confidence": 0.0,
            "extracted_value": None,
            "reasoning": "Failed to parse validation response",
            "coaching_message": f"I had trouble understanding that. Could you provide your {field_name} in a different way?",
            "suggested_clarification": f"What is your {field_name}?",
            "metadata": {
                "error": "llm_parse_failure",
                "severity": "error",
                "requires_confirmation": False,
            },
            "field_name": field_name,
            "original_input": user_input,
            "timestamp": datetime.now().isoformat(),
        }
    
    def validate_multi_field(
        self,
        user_input: str,
        expected_fields: List[str],
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate when user provides multiple pieces of information at once.
        
        Example: "I'm 30 years old and earn 200k per month"
        
        Returns:
            {
                "fields_found": ["age", "income"],
                "validations": {
                    "age": {...},
                    "income": {...}
                },
                "still_needed": ["employment", "tenure"],
                "coaching_message": "Great! I got your age and income. What about your employment?"
            }
        """
        prompt = f"""You are extracting multiple fields from a single user input.

USER INPUT: "{user_input}"

EXPECTED FIELDS: {', '.join(expected_fields)}

CONVERSATION CONTEXT:
{self._format_context(conversation_context)}

TASK:
1. Identify which fields the user provided information for
2. Extract the value for each field
3. Determine what's still missing
4. Generate a natural coaching message to ask for missing info

OUTPUT JSON:
{{
  "fields_found": [<list of field names found>],
  "extracted_data": {{
    "<field_name>": {{
      "value": <extracted value>,
      "confidence": <0.0-1.0>,
      "reasoning": "<why you extracted this>"
    }}
  }},
  "still_needed": [<list of missing fields>],
  "coaching_message": "<natural message to continue conversation>",
  "interpretation": "<how you understood the user's input>"
}}

EXAMPLE:
Input: "I'm 30 and make 200k a month"
Expected: ["age", "income", "employment"]
Output:
{{
  "fields_found": ["age", "income"],
  "extracted_data": {{
    "age": {{"value": 30, "confidence": 0.95, "reasoning": "Directly stated as '30'"}},
    "income": {{"value": {{"monthly_bdt": 200000}}, "confidence": 0.9, "reasoning": "200k per month in BDT"}}
  }},
  "still_needed": ["employment"],
  "coaching_message": "Perfect! You're 30 and earn BDT 200,000/month. What's your employment status?",
  "interpretation": "User provided age and monthly income clearly, but didn't mention employment"
}}"""
        
        raw = ollama_chat(
            system="You are a multi-field extractor. Return only valid JSON.",
            user=prompt,
            temperature=0.1,
            max_tokens=600,
        )
        
        parsed = parse_json(raw)
        if not parsed:
            return {
                "fields_found": [],
                "validations": {},
                "still_needed": expected_fields,
                "coaching_message": f"I'd like to know your {', '.join(expected_fields)}. Could you share those details?"
            }
        
        return parsed
    
    def _format_context(self, context: Optional[Dict[str, Any]]) -> str:
        """Format conversation context for prompts."""
        if not context:
            return "(No prior context)"
        
        lines = []
        for key, value in context.items():
            lines.append(f"- {key}: {value}")
        return '\n'.join(lines)


# ==================== USAGE EXAMPLES ====================

if __name__ == "__main__":
    """
    Example usage demonstrating dynamic validation
    """
    
    # Initialize with business context
    validator = DynamicInputValidator()
    
    # Example 1: Age validation with context
    print("=" * 60)
    print("EXAMPLE 1: Age Validation")
    print("=" * 60)
    
    result = validator.validate_with_context(
        user_input="I'm in my mid-thirties",
        field_name="age",
        conversation_context={"employment_type": "salaried"},
    )
    print(f"Valid: {result['valid']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Extracted: {result['extracted_value']}")
    print(f"Coaching: {result['coaching_message']}")
    
    # Example 2: Income with retry context
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Income with Retry")
    print("=" * 60)
    
    result = validator.validate_with_context(
        user_input="around 200k",
        field_name="income",
        conversation_context={"employment_type": "salaried", "age": 30},
        previous_attempts=["lots", "good amount"]
    )
    print(f"Valid: {result['valid']}")
    print(f"Extracted: {result['extracted_value']}")
    print(f"Coaching: {result['coaching_message']}")
    
    # Example 3: Multi-field extraction
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Multi-field Extraction")
    print("=" * 60)
    
    result = validator.validate_multi_field(
        user_input="I'm 30, work in an office, and make about 250k per month",
        expected_fields=["age", "employment", "income", "tenure"],
        conversation_context={}
    )
    print(f"Fields found: {result['fields_found']}")
    print(f"Still needed: {result['still_needed']}")
    print(f"Coaching: {result['coaching_message']}")
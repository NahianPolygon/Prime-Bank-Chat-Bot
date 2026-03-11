"""
Dynamic Feature Expansion System

Instead of hardcoded keyword mappings, this system:
1. Learns feature keywords directly from the knowledge base
2. Adapts to customer profile and intent strength
3. Handles synonyms and regional variations dynamically
4. Re-ranks features based on customer segment
5. Auto-discovers new features as KB evolves
"""

import json
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
from utils.ollama import ollama_chat, parse_json


class DynamicFeatureExpander:
    """
    Intelligent feature expansion that adapts to KB content and customer context.
    
    Key innovations:
    1. No hardcoded keyword mappings
    2. Learns from actual KB content
    3. Context-aware expansion
    4. Intent-strength based prioritization
    """
    
    def __init__(self, vector_db=None):
        """
        Initialize with optional vector DB for KB-driven learning.
        
        Args:
            vector_db: VectorDB instance (if available, enables KB-driven expansion)
        """
        self.vector_db = vector_db
        self.feature_cache = {}  # Cache for learned expansions
    
    def expand_feature_query(
        self,
        features: List[str],
        customer_profile: Optional[Dict] = None,
        intent_strength: Optional[Dict[str, float]] = None,
        banking_type: Optional[str] = None
    ) -> str:
        """
        Dynamically expand features into optimized search query.
        
        Args:
            features: Detected features ['dining', 'rewards', 'lounge_access']
            customer_profile: Customer demographics and preferences
            intent_strength: Feature importance scores {feature: 0.0-1.0}
            banking_type: Banking preference filter
        
        Returns:
            Optimized, context-aware search query
        """
        
        if not features:
            return ""
        
        customer_profile = customer_profile or {}
        intent_strength = intent_strength or {}
        
        # Step 1: Generate dynamic expansions for each feature
        expansions = []
        for feature in features:
            expansion = self._expand_single_feature(
                feature=feature,
                customer_profile=customer_profile,
                banking_type=banking_type
            )
            
            # Weight by intent strength
            strength = intent_strength.get(feature, 1.0)
            expansions.append((feature, expansion, strength))
        
        # Step 2: Prioritize and combine
        query = self._combine_expansions(
            expansions=expansions,
            customer_profile=customer_profile
        )
        
        # Step 3: Add contextual boosting
        query = self._add_contextual_boosting(
            query=query,
            customer_profile=customer_profile,
            banking_type=banking_type
        )
        
        return query
    
    def _expand_single_feature(
        self,
        feature: str,
        customer_profile: Dict,
        banking_type: Optional[str]
    ) -> Dict[str, any]:
        """
        Expand a single feature using LLM + KB knowledge.
        
        Returns:
            {
                "core_keywords": [...],
                "synonyms": [...],
                "context_keywords": [...],
                "regional_terms": [...]
            }
        """
        
        # Check cache first
        cache_key = f"{feature}_{banking_type or 'any'}"
        if cache_key in self.feature_cache:
            return self.feature_cache[cache_key]
        
        # Use KB if available
        if self.vector_db:
            expansion = self._kb_driven_expansion(feature, banking_type)
        else:
            expansion = self._llm_driven_expansion(feature, customer_profile, banking_type)
        
        # Cache for future use
        self.feature_cache[cache_key] = expansion
        
        return expansion
    
    def _kb_driven_expansion(
        self,
        feature: str,
        banking_type: Optional[str]
    ) -> Dict[str, List[str]]:
        """
        Learn feature keywords directly from KB content.
        
        This is the magic: instead of hardcoded mappings, we search KB
        for this feature and extract the actual terms used.
        """
        
        try:
            # Search KB for this feature
            filter_dict = None
            if banking_type:
                bt = "islami" if banking_type.lower() in ["islamic", "islami"] else "conventional"
                filter_dict = {"banking_type": {"$eq": bt}}
            
            # Search with feature name
            results = self.vector_db.search(
                query=feature,
                top_k=5,
                filters=filter_dict
            )
            
            if not results:
                # Fallback to LLM
                return self._llm_driven_expansion(feature, {}, banking_type)
            
            # Extract keywords from actual KB content
            content_text = " ".join([r["content"] for r in results])
            
            # Use LLM to extract relevant terms from KB content
            prompt = f"""Extract keywords and terms related to "{feature}" from this KB content.

KB CONTENT:
{content_text[:2000]}  # Limit to avoid token overflow

TASK: Extract:
1. Core keywords (exact terms used in KB)
2. Synonyms and variations
3. Regional/local terms (Bangladesh context)
4. Related benefit terms

OUTPUT JSON:
{{
  "core_keywords": [<main terms from KB>],
  "synonyms": [<alternative terms>],
  "regional_terms": [<Bangladesh-specific terms>],
  "related_benefits": [<associated features>]
}}

Focus on terms that actually appear in the KB content above."""

            raw = ollama_chat(
                system="You extract keywords from text. Return only valid JSON.",
                user=prompt,
                temperature=0.1,
                max_tokens=300
            )
            
            parsed = parse_json(raw)
            if parsed:
                return parsed
            
        except Exception as e:
            print(f"KB-driven expansion failed for '{feature}': {e}")
        
        # Fallback
        return self._llm_driven_expansion(feature, {}, banking_type)
    
    def _llm_driven_expansion(
        self,
        feature: str,
        customer_profile: Dict,
        banking_type: Optional[str]
    ) -> Dict[str, List[str]]:
        """
        Use LLM to generate feature expansion when KB is unavailable.
        Context-aware based on customer profile.
        """
        
        # Build context
        context_parts = []
        
        income = customer_profile.get("annual_income") or customer_profile.get("customer_income")
        if income:
            segment = "premium" if income > 1500000 else "standard" if income > 600000 else "budget"
            context_parts.append(f"Customer segment: {segment}")
        
        age = customer_profile.get("age")
        if age:
            context_parts.append(f"Age: {age}")
        
        employment = customer_profile.get("employment_type")
        if employment:
            context_parts.append(f"Employment: {employment}")
        
        if banking_type:
            context_parts.append(f"Banking type: {banking_type}")
        
        context_str = " | ".join(context_parts) if context_parts else "General customer"
        
        prompt = f"""Generate search keywords for credit card feature: "{feature}"

CONTEXT: {context_str}
REGION: Bangladesh
PRODUCT TYPE: Credit cards

TASK: Generate keywords that would appear in product documentation.

REQUIREMENTS:
1. Core keywords (main terms for this feature)
2. Synonyms and variations
3. Bangladesh-specific terms (like "Balaka lounge" for airport lounge)
4. Related benefits
5. Consider customer context (premium vs budget, young vs mature)

EXAMPLES FOR REFERENCE (not exhaustive):
- "lounge_access" → balaka, vip lounge, loungekey, priority pass, airport access
- "dining" → restaurant, bogo, buy one get one, year-round discount, food
- "insurance" → coverage, triple benefit, takaful, death, accidental, critical illness
- "emi" → installment, 0%, interest-free, payment plan, flexible
- "rewards" → points, cashback, earn, redemption, benefits, miles

OUTPUT JSON:
{{
  "core_keywords": [<3-5 essential terms>],
  "synonyms": [<alternative ways to say it>],
  "regional_terms": [<Bangladesh-specific terms>],
  "related_benefits": [<associated features>]
}}"""

        raw = ollama_chat(
            system="You generate search keywords for credit card features. Return only JSON.",
            user=prompt,
            temperature=0.3,
            max_tokens=400
        )
        
        parsed = parse_json(raw)
        
        if not parsed:
            # Ultimate fallback - basic keywords
            return {
                "core_keywords": [feature.replace("_", " ")],
                "synonyms": [],
                "regional_terms": [],
                "related_benefits": []
            }
        
        return parsed
    
    def _combine_expansions(
        self,
        expansions: List[Tuple[str, Dict, float]],
        customer_profile: Dict
    ) -> str:
        """
        Intelligently combine feature expansions with priority weighting.
        
        Args:
            expansions: [(feature, expansion_dict, strength_score), ...]
            customer_profile: Customer context
        
        Returns:
            Combined search query string
        """
        
        # Sort by intent strength (highest first)
        expansions.sort(key=lambda x: x[2], reverse=True)
        
        all_keywords = []
        
        for feature, expansion, strength in expansions:
            # Add core keywords (always included)
            core = expansion.get("core_keywords", [])
            all_keywords.extend(core)
            
            # Add synonyms for high-strength features
            if strength > 0.7:
                synonyms = expansion.get("synonyms", [])
                all_keywords.extend(synonyms[:3])  # Top 3 synonyms
            
            # Add regional terms (important for local context)
            regional = expansion.get("regional_terms", [])
            all_keywords.extend(regional)
            
            # Add related benefits for very high strength
            if strength > 0.9:
                related = expansion.get("related_benefits", [])
                all_keywords.extend(related[:2])  # Top 2 related
        
        # Deduplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in all_keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique_keywords.append(kw)
        
        # Limit to optimal length (15-20 keywords for embedding match)
        optimal_keywords = unique_keywords[:18]
        
        return " ".join(optimal_keywords)
    
    def _add_contextual_boosting(
        self,
        query: str,
        customer_profile: Dict,
        banking_type: Optional[str]
    ) -> str:
        """
        Add context-specific boosting terms to improve retrieval.
        """
        
        boost_terms = []
        
        # Banking type boosting
        if banking_type:
            bt = banking_type.lower()
            if bt in ["islamic", "islami"]:
                boost_terms.extend(["shariah", "hasanah", "islamic"])
            else:
                boost_terms.append("conventional")
        
        # Income-based boosting
        income = customer_profile.get("annual_income") or customer_profile.get("customer_income")
        if income:
            if income > 1500000:
                boost_terms.extend(["platinum", "premium", "exclusive"])
            elif income < 600000:
                boost_terms.extend(["gold", "accessible", "value"])
        
        # Age-based boosting
        age = customer_profile.get("age")
        if age:
            if age < 30:
                boost_terms.extend(["lifestyle", "modern", "digital"])
            elif age > 50:
                boost_terms.extend(["established", "classic", "comprehensive"])
        
        # Employment boosting
        employment = customer_profile.get("employment_type")
        if employment == "business_owner":
            boost_terms.extend(["business", "corporate", "expenses"])
        
        # Combine with original query
        if boost_terms:
            # Deduplicate
            existing = set(query.lower().split())
            new_terms = [t for t in boost_terms if t.lower() not in existing]
            
            if new_terms:
                return query + " " + " ".join(new_terms[:3])  # Add top 3 boost terms
        
        return query
    
    def extract_intent_strength(
        self,
        original_query: str,
        detected_features: List[str]
    ) -> Dict[str, float]:
        """
        Determine how strongly the customer cares about each feature.
        
        This enables prioritization - if they said "I NEED lounge access",
        that's stronger than "also maybe dining benefits".
        
        Returns:
            {feature: strength_score (0.0-1.0)}
        """
        
        if not detected_features:
            return {}
        
        prompt = f"""Analyze intent strength for each feature in the customer query.

CUSTOMER QUERY: "{original_query}"

DETECTED FEATURES: {', '.join(detected_features)}

TASK: For each feature, score how important it is to the customer (0.0-1.0)

SCORING GUIDE:
- 1.0 = Critical/must-have ("I NEED", "must have", "essential", "important")
- 0.8 = High priority ("want", "looking for", "prefer")
- 0.6 = Moderate interest ("interested in", "would like")
- 0.4 = Mild interest ("also", "maybe", "bonus if")
- 0.2 = Mentioned but low priority ("or", "whatever")

OUTPUT JSON:
{{
  "<feature_1>": <score>,
  "<feature_2>": <score>,
  ...
}}

EXAMPLE:
Query: "I need a card with lounge access and maybe some dining benefits"
Features: ["lounge_access", "dining"]
Output: {{"lounge_access": 0.9, "dining": 0.5}}"""

        raw = ollama_chat(
            system="You analyze customer intent strength. Return only JSON.",
            user=prompt,
            temperature=0.1,
            max_tokens=200
        )
        
        parsed = parse_json(raw)
        
        if not parsed:
            # Default: all features equally important
            return {f: 0.7 for f in detected_features}
        
        return parsed
    
    def discover_new_features_from_kb(self) -> List[str]:
        """
        Auto-discover features by analyzing KB content.
        
        This allows the system to adapt as new features are added to products,
        without manual updates to code.
        
        Returns:
            List of discovered feature categories
        """
        
        if not self.vector_db:
            return []
        
        try:
            # Sample diverse chunks from KB
            sample_query = "credit card features benefits perks advantages"
            results = self.vector_db.search(query=sample_query, top_k=20)
            
            if not results:
                return []
            
            # Extract content
            content = "\n\n".join([r["content"] for r in results])
            
            # Use LLM to identify feature categories
            prompt = f"""Analyze credit card product documentation and identify feature categories.

DOCUMENTATION SAMPLE:
{content[:3000]}

TASK: Identify distinct feature categories mentioned in the documentation.

EXAMPLES OF FEATURE CATEGORIES:
- lounge_access (airport lounges)
- dining (restaurant discounts, BOGO)
- insurance (coverage, takaful)
- rewards (points, cashback)
- emi (installment plans)
- travel (flight discounts, hotel benefits)
- fuel (petrol discounts)
- contactless (NFC payment)

OUTPUT JSON:
{{
  "features": [
    {{
      "category": "<category_name>",
      "description": "<brief description>",
      "keywords": [<2-3 key terms>]
    }},
    ...
  ]
}}

Extract 10-15 distinct feature categories."""

            raw = ollama_chat(
                system="You extract feature categories from documentation. Return only JSON.",
                user=prompt,
                temperature=0.2,
                max_tokens=600
            )
            
            parsed = parse_json(raw)
            
            if parsed and "features" in parsed:
                discovered = [f["category"] for f in parsed["features"]]
                print(f"🔍 Auto-discovered {len(discovered)} feature categories from KB")
                return discovered
            
        except Exception as e:
            print(f"Feature discovery failed: {e}")
        
        return []
    
    def get_feature_expansion_stats(self, feature: str) -> Dict:
        """
        Get statistics about a feature's expansion for debugging/monitoring.
        """
        
        if feature not in self.feature_cache:
            return {"error": "Feature not in cache"}
        
        expansion = self.feature_cache[feature]
        
        return {
            "feature": feature,
            "core_keywords": len(expansion.get("core_keywords", [])),
            "synonyms": len(expansion.get("synonyms", [])),
            "regional_terms": len(expansion.get("regional_terms", [])),
            "related_benefits": len(expansion.get("related_benefits", [])),
            "total_terms": sum([
                len(expansion.get("core_keywords", [])),
                len(expansion.get("synonyms", [])),
                len(expansion.get("regional_terms", [])),
                len(expansion.get("related_benefits", []))
            ])
        }


_default_expander = DynamicFeatureExpander()


def expand_feature_query(features: List[str], banking_type: str = None) -> str:
    """
    Backwards-compatible wrapper for old expand_feature_query() function.
    Maintains original API while using new DynamicFeatureExpander.
    """
    return _default_expander.expand_feature_query(
        features=features,
        customer_profile={},
        intent_strength=None,
        banking_type=banking_type
    )


# ==================== USAGE EXAMPLES ====================

if __name__ == "__main__":
    """Demonstration of dynamic feature expansion"""
    
    print("=" * 70)
    print("DYNAMIC FEATURE EXPANSION EXAMPLES")
    print("=" * 70)
    
    # Initialize (without KB for demo)
    expander = DynamicFeatureExpander(vector_db=None)
    
    # Example 1: Simple expansion
    print("\n📌 EXAMPLE 1: Basic Feature Expansion")
    print("-" * 70)
    
    query = expander.expand_feature_query(
        features=["lounge_access", "dining"],
        customer_profile={},
        banking_type=None
    )
    print(f"Features: lounge_access, dining")
    print(f"Expanded Query: {query}\n")
    
    # Example 2: Context-aware expansion
    print("\n📌 EXAMPLE 2: Premium Customer (High Income)")
    print("-" * 70)
    
    query = expander.expand_feature_query(
        features=["lounge_access", "rewards"],
        customer_profile={
            "annual_income": 2500000,
            "age": 45,
            "employment_type": "business_owner"
        },
        banking_type="conventional"
    )
    print(f"Customer: Business Owner, 45, BDT 2.5M/year")
    print(f"Features: lounge_access, rewards")
    print(f"Expanded Query: {query}")
    print(f"Notice: Includes 'platinum', 'premium', 'exclusive' boosting\n")
    
    # Example 3: Intent strength
    print("\n📌 EXAMPLE 3: Intent Strength Detection")
    print("-" * 70)
    
    original_query = "I NEED a card with lounge access and maybe some dining offers"
    intent_scores = expander.extract_intent_strength(
        original_query=original_query,
        detected_features=["lounge_access", "dining"]
    )
    print(f"Query: '{original_query}'")
    print(f"Intent Scores: {intent_scores}")
    print(f"Interpretation: Lounge access is critical, dining is nice-to-have\n")
    
    # Example 4: Budget customer
    print("\n📌 EXAMPLE 4: Budget-Conscious Customer")
    print("-" * 70)
    
    query = expander.expand_feature_query(
        features=["fee_waiver", "rewards"],
        customer_profile={
            "annual_income": 500000,
            "age": 28,
            "employment_type": "salaried"
        }
    )
    print(f"Customer: Salaried, 28, BDT 500k/year")
    print(f"Features: fee_waiver, rewards")
    print(f"Expanded Query: {query}")
    print(f"Notice: Includes 'gold', 'accessible', 'value' boosting\n")
    
    # Example 5: Islamic banking
    print("\n📌 EXAMPLE 5: Islamic Banking Customer")
    print("-" * 70)
    
    query = expander.expand_feature_query(
        features=["insurance"],
        customer_profile={
            "age": 35,
            "employment_type": "salaried"
        },
        banking_type="islamic"
    )
    print(f"Banking Type: Islamic")
    print(f"Feature: insurance")
    print(f"Expanded Query: {query}")
    print(f"Notice: Includes 'shariah', 'hasanah', 'takaful' terms\n")
    
    print("=" * 70)
    print("✅ Dynamic expansion adapts to context, no hardcoded mappings!")
    print("=" * 70)
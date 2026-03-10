"""
Feature-optimized query expansion for feature_inquiry intents.
Converts raw customer queries to KB-optimized search queries.
"""

# Mapping of detected features to KB search keywords
FEATURE_TO_KEYWORDS = {
    "insurance": "triple benefit insurance takaful coverage death accidental critical",
    "lounge_access": "balaka vip lounge access loungekey priority pass",
    "dining": "dining bogo restaurants year-round buy one get one free",
    "credit_limit": "credit limit unsecured collateralized maximum highest",
    "emi": "emi installment 0% 36 months interest-free payment plan",
    "rewards": "reward points cashback earning redemption benefits",
    "airport_benefits": "airport vip assistance welcome exclusive access",
    "fee_waiver": "annual fee waiver free supplementary cards",
    "interest_free": "interest-free period grace days payment",
    "travel": "travel lounge airport flight booking luggage",
}

def expand_feature_query(features: list, banking_type: str = None) -> str:
    """
    Convert array of features into optimized RAG search query.
    
    Args:
        features: List of detected features ['dining', 'rewards', 'lounge_access']
        banking_type: "conventional" or "islami" (optional filter)
    
    Returns:
        Optimized search query for RAG
    """
    if not features:
        return ""
    
    # Combine keywords from all detected features
    keywords = []
    for feature in features:
        feature_lower = str(feature).lower().strip()
        if feature_lower in FEATURE_TO_KEYWORDS:
            keywords.extend(FEATURE_TO_KEYWORDS[feature_lower].split())
    
    # Add banking type if specified
    if banking_type:
        banking_type_lower = banking_type.lower().strip()
        if banking_type_lower == "conventional":
            keywords.append("conventional")
        elif banking_type_lower in ("islamic", "islami"):
            keywords.extend(["islamic", "shariah", "hasanah"])
    
    # Deduplicate and join (limit to 15 keywords for best embedding match)
    unique_keywords = list(dict.fromkeys(keywords))[:15]
    search_query = " ".join(unique_keywords)
    
    return search_query


# Test examples
if __name__ == "__main__":
    print("Feature Query Expansion Examples:\n")
    
    examples = [
        (["insurance"], None),
        (["lounge_access"], None),
        (["dining"], None),
        (["emi"], None),
        (["dining", "rewards"], None),
        (["emi", "insurance"], None),
        (["lounge_access"], "conventional"),
        (["dining"], "islami"),
    ]
    
    for features, banking in examples:
        expanded = expand_feature_query(features, banking)
        print(f"Features: {features} | Banking: {banking}")
        print(f"→ Query: {expanded}\n")

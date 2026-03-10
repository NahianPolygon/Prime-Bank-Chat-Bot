"""
Cardholder service URLs and configurations.
Centralized mapping of cardholder service types to URLs and metadata.
"""

CARDHOLDER_URLS = {
    "activate_card": {
        "url": "https://www.primebank.com.bd/card-activation",
        "keywords": ["activate", "activation", "active"],
        "service_name": "Card Activation",
        "description": "How to activate your credit card"
    },
    
    "setup_pin": {
        "url": "https://www.primebank.com.bd/generate-card-pin-with-myprime",
        "keywords": ["pin", "password", "setup pin", "generate pin", "reset pin", "forgot pin"],
        "service_name": "PIN Setup",
        "description": "How to setup or reset your card PIN"
    },
    
    "endorse_card": {
        "url": None,
        "keywords": ["endorse", "endorsement"],
        "service_name": "Card Endorsement",
        "description": "Card endorsement requires visiting your nearest branch",
        "alternative": "branch"
    },
    
    "report_damage": {
        "url": None,
        "keywords": ["damaged", "damage", "broken"],
        "service_name": "Report Damaged Card",
        "description": "Get your damaged card replaced",
        "alternative": "branch"
    },
    
    "report_stolen": {
        "url": None,
        "keywords": ["stolen", "lost", "block", "freeze"],
        "service_name": "Report Stolen/Lost Card",
        "description": "Block your card immediately",
        "alternative": "contact",
        "contact": "16218",
        "urgent": True
    },
    
    "bill_payment": {
        "url": None,
        "keywords": ["bill payment", "bill", "payment", "pay bill", "dues"],
        "service_name": "Bill Payment",
        "description": "Pay your credit card bill",
        "alternative": "app",
        "app_name": "MyPrime"
    },
    
    "limit_tracking": {
        "url": None,
        "keywords": ["limit", "credit limit", "limit tracking", "available limit", "utilization"],
        "service_name": "Credit Limit Tracking",
        "description": "Check your credit limit and utilization",
        "alternative": "app",
        "app_name": "MyPrime"
    },
    
    "transaction_history": {
        "url": None,
        "keywords": ["transaction", "history", "statement", "transactions"],
        "service_name": "Transaction History",
        "description": "View your transaction history",
        "alternative": "app",
        "app_name": "MyPrime"
    },
    
    "privilege_offers_dining": {
        "url": "https://www.primebank.com.bd/year-round-discount",
        "keywords": ["dining", "restaurant", "food", "discount", "dine"],
        "service_name": "Year-Round Dining Discounts",
        "description": "Year-round dining and travel discounts"
    },
    
    "privilege_offers_emi": {
        "url": "https://www.primebank.com.bd/emi-discount",
        "keywords": ["emi", "installment", "0%", "zero interest", "no interest"],
        "service_name": "0% EMI Options",
        "description": "0% EMI installment plans"
    },
    
    "privilege_offers": {
        "url": None,
        "keywords": ["offer", "privilege", "benefit"],
        "service_name": "Card Offers",
        "description": "Various card offers and privileges",
        "clarification_needed": True,
        "options": [
            {"name": "Year-Round Discounts", "keywords": ["dining", "travel", "discount"]},
            {"name": "0% EMI Options", "keywords": ["emi", "installment", "0%"]}
        ]
    },
    
    "faq": {
        "url": "https://www.primebank.com.bd/assets/downloads/1750936903_Prime-Bank-Hasanah-Credit-Card-FAQ.pdf",
        "keywords": ["faq", "question", "help", "how does", "frequently asked"],
        "service_name": "FAQ",
        "description": "Frequently Asked Questions about credit cards",
        "topics": [
            "Primary and Supplementary Cards",
            "Fees, Charges and Payment Related Queries",
            "Credit Limit",
            "Cash Advance",
            "Transaction Cut-off and Endorsement",
            "Airport and Lounge Facilities",
            "E-Commerce",
            "Reward Points & Loyalty Program",
            "Card Security and Information Protection"
        ]
    },
    
    "terms_conditions": {
        "url": "https://www.primebank.com.bd/Cards-T&C-SOC",
        "keywords": ["terms", "conditions", "t&c", "soc", "schedule of charges", "charges"],
        "service_name": "Terms & Conditions",
        "description": "Terms & Conditions and Schedule of Charges",
        "documents": [
            "Credit Card Terms & Conditions (Conventional)",
            "Credit Card Terms & Conditions (Islamic)",
            "Credit Card Schedule of Charges",
            "Debit Card & ATM Terms & Conditions",
            "Debit Card & ATM Schedule of Charges"
        ]
    }
}


def get_service_by_keyword(keyword: str) -> dict:
    """
    Find cardholder service by keyword.
    Returns the matching service or None.
    """
    keyword_lower = keyword.lower().strip()
    
    for service_key, service_data in CARDHOLDER_URLS.items():
        if any(kw in keyword_lower for kw in service_data["keywords"]):
            return {
                "service_type": service_key,
                "service_name": service_data["service_name"],
                "url": service_data.get("url"),
                "description": service_data.get("description"),
                "alternative": service_data.get("alternative"),
                "contact": service_data.get("contact"),
                "urgent": service_data.get("urgent", False),
                "app_name": service_data.get("app_name"),
                "clarification_needed": service_data.get("clarification_needed", False),
                "options": service_data.get("options"),
                "topics": service_data.get("topics"),
                "documents": service_data.get("documents")
            }
    
    return None


def search_services(query: str) -> list:
    """
    Search for all matching cardholder services for a query.
    Returns list of matching services ranked by relevance.
    """
    query_lower = query.lower()
    matches = []
    
    for service_key, service_data in CARDHOLDER_URLS.items():
        score = 0
        for keyword in service_data["keywords"]:
            if keyword in query_lower:
                score += len(keyword)  # Longer matches score higher
        
        if score > 0:
            matches.append({
                "service_type": service_key,
                "service_name": service_data["service_name"],
                "url": service_data.get("url"),
                "score": score
            })
    
    # Sort by score (highest first)
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches

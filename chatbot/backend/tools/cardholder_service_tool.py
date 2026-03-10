"""
Cardholder service lookup tool for the cardholder agent.
Enables the agent to find relevant URLs and service information.
"""

from crewai.tools import tool
from core.cardholder_urls import get_service_by_keyword, search_services


@tool("Cardholder Service Search")
def cardholder_service_search(query: str) -> dict:
    """
    Search for cardholder services based on customer query.
    
    This tool helps the cardholder support agent find relevant
    URLs, contact information, and service details when helping
    existing cardholders.
    
    Args:
        query: Customer's question or service request
        
    Returns:
        Dictionary with service information including:
        - service_type: Type of service (e.g., 'activate_card')
        - service_name: Human-readable service name
        - url: Direct link if available, None otherwise
        - description: What the service does
        - alternative: How to access if no URL (branch, contact, app)
        - contact: Phone number if applicable
        - urgent: Whether immediate action is needed
        - app_name: App name if applicable (e.g., 'MyPrime')
        - clarification_needed: Whether to ask the user for more info
        - options: Available options for multi-choice services
        
    Example:
        >>> cardholder_service_search("How do I activate my card?")
        {
            "service_type": "activate_card",
            "service_name": "Card Activation",
            "url": "https://www.primebank.com.bd/card-activation",
            "description": "How to activate your credit card"
        }
        
        >>> cardholder_service_search("My card is lost")
        {
            "service_type": "report_stolen",
            "service_name": "Report Stolen/Lost Card",
            "url": None,
            "contact": "16218",
            "urgent": True,
            "description": "Block your card immediately"
        }
    """
    
    # First try exact match
    service = get_service_by_keyword(query)
    
    if service:
        return {
            "found": True,
            "primary_match": service,
            "alternatives": []
        }
    
    # If no exact match, search for partial matches
    matches = search_services(query)
    
    if matches:
        return {
            "found": True,
            "primary_match": {
                "service_type": matches[0]["service_type"],
                "service_name": matches[0]["service_name"],
                "url": matches[0]["url"],
                "score": matches[0]["score"]
            },
            "alternatives": matches[1:3] if len(matches) > 1 else []
        }
    
    return {
        "found": False,
        "primary_match": None,
        "alternatives": [],
        "message": "Could not find a matching service. Please provide more details about what you need."
    }

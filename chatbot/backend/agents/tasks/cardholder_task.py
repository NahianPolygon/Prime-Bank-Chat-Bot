"""
Cardholder service task for the existing cardholder agent.
Defines what the agent should do when handling cardholder queries.
"""

from crewai import Task


def cardholder_service_task(agent, query: str) -> Task:
    """
    Create a task for the cardholder agent to handle existing cardholder queries.
    
    Args:
        agent: The cardholder support agent
        query: The customer's query or service request
        
    Returns:
        Task for the agent to execute
    """
    return Task(
        description=(
            f"""TASK: Help an existing Prime Bank cardholder with their service request.

CUSTOMER REQUEST: "{query}"

INSTRUCTIONS:

1. UNDERSTAND THE REQUEST
   - Read the customer's query carefully
   - Identify what service they need (activation, PIN, offers, etc.)
   - Note any urgency (e.g., lost/stolen card)

2. SEARCH FOR SERVICE INFORMATION
   - Use the cardholder_service_search tool to find relevant information
   - Get the service type, URL, and any special information needed
   - Check if the service requires alternatives (contact, branch, app)

3. FORMULATE RESPONSE
   - Start with empathy: Acknowledge their need
   - Provide the solution clearly:
     * If URL available: Include link with brief context
     * If no URL: Explain the alternative (call, branch, app)
     * If urgent: Emphasize immediate action needed
   - Explain next steps in clear, simple language
   - Offer multiple options if applicable

4. FORMAT RESPONSE
   - Be warm and professional
   - Use clear, readable format
   - Include actionable links when available
   - Keep response concise but complete
   - End with offer of additional help

RESPONSE EXAMPLES:

For "activate my card":
"I'd be happy to help you activate your card! 

Visit our activation guide: [Card Activation Link]

You can activate your card through:
- Online via MyPrime app
- By phone: 16218
- At any Prime Bank branch

The guide above walks you through each method. 
Is there anything else I can help with?"

For "my card is lost":
"I'm sorry to hear your card is lost. 

**Immediate action required:**
Call 16218 right away to block your card and prevent unauthorized use.

Once your card is blocked, you can:
- Request a replacement by visiting your nearest branch
- Or contact us for home delivery options

Your security is our priority. Is there anything else you need?"

For "show me dining offers":
"Great! We have year-round dining and travel discounts available to you.

Check out all our offers here: [Year-Round Discount Link]

You'll find:
- Dining discounts (20-30% off at premium restaurants)
- Travel packages
- Partner and exclusive offers

Is there a specific type of offer you're interested in?"""
        ),
        expected_output=(
            "A warm, empathetic, and helpful response that:\n"
            "- Acknowledges the cardholder's need\n"
            "- Provides relevant URL(s) with context when available\n"
            "- Explains alternatives (branch, phone, app) when no URL exists\n"
            "- Gives clear, step-by-step guidance\n"
            "- For urgent issues (stolen card): Emphasizes immediate action\n"
            "- Maintains professional, supportive tone\n"
            "- Offers follow-up support\n"
            "- Uses simple, easy-to-understand language\n"
            "- Never invents services or URLs"
        ),
        agent=agent,
    )

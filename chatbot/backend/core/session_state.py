NO_PRODUCTS_SENTINEL = "NO_PRODUCTS_FOUND"


class SessionState:

    def __init__(self):
        self.products_text: str | None = None
        self.comparison_done: bool = False
        self.eligibility_done: bool = False
        self.intent: dict = {}
        self.eligibility_active: bool = False
        self.eligibility_chat: list = []
        self.eligibility_product: str | None = None
        # Smart profiling for vague queries
        self.profiling_needed: bool = False
        self.missing_profile_fields: list = []
        self.collected_profile: dict = {}
        # Track tier/brand preference if stated upfront
        self.preferred_tier: str | None = None
        self.card_brand: str | None = None
        # Track recommended product for context preservation
        self.recommended_product: str | None = None
        self.last_query_intent: str | None = None
        # Track all shown products for disambiguation
        self.alternative_products: list[str] = []  # Secondary products shown to user
        self.shown_products_context: str | None = None  # RAG results for reference when user says "it"
        # Input validation and coaching tracking
        self.invalid_attempt_count: int = 0  # Reset per field
        self.last_validated_field: str | None = None  # Track which field we're validating
        self.confusion_counter: int = 0  # Cumulative off-topic/unclear responses
        self.last_data_confirmed: dict = {}  # Track values user has verified
        self.escalation_offered: bool = False  # Don't re-offer support if already offered

    def has_products(self) -> bool:
        return bool(self.products_text) and NO_PRODUCTS_SENTINEL not in (self.products_text or "")

    def reset_products(self):
        self.products_text = None
        self.comparison_done = False
        self.eligibility_done = False
        self.recommended_product = None
        self.alternative_products = []
        self.shown_products_context = None

    def reset_eligibility(self):
        self.eligibility_active = False
        self.eligibility_chat = []
        self.eligibility_product = None
    
    def reset_field_attempts(self, new_field: str = None):
        """Reset invalid attempt counter when moving to a new field."""
        self.invalid_attempt_count = 0
        self.last_validated_field = new_field
    
    def increment_invalid_attempts(self):
        """Track another invalid attempt on current field."""
        self.invalid_attempt_count += 1
        return self.invalid_attempt_count
    
    def increment_confusion(self):
        """Track off-topic or confused interaction."""
        self.confusion_counter += 1
        return self.confusion_counter
    
    def confirm_field_value(self, field_name: str, value: any, formatted_display: str = None):
        """Record that user confirmed a value."""
        self.last_data_confirmed[field_name] = {
            "value": value,
            "display": formatted_display or str(value),
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }
    
    def should_offer_escalation(self) -> bool:
        """Determine if user needs support based on confusion/invalid attempts."""
        # Offer help if: confusion_counter > 3 OR invalid_attempts > 5
        if self.escalation_offered:
            return False  # Already offered
        return self.confusion_counter > 3 or self.invalid_attempt_count > 5

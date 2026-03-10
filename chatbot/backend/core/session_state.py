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
        # Track recommended product for context preservation
        self.recommended_product: str | None = None
        self.last_query_intent: str | None = None

    def has_products(self) -> bool:
        return bool(self.products_text) and NO_PRODUCTS_SENTINEL not in (self.products_text or "")

    def reset_products(self):
        self.products_text = None
        self.comparison_done = False
        self.eligibility_done = False

    def reset_eligibility(self):
        self.eligibility_active = False
        self.eligibility_chat = []
        self.eligibility_product = None

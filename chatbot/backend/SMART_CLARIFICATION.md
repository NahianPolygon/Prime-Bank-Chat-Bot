# Smart Clarification For Vague Queries

## Problem
When a user asks a vague question like **"i want a credit card...which will be best for me?"**, the old system:
- ❌ No clarification questions asked
- ❌ Returned generic products without understanding user needs
- ❌ Didn't consider: banking preference, use case, income, employment

## Solution
New **VectorDB-based Smart Profiler** that asks clarification questions to build customer profile, then finds best-matching cards from the knowledge base.

---

## How It Works

### Step 1: Detect Vague Query
When intent is `product_info` or `product_search_by_income` AND:
- No specific features mentioned
- No income extracted  
- No product name specified

→ Trigger smart profiling

### Step 2: Ask Clarification Questions
Bot asks (one or more based on missing info):
1. **Banking Type**: Conventional or Islamic (Hasanah)?
2. **Primary Use Case**: Travel, Dining, Business, Rewards, or Lifestyle?
3. **Annual Income**: What's your salary (in BDT)?
4. **Employment Type**: Salaried or Business Owner?

### Step 3: Collect Profile Information
When user responds, system extracts:
- Banking preference (conventional/islami)
- Use case keywords (travel/dining/business/rewards/lifestyle)
- Income (converts "80k/month" → 960,000 annual)
- Employment type (salaried/business_owner)

### Step 4: Smart Card Matching
Uses `ClarificationBuilder.find_matching_cards()` to:
- Query vector DB with profile keywords
- Filter by banking_type (conventional vs islami)
- Rank by income tier (mid vs premium)
- Match use cases from KB metadata

### Step 5: Return Matched Cards
Shows best-matching cards WITH explanations based on KB data

---

## File Changes

### New Files
- `pipelines/crew/clarification.py` - VectorDB-based clarification builder

### Modified Files
- `core/session_state.py` - Added profiling state tracking
- `pipelines/crew/main.py` - Integrated vague query detection & profile collection

### Existing Files (Unchanged)
- `pipelines/rag/search.py` - Uses existing RAG search with dynamic queries
- `agents/recommender.py` - Remains for post-eligibility recommendations
- `pipelines/crew/orchestrator.py` - Uses KB data returned by clarification system

---

## Example Conversation Flow

**User**: "i want a credit card...which will be best for me?"

**Bot**: 
```
To recommend the best card for you, I'd like to know:

1. Would you prefer a **conventional** bank card or a **Shariah-compliant Islamic (Hasanah)** card?

2. What's your **primary use case**? For example:
   - Travel: International flights, lounges, airport benefits
   - Dining: BOGO offers, fine dining, restaurants
   - Business: Corporate spending, frequent travel
   - Rewards: Cashback, points, high spending
   - Lifestyle: Premium lounge access, VIP benefits

3. What's your **annual income or typical monthly salary** (in BDT)?

4. Are you **salaried** or a **business owner/self-employed**?
```

**User**: "I prefer conventional, travel a lot for work, earn 80k monthly, I'm salaried"

**Bot**:
```
Great! Based on your profile (conventional banking, business travel, 960k annual income, salaried), 
here are the best credit cards for you:

1. **Mastercard Platinum Credit Card** - Perfect for frequent business travelers with international travel benefits, Priority Pass lounge access, and premium rewards earning.

2. **Visa Platinum Credit Card** - Excellent for business travel with world-class lounge access, dedicated airport welcome service, and year-round exclusive travel discounts.

3. **Visa Gold Credit Card** - Solid option for business travel with 50-day interest-free period, travel discounts, and rewards earning.

Would you like to know more about any of these cards or proceed with application?
```

---

## Key Advantages

✅ **Dynamic**: Uses KB metadata instead of hardcoded profiles
✅ **Conversational**: Asks natural clarification questions
✅ **Contextual**: Understands banking type, use case, income, employment
✅ **Smart**: Ranks recommendations based on profile match
✅ **Extensible**: Works with existing RAG/orchestrator pipeline
✅ **No Privacy Issues**: Profile stored in session, not persistent

---

## Implementation Details

See `ClarificationBuilder` class in `pipelines/crew/clarification.py`:
- `get_clarification_questions()` - Generate questions for missing fields
- `find_matching_cards()` - Query KB with profile keywords  
- `needs_clarification()` - Detect vague queries that need profiling

Session state tracking in `core/session_state.py`:
- `profiling_needed` - Whether we're in profiling mode
- `missing_profile_fields` - Which fields still need collection
- `collected_profile` - What we've learned so far

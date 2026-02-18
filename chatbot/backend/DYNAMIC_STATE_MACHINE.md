# 🚀 Full Dynamic State Machine Implementation

## Architecture Overview

The chatbot now uses a **fully dynamic state machine** that tracks session state across messages and intelligently selects which agents to run based on:
1. User intent (product_info, comparison, eligibility_check, feature_query)
2. Cached products from previous retrievals
3. Filter changes (banking_type, tier, product_type)
4. What operations have already been completed

---

## Key Components

### 1. **SessionState Class** (tracks per-session data)
```python
class SessionState:
    products_text: str          # Raw retrieval output
    product_names: list         # Extracted product names
    comparison_done: bool       # Has comparison been run?
    eligibility_done: bool      # Has eligibility been run?
    intent: dict                # Last known intent filters
```

**State Management Methods:**
- `has_products()` - Check if products cached
- `reset_products()` - Called when filters change (user switches from conventional to Islamic, etc.)

### 2. **BankChatbotCrew.run_agents()** (dynamic agent orchestration)

Dynamically builds agent pipeline based on:
- `needs_retrieval` - No cached products OR first product_info query
- `needs_comparison` - User asking to compare products
- `needs_eligibility` - User asking about eligibility

**Always includes Formatter agent last to format output for frontend.**

### 3. **CrewPipeline.run()** (main logic flow)

**Step 1: Detect Intent**
- Extract: product_type, banking_type, tier, use_case, employment
- Detect: comparison vs eligibility_check vs feature_query vs product_info

**Step 2: Check Filter Changes**
```python
if state.has_products() and _filters_changed(new_intent, old_intent):
    state.reset_products()  # Clear cache if banking_type/tier/product changed
```

**Step 3: Check Clarification**
- Ask missing questions if insufficient info

**Step 4: Run Dynamic Agents**
```python
response, retrieved_products = crew.run_agents(
    query=enriched_query,
    intent_type=intent_type,
    state=state,
    customer_profile=profile
)
```

**Step 5: Update Session State**
- Cache products if just retrieved
- Mark comparison/eligibility as done
- Store intent for next message's filter comparison

---

## Complete Dynamic Flows

### Flow 1: Initial Product Retrieval
```
User: "I want a platinum conventional credit card for business"
         ↓
Intent: product_type=credit_card, banking_type=conventional, tier=platinum, use_case=business
         ↓
Check: No cached products yet
         ↓
Run Agents: [Product Retriever] → [Formatter]
         ↓
Cache products ✅
State: products_text = "Visa Platinum, Mastercard Platinum, ..."
         ↓
Response: Formatted list of 3 platinum conventional cards
```

### Flow 2: Comparison of Cached Products
```
User: "Which is best for me? Compare them"
         ↓
Intent: intent_type=comparison
         ↓
Check: Has cached products + comparison NOT done yet
         ↓
Run Agents: [Comparator] → [Formatter] ✅
         ↓
NO re-retrieval! (saves time)
State: comparison_done = True
         ↓
Response: "Visa Platinum has best rewards, Mastercard Platinum has best limits..."
```

### Flow 3: Eligibility Check After Comparison
```
User: "Am I eligible for the Mastercard one?"
         ↓
Intent: intent_type=eligibility_check
         ↓
Check: Has cached products + eligibility NOT done yet
         ↓
Run Agents: [Eligibility Analyzer] → [Formatter] ✅
         ↓
Customer info: employment=business_owner
         ↓
State: eligibility_done = True
         ↓
Response: "You're eligible! You meet all requirements for Mastercard Platinum"
```

### Flow 4: Comparison + Eligibility Together
```
User: "Compare them and check eligibility"
         ↓
Intent: intent_type=comparison (keyword 'compare' triggers first)
         ↓
Check: Has cached products
         ↓
Run Agents: [Comparator, Eligibility Analyzer] → [Formatter] ✅
         ↓
Response: Comparison + Eligibility analysis combined
```

### Flow 5: Filter Change (Reset Cache)
```
User: "Actually show me Islamic options instead"
         ↓
Intent: banking_type=islami (changed from conventional)
         ↓
Check: Has cached products + filters_changed?
         ↓
⚠️  YES → state.reset_products()
         ↓
Run Agents: [Product Retriever] → [Formatter] ✅
         ↓
Cache NEW Islamic products
         ↓
Response: List of Islamic platinum cards
```

### Flow 6: Retrieve → Compare → Eligibility → Feature Query (All 4)
```
Message 1: "I need a platinum credit card"
→ Retriever + Formatter (products cached)

Message 2: "Compare them"
→ Comparator + Formatter (no retrieval)

Message 3: "Am I eligible?"
→ Eligibility + Formatter (no retrieval)

Message 4: "What are the fees?"
→ Feature query detected, use cached products
→ Formatter only (or Feature Agent if exists)
```

---

## Agent Selection Logic

```
ALWAYS:
  - Intent Classifier (runs implicitly via _detect_intent)
  - Response Formatter (always last)

CONDITIONALLY:
  - Product Retriever
    if: NOT has_products OR intent_type='product_info'
    
  - Comparator
    if: intent_type='comparison' AND has_products
    
  - Eligibility Analyzer
    if: intent_type='eligibility_check' AND has_products
    
  - Feature Analyzer (if exists)
    if: intent_type='feature_query' AND has_products
```

---

## Agent Execution Examples

### Scenario A: First Query
```
"I want platinum credit card as a business owner"
→ Agents: [Product Retriever, Formatter]
→ Products cached
```

### Scenario B: Comparison After Retrieval
```
"Which is best?"
→ Agents: [Comparator, Formatter]
→ No re-retrieval (2 agents instead of 3)
```

### Scenario C: Eligibility After Comparison
```
"Am I eligible?"
→ Agents: [Eligibility, Formatter]
→ Still no re-retrieval (2 agents)
```

### Scenario D: Eligibility + Comparison Together
```
"Compare them and check if I'm eligible"
→ Agents: [Comparator, Eligibility, Formatter]
→ Runs BOTH analysis agents + formatter (3 agents)
```

### Scenario E: Filter Change
```
Original: "platinum, conventional"
New: "platinum, islamic"
→ Filters changed! Reset cache
→ Agents: [Product Retriever, Formatter]
→ New Islamic products cached
```

---

## State Tracking Example

```python
# Session starts empty
session.products_text = None
session.comparison_done = False
session.eligibility_done = False
session.intent = {}

# After Message 1: "I want platinum conventional card"
session.products_text = "[Visa Platinum, Mastercard Platinum, JCB Gold]"
session.comparison_done = False
session.eligibility_done = False
session.intent = {banking_type: conventional, tier: platinum, ...}

# After Message 2: "Compare them"
session.products_text = "[Visa Platinum, Mastercard Platinum, JCB Gold]"  # unchanged
session.comparison_done = True  # marked as done
session.eligibility_done = False
session.intent = {banking_type: conventional, tier: platinum, ...}  # unchanged

# After Message 3: "Am I eligible for Visa?"
session.products_text = "[Visa Platinum, Mastercard Platinum, JCB Gold]"  # unchanged
session.comparison_done = True
session.eligibility_done = True  # marked as done
session.intent = {banking_type: conventional, tier: platinum, ...}  # unchanged

# After Message 4: "Actually, Islamic please"
session.products_text = None  # RESET (filter changed)
session.comparison_done = False  # RESET
session.eligibility_done = False  # RESET
session.intent = {banking_type: islami, tier: platinum, ...}  # updated
```

---

## Key Optimizations

| Scenario | Before | After | Savings |
|----------|--------|-------|---------|
| Comparison after retrieval | Retrieve + Compare + Format | Compare + Format | 1 retrieval agent |
| Eligibility after retrieval | Retrieve + Eligibility + Format | Eligibility + Format | 1 retrieval agent |
| Both together | 2x Retrieve + Compare + Eligibility + Format | Compare + Eligibility + Format | 1 retrieval agent |
| Feature query | Retrieve + Format | Format | 1 retrieval agent |

---

## Session Isolation

Each session maintains its own:
- `SessionState` object with products_text and operation tracking
- Conversation history
- Cached intents

**Multiple users** have zero interference:
```
Session A: User 1 comparing Visa vs Mastercard platinum
Session B: User 2 checking Islamic gold eligibility

→ Completely isolated state, different products, different agents
```

---

## Implementation Files

1. **crew_pipeline.py** - Complete rewrite with SessionState + dynamic orchestration
2. **app.py** - Already passes session_id to crew_pipeline.run()
3. **No changes needed** to agents or tasks - they work the same, just called conditionally

---

## Usage from Frontend

```javascript
// Initialize with session_id
const sessionId = generateUUID();

// Message 1: Retrieval
const msg1 = await fetch('/chat', {
    method: 'POST',
    body: JSON.stringify({
        query: "I want platinum credit card",
        session_id: sessionId,
        user_employment: "business_owner",
        mode: "crew"
    })
});

// Message 2: Comparison (reuses products)
const msg2 = await fetch('/chat', {
    method: 'POST',
    body: JSON.stringify({
        query: "Compare them",
        session_id: sessionId,  // ← Same session!
        user_employment: "business_owner",
        mode: "crew"
    })
});

// Message 3: Eligibility (still reuses)
const msg3 = await fetch('/chat', {
    method: 'POST',
    body: JSON.stringify({
        query: "Am I eligible?",
        session_id: sessionId,  // ← Same session!
        user_employment: "business_owner",
        mode: "crew"
    })
});
```

---

## Benefits

✅ **Zero Redundant Retrieval** - Products retrieved once, reused infinitely  
✅ **Faster Response Times** - Comparison/eligibility run instantly (no DB queries)  
✅ **Full Dynamism** - Any message can trigger comparison, eligibility, or features  
✅ **Smart Filtering** - Automatic cache reset when filters change  
✅ **Session Isolation** - Multiple users don't interfere  
✅ **Cost Efficient** - Fewer agent runs = fewer LLM calls  

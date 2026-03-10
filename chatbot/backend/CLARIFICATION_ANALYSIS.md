## CLARIFICATION QUESTIONS ANALYSIS

### Current Intent → Clarification Status

| Intent Type | Has Clarification | When? | Code Location |
|------------|--------|-------|---------------|
| **greeting** | ❌ No | Always returns greeting | classifier.py:117 |
| **small_talk** | ❌ No | Always returns chat | classifier.py:117 |
| **product_info** | ⚠️ Conditional | Only if LLM returns `needs_clarification=true` | classifier.py:120 |
| **feature_inquiry** | ❌ No | Disabled by design (line 119) | classifier.py:119-121 |
| **product_search_by_income** | ❌ No | Disabled by design (line 119) | classifier.py:119-121 |
| **eligibility_matching** | ✅ Yes | Only if income OR features missing | main.py:120-140 |
| **comparison** | ❌ No | Disabled by design (line 119) | classifier.py:119-121 |
| **eligibility_check** | ✅ Yes | Always asks (for eligibility collection) | main.py:108-115 |

---

### THE PROBLEM

**User Query**: "i want a credit card...which will be best for nmme?"

1. ❌ Classifier set it as `product_search_by_income` 
2. ❌ BUT no income was extracted (income = None)
3. ❌ NO clarification triggered because `product_search_by_income` is hardcoded to skip clarification (line 119)
4. ✗ System proceeded directly to RAG search with vague query
5. ✗ Got generic results instead of asking "What's your monthly income?"

**Root Cause**: Line 117-121 in classifier.py **disables clarification for 4 intent types by design**:
```python
needs_clarification = False if is_social or intent_type in (
    "eligibility_matching", "feature_inquiry", "product_search_by_income", "comparison"
)
```

---

### THE SOLUTION

For `product_search_by_income`, clarification SHOULD be required if:
- ❌ No income detected
- ✅ But should NOT ask again if income is already from history

Similarly for `eligibility_matching`, there's active logic (line 120-140 in main.py) that asks:
```
To find matching products, I need:
- Your monthly salary or annual income (in BDT)
- Specific feature you need (lounge, dining, rewards, etc.)
```

---

### FIX NEEDED

**Option 1**: Add `product_search_by_income` clarification logic like `eligibility_matching` has

In `main.py` around line 145, add:
```python
# Handle product_search_by_income (income-only queries)
if intent_type == "product_search_by_income":
    income = intent.get("customer_income")
    if not income:
        return self._respond(
            "To show you the best cards for your income level, could you share your monthly salary or annual income (in BDT)?",
            ["Intent Classifier"],
            intent,
            needs_clarification=True,
        )
```

**Option 2**: Enable LLM to detect vague `product_info` queries

Modify classifier.py line 120 to let LLM decide for `product_info` intent whether clarification is needed.

---

### WHICH INTENTS CURRENTLY ASK CLARIFICATION?

✅ **ALWAYS**:
- `eligibility_check` - Always starts eligibility collection with first question
- `eligibility_matching` - Asks if income OR features missing

⚠️ **SOMETIMES**:
- `product_info` - Only if LLM returns `needs_clarification=true` (rarely)

❌ **NEVER** (by design, but maybe shouldn't):
- `product_search_by_income` - Should ask if income is None
- `feature_inquiry` - Okay, has enough info
- `comparison` - Okay, comparing specified products
- `greeting/small_talk` - Okay, social

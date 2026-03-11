# Conversation Flow Audit - Comprehensive Review

**Date**: March 11, 2026  
**Status**: IDENTIFIED GAPS - Ready for Implementation  
**Priority**: HIGH - Dynamic conversation guidance missing

---

## Executive Summary

✅ **Strengths Found:**
- Query classification system exists (intent classifier)
- Clarification questions implemented for vague queries
- Smart profiler asks for missing fields
- Eligibility questions guided through LLM

❌ **GAPS IDENTIFIED:**
1. **No irrelevant response handlers** - If user gives off-topic answer, bot doesn't guide back
2. **No input validation** - Some numeric fields accept invalid data without coaching
3. **No context awareness in clarification** - Doesn't reference previous context when guiding
4. **No fallback for confused responses** - No "I didn't understand, let me rephrase" logic
5. **No confirmation/verification flow** - Extracted data not repeated back to user for confirmation
6. **No retry logic with coaching** - Invalid entries cause hard failures instead of gentle retry
7. **No conversation history leverage** - Doesn't remind user of their previous answers in context
8. **No polite redirection** - When user is off-topic, bot doesn't guide back warmly

---

## Detailed Analysis by Component

### 1. Intent Classification (`backend/intent/classifier.py` - lines 21-147)

**Current State:**
- ✅ Comprehensive intent detection system
- ✅ Strict rules about inferring features/income
- ✅ Identifies existing cardholder queries
- ✅ Handles vague queries detection

**Gaps:**
- ❌ **No irrelevant query detection**: What if user asks "What's the weather?" - not detected as off-topic
- ❌ **No confidence scoring**: Doesn't tell us how confident the classification is
- ❌ **No fallback intent**: Should have "off_topic" or "unclear" intent type

**Required Fix:**
- Add `relevance_score` field (0-100) - only proceed if > 70
- Add `off_topic_reason` when confidence is low
- Add "off_topic" and "unclear" to intent_type options
- Return `suggested_clarification` when irrelevant

---

### 2. Profiling Flow (`backend/pipelines/crew/clarification.py`)

**Current State:**
- ✅ Asks missing profile fields dynamically
- ✅ LLM generates natural questions
- ✅ Tracks what's been collected

**Gaps:**
- ❌ **No validation of answers**: User says "income: pasta" - not caught
- ❌ **No context reference**: Doesn't remind user of what they said earlier
- ❌ **No confirmation**: Doesn't ask "So you're earning 200k monthly, is that right?"
- ❌ **No coaching for invalid input**: If user enters "xyz" for income, just asks again without explanation
- ❌ **No extraction confirmation**: Doesn't show extracted values back

**Example Problem:**
```
Bot: "What's your annual income?"
User: "I dunno, maybe 50k?"
Bot: [EXTRACTS 600,000] ← No confirmation shown!
Bot: "Great, do you prefer conventional or islamic banking?"
User: "Wait, 600k is wrong!"
``` 

**Required Fix:**
- Always show extracted data back: "Got it - **BDT 200,000/month** (2.4M annually). Is that correct?"
- Validate income: If < 10,000 or > 1,000,000,000, ask "Just to confirm, is that BDT X per year?"
- Track validation attempts: If user says "no", re-ask with coaching
- Provide context in questions: "You mentioned you travel a lot. So for annual income..."

---

### 3. Eligibility Flow (`backend/pipelines/crew/eligibility.py`)

**Current State:**
- ✅ Asks for required fields (age, employment, tenure, income, E-TIN)
- ✅ LLM generates natural questions
- ✅ Validates completeness before assessment

**Gaps:**
- ❌ **No input range validation**: Age=999 accepted, age=-5 not caught
- ❌ **No guidance on errors**: "Please enter a valid age" too generic
- ❌ **No coaching**: Doesn't explain why field matters ("This helps verify steady income")
- ❌ **No extraction verification**: Doesn't show back "OK, you're 32, working full-time for 8 years"
- ❌ **No retry count**: After 3 invalid entries, should suggest "Let's chat with support"

**Example Problem:**
```
Bot: "What's your age?"
User: "I'm a 5-year-old child"
Bot: [ACCEPTS] ← Should validate age 18-70!
Bot: [Later] "Unfortunately you don't eligible because customer is < 18"
```

**Required Fix:**
- Add age validation: "Age must be between 18 and 70. Could you confirm your age?"
- Add employment validation: Only accept `salaried|self_employed|business_owner|student`
- Add tenure validation: "Employment period must be at least 6 months. How long have you worked?"
- Show back extracted data: "So - 32 years old, full-time employment, 8 years tenure. That's correct?"
- Count attempts: If invalid 3x, offer "Would you like to speak with our team?"

---

### 4. How-to-Apply Flow (`backend/pipelines/crew/main.py` - lines 96-155)

**Current State:**
- ✅ Detects "how to apply" queries
- ✅ Routes to product-specific retrieval
- ✅ Handles multiple products (ask which one)

**Gaps:**
- ❌ **No disambiguation if unclear**: User says "how to apply" without selecting - loops infinitely
- ❌ **No confirmation before detailed process**: Doesn't ask "Ready for detailed steps?"
- ❌ **No tracking if user reads**: After showing docs, doesn't ask "Any questions about these?"
- ❌ **No guidance for confusing steps**: If documents section is long, doesn't break it up

**Example Problem:**
```
Bot: "Which card? 1. JCB 2. Visa"
User: "both"
Bot: [NO HANDLER] ← What happens here?
```

**Required Fix:**
- Add regex validation for numeric responses: Only 1/2/3 or product name
- If user says "both", ask "You'll need to apply separately for each. Which first?"
- Before showing documents, ask confirmation: "Ready to see the application steps?"
- After showing steps, add: "Got it? Any questions about the required documents?"

---

### 5. Comparison Flow (`backend/pipelines/crew/main.py`)

**Current State:**
- ✅ Identifies comparison queries
- ✅ Uses updated task with TABLE-ONLY format

**Gaps:**
- ❌ **No follow-up after comparison**: Doesn't ask "Want to apply for one of these?"
- ❌ **No context preservation**: If user later asks "what about eligibility?", doesn't know which card they were comparing
- ❌ **No clarification if ambiguous**: User says "compare" but no products shown yet - doesn't guide

**Required Fix:**
- After comparison, add: "Which one interests you most? We can check eligibility or start the application."
- Store comparison context: `state.last_comparison_cards = ["Visa Platinum", "JCB Platinum"]`
- If user says "compare" but no products shown, ask: "Which cards would you like to compare?"

---

### 6. Small Talk & Off-Topic (`backend/pipelines/crew/helpers.py`)

**Current State:**
- ✅ `greet()` handles greetings
- ✅ `chat()` handles small talk
- ✅ Both try to redirect to banking

**Gaps:**
- ❌ **`chat()` function too generic**: Accepts any small-talk, redirects weakly
- ❌ **No context in redirection**: "How can I help with banking?" if user just said they love pizza
- ❌ **No detection of confusion**: "I don't understand your question" not caught
- ❌ **No escalation path**: If user is confused multiple times, doesn't offer human chat

**Example Problem:**
```
User: "My cat is cute"
Bot: "That's nice! How can I help you with our banking services?" ← Too generic!
User: "My dog likes swimming"
Bot: [Same response]
User: [Frustrated, leaves]
```

**Required Fix:**
- Enhanced `chat()` to reference conversation: "I see you're thinking about pets! By the way, have you decided on a credit card yet?"
- Add confusion counter: After 3 unrelated responses, offer "Would you like to chat with our team?"
- Smarter redirect: "That sounds great! Now, back to finding you the right card..."

---

## Implementation Roadmap

### Phase 1: Input Validation & Coaching (HIGHEST PRIORITY)
**File**: Create `backend/pipelines/crew/validation.py`
- Add `validate_age(input)` - returns (valid, error_message, suggestion)
- Add `validate_income(input)` - returns (valid, error_message, confirmed_amount)
- Add `validate_employment(input)` - case-insensitive matching
- Add `validate_tenure(input)` - accepts "8 years", "96 months", etc.
- Add `validate_etin(input)` - checks format, guides if unsure
- Each returns helpful error, not just "invalid"

### Phase 2: Confirmation & Verification Flows
**Files**: `backend/pipelines/crew/eligibility.py`, `backend/pipelines/crew/clarification.py`
- Add `confirm_extracted_data(profile)` → Shows back to user with formatting
- Add retry logic: Max 3 attempts before offering help
- Add history reference: "You mentioned you travel for work (earlier), so..."

### Phase 3: Off-Topic Detection & Guidance
**File**: Enhance `backend/intent/classifier.py`
- Add relevance scoring
- Add "off_topic" intent type
- Add `detect_confusion()` - tracks multiple unrelated queries
- Add escalation logic: "Would you like to speak with our team?"

### Phase 4: Dynamic Context & Memory
**File**: Enhance `backend/core/session_state.py`
- Add `invalid_attempt_count` - track when user gives bad input
- Add `confusion_counter` - track off-topic queries
- Add `user_preferences_mentioned` - reference what they said earlier
- Add `last_clarification_timestamp` - avoid re-asking same thing

---

## Testing Checklist

### Test Irrelevant Response Handling
```
Bot: "What's your annual income?"
User: "The sky is blue"
Bot: [Should politely ask again or clarify]
✅ Not: "Got it, sky is blue. Let me search..."
```

### Test Invalid Input Handling
```
Bot: "What's your age?"
User: "pizza"
Bot: "Ages must be between 18-70. How old are you?"
✅ Coaching included, not just "invalid"
```

### Test Confirmation Flow
```
Bot: [After income extraction]
Bot: "So you earn **BDT 200,000/month** (2.4M annually). Is that correct?"
User: "Yes"
✅ Data confirmed before proceeding
```

### Test Escalation
```
Bot: [User asks off-topic 5 times in a row]
Bot: "I'm having trouble understanding. Would you like to chat  with our support team?"
✅ Graceful escalation, not loop
```

### Test Context In Guidance
```
Bot: "You mentioned you travel frequently. So for your annual income..."
✅ References what user said earlier
```

---

## Success Metrics

- **Conversation Completion Rate**: 90%+ of vague queries → product recommendation
- **Validation Success**: 95%+ of user inputs correctly captured on first try
- **Clarification Efficiency**: Average 3 questions to complete profile (currently variable)
- **Escalation Rate**: < 5% need human intervention (currently unknown)
- **User Confirmation**: 100% of extracted data shown back to user before proceeding

---

## Priority Implementation Order

1. **CRITICAL** (This week): Input validation + coaching system
2. **HIGH** (Next week): Confirmation flows for all guided questions
3. **MEDIUM** (Week 3): Off-topic detection + context references
4. **LOW** (Week 4): Advanced escalation + session memory enhancements


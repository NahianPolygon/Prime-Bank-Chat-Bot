# Prompt-Based Improvements Implementation

## Overview
Full implementation of LLM-driven validation, confirmation flows, off-topic detection, and context-aware guidance throughout the chatbot conversation. All logic is prompt-based using Ollama, not hardcoded rules.

## Phase 3 Implementation Summary (Complete)

### 1. NEW FILE: `validation.py`
**Location**: `chatbot/backend/pipelines/crew/validation.py`

LLM-based input validation system with warm, contextual coaching. All validators use Ollama for natural language processing.

**Validators Created**:
- `validate_age(user_input, context)` - Validates 18-70 range with context awareness
- `validate_income(user_input, context)` - Parses BDT amounts (k, lakh, monthly, annual) with aggressive extraction
- `validate_employment(user_input)` - Maps to salaried/self-employed/business_owner/student
- `validate_tenure(user_input, employment_type)` - Parses job duration (years, months)
- `validate_etin(user_input)` - Yes/no validation for Tax ID
- `validate_profile_response(user_input, field_type)` - Generic router to appropriate validator

**Return Structure**: `{valid, extracted_value, coaching_message, is_retryable}`

**Key Features**:
- All messages LLM-generated, not templates
- Shows confirmations formatted with bold: "**BDT 2,400,000/month**"
- Tracks invalid attempts, offers escalation after 3 failures
- Context-aware prompts using previous responses

---

### 2. UPDATED: `session_state.py`
**Location**: `chatbot/backend/core/session_state.py`

**New Fields Added**:
```python
invalid_attempt_count: int = 0          # Reset per field - tracks invalid inputs
last_validated_field: str | None        # Current field being validated
confusion_counter: int = 0              # Cumulative off-topic interactions
last_data_confirmed: dict = {}          # Values user verified
escalation_offered: bool = False        # Prevent re-offering support
```

**New Methods**:
- `reset_field_attempts(new_field)` - Clear attempt counter for new field
- `increment_invalid_attempts()` - Track failed validation attempts
- `increment_confusion()` - Track off-topic interactions
- `confirm_field_value(field_name, value, display)` - Record confirmed values
- `should_offer_escalation()` - Decide if user needs support

---

### 3. UPDATED: `classifier.py` - Off-Topic Detection
**Location**: `chatbot/backend/intent/classifier.py`

**New Fields in Intent**:
```python
relevance_score: int (0-100)    # Banking relevance assessment
is_off_topic: bool              # True if score < 55 (clearly off-topic)
```

**Relevance Scale**:
- 95-100: Crystal clear banking query
- 85-94: Clear banking with context
- 75-84: Somewhat clear, maybe vague
- 65-74: Minimal banking context
- 55-64: Very vague or mostly off-topic
- 0-54: Clearly off-topic

**Classification Logic**:
- LLM generates relevance_score for every query
- Automatic is_off_topic flag if score < 55
- Guides routing to appropriate handler (validation, escalation, etc.)

---

### 4. UPDATED: `eligibility.py` - Validation & Confirmations
**Location**: `chatbot/backend/pipelines/crew/eligibility.py`

**New Flow**:
```
User Input → ask_for_next_field(field, collected, state, user_input)
    ↓
    Validate Input Using Validator
    ↓
    If Valid:
        - Show formatted confirmation ("You earn **BDT 2.4M annually**")
        - Move to next field
    ↓
    If Invalid:
        - Provide coaching message
        - Increment attempt counter
        - After 3 failures: Offer escalation
    ↓
    Continue until all fields collected
```

**Updated Functions**:
- `ask_for_next_field()` - Now validates input, shows confirmations, handles escalation
- `_ask_field_question()` - Generates contextual questions with history reference
- Import: `InputValidator` from validation.py

**Integration Points**:
- Called from `_eligibility_turn()` in main.py
- Receives user input for validation
- Tracks confirmation in state.last_data_confirmed

---

### 5. UPDATED: `main.py` - Multi-Layer Updates
**Location**: `chatbot/backend/pipelines/crew/main.py`

#### A. Off-Topic Detection & Handling
```python
if intent.get("is_off_topic") or intent.get("relevance_score", 100) < 55:
    state.increment_confusion()
    # Generate warm redirection
    # Offer escalation if confusion > 3
```

#### B. Eligibility Assessment Follow-Ups
```python
def _run_eligibility_assessment():
    # ... existing logic ...
    # NEW: Add follow-up based on eligibility result
    follow_up = "Would you like to apply, explore other cards, or need more info?"
```

#### C. Eligibility Turn with Validation
```python
def _eligibility_turn():
    # Pass user query to ask_for_next_field for validation
    reply = ask_for_next_field(
        status["next_field"], 
        status["collected"], 
        state, 
        query  # ← NEW parameter for validation
    )
```

#### D. Small-Talk with State Passing
```python
if intent["category"] == "small_talk":
    return self._respond(chat(query, history, state), [], intent)  # ← Pass state
```

---

### 6. UPDATED: `helpers.py` - Context-Aware Off-Topic Handling
**Location**: `chatbot/backend/pipelines/crew/helpers.py`

**Updated Functions**:
- `chat(query, history, state)` - Accepts state for tracking confusion
  - References recent conversation in small-talk responses
  - Increments state.confusion_counter
  - Offers escalation after 3+ off-topic turns
  - Message: "Would it help to speak with our support specialists?"

---

## Feature Showcase

### Validation Example Flow
```
Bot: "What's your age?"
User: "idk"

Bot: "That's okay! Could you give me an approximate age? 
      For example, are you in your 20s, 30s, 40s, or 50s?"

User: "99 years old"

Bot: "Thanks for sharing! Just to confirm - you're 99 years old?
      Note: Most cards require customers aged 18-70. 
      Would you like to continue anyway?"

User: "No, I'm actually 42"

Bot: "Perfect! So you're 42 years old. ✓
      Next, could you tell me your employment type?"
```

### Confirmation Example
```
Bot: "What's your monthly income?"
User: "50 thousand monthly"

Bot: "Got it - you earn **BDT 50,000/month** 
      (approximately **BDT 600,000 annually**). 
      Is that correct?"

User: "yes"

Bot: "Great! ✓ Moving on... Do you have an E-TIN?"
```

### Off-Topic Detection
```
Bot: "I'd love to help with cards. What brings you in?"
User: "What's the weather like?"

Bot: [relevance_score: 15, is_off_topic: true]
Bot: "I see you're curious about the weather! 😊
      I'm here to help with credit cards and banking. 
      Shall we find a card that works for you?"

(After 3+ off-topic exchanges)
Bot: "...
      I notice we're going in different directions. 
      Would you like to speak with our support team 
      who might help you better?"
```

### Escalation Example
```
Bot: "What's your age?"
User: "Yes"           [Attempt 1 - Invalid]
Bot: "[Coaching] Could you tell me your age as a number?"

User: "sure"          [Attempt 2 - Invalid]
Bot: "[Coaching] Are you in your 20s, 30s, 40s, or 50s?"

User: "maybe"         [Attempt 3 - Invalid]
Bot: "[Coaching] I'm having trouble understanding. 
      Let me try differently..."

User: "still confused" [Attempt 4 - Invalid]
Bot: "I notice we're having difficulty here. 
      Would you like to speak with our support team? 
      They can help guide you personally."
```

---

## Technical Integration Points

### Session State Lifecycle
1. **User starts conversation** → New SessionState created
2. **Each profiling field** → `reset_field_attempts("field_name")`
3. **Invalid input received** → `increment_invalid_attempts()`
4. **Valid input received** → `confirm_field_value(field, value, display)`
5. **Off-topic response** → `increment_confusion()`
6. **Confusion reaches threshold** → `should_offer_escalation()` → offer support

### Validation Flow in Eligibility
1. User answers profiling question
2. `ask_for_next_field()` called with user input
3. `InputValidator.validate_profile_response()` determines validity
4. If valid: Show confirmation, store in last_data_confirmed, ask next
5. If invalid: Show coaching, increment attempts, reask same field
6. After 3+ invalid: Offer escalation option

### Off-Topic Detection Pipeline
1. Query received in main.py
2. `IntentClassifier.classify()` generates relevance_score
3. If is_off_topic=true or relevance_score < 55:
   - Increment state.confusion_counter
   - Generate redirect message
   - If confusion > 3: Offer escalation
4. Conversation continues with state tracking

---

## Testing Scenarios

### Test 1: Income Validation
```
INPUT: "50k monthly"
EXPECTED:
  - valid: true
  - extracted_monthly_bdt: 50000
  - extracted_annual_bdt: 600000
  - confirmation_message shows bold amounts
```

### Test 2: Age Rejection with Coaching
```
INPUT: "25 years old"
EXPECTED:
  - valid: true
  - extracted_age: 25
  - no coaching needed
  
INPUT: "pizza"
EXPECTED:
  - valid: false
  - coaching: "Could you tell me your age as a number?"
  - is_retryable: true
```

### Test 3: Invalid Attempt Escalation
```
ATTEMPT 1: Invalid → coaching
ATTEMPT 2: Invalid → coaching
ATTEMPT 3: Invalid → coaching
ATTEMPT 4: Invalid → "Would you like to speak with support?"
```

### Test 4: Off-Topic Detection
```
INPUT: "What's the weather?"
EXPECTED:
  - relevance_score: ~20
  - is_off_topic: true
  - response redirects warmly
  - confusion_counter incremented
```

### Test 5: Confirmation Flow
```
EXTRACTION: Income 200,000/month
CONFIRMATION: "**BDT 200,000/month** 
               (approximately **BDT 2,400,000 annually**). 
               Is that right?"
STORED: last_data_confirmed["income"] = {
          value: 2400000,
          display: "BDT 200,000/month (2,400,000 annually)"
        }
```

---

## Logging & Debugging

### Key Debug Points
```python
# Validation attempts
print(f"Invalid attempt #{state.invalid_attempt_count} for {state.last_validated_field}")

# Confusion tracking
print(f"Confusion level: {state.confusion_counter}")

# Off-topic detection
print(f"Relevance: {intent['relevance_score']}, Off-topic: {intent['is_off_topic']}")

# Escalation events
print(f"Escalation offered: {state.escalation_offered}")
```

---

## Future Enhancements

1. **Escalation Handler**: Route to support team when escalation offered
2. **Conversation Recovery**: Detect when user is cycling/frustrated, offer help sooner
3. **Context Awareness**: Remember previous answers in follow-up questions
4. **Multi-Language**: Support Bangla, English code-switching
5. **Preference Learning**: Remember banking type, income level for future sessions
6. **Follow-Up Automation**: Auto-continue after user confirms data

---

## Key Design Principles

✅ **Prompt-Based**: All logic via LLM, no hardcoded rules  
✅ **Contextual**: Questions reference what user said  
✅ **Warm**: Messages are coaching, not error messages  
✅ **Trackable**: Session state manages all interactions  
✅ **Escalation-Ready**: Support team integration prepared  
✅ **User-Friendly**: Confirmations show formatted data  
✅ **Recoverable**: Invalid attempts get coaching, not rejection  
✅ **Observable**: Logging shows intent, validation, confusion, escalation  

---

## Files Modified Summary

| File | Changes | Purpose |
|------|---------|---------|
| validation.py | NEW | 6 LLM validators with coaching |
| session_state.py | +5 fields, +5 methods | Tracking state for validation/confusion/escalation |
| classifier.py | +2 fields | relevance_score, is_off_topic detection |
| eligibility.py | Updated ask_for_next_field | +validation, +confirmation, +escalation |
| main.py | Updated 3 areas | Off-topic handling, eligibility follow-up, state passing |
| helpers.py | Updated chat() | Off-topic tracking, confusion increment |

**Total Files Modified**: 6  
**New Files Created**: 1  
**Syntax Errors**: 0  
**Ready for Testing**: ✅ YES


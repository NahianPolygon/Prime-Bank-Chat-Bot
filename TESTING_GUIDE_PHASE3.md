# Testing Guide for Phase 3: Prompt-Based Validation & Confirmation

## Test Environment Setup
```bash
cd chatbot/backend
python3 app.py
# Server runs at http://localhost:8000
```

## Manual Test Scenarios

### Test Suite 1: Income Validation

#### Scenario 1.1: Standard Monthly Income
```
Bot: "What's your monthly income?"
User: "50000"
Expected Output:
  - valid: true
  - extracted_monthly_bdt: 50000
  - extracted_annual_bdt: 600000
  - confirmation_message: "**BDT 50,000/month** (approximately **BDT 600,000 annually**). Is that right?"
```

#### Scenario 1.2: Shorthand with K
```
Bot: "What's your monthly income?"
User: "50k"
Expected Output:
  - valid: true
  - extracted_monthly_bdt: 50000
  - extracted_annual_bdt: 600000
  - confirmation_message shows bold amounts
```

#### Scenario 1.3: Annual Income with Lakh
```
Bot: "What's your income?"
User: "5 lakh annual"
Expected Output:
  - valid: true
  - extracted_annual_bdt: 500000
  - extracted_monthly_bdt: ~41667
  - confirmation shows annual figure first
```

#### Scenario 1.4: Invalid Income
```
Bot: "What's your income?"
User: "i dont know"
Expected Output:
  - valid: false
  - coaching_message: "No problem! Could you share an approximate income? For example: '200,000/month' or '2.4 million annual'."
  - is_retryable: true
  - state.invalid_attempt_count: 1
```

### Test Suite 2: Age Validation

#### Scenario 2.1: Valid Age
```
Bot: "What's your age?"
User: "thirty"
Expected Output:
  - valid: true
  - extracted_age: 30
  - coaching_message: ""
```

#### Scenario 2.2: Invalid Age (Child)
```
Bot: "What's your age?"
User: "5-year-old"
Expected Output:
  - valid: false
  - extracted_age: null
  - coaching_message contains guidance about 18-70 age requirement
```

#### Scenario 2.3: Invalid Age (Ambiguous)
```
Bot: "What's your age?"
User: "middle aged"
Expected Output:
  - valid: false
  - coaching_message: "I understand - could you give me a specific age? For example, are you in your 30s, 40s, or 50s?"
  - is_retryable: true
```

### Test Suite 3: Invalid Attempt Escalation

#### Scenario 3.1: Escalation After 3rd Invalid Attempt
```
Attempt 1:
  User: "yes"
  Bot: [Coaching] "Could you tell me your age as a number?"
  state.invalid_attempt_count: 1

Attempt 2:
  User: "sure"
  Bot: [Coaching] "Are you in your 20s, 30s, 40s, or 50s?"
  state.invalid_attempt_count: 2

Attempt 3:
  User: "maybe"
  Bot: [Coaching] "I'm having trouble understanding. Let me try differently..."
  state.invalid_attempt_count: 3

Attempt 4:
  User: "still confused"
  Bot: "I notice we're having difficulty here. Would you like to speak with our support team? 
        They can help guide you personally."
  state.escalation_offered: true
```

### Test Suite 4: Off-Topic Detection

#### Scenario 4.1: Clearly Off-Topic
```
Query: "What's the weather?"
Expected:
  - relevance_score: < 50
  - is_off_topic: true
  - Bot response: Warm redirect like "I see you're curious! 😊 
                  I'm here to help with credit cards. Shall we find the right card for you?"
  - state.confusion_counter: 1
```

#### Scenario 4.2: Somewhat Off-Topic
```
Query: "I like shopping"
Expected:
  - relevance_score: 50-65
  - is_off_topic: false
  - Bot still acknowledges but redirects to cards
  - state.confusion_counter: 1
```

#### Scenario 4.3: Clear Banking Query
```
Query: "I need a card with dining rewards"
Expected:
  - relevance_score: > 85
  - is_off_topic: false
  - Regular processing continues
  - state.confusion_counter: unchanged
```

### Test Suite 5: Escalation After Repeated Off-Topic

#### Scenario 5.1: Multiple Off-Topic Turns
```
Turn 1: "What's the weather?" → confusion_counter: 1
Turn 2: "Tell me a joke" → confusion_counter: 2  
Turn 3: "How's your day?" → confusion_counter: 3
Turn 4: "Favorite movie?" → confusion_counter: 4

After Turn 4:
Bot: "I notice we're going in different directions. Would you like to speak 
      with our support team who might help you better?"
state.escalation_offered: true
```

### Test Suite 6: Confirmation Flow

#### Scenario 6.1: Full Profiling with Confirmations
```
Bot: "What's your age?"
User: "30"
Bot: "Got it - you're **30 years old**. ✓\nNext, what's your employment type?"

User: "salaried"
Bot: "Perfect - you're **employed/salaried**. ✓\nHow long have you been employed?"

User: "8 years"
Bot: "Great! So you've been employed for **8 years**. ✓\nWhat's your monthly income?"

User: "50k"
Bot: "Excellent - you earn **BDT 50,000/month** (approximately **BDT 600,000 annually**). Correct?\n
      Do you have an E-TIN?"

Result:
- state.last_data_confirmed contains all confirmed values with timestamps
- No ambiguity, all values formatted with bold
```

### Test Suite 7: Employment Type Validation

#### Scenario 7.1: Standard Employment
```
User: "I'm a civil engineer at a software company"
Expected:
  - valid: true
  - employment_type: "salaried"
  - coaching_message: ""
```

#### Scenario 7.2: Ambiguous Employment
```
User: "not sure"
Expected:
  - valid: false
  - employment_type: null
  - coaching_message: "Could you tell me your employment situation? Are you: 
                      1) Employed (salaried), 2) Self-employed/freelancer, 
                      3) Business owner, or 4) Student?"
  - is_retryable: true
```

### Test Suite 8: E-TIN Validation

#### Scenario 8.1: Yes Response
```
User: "yes i have"
Expected:
  - valid: true
  - has_etin: true
  - coaching_message: ""
```

#### Scenario 8.2: No Response
```
User: "no, never"
Expected:
  - valid: true
  - has_etin: false
  - coaching_message: "" (or explanation if applicable)
```

#### Scenario 8.3: Unclear Response
```
User: "maybe"
Expected:
  - valid: false
  - has_etin: null
  - coaching_message: "Do you have an E-TIN (Employer's Tax ID) or not? 
                      Please answer 'yes' or 'no'."
  - is_retryable: true
```

### Test Suite 9: Context References

#### Scenario 9.1: Context in Follow-Up
```
User: "What cards are best?"
Bot: [collects profile data]
[Later after eligibility check]
Bot: "Based on what you mentioned earlier - earning **BDT 600,000 annually** 
     with 8 years in your salaried role - the Visa Gold Card would be ideal..."
```

### Test Suite 10: Follow-Up Questions

#### Scenario 10.1: Follow-Up After Eligibility
```
Bot: [Eligibility result]
"Based on your profile, you're eligible for: [Product A, Product B]

**Next Steps:**
Would you like to:
1. Check eligibility for another card?
2. Apply for one of these cards?
3. Learn more about a specific card?"
```

## Performance Benchmarks

### Expected Response Times
- Age validation: < 1s
- Income extraction: 1-2s (complex parsing)
- Employment match: < 1s
- E-TIN validation: < 1s
- Off-topic detection: < 1s
- Full profiling cycle: 5-8s total

### State Tracking Verification
```python
# After testing, verify state contents:
print(f"Invalid attempts: {state.invalid_attempt_count}")
print(f"Confusion counter: {state.confusion_counter}")
print(f"Confirmed values: {state.last_data_confirmed}")
print(f"Escalation offered: {state.escalation_offered}")
print(f"Last validated field: {state.last_validated_field}")
```

## Debugging Checklist

- [ ] All validators import successfully
- [ ] Ollama responds within 2 seconds
- [ ] JSON parsing works for all validators
- [ ] Confirmations show bold formatted data
- [ ] Invalid attempts tracked correctly
- [ ] Escalation offered after 3+ invalid
- [ ] Off-topic queries detected (relevance < 55)
- [ ] Confusion counter increments on off-topic
- [ ] Escalation flag prevents re-offering
- [ ] Follow-ups appear after key events
- [ ] Warm tone (not robotic) in all messages
- [ ] Context references work ("You mentioned...")
- [ ] State persists across conversation turns

## Edge Cases to Test

1. **Income**: "200k", "200,000", "200000", "2 lakh", "5 lakh", "0", "-100k"
2. **Age**: "17", "18", "70", "71", "100", "three hundred"
3. **Employment**: "freelance", "own amazon", "startup founder", "retired"
4. **Tenure**: "just started", "1 month", "6 months", "1 year", "20 years"
5. **E-TIN**: "yes but not sure what it is", "my company has it", "never heard of it"
6. **Off-topic**: Weather, jokes, personal questions, language mix

## Success Criteria

✅ All validators return expected output structure  
✅ Coaching messages are warm and contextual  
✅ Confirmations show formatted data with bold  
✅ Invalid attempts trigger escalation at threshold  
✅ Off-topic queries redirect appropriately  
✅ Confusion counter tracks accurately  
✅ Follow-ups appear after key events  
✅ State persists and tracks properly  
✅ All responses feel natural (not robotic)  
✅ Response times < 2s per validation  

## Regression Testing

After each change, verify:
1. Previous working scenarios still work
2. No new syntax errors
3. State tracking remains accurate
4. Ollama connectivity stable
5. JSON parsing handles edge cases
6. Warm tone maintained
7. No generic error messages

---

**Ready to Test**: ✅ YES - All code compiles, all imports work, ready for integration testing

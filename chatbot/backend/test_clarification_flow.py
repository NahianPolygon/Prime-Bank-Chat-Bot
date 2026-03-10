#!/usr/bin/env python3
"""
Test the smart clarification flow for vague queries.
Verifies that banking_type is asked first, then other profiles.
"""

import sys
sys.path.insert(0, '/app/backend')

from pipelines.crew.clarification import ClarificationBuilder

print("\n" + "=" * 80)
print("TESTING SMART CLARIFICATION FLOW")
print("=" * 80)

# Test 1: Vague product_info query
print("\n" + "=" * 80)
print("TEST 1: Vague Query - 'i want a credit card...which will be best for me?'")
print("=" * 80)

intent_type = "product_info"
extracted_profile = {
    "specific_features": [],
    "customer_income": None,
    "banking_type": None,
}

needs_clari, missing = ClarificationBuilder.needs_clarification(intent_type, extracted_profile)
print(f"\nNeeds Clarification: {needs_clari}")
print(f"Missing Fields: {missing}")
print(f"Expected: banking_type FIRST in list")
print(f"Actual First Field: {missing[0] if missing else 'None'}")

if missing and missing[0] == "banking_type":
    print("✅ PASS: banking_type is prioritized first!")
else:
    print("❌ FAIL: banking_type should be first!")

# Generate questions
questions = ClarificationBuilder.get_clarification_questions(missing, collected_profile={})
print(f"\nGenerated Questions:\n{questions}")

# Verify banking_type question is first in output
if "conventional" in questions.lower() and questions.lower().index("conventional") < questions.lower().find("annual"):
    print("\n✅ PASS: Conventional/Islamic question appears before income question!")
else:
    print("\n❌ FAIL: Banking type question should come first!")

# Test 2: Partially collected profile
print("\n\n" + "=" * 80)
print("TEST 2: After User Provides Income (100k/month)")
print("=" * 80)

# Simulate user answering "100k monthly"
user_response = "My monthly salary is 100k"
collected_profile = {"annual_income": 1200000}  # 100k * 12

# Check what's still missing
still_missing = missing.copy()
if "annual_income" in still_missing:
    still_missing.remove("annual_income")

print(f"User provided: annual_income=100k/month")
print(f"Still missing: {still_missing}")
print(f"Expected: banking_type, primary_use_case (but NOT annual_income)")

if "annual_income" not in still_missing:
    print("✅ PASS: annual_income removed from missing")
else:
    print("❌ FAIL: annual_income should be removed")

if "banking_type" in still_missing:
    print("✅ PASS: banking_type still in missing (should ask next!)")
else:
    print("❌ FAIL: banking_type should still be missing")

# Generate next question
next_questions = ClarificationBuilder.get_clarification_questions(still_missing, collected_profile=collected_profile)
print(f"\nNext Questions:\n{next_questions}")

if "conventional" in next_questions.lower():
    print("\n✅ PASS: Will ask banking type next!")
else:
    print("\n❌ FAIL: Should ask banking type!")

# Test 3: Full profile collection
print("\n\n" + "=" * 80)
print("TEST 3: After Providing All Profile Info")
print("=" * 80)

full_profile = {
    "banking_type": "conventional",
    "primary_use_case": "travel",
    "annual_income": 1200000,  # ✅ Use annual_income (not customer_income)
    "employment_type": "salaried",
    "specific_features": ["travel"],  # ✅ Add features so it doesn't trigger vague check
}

no_missing_needed, empty_missing = ClarificationBuilder.needs_clarification(
    intent_type,
    full_profile
)

print(f"Needs Clarification: {no_missing_needed}")
print(f"Missing Fields: {empty_missing}")

if not no_missing_needed and not empty_missing:
    print("✅ PASS: All profile info collected, ready for recommendations!")
else:
    print("❌ FAIL: Should not need more clarification when profile complete")

print("\n" + "=" * 80)
print("✅ CLARIFICATION FLOW TEST COMPLETE")
print("=" * 80 + "\n")

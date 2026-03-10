"""
Eligibility Extraction Tool for CrewAI — parses product requirements from markdown.
Wraps the EligibilityExtractor to be usable as a CrewAI tool.
"""

from crewai.tools import tool
from utils.eligibility_extractor import EligibilityExtractor


@tool
def extract_eligibility_requirements(product_text: str) -> dict:
    """
    Extract eligibility requirements from a product's text.
    
    Args:
        product_text: Full markdown text of the product (from RAG search result)
    
    Returns:
        Dictionary with:
        - income_min: Minimum annual income (BDT) or None if not found
        - tenure_min: Minimum tenure in months or None
        - age_min/age_max: Age requirements or None
        - features: List of product features (lounge_access, airport_benefits, etc.)
        - confidence: How confident we are about the extracted requirements
    """
    # Use the extract_all method which returns comprehensive data
    extracted = EligibilityExtractor.extract_all(product_text)
    
    eligibility = extracted["eligibility"]
    features = extracted["features"]
    
    # Filter features to only those that are True
    active_features = [f for f, active in features.items() if active]
    
    return {
        "income_min": eligibility["min_annual_income"],
        "tenure_min": eligibility["tenure"].get("salaried_months") or eligibility["tenure"].get("self_employed_years"),
        "age_min": eligibility["age"].get("min_age"),
        "age_max": eligibility["age"].get("max_age"),
        "features": active_features,
        "all_features": features,
        "confidence": "high" if eligibility["min_annual_income"] else "medium",
    }


@tool
def check_eligibility(
    customer_age: int = None,
    customer_income: float = None,
    customer_tenure_months: int = None,
    income_min: float = 0,
    tenure_min: int = 0,
    age_min: int = 0,
    age_max: int = 100,
) -> dict:
    """
    Check if a customer meets product eligibility requirements.
    
    Args:
        customer_age: Customer's age in years (optional)
        customer_income: Customer's annual income in BDT (optional)
        customer_tenure_months: Banking tenure in months (optional)
        income_min: Minimum required income (BDT) - use 0 for no requirement
        tenure_min: Minimum required tenure (months) - use 0 for no requirement
        age_min: Minimum age - use 0 for no requirement
        age_max: Maximum age - use 100 for no requirement
    
    Returns:
        Dictionary with:
        - is_eligible: Boolean
        - fit_level: "EXCELLENT", "GOOD", "MARGINAL", or "NOT_ELIGIBLE"
        - gaps: List of unmet requirements
        - meets: List of met requirements
        - next_income_needed: Income required to become eligible (if not now)
    """
    gaps = []
    meets = []
    requirements_checked = 0
    
    # Check income (only if income_min > 0, meaning requirement exists)
    if income_min > 0 and customer_income:
        requirements_checked += 1
        if customer_income >= income_min:
            meets.append(f"Income: ✓ BDT {customer_income:,.0f}/year (exceeds {income_min:,.0f})")
        else:
            gap = income_min - customer_income
            gaps.append(f"Income: short by BDT {gap:,.0f}/year (need {income_min:,.0f}, have {customer_income:,.0f})")
    elif income_min > 0 and not customer_income:
        gaps.append("Income: Not provided, cannot verify")
    
    # Check tenure (only if tenure_min > 0)
    if tenure_min > 0 and customer_tenure_months:
        requirements_checked += 1
        if customer_tenure_months >= tenure_min:
            meets.append(f"Tenure: ✓ {customer_tenure_months} months (exceeds {tenure_min})")
        else:
            gap_months = tenure_min - customer_tenure_months
            gaps.append(f"Tenure: short by {gap_months} months")
    elif tenure_min > 0 and not customer_tenure_months:
        gaps.append("Tenure: Not provided, cannot verify")
    
    # Check age (only if age_min > 0 or age_max < 100)
    if (age_min > 0 or age_max < 100) and customer_age:
        requirements_checked += 1
        if customer_age >= age_min and customer_age <= age_max:
            meets.append(f"Age: ✓ {customer_age} years (within {age_min}-{age_max})")
        else:
            gaps.append(f"Age: {customer_age} outside range {age_min}-{age_max}")
    elif (age_min > 0 or age_max < 100) and not customer_age:
        gaps.append("Age: Not provided, cannot verify")
    
    # Determine fit level
    is_eligible = len(gaps) == 0 and requirements_checked > 0
    if is_eligible:
        # Excellent if exceeds income by 30%+
        fit_level = "EXCELLENT" if (income_min > 0 and customer_income and customer_income >= income_min * 1.3) else "GOOD"
    elif len(gaps) == 1:
        fit_level = "MARGINAL"
    elif len(gaps) > 1:
        fit_level = "NOT_ELIGIBLE"
    else:
        fit_level = "GOOD"  # No requirements specified
    
    return {
        "is_eligible": is_eligible,
        "fit_level": fit_level,
        "gaps": gaps,
        "meets": meets,
        "next_income_needed": max(0, (income_min - customer_income)) if income_min > 0 and customer_income else 0,
    }

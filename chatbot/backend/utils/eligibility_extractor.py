"""
Eligibility Extractor — parses markdown product data to extract structured requirements.
Converts vague text like "Annual income typically BDT 5+ lakh" into {min_annual_income: 500000}.
"""

import re
from typing import Dict, Any, Optional


class EligibilityExtractor:
    """Extracts structured eligibility data from markdown product text."""
    
    # Patterns to match income requirements
    INCOME_PATTERNS = [
        r"(?:annual\s+)?income\s+(?:typically|at\s+least)?\s*(?:BDT|₹)?\s*([0-9.]+)\s*(?:lakh|lac|l)(?:\s*\+)?",
        r"(?:minimum|min)\s+(?:annual\s+)?income\s*[:\-]?\s*(?:BDT|₹)?\s*([0-9.]+)\s*(?:lakh|lac|l)",
        r"(?:bdt|₹)?\s*([0-9.]+)\s*(?:lakh|lac|l)\+?(?:\s+(?:annual|per\s+year))?",
    ]
    
    # Patterns for tenure/employment
    TENURE_PATTERNS = [
        r"(?:salaried|employed).*?(?:minimum|min)?\s*([0-9]+)\s*(?:month|year)s?",
        r"(?:self-employed|business owner).*?(?:minimum|min)?\s*([0-9]+)\s*(?:month|year)s?",
    ]
    
    # Age patterns
    AGE_PATTERNS = [
        r"age\s*[:\-]?\s*([0-9]+)\s*(?:\-|to)\s*([0-9]+)",
        r"ages?\s+([0-9]+)\s+(?:to\s+)?([0-9]+)",
    ]
    
    # Feature patterns
    FEATURE_KEYWORDS = {
        "lounge_access": ["lounge", "vip access", "balaka", "loungekey"],
        "airport_benefits": ["airport", "welcome service", "fast-track"],
        "dining_benefits": ["dining", "bogo", "restaurant"],
        "travel_benefits": ["travel", "priority pass", "international"],
        "rewards": ["reward points", "cashback", "points per"],
        "interest_free": ["interest-free", "0%", "grace period"],
    }
    
    @staticmethod
    def convert_lakh_to_number(lakh_str: str) -> Optional[int]:
        """Convert '5+ lakh' or '12 lakh' to 500000 or 1200000."""
        try:
            # Extract number
            match = re.search(r"([0-9.]+)", lakh_str)
            if not match:
                return None
            
            num = float(match.group(1))
            # Convert lakh to absolute number (1 lakh = 100,000)
            return int(num * 100000)
        except (ValueError, AttributeError):
            return None
    
    @staticmethod
    def extract_income_requirement(text: str) -> Optional[int]:
        """
        Extract minimum annual income from text.
        Returns: Annual income in absolute numbers (e.g., 1200000 for "12 lakh")
        """
        text_lower = text.lower()
        
        for pattern in EligibilityExtractor.INCOME_PATTERNS:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                lakh_value = match.group(1)
                converted = EligibilityExtractor.convert_lakh_to_number(lakh_value + " lakh")
                if converted:
                    return converted
        
        return None
    
    @staticmethod
    def extract_tenure_requirements(text: str) -> Dict[str, Optional[int]]:
        """
        Extract tenure requirements for salaried and self-employed.
        Returns: {"salaried_months": 6, "self_employed_years": 3}
        """
        result = {"salaried_months": None, "self_employed_years": None}
        text_lower = text.lower()
        
        # Look for salaried tenure
        salaried_match = re.search(r"salaried.*?(?:minimum|min)?\s*([0-9]+)\s*(?:month|year)s?", text_lower)
        if salaried_match:
            months = int(salaried_match.group(1))
            # If years, convert to months
            if "year" in salaried_match.group(0):
                months *= 12
            result["salaried_months"] = months
        
        # Look for self-employed tenure
        self_employed_match = re.search(r"(?:self-employed|self employed).*?(?:minimum|min)?\s*([0-9]+)\s*(?:month|year)s?", text_lower)
        if self_employed_match:
            value = int(self_employed_match.group(1))
            # If months, convert to years
            if "month" in self_employed_match.group(0):
                value = value // 12
            result["self_employed_years"] = value
        
        return result
    
    @staticmethod
    def extract_age_requirements(text: str) -> Dict[str, Optional[int]]:
        """
        Extract age requirements.
        Returns: {"min_age": 18, "max_age": 70}
        """
        result = {"min_age": None, "max_age": None}
        text_lower = text.lower()
        
        for pattern in EligibilityExtractor.AGE_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                age1 = int(match.group(1))
                age2 = int(match.group(2))
                result["min_age"] = min(age1, age2)
                result["max_age"] = max(age1, age2)
                break
        
        return result
    
    @staticmethod
    def extract_features(text: str) -> Dict[str, bool]:
        """
        Extract what features the product has.
        Returns: {"lounge_access": True, "airport_benefits": True, ...}
        """
        features = {}
        text_lower = text.lower()
        
        for feature, keywords in EligibilityExtractor.FEATURE_KEYWORDS.items():
            has_feature = any(keyword in text_lower for keyword in keywords)
            features[feature] = has_feature
        
        return features
    
    @staticmethod
    def extract_all(product_markdown: str, product_name: str = "") -> Dict[str, Any]:
        """
        Extract all eligibility and feature information from product markdown.
        
        Args:
            product_markdown: Raw markdown text from knowledge base
            product_name: Name of the product (for reference)
        
        Returns:
            Dictionary with extracted eligibility requirements and features
        """
        result = {
            "product_name": product_name,
            "eligibility": {
                "min_annual_income": EligibilityExtractor.extract_income_requirement(product_markdown),
                "tenure": EligibilityExtractor.extract_tenure_requirements(product_markdown),
                "age": EligibilityExtractor.extract_age_requirements(product_markdown),
            },
            "features": EligibilityExtractor.extract_features(product_markdown),
            "raw_text": product_markdown[:500],  # Store snippet for debugging
        }
        
        return result
    
    @staticmethod
    def check_eligibility(
        customer_age: Optional[int],
        customer_monthly_income: Optional[int],
        customer_tenure_months: Optional[int],
        employment_type: str,
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if customer meets product eligibility.
        
        Args:
            customer_age: Customer's age
            customer_monthly_income: Customer's monthly income in absolute numbers
            customer_tenure_months: Months in current job
            employment_type: "salaried" or "self_employed"
            requirements: Extracted eligibility from extract_all()
        
        Returns:
            {
                "eligible": bool,
                "reasons": [str],  # Why eligible/ineligible
                "gaps": [str],     # What doesn't match
                "confidence": float # 0-1, how confident we are
            }
        """
        reasons = []
        gaps = []
        checks_passed = 0
        total_checks = 0
        
        # Check age
        if customer_age and requirements["eligibility"]["age"]["min_age"]:
            total_checks += 1
            if customer_age >= requirements["eligibility"]["age"]["min_age"]:
                checks_passed += 1
                reasons.append(f"✓ Age {customer_age} meets minimum {requirements['eligibility']['age']['min_age']}")
            else:
                gaps.append(f"✗ Age {customer_age} below minimum {requirements['eligibility']['age']['min_age']}")
        
        # Check income
        if customer_monthly_income and requirements["eligibility"]["min_annual_income"]:
            customer_annual = customer_monthly_income * 12
            total_checks += 1
            if customer_annual >= requirements["eligibility"]["min_annual_income"]:
                checks_passed += 1
                reasons.append(f"✓ Income BDT {customer_annual:,}/year meets minimum BDT {requirements['eligibility']['min_annual_income']:,}")
            else:
                gap_amount = requirements["eligibility"]["min_annual_income"] - customer_annual
                gaps.append(f"✗ Income BDT {customer_annual:,}/year (need BDT {gap_amount:,} more)")
        
        # Check tenure
        tenure_key = f"{employment_type}_months" if employment_type == "salaried" else f"self_employed_years"
        tenure_value = requirements["eligibility"]["tenure"].get(tenure_key)
        
        if tenure_value and customer_tenure_months:
            total_checks += 1
            if employment_type == "salaried":
                if customer_tenure_months >= tenure_value:
                    checks_passed += 1
                    reasons.append(f"✓ Tenure {customer_tenure_months}m meets minimum {tenure_value}m")
                else:
                    gaps.append(f"✗ Tenure {customer_tenure_months}m below minimum {tenure_value}m")
            else:
                customer_tenure_years = customer_tenure_months // 12
                if customer_tenure_years >= tenure_value:
                    checks_passed += 1
                    reasons.append(f"✓ Business tenure {customer_tenure_years}y meets minimum {tenure_value}y")
                else:
                    gaps.append(f"✗ Business tenure only {customer_tenure_years}y, need {tenure_value}y")
        
        eligible = len(gaps) == 0 if total_checks > 0 else None
        confidence = checks_passed / total_checks if total_checks > 0 else 0.5
        
        return {
            "eligible": eligible,
            "reasons": reasons,
            "gaps": gaps,
            "confidence": confidence,
            "checks_passed": checks_passed,
            "total_checks": total_checks,
        }

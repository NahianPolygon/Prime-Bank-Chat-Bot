"""Eligibility and validation tools for bank chatbot agents."""

from crewai.tools import tool
from typing import Optional


class EligibilityTools:
    """Tools for checking eligibility and requirements."""
    
    @tool("check_employment_eligibility")
    def check_employment_eligibility(employment_type: str, 
                                     tenure_months: Optional[int] = None,
                                     product_name: str = "Credit Card") -> str:
        """
        Check if employment type and tenure meet product requirements.
        
        Args:
            employment_type: Type of employment (e.g., 'salaried', 'self-employed', 'business_owner')
            tenure_months: Months in current employment/business
            product_name: Name of the product
            
        Returns:
            Eligibility status and explanation
        """
        assessment = f"**Employment Eligibility for {product_name}**\n\n"
        
        employment_lower = employment_type.lower()
        
        # Standard requirements for credit products
        if 'credit' in product_name.lower():
            if 'salaried' in employment_lower:
                required_tenure = 6  # 6 months for salaried
                assessment += f"**Status:** Salaried Professional\n"
                assessment += f"**Requirement:** Minimum {required_tenure} months in current job\n"
                
                if tenure_months:
                    if tenure_months >= required_tenure:
                        assessment += f"✓ **You have {tenure_months} months** - ELIGIBLE\n"
                        return assessment
                    else:
                        gap = required_tenure - tenure_months
                        assessment += f"✗ **You have {tenure_months} months** - Need {gap} more months\n"
                        assessment += f"**Timeline:** You can apply after {gap} month(s)\n"
                        return assessment
                else:
                    assessment += f"ℹ️ Please provide your tenure details\n"
                    
            elif 'self-employed' in employment_lower or 'business' in employment_lower:
                required_tenure = 36  # 3 years for self-employed
                assessment += f"**Status:** Self-Employed / Business Owner\n"
                assessment += f"**Requirement:** Minimum {required_tenure} months (3 years) business tenure\n"
                
                if tenure_months:
                    if tenure_months >= required_tenure:
                        assessment += f"✓ **You have {tenure_months} months** - ELIGIBLE\n"
                        return assessment
                    else:
                        gap = required_tenure - tenure_months
                        assessment += f"✗ **You have {tenure_months} months** - Need {gap} more months\n"
                        assessment += f"**Timeline:** You can apply in {int(gap/12)} year(s) and {gap%12} month(s)\n"
                        return assessment
                else:
                    assessment += f"ℹ️ Please provide your business tenure details\n"
            else:
                assessment += f"**Status:** {employment_type}\n"
                assessment += f"Please clarify your employment status for accurate assessment\n"
        
        return assessment
    
    @tool("check_credit_requirements")
    def check_credit_requirements(has_etin: bool = None,
                                  age: Optional[int] = None, 
                                  has_credit_history: Optional[bool] = None,
                                  monthly_income: Optional[float] = None) -> str:
        """
        Check eligibility requirements for credit products.
        
        Args:
            has_etin: Do they have valid E-TIN?
            age: Age in years
            has_credit_history: Do they have good credit history?
            monthly_income: Monthly income
            
        Returns:
            Eligibility assessment
        """
        assessment = "**Credit Product Requirements Assessment**\n\n"
        
        # E-TIN Check (Mandatory)
        assessment += "**1. E-TIN (Tax ID) - MANDATORY**\n"
        if has_etin is not None:
            if has_etin:
                assessment += "✓ Have valid E-TIN\n\n"
            else:
                assessment += "✗ Missing valid E-TIN - REQUIRED to apply\n"
                assessment += "   Please register for E-TIN at tax office\n\n"
        else:
            assessment += "ℹ️ Please confirm if you have valid E-TIN\n\n"
        
        # Age Check
        assessment += "**2. Age - 18-70 years required**\n"
        if age is not None:
            if 18 <= age <= 70:
                assessment += f"✓ Age {age} - ELIGIBLE\n\n"
            else:
                assessment += f"✗ Age {age} - Outside acceptable range (18-70)\n\n"
        else:
            assessment += "ℹ️ Please provide your age\n\n"
        
        # Credit History
        assessment += "**3. Credit History - Preferred but may be waivable**\n"
        if has_credit_history is not None:
            if has_credit_history:
                assessment += "✓ Good credit history\n\n"
            else:
                assessment += "⚠️ No/Limited credit history - Can still apply with guarantor\n\n"
        else:
            assessment += "ℹ️ Have you used credit cards or loans before?\n\n"
        
        # Income Check
        assessment += "**4. Monthly Income - Regular income required**\n"
        if monthly_income:
            if monthly_income >= 30000:
                if monthly_income >= 100000:
                    assessment += f"✓ Monthly Income: BDT {monthly_income:,} - Eligible for high-limit products\n"
                else:
                    assessment += f"✓ Monthly Income: BDT {monthly_income:,} - Eligible for standard products\n"
            else:
                assessment += f"⚠️ Monthly Income: BDT {monthly_income:,} - Low income, may get limited credit\n"
        else:
            assessment += "ℹ️ Please provide approximate monthly income\n"
        
        return assessment
    
    @tool("check_document_requirements")
    def check_document_requirements(product_type: str = "Credit Card",
                                    employment_type: str = "salaried") -> str:
        """
        List and check required documents for a product.
        
        Args:
            product_type: Type of product (e.g., 'Credit Card')
            employment_type: Employment type ('salaried', 'self-employed', 'business_owner')
            
        Returns:
            Required documents checklist
        """
        docs = "**Required Documents for " + product_type + "**\n\n"
        
        docs += "**Identity & Address Proof:**\n"
        docs += "- [ ] NID/Passport (copy, attested)\n"
        docs += "- [ ] Driving License (if available)\n"
        docs += "- [ ] Utility Bill (less than 2 months old)\n"
        docs += "- [ ] Permanent Address Certificate\n\n"
        
        docs += "**Tax & Legal Documents:**\n"
        docs += "- [ ] Valid E-TIN Certificate (MANDATORY)\n\n"
        
        # Employment-specific documents
        if 'salaried' in employment_type.lower():
            docs += "**Salaried-Specific Documents:**\n"
            docs += "- [ ] Last 3 months salary slips\n"
            docs += "- [ ] Employment letter from employer\n"
            docs += "- [ ] Appointment letter (if recent)\n\n"
        
        elif 'self-employed' in employment_type.lower() or 'business' in employment_type.lower():
            docs += "**Self-Employed/Business-Specific Documents:**\n"
            docs += "- [ ] Latest Income Tax Return (ITR)\n"
            docs += "- [ ] Business Registration Certificate\n"
            docs += "- [ ] 3-year Audited Financial Statements\n"
            docs += "- [ ] Trade License\n\n"
        
        docs += "**Financial Documents:**\n"
        docs += "- [ ] Bank statements (6 months)\n"
        docs += "- [ ] Income Tax Return\n\n"
        
        docs += "**Personal Documents:**\n"
        docs += "- [ ] Passport-size photos (4 copies)\n"
        docs += "- [ ] Nominee identity proof\n"
        docs += "- [ ] Nominee relation certificate\n\n"
        
        docs += "**Processing Timeline:**\n"
        docs += "- Days 1-2: Document submission and verification\n"
        docs += "- Days 3-5: Background & credit verification\n"
        docs += "- Day 6: Credit decision\n"
        docs += "- Day 7+: Card issuance and activation\n"
        
        return docs

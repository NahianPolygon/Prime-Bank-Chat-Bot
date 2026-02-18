"""Eligibility and validation tools for bank chatbot agents."""

from crewai.tools import tool
from typing import Optional


class EligibilityTools:
    """Tools for checking eligibility and requirements."""
    
    @tool("check_employment_eligibility")
    def check_employment_eligibility(employment_type: str, product_name: str) -> str:
        """
        Check if employment type is eligible for a product.
        
        Args:
            employment_type: Type of employment (e.g., 'salaried', 'self-employed', 'student')
            product_name: Name of the product
            
        Returns:
            Eligibility status and explanation
        """
        # Employment compatibility matrix
        compatibility = {
            'salaried': ['credit', 'debit', 'savings'],
            'self-employed': ['business', 'credit', 'debit'],
            'student': ['student', 'savings', 'debit'],
            'retired': ['senior', 'savings', 'debit'],
            'business_owner': ['business', 'credit']
        }
        
        employment_lower = employment_type.lower()
        product_lower = product_name.lower()
        
        eligible_types = compatibility.get(employment_lower, [])
        
        is_compatible = any(comp in product_lower for comp in eligible_types)
        
        if is_compatible:
            return f"✓ {employment_type} is ELIGIBLE for {product_name}"
        else:
            return f"✗ {employment_type} may NOT be eligible for {product_name}. Recommend checking with bank."
    
    @tool("check_credit_requirements")
    def check_credit_requirements(credit_score: Optional[int] = None, 
                                  monthly_income: Optional[float] = None) -> str:
        """
        Check credit and income requirements.
        
        Args:
            credit_score: Optional credit score (0-900)
            monthly_income: Optional monthly income
            
        Returns:
            Eligibility assessment
        """
        assessment = "Credit Requirements Assessment:\n"
        
        if credit_score:
            if credit_score >= 750:
                assessment += f"✓ Credit Score {credit_score}: Excellent - Eligible for premium products\n"
            elif credit_score >= 650:
                assessment += f"✓ Credit Score {credit_score}: Good - Eligible for standard products\n"
            else:
                assessment += f"✗ Credit Score {credit_score}: May need improvement\n"
        
        if monthly_income:
            if monthly_income >= 100000:
                assessment += f"✓ Monthly Income: {monthly_income} - Eligible for high-limit cards\n"
            elif monthly_income >= 30000:
                assessment += f"✓ Monthly Income: {monthly_income} - Eligible for standard cards\n"
            else:
                assessment += f"✗ Monthly Income: {monthly_income} - May have lower limits\n"
        
        return assessment
    
    @tool("check_document_requirements")
    def check_document_requirements(product_type: str) -> str:
        """
        List required documents for a product.
        
        Args:
            product_type: Type of product (credit, debit, loan, etc.)
            
        Returns:
            List of required documents
        """
        requirements = {
            'credit': ['ID', 'Proof of Income', 'Bank Statement', 'Address Proof'],
            'debit': ['ID', 'Address Proof'],
            'loan': ['ID', 'Proof of Income', '3 Months Bank Statements', 'Address Proof', 'Collateral docs'],
            'savings': ['ID', 'Address Proof'],
            'investment': ['ID', 'Proof of Income', 'Bank Account', 'KYC']
        }
        
        docs = requirements.get(product_type.lower(), ['ID', 'Address Proof'])
        
        return f"Required Documents for {product_type}:\n" + "\n".join(f"- {doc}" for doc in docs)

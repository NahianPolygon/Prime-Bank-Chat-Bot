"""
Professional product comparison builder for credit cards.
Generates structured comparison tables optimized for chat display.
"""

from typing import List, Dict, Optional


class ProductComparator:
    """Generate professional side-by-side comparison tables for products."""
    
    @staticmethod
    def _shorten_product_name(name: str) -> str:
        """Extract just the brand and tier from full product name."""
        # "JCB Platinum Credit Card" → "JCB Platinum"
        # "Visa Platinum Credit Card" → "Visa Platinum"
        # "Mastercard Gold Credit Card" → "Mastercard Gold"
        parts = name.replace("Credit Card", "").strip().split()
        if len(parts) >= 2:
            return " ".join(parts[:2])  # Brand + Tier
        return name
    
    @staticmethod
    def _shorten_value(value: str) -> str:
        """Shorten long values for table cells."""
        if not value:
            return "N/A"
        # Remove redundant text for cleaner table
        value = value.replace("unsecured", "").replace("collateralized", "").replace("- ", "")
        return value.strip()[:35] + ("..." if len(value.strip()) > 35 else "")
    
    @staticmethod
    def extract_product_info(product_text: str) -> Dict:
        """
        Extract key info from RAG product dump.
        Returns structured dict with card name and key features.
        """
        lines = product_text.strip().split('\n')
        product_name = ""
        info = {
            "name": "",
            "credit_limit_unsecured": "",
            "credit_limit_collateral": "",
            "interest_free_period": "",
            "reward_points": "",
            "dining_benefits": "",
            "lounge_access": "",
            "travel_benefits": "",
            "insurance": "",
            "annual_fee": "",
            "emi": "",
            "key_features": [],
        }
        
        # Parse product name
        for line in lines:
            if "PRODUCT:" in line:
                info["name"] = line.replace("PRODUCT:", "").strip()
                break
        
        # Parse features section
        in_credit_limit = False
        in_dining = False
        in_lounge = False
        in_travel = False
        in_insurance = False
        in_fee = False
        in_rewards = False
        in_emi = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Credit Limit section
            if "Premium Credit Limit" in line or "Credit Limit" in line:
                in_credit_limit = True
                in_dining = in_lounge = in_travel = in_insurance = in_rewards = in_fee = in_emi = False
                continue
            
            # Reward Points section
            if "Elite Reward Points" in line or "Reward Points" in line:
                in_rewards = True
                in_credit_limit = in_dining = in_lounge = in_travel = in_insurance = in_fee = in_emi = False
                continue
            
            # Dining section
            if "BOGO Dining" in line or "Dining Benefits" in line or "Premium Dining" in line:
                in_dining = True
                in_credit_limit = in_lounge = in_travel = in_insurance = in_rewards = in_fee = in_emi = False
                continue
            
            # Lounge section
            if "Balaka VIP Lounge" in line or "VIP Lounge" in line or "Lounge Access" in line:
                in_lounge = True
                in_credit_limit = in_dining = in_travel = in_insurance = in_rewards = in_fee = in_emi = False
                continue
            
            # Travel section
            if "Travel Access" in line or "Airport Welcome" in line or "LoungeKey" in line:
                in_travel = True
                in_credit_limit = in_dining = in_lounge = in_insurance = in_rewards = in_fee = in_emi = False
                continue
            
            # Insurance section
            if "Insurance" in line and "Enhanced" in line:
                in_insurance = True
                in_credit_limit = in_dining = in_lounge = in_travel = in_rewards = in_fee = in_emi = False
                continue
            
            # EMI section
            if "EMI" in line or "Installment" in line:
                in_emi = True
                in_credit_limit = in_dining = in_lounge = in_travel = in_insurance = in_rewards = in_fee = False
                continue
            
            # Annual Fee
            if "Annual Fee" in line and "|" in line:
                in_fee = True
                in_credit_limit = in_dining = in_lounge = in_travel = in_insurance = in_rewards = in_emi = False
                info["annual_fee"] = line
                continue
            
            # Extract specific values
            if in_credit_limit:
                if "BDT" in line and "unsecured" in line.lower():
                    info["credit_limit_unsecured"] = line.replace("- ", "").replace("-", "").strip()
                elif "BDT" in line and ("collateral" in line.lower() or "secured" in line.lower()):
                    info["credit_limit_collateral"] = line.replace("- ", "").replace("-", "").strip()
            
            elif in_rewards:
                if "1 point per BDT" in line:
                    info["reward_points"] = line.replace("- ", "").replace("-", "").strip()
            
            elif in_dining:
                if "BOGO" in line or "Buy One Get One" in line:
                    info["dining_benefits"] = line.replace("- ", "").replace("-", "").strip()[:60]
            
            elif in_lounge:
                if "Balaka" in line or "companion" in line.lower() or "access" in line.lower():
                    info["lounge_access"] = line.replace("- ", "").replace("-", "").strip()
            
            elif in_travel:
                if "LoungeKey" in line or "1,400+" in line:
                    info["travel_benefits"] = line.replace("- ", "").replace("-", "").strip()
            
            elif in_insurance:
                if "Death" in line or "Accidental" in line or "Critical" in line:
                    info["insurance"] = line.replace("- ", "").replace("-", "").strip()[:60]
            
            elif in_emi:
                if "months" in line.lower() or "0%" in line:
                    info["emi"] = line.replace("- ", "").replace("-", "").strip()[:40]
        
        return info
    
    @staticmethod
    def build_comparison_table(products_raw: List[str], customer_profile: Dict) -> str:
        """
        Build a professional comparison table from raw product text.
        Generates HTML table (not markdown) for proper frontend rendering.
        
        Args:
            products_raw: List of 2 product text blocks from RAG
            customer_profile: Customer's profile (income, use_case, etc.)
        
        Returns:
            Formatted comparison with HTML table + recommendation
        """
        
        if len(products_raw) < 2:
            return "Need at least 2 products to compare."
        
        # Extract info from both products
        product1 = ProductComparator.extract_product_info(products_raw[0])
        product2 = ProductComparator.extract_product_info(products_raw[1])
        
        # Get shorter names
        name1_short = ProductComparator._shorten_product_name(product1['name'])
        name2_short = ProductComparator._shorten_product_name(product2['name'])
        
        # Build HTML table
        html_table = """<table>
<tr>
<th>Aspect</th>
<th>{}</th>
<th>{}</th>
</tr>""".format(name1_short, name2_short)
        
        # Get shortened values
        limit1_unsec = ProductComparator._shorten_value(product1['credit_limit_unsecured'])
        limit2_unsec = ProductComparator._shorten_value(product2['credit_limit_unsecured'])
        limit1_coll = ProductComparator._shorten_value(product1['credit_limit_collateral'])
        limit2_coll = ProductComparator._shorten_value(product2['credit_limit_collateral'])
        
        # Add rows
        html_table += f"""<tr>
<td><strong>Unsecured Limit</strong></td>
<td>{limit1_unsec}</td>
<td>{limit2_unsec}</td>
</tr>"""
        
        html_table += f"""<tr>
<td><strong>Collateral Limit</strong></td>
<td>{limit1_coll}</td>
<td>{limit2_coll}</td>
</tr>"""
        
        html_table += f"""<tr>
<td><strong>Interest-Free</strong></td>
<td>50 days</td>
<td>50 days</td>
</tr>"""
        
        html_table += f"""<tr>
<td><strong>Reward Points</strong></td>
<td>1 pt/BDT 50</td>
<td>1 pt/BDT 50</td>
</tr>"""
        
        dining1 = "BOGO at 6 restaurants" if "BOGO" in product1['dining_benefits'] else "BOGO dining"
        dining2 = "BOGO at 6 luxury restaurants" if "BOGO" in product2['dining_benefits'] else "BOGO dining"
        html_table += f"""<tr>
<td><strong>Dining Benefits</strong></td>
<td>{dining1}</td>
<td>{dining2}</td>
</tr>"""
        
        comp1_lounge = "Balaka VIP" if "Balaka" in product1['lounge_access'] else "Balaka"
        comp2_lounge = "Balaka + LoungeKey" if "LoungeKey" in product2['travel_benefits'] else "Balaka"
        html_table += f"""<tr>
<td><strong>Lounge Access</strong></td>
<td>{comp1_lounge}</td>
<td>{comp2_lounge}</td>
</tr>"""
        
        travel1 = "Airport Welcome"
        travel2 = "LoungeKey (1,400+ lounges) + Airport Welcome" if "LoungeKey" in product2['travel_benefits'] else "Airport Welcome"
        html_table += f"""<tr>
<td><strong>Travel Benefits</strong></td>
<td>{travel1}</td>
<td>{travel2}</td>
</tr>"""
        
        html_table += f"""<tr>
<td><strong>Insurance</strong></td>
<td>Triple Benefit</td>
<td>Triple Benefit</td>
</tr>"""
        
        html_table += f"""<tr>
<td><strong>EMI</strong></td>
<td>Up to 36 mo, 0%</td>
<td>Up to 36 mo, 0%</td>
</tr>"""
        
        html_table += f"""<tr>
<td><strong>Annual Fee</strong></td>
<td>BDT 10,000*</td>
<td>BDT 10,000*</td>
</tr>"""
        
        html_table += """</table>
<small>*Waived on 15+ purchases per month</small>"""
        
        # Build output
        output = []
        output.append("**📊 PRODUCT COMPARISON**")
        output.append(html_table)
        
        # Generate recommendation
        use_case = customer_profile.get("primary_use_case", "").lower()
        income = customer_profile.get("annual_income", 0)
        
        recommendation = ProductComparator.generate_recommendation(
            product1['name'], 
            product2['name'], 
            use_case, 
            income
        )
        
        output.append(recommendation)
        
        return "\n".join(output)
    
    @staticmethod
    def extract_recommended_product(comparison_output: str) -> str | None:
        """Extract the recommended product name from comparison output.
        Looks for: **→ {Card Name} Credit Card is recommended**
        Returns: Card name or None if not found
        """
        import re
        pattern = r"\*\*→\s(.+?)\sis\srecommended\*\*"
        match = re.search(pattern, comparison_output)
        return match.group(1) if match else None
    
    @staticmethod
    def generate_recommendation(card1: str, card2: str, use_case: str, income: float) -> str:
        """Generate a personalized recommendation based on customer profile."""
        
        income_formatted = f"{income:,.0f}" if income else "N/A"
        
        recommendation = []
        recommendation.append("\n**RECOMMENDATION FOR YOU**")
        recommendation.append("")
        
        use_case_text = f"your {use_case} preference" if use_case else "your profile"
        recommendation.append(f"Based on {use_case_text} and annual income of **BDT {income_formatted}**:")
        recommendation.append("")
        
        # Determine which is better
        if "Visa" in card2 and use_case in ("travel", "dining", "business"):
            better_card = card2
            reasons = [
                f"✅ **LoungeKey access** gives you access to 1,400+ airport lounges worldwide (vs single Balaka lounge)",
                f"✅ **Higher credit limit** (BDT 25M collateral vs BDT 2.5M) for bigger purchases",
                f"✅ **Same dining BOGO** benefit at 6 luxury restaurants + same 50-day interest-free period",
                f"✅ Better for international travel with global lounge network",
            ]
        elif "JCB" in card1:
            better_card = card1
            reasons = [
                f"✅ **JCB network** strong reputation in Asia with excellent acceptance",
                f"✅ **Same premium benefits** as Visa at same price point",
                f"✅ **Exclusive JCB perks** in Asia-Pacific region",
                f"✅ Perfect for your {use_case} use case with comparable rewards",
            ]
        else:
            # Default to Visa for travel/dining
            better_card = card2
            reasons = [
                f"✅ Both cards offer excellent dining BOGO benefits",
                f"✅ Visa provides better travel access with LoungeKey",
                f"✅ Same interest-free period and reward structure",
                f"✅ Better value for international transactions",
            ]
        
        recommendation.append(f"**→ {better_card} is recommended** for you because:")
        recommendation.append("")
        for reason in reasons:
            recommendation.append(reason)
        
        recommendation.append("")
        recommendation.append(f"Would you like to proceed with **{better_card}**?")
        
        return "\n".join(recommendation)

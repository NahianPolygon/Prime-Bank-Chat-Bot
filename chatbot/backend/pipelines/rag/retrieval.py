"""
Dynamic RAG Pipeline — Adapts to customer profile, conversation context, and intent.

Key improvements:
1. Customer profiling from conversation history
2. Dynamic prompt generation based on customer segment
3. Adaptive response formatting
4. Context-aware information prioritization
5. Conversation continuity tracking
"""

import json
from typing import Dict, List, Any, Optional
from pipelines.rag.llm_wrapper import OllamaLLM, _clean


class DynamicRAGPipeline:
    """
    Context-aware RAG pipeline that adapts responses to customer profile.
    
    Instead of static templates, the LLM decides:
    - How formal/casual to be
    - Which features to emphasize
    - What level of detail to provide
    - What format works best (table vs narrative vs bullets)
    """

    def __init__(self, vector_db, config: Dict[str, Any]):
        self.vector_db = vector_db
        self.config = config
        self.llm = OllamaLLM(config["llm"])
        self.fallback = config.get("fallback", {
            "out_of_scope": "I can only help with Prime Bank products and services. Feel free to ask about credit cards, loans, or savings accounts!",
            "low_confidence": "I don't have enough information to answer that accurately. Please call 16218 or visit any Prime Bank branch.",
            "error": "Something went wrong. Please call 16218 or visit any Prime Bank branch.",
        })

    # ------------------------------------------------------------------
    # NEW: Customer Profiling Layer
    # ------------------------------------------------------------------

    def _profile_customer(
        self, 
        query: str,
        conversation_history: Optional[List[Dict]] = None,
        customer_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Build a dynamic customer profile from available signals.
        
        Returns:
            {
                "segment": "premium" | "standard" | "budget" | "student",
                "sophistication": "high" | "medium" | "basic",
                "tone_preference": "formal" | "professional" | "casual",
                "primary_concerns": ["rewards", "fees", "limits", "perks"],
                "decision_stage": "exploring" | "comparing" | "ready_to_apply",
                "communication_style": "detailed" | "concise" | "examples_driven"
            }
        """
        
        # Gather all available signals
        signals = {
            "current_query": query,
            "conversation_history": conversation_history or [],
            "customer_data": customer_data or {},
        }
        
        prompt = f"""Analyze customer profile from available signals to personalize response.

CURRENT QUERY: "{query}"

CONVERSATION HISTORY:
{self._format_conversation_history(conversation_history)}

CUSTOMER DATA:
{self._format_customer_data(customer_data)}

TASK: Build customer profile to guide response personalization.

PROFILING DIMENSIONS:

1. SEGMENT (infer from income, queries, employment):
   - premium: High income (200k+/month), asks about platinum/exclusive features
   - standard: Middle income (75k-200k), balanced cost-benefit focus
   - budget: Lower income (<75k), very cost-conscious, fee-sensitive
   - student: Student/young professional, first card, learning-oriented

2. SOPHISTICATION (infer from language, questions):
   - high: Uses financial jargon, asks detailed questions, understands credit mechanics
   - medium: Basic financial literacy, asks practical questions
   - basic: New to credit cards, needs explanations, asks fundamental questions

3. TONE PREFERENCE (infer from their language):
   - formal: Uses formal language, business-like queries
   - professional: Balanced, clear, respectful
   - casual: Friendly, conversational, uses colloquial language

4. PRIMARY CONCERNS (what they've asked about most):
   - List top 3-5 from: rewards, fees, limits, perks, eligibility, safety, convenience, status

5. DECISION STAGE:
   - exploring: Just learning, asking "what cards exist?"
   - comparing: Narrowed down options, asking "X vs Y?"
   - ready_to_apply: Asking about eligibility, documents, application process

6. COMMUNICATION STYLE:
   - detailed: Wants comprehensive info, long explanations
   - concise: Wants quick answers, bullet points
   - examples_driven: Wants scenarios and use cases ("if I spend X, I get Y")

OUTPUT JSON ONLY:
{{
  "segment": "premium"|"standard"|"budget"|"student",
  "sophistication": "high"|"medium"|"basic",
  "tone_preference": "formal"|"professional"|"casual",
  "primary_concerns": [<list of concerns>],
  "decision_stage": "exploring"|"comparing"|"ready_to_apply",
  "communication_style": "detailed"|"concise"|"examples_driven",
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation of profile decisions>"
}}"""

        raw = self.llm.generate(prompt, temperature=0.2, max_tokens=400)
        
        try:
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            profile = json.loads(cleaned[start:end]) if start >= 0 and end > start else {}
        except Exception as e:
            print(f"Profile parsing failed: {e}")
            profile = {}
        
        # Provide sensible defaults
        return {
            "segment": profile.get("segment", "standard"),
            "sophistication": profile.get("sophistication", "medium"),
            "tone_preference": profile.get("tone_preference", "professional"),
            "primary_concerns": profile.get("primary_concerns", ["fees", "rewards"]),
            "decision_stage": profile.get("decision_stage", "exploring"),
            "communication_style": profile.get("communication_style", "concise"),
            "confidence": profile.get("confidence", 0.5),
            "reasoning": profile.get("reasoning", "Default profile"),
        }

    def _format_conversation_history(self, history: Optional[List[Dict]]) -> str:
        """Format conversation history for profiling."""
        if not history:
            return "(No conversation history)"
        
        recent = history[-6:]  # Last 3 exchanges
        formatted = []
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted.append(f"{role.upper()}: {content[:150]}...")
        
        return "\n".join(formatted)

    def _format_customer_data(self, data: Optional[Dict]) -> str:
        """Format explicit customer data."""
        if not data:
            return "(No explicit customer data)"
        
        lines = []
        for key, value in data.items():
            if value:  # Only show non-empty values
                lines.append(f"- {key}: {value}")
        
        return "\n".join(lines) if lines else "(No explicit customer data)"

    # ------------------------------------------------------------------
    # Enhanced Query Analysis with Profile Awareness
    # ------------------------------------------------------------------

    def _analyze_query_with_profile(
        self, 
        query: str, 
        customer_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze query with customer profile awareness for smarter routing.
        """
        
        prompt = f"""Analyze query with customer profile context for intelligent routing.

CUSTOMER PROFILE:
- Segment: {customer_profile['segment']}
- Sophistication: {customer_profile['sophistication']}
- Decision Stage: {customer_profile['decision_stage']}
- Primary Concerns: {', '.join(customer_profile['primary_concerns'])}

CUSTOMER QUERY: "{query}"

TASK: Extract routing parameters and information priorities.

OUTPUT JSON:
{{
  "on_topic": true/false,
  "banking_type": "conventional"|"islami"|"",
  "tier": "platinum"|"gold"|"silver"|"",
  "mode": "product_info"|"comparison"|"feature_query"|"eligibility",
  "info_priorities": [<ordered list: "cost", "rewards", "perks", "eligibility", "limits">],
  "response_format": "table"|"narrative"|"bullets"|"hybrid",
  "emphasis": "<what aspect to emphasize based on profile>"
}}

REASONING:
- If customer is budget-conscious (budget segment), prioritize cost info
- If customer is premium segment, emphasize exclusive perks and rewards
- If sophistication is basic, use simpler language and more examples
- If decision stage is comparing, use table format
- If decision stage is exploring, use narrative with examples
"""

        raw = self.llm.generate(prompt, temperature=0.1, max_tokens=300)
        
        try:
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            analysis = json.loads(cleaned[start:end]) if start >= 0 and end > start else {}
        except Exception:
            analysis = {}
        
        return {
            "on_topic": bool(analysis.get("on_topic", False)),
            "banking_type": str(analysis.get("banking_type") or "").strip().lower(),
            "tier": str(analysis.get("tier") or "").strip().lower(),
            "mode": str(analysis.get("mode") or "product_info").strip().lower(),
            "info_priorities": analysis.get("info_priorities", ["rewards", "fees"]),
            "response_format": analysis.get("response_format", "bullets"),
            "emphasis": analysis.get("emphasis", ""),
        }

    # ------------------------------------------------------------------
    # Dynamic Context Prioritization
    # ------------------------------------------------------------------

    def _prioritize_context(
        self,
        results: List[Dict],
        info_priorities: List[str],
        customer_profile: Dict[str, Any]
    ) -> str:
        """
        Re-organize retrieved context based on what customer cares about.
        
        Instead of just grouping by product, we:
        1. Identify which chunks contain priority information
        2. Surface those first
        3. Annotate chunks with relevance to customer segment
        """
        
        # Group by product
        product_groups: Dict[str, List[Dict]] = {}
        for r in results:
            product_name = r["metadata"].get("product_name", "Unknown")
            product_groups.setdefault(product_name, []).append(r)
        
        # Build prioritized context
        context_parts = []
        
        for product_name, chunks in product_groups.items():
            # Identify priority chunks for this customer
            priority_chunks = []
            standard_chunks = []
            
            for chunk in chunks:
                section = chunk["metadata"].get("section", "").lower()
                content_lower = chunk["content"].lower()
                
                # Score chunk relevance to customer priorities
                relevance_score = 0
                for priority in info_priorities:
                    if priority in section or priority in content_lower:
                        relevance_score += 1
                
                if relevance_score > 0:
                    priority_chunks.append((relevance_score, chunk))
                else:
                    standard_chunks.append(chunk)
            
            # Sort priority chunks by relevance
            priority_chunks.sort(key=lambda x: x[0], reverse=True)
            
            # Format product section
            product_context = f"=== {product_name} ===\n"
            
            # Add priority chunks first
            if priority_chunks:
                product_context += "[PRIORITY INFORMATION FOR THIS CUSTOMER]\n"
                for score, chunk in priority_chunks[:3]:  # Top 3 priority chunks
                    product_context += f"• [{chunk['metadata'].get('section', 'Info')}] {chunk['content']}\n"
            
            # Add standard chunks
            if standard_chunks:
                product_context += "\n[ADDITIONAL INFORMATION]\n"
                for chunk in standard_chunks[:2]:  # Limit standard chunks
                    product_context += f"• [{chunk['metadata'].get('section', 'Info')}] {chunk['content']}\n"
            
            context_parts.append(product_context)
        
        return "\n\n".join(context_parts)

    # ------------------------------------------------------------------
    # Dynamic Prompt Generation
    # ------------------------------------------------------------------

    def _build_dynamic_prompt(
        self,
        query: str,
        context: str,
        analysis: Dict[str, Any],
        customer_profile: Dict[str, Any]
    ) -> str:
        """
        Build a fully dynamic prompt that adapts to customer profile.
        NO hardcoded templates - LLM decides structure based on profile.
        """
        
        # Build profile-aware system message
        system_adaptation = self._generate_system_adaptation(customer_profile)
        
        # Build response guidance
        response_guidance = self._generate_response_guidance(
            customer_profile, 
            analysis
        )
        
        prompt = f"""{system_adaptation}

CUSTOMER PROFILE (adapt your response to this):
- Segment: {customer_profile['segment']} ({customer_profile['reasoning']})
- Communication style: {customer_profile['communication_style']}
- Sophistication: {customer_profile['sophistication']}
- Primary concerns: {', '.join(customer_profile['primary_concerns'])}
- Decision stage: {customer_profile['decision_stage']}
- Tone preference: {customer_profile['tone_preference']}

AVAILABLE PRODUCT INFORMATION:
{context}

CUSTOMER QUERY: {query}

{response_guidance}

CRITICAL RULES:
1. Never invent product names, fees, rates, or features not in the context
2. If information is missing, say "I don't have that specific detail"
3. Match the customer's tone and sophistication level
4. Prioritize information they care about most
5. Use their preferred communication style
6. If data allows, provide concrete examples relevant to their segment

RESPONSE:"""

        return prompt

    def _generate_system_adaptation(self, profile: Dict[str, Any]) -> str:
        """Generate system message that adapts to customer profile."""
        
        base = "You are a Prime Bank product advisor."
        
        # Adapt based on segment
        segment_adaptations = {
            "premium": "You're speaking with a high-value customer. Emphasize exclusive benefits, premium perks, and VIP services. Use confident, sophisticated language.",
            "standard": "You're speaking with a practical customer who values balance. Emphasize value, reliability, and smart benefits. Use clear, professional language.",
            "budget": "You're speaking with a cost-conscious customer. Lead with affordability, fee waivers, and practical savings. Use accessible, helpful language.",
            "student": "You're speaking with a young customer new to credit. Educate while informing. Explain concepts simply and build confidence. Use encouraging, friendly language.",
        }
        
        # Adapt based on sophistication
        sophistication_adaptations = {
            "high": "They understand financial products well. You can use precise terminology and skip basic explanations.",
            "medium": "They have basic financial knowledge. Use clear language with brief explanations when needed.",
            "basic": "They're learning about credit products. Explain concepts as you go and avoid jargon.",
        }
        
        return f"""{base}

CUSTOMER CONTEXT:
{segment_adaptations.get(profile['segment'], segment_adaptations['standard'])}
{sophistication_adaptations.get(profile['sophistication'], sophistication_adaptations['medium'])}"""

    def _generate_response_guidance(
        self, 
        profile: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> str:
        """
        Generate dynamic response guidance based on profile + query analysis.
        LLM decides the format, not hardcoded templates.
        """
        
        mode = analysis['mode']
        format_pref = analysis.get('response_format', 'bullets')
        comm_style = profile['communication_style']
        
        # Dynamic format selection
        format_guidance = {
            "table": "Use a clean markdown table to compare options side-by-side. After the table, provide a 'Best for you' recommendation with specific reasons.",
            "narrative": "Write a flowing narrative that tells a story about how each option fits their needs. Use paragraphs with clear topic sentences.",
            "bullets": "Use bullet points for quick scanning. Group related points together. Lead with the most important information for this customer.",
            "hybrid": "Combine formats: start with a brief summary paragraph, use bullets for features, and end with a recommendation.",
        }
        
        # Dynamic style guidance
        style_guidance = {
            "detailed": "Provide comprehensive information. Include specifics, examples, and context. Don't skip nuances.",
            "concise": "Be brief and direct. Lead with key points. Use short sentences. Cut unnecessary details.",
            "examples_driven": "Use real scenarios and calculations. Show concrete examples like 'If you spend BDT 50,000/month on dining, you'll earn...'",
        }
        
        # Mode-specific adaptations
        mode_guidance = {
            "comparison": f"Compare products using {format_pref} format. Highlight differences that matter to {profile['segment']} customers. End with a clear recommendation.",
            "feature_query": f"Answer their specific question in the first sentence. Then elaborate using {comm_style} style. Include examples if data allows.",
            "product_info": f"Present products in {format_pref} format. Emphasize {', '.join(analysis.get('info_priorities', ['features'])[:2])}. Match the {profile['tone_preference']} tone.",
            "eligibility": "Lead with requirements clearly. List documents needed. State processing time. End with next steps (call 16218 or visit branch).",
        }
        
        return f"""RESPONSE GUIDELINES:

FORMAT: {format_guidance.get(format_pref, format_guidance['bullets'])}

STYLE: {style_guidance.get(comm_style, style_guidance['concise'])}

MODE: {mode_guidance.get(mode, mode_guidance['product_info'])}

EMPHASIS: {analysis.get('emphasis', 'Provide balanced information')}

Let the customer's profile guide how you structure and present the information. There's no single right format - choose what works best for THIS customer."""

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def generate_response(
        self, 
        query: str,
        conversation_history: Optional[List[Dict]] = None,
        customer_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate a fully dynamic, context-aware response.
        
        Args:
            query: Customer's question
            conversation_history: Previous messages in conversation
            customer_data: Explicit customer info (age, income, employment, etc.)
        
        Returns:
            Response dict with answer, sources, profile used, etc.
        """
        
        try:
            # Step 1: Build customer profile
            customer_profile = self._profile_customer(
                query=query,
                conversation_history=conversation_history,
                customer_data=customer_data
            )
            
            print(f"📊 Customer Profile: {customer_profile['segment']} | "
                  f"{customer_profile['sophistication']} | "
                  f"{customer_profile['decision_stage']}")
            
            # Step 2: Analyze query with profile awareness
            analysis = self._analyze_query_with_profile(query, customer_profile)
            
            print(f"🎯 Query Analysis: {analysis['mode']} | "
                  f"Format: {analysis.get('response_format')} | "
                  f"Priorities: {analysis.get('info_priorities')}")
            
            if not analysis["on_topic"]:
                return {
                    "answer": self.fallback["out_of_scope"],
                    "sources": [],
                    "confidence": 0.0,
                    "success": False,
                    "error": "out_of_scope",
                    "profile_used": customer_profile,
                }
            
            # Step 3: Search with filters
            bt = analysis["banking_type"] or None
            tier = analysis["tier"] or None
            mode = analysis["mode"]
            
            top_k = 12 if mode == "comparison" else 8
            
            filter_parts = []
            if bt:
                filter_parts.append({"banking_type": {"$eq": bt}})
            if tier:
                filter_parts.append({"tier": {"$eq": tier}})
            
            chroma_filter = None
            if len(filter_parts) == 1:
                chroma_filter = filter_parts[0]
            elif len(filter_parts) == 2:
                chroma_filter = {"$and": filter_parts}
            
            results = self.vector_db.search(query, top_k=top_k, filters=chroma_filter)
            
            if not results:
                return {
                    "answer": self.fallback["low_confidence"],
                    "sources": [],
                    "confidence": 0.0,
                    "success": False,
                    "error": "no_results",
                    "profile_used": customer_profile,
                }
            
            # Step 4: Prioritize and format context
            context = self._prioritize_context(
                results=results,
                info_priorities=analysis.get("info_priorities", []),
                customer_profile=customer_profile
            )
            
            # Step 5: Build dynamic prompt
            prompt = self._build_dynamic_prompt(
                query=query,
                context=context,
                analysis=analysis,
                customer_profile=customer_profile
            )
            
            # Step 6: Generate response
            answer = self.llm.generate(prompt, max_tokens=1000)
            answer = _clean(answer)
            
            # Step 7: Build response
            avg_conf = sum(r["similarity"] for r in results) / len(results)
            
            seen: set = set()
            sources = []
            for r in results:
                key = f"{r['metadata'].get('product_name','?')}|{r['metadata'].get('section','?')}"
                if key not in seen:
                    seen.add(key)
                    sources.append({
                        "product": r["metadata"].get("product_name", "?"),
                        "section": r["metadata"].get("section", "?"),
                        "confidence": f"{r['similarity']:.0%}",
                    })
            
            return {
                "answer": answer,
                "sources": sources[:6],
                "confidence": avg_conf,
                "success": True,
                "error": None,
                "profile_used": customer_profile,
                "analysis_used": analysis,
            }
        
        except Exception as e:
            print(f"RAG error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "answer": self.fallback["error"],
                "sources": [],
                "confidence": 0.0,
                "success": False,
                "error": str(e),
            }
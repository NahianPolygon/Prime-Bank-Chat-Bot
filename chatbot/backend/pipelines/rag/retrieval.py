"""
RAG pipeline — prompt-driven routing and response generation.
"""

import json
from typing import Dict, List, Any
from pipelines.rag.llm_wrapper import OllamaLLM, _clean


class RAGPipeline:
    """
    Direct RAG pipeline for the non-CrewAI path.

    Routing decisions (topic check, mode detection, filter extraction) are all
    made by the LLM reading the query — no keyword lists, no regex filters.
    """

    SYSTEM = (
        "You are a helpful, warm, and knowledgeable Prime Bank product advisor. "
        "You only discuss Prime Bank products and services. "
        "You never invent product names, fees, interest rates, or any figures not "
        "explicitly found in the context provided to you."
    )

    def __init__(self, vector_db, config: Dict[str, Any]):
        self.vector_db = vector_db
        self.config = config
        self.llm = OllamaLLM(config["llm"])
        self.fallback = config.get(
            "fallback",
            {
                "out_of_scope": "I can only help with Prime Bank products and services. Feel free to ask about credit cards, loans, or savings accounts!",
                "low_confidence": "I don't have enough information to answer that accurately. Please call 16218 or visit any Prime Bank branch.",
                "error": "Something went wrong. Please call 16218 or visit any Prime Bank branch.",
            },
        )

    # ------------------------------------------------------------------
    # Step 1: LLM decides if query is banking-related and extracts filters
    # ------------------------------------------------------------------

    def _llm_analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Single LLM call that does everything keyword detection used to do:
        - Is this about banking/financial products?
        - What banking_type filter to use?
        - What tier filter to use?
        - What response mode fits? (product_info / comparison / feature_query / eligibility)

        Returns a dict with: on_topic, banking_type, tier, mode
        """
        prompt = f"""TASK: Analyze customer query and extract routing parameters.

ROLE: Query analyzer for bank chatbot.

REQUIRED FIELDS:
- on_topic: true/false (banking, credit cards, loans, accounts, financial products?)
- banking_type: "conventional" | "islami" | "" (empty if not specified)
- tier: "platinum" | "gold" | "silver" | "" (empty if not specified or unclear)
- mode: "product_info" | "comparison" | "feature_query" | "eligibility"

MODE DEFINITIONS:
- product_info: customer wants to find or learn about products
- comparison: customer wants to compare 2+ specific products side-by-side
- feature_query: customer asks about specific feature (lounge, dining, EMI, etc.)
- eligibility: customer asks if they qualify, about requirements, or documents

CUSTOMER QUERY: "{query}"

OUTPUT FORMAT: JSON only. No explanation. No markdown.
{{"on_topic": true/false, "banking_type": "", "tier": "", "mode": ""}}"""

        raw = self.llm.generate(prompt, temperature=0.0, max_tokens=150)
        try:
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            data = (
                json.loads(cleaned[start:end]) if start >= 0 and end > start else {}
            )
        except Exception:
            data = {}

        return {
            "on_topic": bool(data.get("on_topic", False)),
            "banking_type": str(data.get("banking_type") or "").strip().lower(),
            "tier": str(data.get("tier") or "").strip().lower(),
            "mode": str(data.get("mode") or "product_info").strip().lower(),
        }

    # ------------------------------------------------------------------
    # Step 2: Format context grouped by product
    # ------------------------------------------------------------------

    def _format_context(self, results: List[Dict], mode: str) -> str:
        if mode in ("product_info", "comparison"):
            groups: Dict[str, List] = {}
            for r in results:
                name = r["metadata"].get("product_name", "?")
                groups.setdefault(name, []).append(r)
            parts = []
            for name, chunks in groups.items():
                block = f"=== {name} ===\n"
                for c in chunks:
                    block += (
                        f"[{c['metadata'].get('section', 'General')}]\n{c['content']}\n"
                    )
                parts.append(block)
            return "\n\n".join(parts)
        else:
            return "\n\n".join(
                f"[{r['metadata'].get('product_name','?')} — "
                f"{r['metadata'].get('section','?')}]\n{r['content']}"
                for r in results
            )

    # ------------------------------------------------------------------
    # Step 3: Build a single natural-language prompt — no mode branching
    # ------------------------------------------------------------------

    def _build_prompt(self, query: str, context: str, analysis: Dict) -> str:
        """
        One prompt that adapts naturally to what the customer asked.
        The LLM figures out the right structure from the query itself —
        no hardcoded if/else for comparison vs feature_query vs product_info.
        """
        mode = analysis.get("mode", "product_info")

        structure_guidance = {
            "product_info": (
                "Present each product as a named section with 4-5 bullet benefits. "
                "Show the annual fee clearly. End with an offer to check eligibility."
            ),
            "comparison": (
                "Build a markdown comparison table across all products found in context. "
                "After the table, write a 'Best for you:' section naming the winner "
                "with 3 specific reasons. Acknowledge the trade-off."
            ),
            "feature_query": (
                "Answer the specific question directly in your first sentence. "
                "For each relevant feature, write a bold sub-header and bullet points. "
                "Where the context has specific figures, include a concrete example "
                "(e.g. 'If you spend BDT 20,000/month -> save BDT X/year'). "
                "End with an offer to check eligibility."
            ),
            "eligibility": (
                "State which product this covers. List eligibility requirements as bullets. "
                "List required documents as bullets. State processing time. "
                "End with: 'Call 16218 or visit any Prime Bank branch to apply.'"
            ),
        }.get(mode, "")

        return f"""{self.SYSTEM}

CONTEXT (facts only — never invent):
{context}

CUSTOMER QUERY: {query}

RESPONSE RULES BY MODE:
- product_info: List each product with 4-5 bullet benefits + annual fee. End with eligibility offer.
- feature_query: Answer the specific feature directly. Use relevant bullet points and examples when data allows.
- comparison: Show markdown table across all products. Name winner with 3 reasons + 1 acknowledged trade-off.
- eligibility: State requirements and documents as bullets. List processing time if available. End with branch/phone.

OUTPUT FORMAT:
1. No section labels like [Opening] or [Closing]
2. Use only facts from context above
3. If fact missing: "I don't have that detail in our database"
4. Never invent product names, fees, rates, limits, or figures
5. Warm tone, plain language"""

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def generate_response(self, query: str) -> Dict[str, Any]:
        """
        Generate a response using fully prompt-driven routing.
        No keyword lists. No regex filters. The LLM reads the query and decides everything.
        """
        from pipelines.rag.search import NO_PRODUCTS_SENTINEL

        if NO_PRODUCTS_SENTINEL in query:
            return {
                "answer": "I wasn't able to find matching products right now. Please call **16218** or visit any Prime Bank branch.",
                "sources": [],
                "confidence": 0.0,
                "success": False,
                "error": "no_products",
            }

        try:
            # Step 1: LLM analyzes query — topic check + filters + mode
            analysis = self._llm_analyze_query(query)
            print(f"RAG analysis: {analysis}")

            if not analysis["on_topic"]:
                return {
                    "answer": self.fallback["out_of_scope"],
                    "sources": [],
                    "confidence": 0.0,
                    "success": False,
                    "error": "out_of_scope",
                }

            bt = analysis["banking_type"] or None
            tier = analysis["tier"] or None
            mode = analysis["mode"]

            # Step 2: Search (more chunks for comparison so we get multiple products)
            top_k = 10 if mode == "comparison" else 8
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
                }

            # Step 3: Build context and prompt
            context = self._format_context(results, mode)
            prompt = self._build_prompt(query, context, analysis)

            # Step 4: Generate and clean
            answer = self.llm.generate(prompt, max_tokens=900)
            answer = _clean(answer)

            avg_conf = sum(r["similarity"] for r in results) / len(results)

            seen: set = set()
            sources = []
            for r in results:
                key = f"{r['metadata'].get('product_name','?')}|{r['metadata'].get('section','?')}"
                if key not in seen:
                    seen.add(key)
                    sources.append(
                        {
                            "product": r["metadata"].get("product_name", "?"),
                            "section": r["metadata"].get("section", "?"),
                            "confidence": f"{r['similarity']:.0%}",
                        }
                    )

            return {
                "answer": answer,
                "sources": sources[:6],
                "confidence": avg_conf,
                "success": True,
                "error": None,
            }

        except Exception as e:
            print(f"RAG error: {e}")
            return {
                "answer": self.fallback["error"],
                "sources": [],
                "confidence": 0.0,
                "success": False,
                "error": str(e),
            }

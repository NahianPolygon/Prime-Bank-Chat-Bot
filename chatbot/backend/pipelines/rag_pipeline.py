"""
RAG (Retrieval Augmented Generation) pipeline.
Orchestrates vector search and LLM generation.
"""

import os
import re
from typing import List, Dict, Any, Tuple
import requests
import yaml


class OllamaLLM:
    """Interface to Qwen3-1.7B via Ollama."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Ollama LLM interface.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.llm_config = config['llm']
        self.base_url = self.llm_config['base_url'].rstrip('/')
        self.model_name = self.llm_config['model_name']
        
        # Check if Ollama is available
        if not self._check_ollama_availability():
            raise RuntimeError(
                f"Ollama not available at {self.base_url}. "
                "Please start Ollama: ollama serve"
            )
        
        print(f"✓ Connected to Ollama at {self.base_url}")
    
    def _check_ollama_availability(self) -> bool:
        """Check if Ollama service is available."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def generate(self, prompt: str, stream: bool = False) -> str:
        """
        Generate response from Qwen3-1.7B.
        
        Args:
            prompt: Full prompt including system message
            stream: Whether to stream response
            
        Returns:
            Generated response text
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    'model': self.model_name,
                    'prompt': prompt,
                    'stream': stream,
                    'temperature': self.llm_config['temperature'],
                    'top_p': self.llm_config['top_p'],
                },
                timeout=self.llm_config['timeout']
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"Ollama error: {response.status_code}")
            
            # Parse response
            if stream:
                # Streaming response
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        full_response += data.get('response', '')
                        if data.get('done', False):
                            break
                return full_response.strip()
            else:
                # Non-streaming response
                import json
                data = response.json()
                return data.get('response', '').strip()
        
        except requests.Timeout:
            raise RuntimeError(
                f"Ollama timeout after {self.llm_config['timeout']}s. "
                "Response generation took too long."
            )
        except Exception as e:
            raise RuntimeError(f"Error calling Ollama: {str(e)}")


class RAGPipeline:
    """Retrieval Augmented Generation pipeline."""
    
    def __init__(self, vector_db, config: Dict[str, Any]):
        """
        Initialize RAG pipeline.
        
        Args:
            vector_db: Initialized VectorDB instance
            config: Configuration dictionary
        """
        self.vector_db = vector_db
        self.config = config
        self.llm = OllamaLLM(config)
        self.system_prompt = config['system_prompt']
        self.fallback_responses = config['fallback']
    
    def _format_context(self, search_results: List[Dict[str, Any]]) -> str:
        """Format search results into context for LLM."""
        if not search_results:
            return ""
        
        context_parts = []
        for idx, result in enumerate(search_results, 1):
            metadata = result['metadata']
            source = f"{metadata['product_name']} - {metadata['section']}"
            confidence = f"{result['similarity']:.0%}"
            
            context_parts.append(
                f"[Source {idx}: {source} (Confidence: {confidence})]\n"
                f"{result['content']}\n"
            )
        
        return "\n".join(context_parts)
    
    def _build_prompt(self, query: str, context: str) -> str:
        """Build full prompt for LLM."""
        if context:
            prompt = f"""{self.system_prompt}

KNOWLEDGE BASE CONTEXT:
{context}

USER QUESTION:
{query}

Please answer based on the context provided above. If the context doesn't contain relevant information, say "I don't know"."""
        else:
            prompt = f"""{self.system_prompt}

USER QUESTION:
{query}

I don't have any relevant information to answer this question."""
        
        return prompt
    
    def _is_on_topic(self, query: str) -> bool:
        """Quick heuristic check if query is about banking/products."""
        keywords = [
            'card', 'credit', 'loan', 'bank', 'account', 'visa', 'mastercard',
            'jcb', 'fee', 'interest', 'reward', 'Islamic', 'conventional',
            'eligibility', 'apply', 'hasanah', 'platinum', 'gold', 'lounge',
            'insurance', 'benefits', 'limit', 'prime bank', 'hasanah'
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in keywords)
    
    def _extract_filters(self, query: str) -> Tuple[str, str]:
        """
        Extract banking_type and tier filters from query.
        
        Returns:
            Tuple of (banking_type_filter, tier_filter) or (None, None)
        """
        banking_type = None
        tier = None
        
        query_lower = query.lower()
        
        # Banking type detection
        if 'islamic' in query_lower or 'islami' in query_lower or 'sharia' in query_lower:
            banking_type = 'islami'
        elif 'conventional' in query_lower:
            banking_type = 'conventional'
        
        # Tier detection
        if 'platinum' in query_lower:
            tier = 'platinum'
        elif 'gold' in query_lower:
            tier = 'gold'
        
        return banking_type, tier
    
    def generate_response(self, query: str) -> Dict[str, Any]:
        """
        Generate response for user query using RAG.
        
        Args:
            query: User query
            
        Returns:
            Response dictionary with answer, sources, confidence, etc.
        """
        # Check if query is on topic
        if not self._is_on_topic(query):
            return {
                'answer': self.fallback_responses['out_of_scope'],
                'sources': [],
                'confidence': 0.0,
                'success': False,
                'error': 'out_of_scope'
            }
        
        try:
            # Extract filters from query
            banking_type_filter, tier_filter = self._extract_filters(query)
            
            # Retrieve relevant chunks
            search_results = self.vector_db.search(
                query,
                banking_type_filter=banking_type_filter,
                tier_filter=tier_filter
            )
            
            # Check if we found relevant results
            if not search_results:
                return {
                    'answer': self.fallback_responses['low_confidence'],
                    'sources': [],
                    'confidence': 0.0,
                    'success': False,
                    'error': 'no_results'
                }
            
            # Build context and prompt
            context = self._format_context(search_results)
            prompt = self._build_prompt(query, context)
            
            # Generate response
            answer = self.llm.generate(prompt, stream=False)
            
            # Calculate average confidence from results
            avg_confidence = sum(r['similarity'] for r in search_results) / len(search_results)
            
            # Extract sources for citation
            sources = [
                {
                    'product': result['metadata']['product_name'],
                    'section': result['metadata']['section'],
                    'confidence': f"{result['similarity']:.0%}"
                }
                for result in search_results[:3]  # Top 3 sources
            ]
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': avg_confidence,
                'success': True,
                'error': None
            }
        
        except Exception as e:
            print(f"Error in RAG pipeline: {e}")
            return {
                'answer': self.fallback_responses['error'],
                'sources': [],
                'confidence': 0.0,
                'success': False,
                'error': str(e)
            }


if __name__ == "__main__":
    # Test RAG pipeline
    from vector_db import initialize_knowledge_base
    
    config_path = "./config.yaml"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        print("Initializing RAG pipeline...")
        vector_db = initialize_knowledge_base(config)
        rag = RAGPipeline(vector_db, config)
        
        # Test queries
        test_queries = [
            "Tell me about Visa Gold credit card",
            "Which Islamic banking credit card options are available?",
            "What's the difference between gold and platinum cards?",
        ]
        
        print("\n" + "="*80)
        print("Testing RAG pipeline:")
        print("="*80)
        
        for query in test_queries:
            print(f"\nQuery: {query}")
            response = rag.generate_response(query)
            print(f"Answer: {response['answer'][:200]}...")
            print(f"Confidence: {response['confidence']:.2%}")
            print(f"Sources: {len(response['sources'])} documents")

"""
Deprecated RAG pipeline module.

This module was replaced by the simplified `Pipeline` implementation.
Keep this file present temporarily for historical reference only.
"""

raise ImportError("rag_pipeline.py is deprecated; use pipelines.Pipeline instead")
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

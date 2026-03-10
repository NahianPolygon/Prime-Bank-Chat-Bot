#!/usr/bin/env python3
"""
Test script to verify eligibility flow works correctly without product hallucination.
"""

import yaml
from pipelines.crew.main import CrewPipeline
from vector_db import initialize_knowledge_base
from pipelines.rag.search import initialize_rag_tool

def test_eligibility_flow():
    """Test the complete eligibility flow."""
    
    print("=" * 80)
    print("ELIGIBILITY FLOW TEST - Verifying no hallucinated products")
    print("=" * 80)
    
    # Initialize
    config_path = "./config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    vector_db = initialize_knowledge_base(config, force_reindex=False)
    initialize_rag_tool(vector_db, config.get("llm"))
    print("✓ Vector DB and RAG tool initialized\n")
    
    pipeline = CrewPipeline()
    session_id = "eligibility_test_"+ str(__import__('uuid').uuid4())[:8]
    
    # Test conversation flow
    conversation = [
        ("I want a credit card", "Initial request"),
        ("conventional, my use case will be dining, my monthly income is 200k", "Profile data"),
        ("am i eligible for it?", "Eligibility check for recommended product"),
    ]
    
    history = []
    
    for query, desc in conversation:
        print(f"\n{'='*80}")
        print(f"[{desc}]")
        print(f"User: {query}")
        print(f"{'='*80}")
        
        try:
            response = pipeline.run(
                query=query,
                session_id=session_id,
                conversation_history=history
            )
            
            print(f"\nAgent Chain: {' → '.join(response.get('agent_chain', []))}")
            print(f"\nSystem Response:\n {response.get('response', '')[:500]}...\n")
            
            # Add to history
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": response.get('response', '')})
            
            # Check for hallucinated products
            resp_lower = response.get('response', '').lower()
            hallucinated = []
            
            if 'hsbc' in resp_lower:
                hallucinated.append("❌ HSBC hallucinated")
            if 'standard chartered' in resp_lower:
                hallucinated.append("❌ Standard Chartered hallucinated")
            if hallucinated:
                print(f"\n🚨 HALLUCINATION DETECTED:")
                for h in hallucinated:
                    print(f"   {h}")
            else:
                print(f"\n✅ No hallucinated products detected")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\n\n{'='*80}")
    print("ELIGIBILITY FLOW TEST COMPLETE")
    print(f"{'='*80}")

if __name__ == "__main__":
    test_eligibility_flow()

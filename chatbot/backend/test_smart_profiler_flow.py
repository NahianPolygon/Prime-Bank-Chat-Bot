#!/usr/bin/env python3
"""Test smart profiler with vague query."""

from pipelines.crew.main import CrewPipeline

pipeline = CrewPipeline()

# Test vague query
query = "i want to know which credit card is best for me"
session_id = "test_smart_profiler_123"

print(f"\n{'='*70}")
print(f"Query: {query}")
print(f"{'='*70}\n")

response = pipeline.run(query, session_id)

print(f"Response:\n{response['answer']}")
print(f"\nNeeds Clarification: {response.get('needs_clarification', False)}")
print(f"Agent Chain: {response.get('agent_chain', [])}")

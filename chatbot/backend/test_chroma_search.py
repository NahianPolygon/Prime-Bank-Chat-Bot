#!/usr/bin/env python3
"""
Test script to directly query Chroma DB and verify content exists.
"""

import chromadb
from sentence_transformers import SentenceTransformer
import json

# Connect to Chroma
persist_dir = "data/vector_db"
client = chromadb.PersistentClient(path=persist_dir)

# Get collection
collection = client.get_or_create_collection(
    name="credit_cards_kb",
    metadata={"hnsw:space": "cosine"}
)

print(f"Total documents in collection: {collection.count()}")
print("\n" + "="*80)

# Initialize embedding model
print("Loading embedding model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

# Search 1: "How to Apply Visa Platinum"
query1 = "How to Apply Visa Platinum Credit Card"
print(f"\n🔍 SEARCH 1: '{query1}'")
results1 = collection.query(query_texts=[query1], n_results=5)

if results1['documents']:
    for i, (doc, distance) in enumerate(zip(results1['documents'][0], results1['distances'][0])):
        print(f"\n--- Result {i+1} (distance: {distance:.3f}) ---")
        print(doc[:500] + "..." if len(doc) > 500 else doc)
else:
    print("No results found")

# Search 2: Just "How to Apply"
query2 = "How to Apply Required Documents"
print(f"\n{'='*80}\n🔍 SEARCH 2: '{query2}'")
results2 = collection.query(query_texts=[query2], n_results=5)

if results2['documents']:
    for i, (doc, distance) in enumerate(zip(results2['documents'][0], results2['distances'][0])):
        print(f"\n--- Result {i+1} (distance: {distance:.3f}) ---")
        print(doc[:500] + "..." if len(doc) > 500 else doc)
else:
    print("No results found")

# Search 3: "Visa Platinum"
query3 = "Visa Platinum Credit Card"
print(f"\n{'='*80}\n🔍 SEARCH 3: '{query3}'")
results3 = collection.query(query_texts=[query3], n_results=3)

if results3['documents']:
    for i, (doc, distance) in enumerate(zip(results3['documents'][0], results3['distances'][0])):
        print(f"\n--- Result {i+1} (distance: {distance:.3f}) ---")
        print(doc[:300] + "..." if len(doc) > 300 else doc)
else:
    print("No results found")

# Check all documents about "Visa Platinum"
print(f"\n{'='*80}\n📋 ALL DOCUMENTS CHECK:")
all_results = collection.get(
    where={"source": {"$contains": "visa_platinum"}},
    limit=10
)
print(f"\nDocuments matching 'visa_platinum' source: {len(all_results['documents'])}")

# Get all metadata
print(f"\n🏷️  SAMPLE METADATA FROM COLLECTION:")
all_data = collection.get(limit=3)
for i, meta in enumerate(all_data.get('metadatas', [])):
    print(f"\n--- Doc {i+1} ---")
    print(json.dumps(meta, indent=2))

print("\n" + "="*80)
print(f"✅ Test complete. Total docs in collection: {collection.count()}")

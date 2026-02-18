"""
Vector database and embedding management using Chroma.
Handles embedding generation and vector storage/retrieval.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
import chromadb
from sentence_transformers import SentenceTransformer
import numpy as np

from .chunker import Chunk, chunk_to_dict, process_knowledge_base


class VectorDB:
    """Manages Chroma vector database for RAG."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize vector DB and embedding model.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.chunk_config = config['chunking']
        self.vector_config = config['vector_db']
        self.embed_config = config['embeddings']
        self.rag_config = config['rag']
        
        # Create persist directory if doesn't exist
        persist_dir = self.vector_config['persist_directory']
        os.makedirs(persist_dir, exist_ok=True)
        
        # Initialize Chroma client (using new persistent client API)
        self.client = chromadb.PersistentClient(path=persist_dir)
        
        # Initialize embedding model
        print(f"Loading embedding model: {self.embed_config['model_name']}")
        self.embedding_model = SentenceTransformer(
            self.embed_config['model_name'],
            device=self.embed_config['device']
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.vector_config['collection_name'],
            metadata={"hnsw:space": "cosine"}
        )
        
        print(f"✓ Vector DB initialized (collection: {self.vector_config['collection_name']})")
    
    def index_chunks(self, chunks: List[Chunk]) -> int:
        """
        Index chunks into vector database.
        
        Args:
            chunks: List of Chunk objects to index
            
        Returns:
            Number of chunks indexed
        """
        if not chunks:
            print("No chunks to index")
            return 0
        
        print(f"\nIndexing {len(chunks)} chunks into vector DB...")
        
        # Prepare data for Chroma
        ids = []
        embeddings = []
        documents = []
        metadatas = []
        
        for idx, chunk in enumerate(chunks):
            # Generate embedding
            embedding = self.embedding_model.encode(chunk.content)
            
            ids.append(chunk.chunk_id)
            embeddings.append(embedding.tolist())
            documents.append(chunk.content)
            
            # Create metadata with all fields
            metadata = {
                'product_id': chunk.product_id,
                'product_name': chunk.product_name,
                'banking_type': chunk.banking_type,
                'product_type': chunk.product_type,
                'feature_category': chunk.feature_category,
                'tier': chunk.tier,
                'category': chunk.category,
                'section': chunk.section,
                'subsection': chunk.subsection,
                'source_file': chunk.source_file,
                'employment_suitable': ','.join(chunk.employment_suitable) if chunk.employment_suitable else '',
                'use_cases': ','.join(chunk.use_cases) if chunk.use_cases else '',
                'keywords': ','.join(chunk.keywords) if chunk.keywords else '',
            }
            metadatas.append(metadata)
            
            if (idx + 1) % 50 == 0:
                print(f"  Processed {idx + 1}/{len(chunks)} chunks")
        
        # Add to collection
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        print(f"✓ Successfully indexed {len(chunks)} chunks")
        return len(chunks)
    
    def search(
        self,
        query: str,
        top_k: int = None,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search vector DB for relevant chunks with advanced metadata filtering.
        
        Args:
            query: Search query
            top_k: Number of results to return (default from config)
            filters: Advanced filter dict with Chroma operators ($eq, $and, etc.)
            
        Returns:
            List of search results with metadata
        """
        if top_k is None:
            top_k = self.rag_config['top_k']
        
        # Encode query
        query_embedding = self.embedding_model.encode(query)
        
        # Pass filter directly - already formatted by caller with Chroma operators
        where_filter = filters if filters else None
        
        # Query collection
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where_filter,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Process results
        search_results = []
        if results['ids'] and len(results['ids']) > 0:
            # Lower threshold if filters are applied (more specific search)
            threshold = 0.3 if where_filter else self.rag_config['similarity_threshold']
            
            for idx, chunk_id in enumerate(results['ids'][0]):
                # Chroma returns distances (lower = more similar)
                # Convert to similarity score (0-1, higher = better)
                distance = results['distances'][0][idx]
                similarity = 1 / (1 + distance)  # Convert distance to similarity
                
                metadata = results['metadatas'][0][idx]
                result = {
                    'chunk_id': chunk_id,
                    'content': results['documents'][0][idx],
                    'similarity': similarity,
                    'metadata': metadata,
                    # Flatten common metadata fields for easier access
                    'product_name': metadata.get('product_name', 'Unknown'),
                    'banking_type': metadata.get('banking_type'),
                    'tier': metadata.get('tier'),
                    'section': metadata.get('section'),
                    'source_file': metadata.get('source_file'),
                }
                
                # Apply confidence threshold
                if similarity >= threshold:
                    search_results.append(result)
        
        return search_results
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection."""
        count = self.collection.count()
        return {
            'collection_name': self.vector_config['collection_name'],
            'total_chunks': count,
        }
    
    def clear_collection(self) -> bool:
        """Clear all data from collection (use with caution)."""
        try:
            self.client.delete_collection(
                name=self.vector_config['collection_name']
            )
            self.collection = self.client.get_or_create_collection(
                name=self.vector_config['collection_name'],
                metadata={"hnsw:space": "cosine"}
            )
            print("✓ Collection cleared")
            return True
        except Exception as e:
            print(f"✗ Error clearing collection: {e}")
            return False


def initialize_knowledge_base(config: Dict[str, Any], force_reindex: bool = False) -> VectorDB:
    """
    Initialize vector DB and index knowledge base.
    
    Args:
        config: Configuration dictionary
        force_reindex: Force re-indexing even if DB exists
        
    Returns:
        Initialized VectorDB instance
    """
    # Initialize vector DB
    vector_db = VectorDB(config)
    
    # Check if already indexed
    stats = vector_db.get_collection_stats()
    
    if stats['total_chunks'] > 0 and not force_reindex:
        print(f"\n✓ Vector DB already indexed ({stats['total_chunks']} chunks)")
        return vector_db
    
    # Process knowledge base and index
    kb_root = config['knowledge_base']['root_path']
    
    if not os.path.exists(kb_root):
        print(f"✗ Knowledge base path not found: {kb_root}")
        return vector_db
    
    # Clear and reindex
    if force_reindex:
        vector_db.clear_collection()
    
    chunks = process_knowledge_base(kb_root, config)
    vector_db.index_chunks(chunks)
    
    return vector_db


if __name__ == "__main__":
    import yaml
    
    config_path = "./config.yaml"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize KB
        vector_db = initialize_knowledge_base(config, force_reindex=False)
        
        # Test search
        print("\n" + "="*80)
        print("Testing search functionality:")
        print("="*80)
        
        test_queries = [
            "Tell me about Visa Gold credit card",
            "What are the fees for Mastercard Platinum?",
            "I'm interested in Islamic banking options",
        ]
        
        for query in test_queries:
            print(f"\nQuery: {query}")
            results = vector_db.search(query)
            print(f"Found {len(results)} relevant chunks:")
            for result in results[:2]:
                print(f"  - {result['metadata']['product_name']} "
                      f"(Similarity: {result['similarity']:.2f})")
                print(f"    Section: {result['metadata']['section']}")

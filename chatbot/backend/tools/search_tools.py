"""
Search tools configuration and vector DB injection.
Provides the set_vector_db function to inject vector DB into RAG tools.
"""

# Global state for vector DB
_vector_db = None


def set_vector_db(vector_db):
    """
    Inject the vector database instance into search tools.
    Called at startup to make vector DB available to RAG tool.
    
    Args:
        vector_db: Initialized vector database instance
    """
    global _vector_db
    _vector_db = vector_db
    print("✓ Vector DB injected into search tools")


def get_vector_db():
    """Get the injected vector database instance."""
    global _vector_db
    return _vector_db

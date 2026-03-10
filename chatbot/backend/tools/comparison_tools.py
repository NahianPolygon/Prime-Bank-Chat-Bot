"""
Comparison tools configuration and vector DB injection.
Provides the set_vector_db_for_comparison function.
"""

# Global state for vector DB
_vector_db = None


def set_vector_db_for_comparison(vector_db):
    """
    Inject the vector database instance into comparison tools.
    Called at startup to make vector DB available to comparison agents.
    
    Args:
        vector_db: Initialized vector database instance
    """
    global _vector_db
    _vector_db = vector_db
    print("✓ Vector DB injected into comparison tools")


def get_vector_db():
    """Get the injected vector database instance."""
    global _vector_db
    return _vector_db

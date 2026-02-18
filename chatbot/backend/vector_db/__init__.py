"""
Vector database module.
Handles Chroma vector DB, embedding management, and knowledge base chunking.
"""

from .db import VectorDB, initialize_knowledge_base
from .chunker import (
    Chunk, 
    extract_frontmatter,
    split_by_headers,
    chunk_section_content,
    extract_hierarchy_metadata,
    process_markdown_file,
    process_knowledge_base,
)

__all__ = [
    'VectorDB', 
    'initialize_knowledge_base',
    'Chunk',
    'extract_frontmatter',
    'split_by_headers',
    'chunk_section_content',
    'extract_hierarchy_metadata',
    'process_markdown_file',
    'process_knowledge_base',
]

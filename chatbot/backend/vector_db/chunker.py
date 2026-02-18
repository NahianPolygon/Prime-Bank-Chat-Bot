"""
Chunking module for breaking markdown files into semantic chunks with metadata.
Handles hierarchical chunking based on markdown structure.
"""

import os
import re
import yaml
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class Chunk:
    """Represents a single chunk of text with metadata."""
    chunk_id: str
    product_id: str
    product_name: str
    banking_type: str  # "conventional" or "islami"
    product_type: str  # "credit", "debit", "loan", etc.
    feature_category: str  # "i_need_a_credit_card", "i_am_existing_holder", etc.
    tier: str  # "gold", "platinum", etc.
    category: str  # "credit_card", "loan", etc.
    section: str  # "overview", "features", "eligibility", etc.
    subsection: str  # detailed subsection name
    content: str
    use_cases: List[str]
    employment_suitable: List[str]  # New: employment types
    keywords: List[str]
    source_file: str


def extract_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Extract YAML frontmatter from markdown file.
    
    Args:
        content: Full markdown file content
        
    Returns:
        Tuple of (frontmatter_dict, body_without_frontmatter)
    """
    if content.startswith("---"):
        try:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                body = parts[2].strip()
                return frontmatter or {}, body
        except yaml.YAMLError:
            pass
    return {}, content


def split_by_headers(content: str) -> List[Tuple[str, str]]:
    """
    Split markdown content by headers (##).
    
    Args:
        content: Markdown body without frontmatter
        
    Returns:
        List of (header_name, section_content) tuples
    """
    # Split by level 2 headers (##)
    sections = []
    pattern = r'^## (.+?)$'
    
    parts = re.split(f'({pattern})', content, flags=re.MULTILINE)
    
    # parts will be: ["intro", "## Header 1", "content1", "## Header 2", "content2", ...]
    current_header = "Overview"
    current_content = parts[0].strip() if parts[0].strip() else ""
    
    for i in range(1, len(parts), 2):
        if i < len(parts):
            current_header = parts[i].replace("##", "").strip()
            current_content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if current_content:
                sections.append((current_header, current_content))
    
    # Add intro if exists
    if current_content or len(sections) == 0:
        intro = parts[0].strip() if parts[0].strip() else ""
        if intro:
            sections.insert(0, ("Overview", intro))
    
    return sections


def count_tokens_approximate(text: str) -> int:
    """
    Approximate token count using word count (roughly 1 word = 1.3 tokens).
    More accurate methods would use tiktoken, but keeping it lightweight.
    """
    return int(len(text.split()) * 1.3)


def chunk_section_content(section_name: str, content: str, chunk_size: int = 350, overlap: int = 100) -> List[str]:
    """
    Chunk a section's content into smaller pieces.
    
    Args:
        section_name: Name of the section being chunked
        content: Content to chunk
        chunk_size: Target tokens per chunk
        overlap: Overlap tokens between chunks
        
    Returns:
        List of text chunks
    """
    chunks = []
    
    # Split by sentences/paragraphs for semantic boundaries
    paragraphs = content.split("\n\n")
    
    current_chunk = ""
    current_tokens = 0
    
    for para in paragraphs:
        para_tokens = count_tokens_approximate(para)
        
        if current_tokens + para_tokens > chunk_size and current_chunk:
            # Save current chunk and start new one
            chunks.append(current_chunk.strip())
            # Add overlap: include last paragraph(s) of previous chunk
            current_chunk = para
            current_tokens = para_tokens
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
            current_tokens += para_tokens
    
    # Add remaining content
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks if chunks else [content]


def extract_hierarchy_metadata(file_path: str) -> Dict[str, str]:
    """
    Extract metadata from folder hierarchy.
    
    Args:
        file_path: Full path to markdown file
        
    Returns:
        Dictionary with banking_type, product_type, feature_category
        
    Example:
        /knowledge_base/islami/credit/i_need_a_credit_card/visa_hasanah_gold.md
        → {banking_type: "islami", product_type: "credit", feature_category: "i_need_a_credit_card"}
    """
    path_parts = file_path.lower().split('/')
    
    hierarchy = {
        'banking_type': None,
        'product_type': None,
        'feature_category': None,
    }
    
    # Find knowledge_base index
    if 'knowledge_base' in path_parts:
        kb_index = path_parts.index('knowledge_base')
        
        # Extract based on folder depth after knowledge_base
        if len(path_parts) > kb_index + 1:
            hierarchy['banking_type'] = path_parts[kb_index + 1]  # conventional/islami
        if len(path_parts) > kb_index + 2:
            hierarchy['product_type'] = path_parts[kb_index + 2]  # credit/debit/loan
        if len(path_parts) > kb_index + 3:
            hierarchy['feature_category'] = path_parts[kb_index + 3]  # i_need_a_credit_card
    
    return hierarchy


def process_markdown_file(file_path: str, config: Dict[str, Any]) -> List[Chunk]:
    """
    Process a single markdown file into chunks.
    
    Args:
        file_path: Path to markdown file
        config: Configuration dictionary
        
    Returns:
        List of Chunk objects
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract frontmatter
    frontmatter, body = extract_frontmatter(content)
    
    # Extract hierarchy metadata from folder path
    hierarchy_meta = extract_hierarchy_metadata(file_path)
    
    # Extract metadata - prefer frontmatter, fall back to hierarchy
    product_id = frontmatter.get('product_id', 'UNKNOWN')
    product_name = frontmatter.get('product_name', 'Unknown Product')
    banking_type = frontmatter.get('banking_type', hierarchy_meta['banking_type'] or 'conventional')
    tier = frontmatter.get('tier', 'standard')
    category = frontmatter.get('category', 'general')
    use_cases = frontmatter.get('use_cases', [])
    employment_suitable = frontmatter.get('employment_suitable', [])
    
    chunks_list = []
    chunk_counter = 0
    
    # Split into sections
    sections = split_by_headers(body)
    
    for section_name, section_content in sections:
        if not section_content.strip():
            continue
        
        # Chunk section content
        section_chunks = chunk_section_content(
            section_name,
            section_content,
            chunk_size=config['chunking']['chunk_size'],
            overlap=config['chunking']['chunk_overlap']
        )
        
        for sub_idx, chunk_content in enumerate(section_chunks):
            chunk_counter += 1
            chunk_id = f"{product_id}_section_{chunk_counter}"
            
            # Extract keywords from chunk content (simple approach)
            keywords = []
            for use_case in use_cases:
                if use_case.lower().replace('_', ' ') in chunk_content.lower():
                    keywords.append(use_case)
            
            chunk = Chunk(
                chunk_id=chunk_id,
                product_id=product_id,
                product_name=product_name,
                banking_type=banking_type,
                product_type=hierarchy_meta['product_type'] or 'credit',
                feature_category=hierarchy_meta['feature_category'] or 'general',
                tier=tier,
                category=category,
                section=section_name,
                subsection=f"Part {sub_idx + 1}" if len(section_chunks) > 1 else section_name,
                content=chunk_content,
                use_cases=use_cases,
                employment_suitable=employment_suitable,
                keywords=keywords,
                source_file=os.path.basename(file_path)
            )
            chunks_list.append(chunk)
    
    return chunks_list


def process_knowledge_base(kb_root: str, config: Dict[str, Any]) -> List[Chunk]:
    """
    Process entire knowledge base into chunks.
    
    Args:
        kb_root: Root path to knowledge base
        config: Configuration dictionary
        
    Returns:
        List of all Chunk objects
    """
    all_chunks = []
    
    # Find all markdown files
    kb_path = Path(kb_root)
    md_files = list(kb_path.rglob("*.md"))
    
    print(f"Found {len(md_files)} markdown files")
    
    for file_path in md_files:
        print(f"Processing: {file_path.name}")
        try:
            chunks = process_markdown_file(str(file_path), config)
            all_chunks.extend(chunks)
            print(f"  ✓ Created {len(chunks)} chunks")
        except Exception as e:
            print(f"  ✗ Error processing {file_path}: {e}")
    
    print(f"\nTotal chunks created: {len(all_chunks)}")
    return all_chunks


def chunk_to_dict(chunk: Chunk) -> Dict[str, Any]:
    """Convert Chunk object to dictionary for storage."""
    return {
        'chunk_id': chunk.chunk_id,
        'product_id': chunk.product_id,
        'product_name': chunk.product_name,
        'banking_type': chunk.banking_type,
        'product_type': chunk.product_type,
        'feature_category': chunk.feature_category,
        'tier': chunk.tier,
        'category': chunk.category,
        'section': chunk.section,
        'subsection': chunk.subsection,
        'content': chunk.content,
        'use_cases': chunk.use_cases,
        'employment_suitable': chunk.employment_suitable,
        'keywords': chunk.keywords,
        'source_file': chunk.source_file,
    }


if __name__ == "__main__":
    # For testing
    import sys
    config_path = "./config.yaml"
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        kb_root = config['knowledge_base']['root_path']
        chunks = process_knowledge_base(kb_root, config)
        
        # Print sample chunk
        if chunks:
            print("\n" + "="*80)
            print("Sample Chunk:")
            print("="*80)
            sample = chunks[0]
            print(f"ID: {sample.chunk_id}")
            print(f"Product: {sample.product_name}")
            print(f"Section: {sample.section}")
            print(f"Banking Type: {sample.banking_type}")
            print(f"Content preview: {sample.content[:200]}...")

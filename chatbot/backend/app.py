"""
FastAPI backend for bank chatbot with CrewAI multi-agent support.
Serves both RAG and CrewAI pipelines via REST API.
"""

import os
import yaml
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from vector_db import initialize_knowledge_base
from pipelines import RAGPipeline, CrewPipeline
from tools.search_tools import set_vector_db
from tools.comparison_tools import set_vector_db_for_comparison


# Request/Response models
class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    user_employment: Optional[str] = None
    mode: str = "crew"  # "crew" or "rag"


class ChatResponse(BaseModel):
    query: str
    answer: str
    sources: Optional[List[Dict[str, str]]] = None
    agent_chain: Optional[List[str]] = None
    products_found: Optional[List[str]] = None
    session_id: str
    timestamp: str
    success: bool


class ReindexRequest(BaseModel):
    force: bool = False


class ReindexResponse(BaseModel):
    status: str
    chunks_indexed: int
    message: str


class HealthResponse(BaseModel):
    status: str
    vector_db_size: int
    model: str
    pipeline_modes: List[str]


class ConversationHistoryResponse(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]
    timestamp: str


# Global state
rag_pipeline = None
crew_pipeline = None
vector_db = None
session_history: dict = {}  # In-memory session store (replace with Redis for production)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, cleanup on shutdown."""
    global rag_pipeline, crew_pipeline, vector_db
    
    print("🚀 Starting chatbot backend with CrewAI support...")
    
    # Load config
    config_path = "./config.yaml"
    if not os.path.exists(config_path):
        print("✗ config.yaml not found")
        raise RuntimeError("Configuration file not found")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize vector DB
    try:
        vector_db = initialize_knowledge_base(config, force_reindex=False)
        print("✓ Vector DB initialized")
        
        # Inject vector_db into search tools
        set_vector_db(vector_db)
        
        # Inject vector_db into comparison tools
        set_vector_db_for_comparison(vector_db)
        print("✓ Search tools configured with vector DB")
        
        # Initialize RAG pipeline (for backward compatibility)
        rag_pipeline = RAGPipeline(vector_db, config)
        print("✓ RAG pipeline initialized")
        
        # Initialize CrewAI pipeline (new)
        crew_pipeline = CrewPipeline()
        print("✓ CrewAI pipeline initialized")
        
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        raise
    
    yield
    
    print("Shutting down chatbot backend...")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Prime Bank Chatbot API",
    description="Multi-agent chatbot with RAG support",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== ROUTES ====================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    if not crew_pipeline or not vector_db:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    stats = vector_db.get_collection_stats()
    
    return HealthResponse(
        status="healthy",
        vector_db_size=stats['total_chunks'],
        model="Qwen3-1.7B Q4 (via Ollama)",
        pipeline_modes=["crew", "rag"]
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint - routes to appropriate pipeline.
    Supports both RAG and CrewAI modes with session history.
    """
    if not crew_pipeline and not rag_pipeline:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    # Get or create session history
    history = session_history.get(session_id, [])
    print(f"Session [{session_id[-8:]}]: {len(history)} messages in history")
    
    mode = request.mode.lower()
    
    # Route to appropriate pipeline
    try:
        if mode == "crew":
            if not crew_pipeline:
                raise HTTPException(status_code=503, detail="CrewAI pipeline not initialized")
            
            # Use CrewAI multi-agent pipeline with history and session tracking
            result = crew_pipeline.run(
                query=request.query,
                customer_info={"employment": request.user_employment},
                conversation_history=history,  # Pass history for context
                session_id=session_id  # Pass session ID for product caching
            )
            
            # Save to session
            history.append({"role": "user", "content": request.query})
            history.append({"role": "assistant", "content": result['response']})
            session_history[session_id] = history[-20:]  # Keep last 10 exchanges
            
            return ChatResponse(
                query=request.query,
                answer=result['response'],
                sources=None,
                agent_chain=result.get('agent_chain', []),
                products_found=result.get('products_found', []),
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                success=True
            )
        
        elif mode == "rag":
            if not rag_pipeline:
                raise HTTPException(status_code=503, detail="RAG pipeline not initialized")
            
            # Use traditional RAG pipeline
            result = rag_pipeline.generate_response(request.query)
            
            # Save to session
            history.append({"role": "user", "content": request.query})
            history.append({"role": "assistant", "content": result['answer']})
            session_history[session_id] = history[-20:]
            
            return ChatResponse(
                query=request.query,
                answer=result['answer'],
                sources=result['sources'],
                agent_chain=["RAG"],
                products_found=[s.get('product_name', 'Unknown') for s in result['sources']],
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                success=result['success']
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}. Use 'crew' or 'rag'")
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()  # prints full stack to docker logs
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.get("/stats")
async def get_stats():
    """Get chatbot statistics."""
    if not vector_db:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    stats = vector_db.get_collection_stats()
    
    return {
        'collection_name': stats['collection_name'],
        'total_chunks': stats['total_chunks'],
        'embedding_model': 'all-MiniLM-L6-v2',
        'llm_model': 'Qwen3-1.7B Q4 (via Ollama)',
        'vector_db': 'Chroma',
        'pipeline_modes': ['crew', 'rag'],
        'description': 'Multi-agent system with 5 specialized agents'
    }


@app.post("/reindex", response_model=ReindexResponse)
async def reindex(request: ReindexRequest):
    """
    Reindex knowledge base.
    Warning: This operation may take several minutes.
    """
    global vector_db, rag_pipeline, crew_pipeline
    
    if not vector_db:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Load config
        with open("./config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        # Reinitialize
        vector_db = initialize_knowledge_base(config, force_reindex=request.force)
        rag_pipeline = RAGPipeline(vector_db, config)
        crew_pipeline = CrewPipeline()
        
        stats = vector_db.get_collection_stats()
        
        return ReindexResponse(
            status="success",
            chunks_indexed=stats['total_chunks'],
            message=f"Successfully indexed {stats['total_chunks']} chunks"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Reindexing failed: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with API documentation."""
    return {
        "message": "Prime Bank Chatbot API v2",
        "version": "2.0.0",
        "description": "CrewAI multi-agent + RAG chatbot",
        "endpoints": {
            "POST /chat": "Send query (supports 'crew' or 'rag' mode)",
            "GET /health": "Health check",
            "GET /stats": "System statistics",
            "POST /reindex": "Reindex knowledge base (admin)",
        },
        "examples": {
            "crew_mode": {
                "url": "POST /chat",
                "body": {"query": "Tell me about Visa Gold", "mode": "crew"}
            },
            "rag_mode": {
                "url": "POST /chat",
                "body": {"query": "Tell me about Visa Gold", "mode": "rag"}
            }
        },
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    
    # Load config for server settings
    config_path = "./config.yaml"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        api_config = config['api']
        
        print(f"Starting server at http://{api_config['host']}:{api_config['port']}")
        print("API docs available at http://localhost:8000/docs")
        print("Mode: CrewAI + RAG (multi-pipeline)")
        
        uvicorn.run(
            app,
            host=api_config['host'],
            port=api_config['port'],
            log_level="info"
        )

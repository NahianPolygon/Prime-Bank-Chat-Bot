"""
FastAPI backend for bank chatbot with simplified RAG pipeline.
Serves chatbot via REST API without CrewAI agents.
"""

import os
import yaml
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from vector_db import initialize_knowledge_base
from pipelines import Pipeline


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
pipeline = None
vector_db = None
session_history: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, cleanup on shutdown."""
    global pipeline, vector_db
    
    print("🚀 Starting chatbot backend...")
    
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
        
        # Initialize simplified Pipeline (no CrewAI)
        pipeline = Pipeline(vector_db=vector_db)
        print("✓ Pipeline initialized")
        
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        raise
    
    yield
    
    print("Shutting down chatbot backend...")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Prime Bank Chatbot API",
    description="Bank chatbot with RAG and simplified LLM pipeline",
    version="3.0.0",
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
    if not pipeline or not vector_db:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    stats = vector_db.get_collection_stats()
    
    return HealthResponse(
        status="healthy",
        vector_db_size=stats['total_chunks'],
        model="Qwen3-1.7B Q4 (via Ollama)",
        pipeline_modes=["simplified"]
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint - uses simplified pipeline with direct Ollama calls.
    """
    if not pipeline:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    # Get or create session history
    history = session_history.get(session_id, [])
    print(f"Session [{session_id[-8:]}]: {len(history)} messages in history")
    
    # Use simplified Pipeline
    try:
        result = pipeline.run(
            query=request.query,
            customer_info={"employment": request.user_employment},
            conversation_history=history,
            session_id=session_id
        )
        
        # Save to session
        history.append({"role": "user", "content": request.query})
        history.append({"role": "assistant", "content": result['response']})
        session_history[session_id] = history[-20:]
        
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
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream LLM responses (SSE) for RAG-style answers.

    Frontend should connect with EventSource and read `data:` events.
    """
    if not pipeline:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    session_id = request.session_id or str(uuid.uuid4())
    history = session_history.get(session_id, [])

    try:
        result = pipeline.run(
            query=request.query,
            customer_info={"employment": request.user_employment},
            conversation_history=history,
            session_id=session_id,
            stream=True
        )

        # If pipeline returned a streaming wrapper
        if isinstance(result, dict) and 'stream_generator' in result:
            gen = result['stream_generator']

            def event_stream():
                try:
                    for chunk in gen:
                        # simple SSE data event
                        yield f"data: {chunk}\n\n"
                    # send finalization event with products metadata
                    payload = {
                        'products_text': result.get('products_text', ''),
                        'product_names': getattr(pipeline._get_state(session_id), 'product_names', [])
                    }
                    yield f"event: done\ndata: {json.dumps(payload)}\n\n"
                except Exception as e:
                    yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

            # append first user/assistant messages to history asynchronously
            history.append({"role": "user", "content": request.query})
            session_history[session_id] = history[-20:]

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        # non-streaming fallback
        return ChatResponse(
            query=request.query,
            answer=result.get('response', ''),
            sources=None,
            agent_chain=result.get('agent_chain', []),
            products_found=result.get('products_found', []),
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            success=True
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
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
        'description': 'Simplified pipeline with 3 focused LLM calls'
    }


@app.post("/reindex", response_model=ReindexResponse)
async def reindex(request: ReindexRequest):
    """
    Reindex knowledge base.
    Warning: This operation may take several minutes.
    """
    global vector_db, pipeline
    
    if not vector_db:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Load config
        with open("./config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        # Reinitialize
        vector_db = initialize_knowledge_base(config, force_reindex=request.force)
        pipeline = Pipeline(vector_db=vector_db)
        
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
        "message": "Prime Bank Chatbot API",
        "version": "2.0.0",
        "description": "Simplified pipeline: direct Ollama + Vector DB",
        "endpoints": {
            "POST /chat": "Send query",
            "GET /health": "Health check",
            "GET /stats": "System statistics",
            "POST /reindex": "Reindex knowledge base (admin)",
        },
        "examples": {
            "basic": {
                "url": "POST /chat",
                "body": {"query": "Tell me about Visa Gold"}
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
        print("Mode: simplified pipeline (Ollama + Vector DB)")
        
        uvicorn.run(
            app,
            host=api_config['host'],
            port=api_config['port'],
            log_level="info"
        )

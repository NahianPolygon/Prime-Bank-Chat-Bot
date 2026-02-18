# CrewAI Multi-Agent Chatbot - Quick Start Guide

## Installation

### 1. Install Dependencies
```bash
cd /mnt/sda1/Polygon/primebot/chatbot/backend
pip install -r requirements.txt
```

### 2. Verify Knowledge Base
```bash
# Check knowledge base exists
ls -la ../knowledge_base/
# Should show: conventional/, islami/
```

### 3. Start Ollama (in separate terminal)
```bash
ollama serve
# Wait until: "Listening on 127.0.0.1:11434"

# In another terminal, pull model (first time only)
ollama pull qwen:1.7b-q4
```

### 4. Start Backend Server
```bash
cd /mnt/sda1/Polygon/primebot/chatbot/backend
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

**Expected Output**:
```
🚀 Starting chatbot backend with CrewAI support...
✓ Vector DB initialized
✓ RAG pipeline initialized
✓ CrewAI pipeline initialized with multi-turn context
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## API Testing

### 1. Health Check
```bash
curl http://localhost:8000/health
```

### 2. CrewAI Mode (Multi-Agent)
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Tell me about Visa Gold",
    "session_id": "user_001",
    "mode": "crew"
  }'
```

**Expected Response**:
```json
{
  "query": "Tell me about Visa Gold",
  "answer": "## Visa Gold Credit Card\n...",
  "agent_chain": [
    "IntentClassifier",
    "ProductRetriever",
    "ResponseFormatter"
  ],
  "products_found": ["Visa Gold Credit Card"],
  "session_id": "user_001",
  "success": true
}
```

### 3. RAG Mode (Traditional)
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Tell me about Visa Gold",
    "session_id": "user_001",
    "mode": "rag"
  }'
```

### 4. Multi-Turn Conversation
```bash
# Turn 1
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I am salaried and looking for Islamic cards",
    "session_id": "user_002",
    "user_employment": "salaried",
    "mode": "crew"
  }'

# Turn 2 (same session - will remember salaried + islamic preference)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What about platinum options?",
    "session_id": "user_002",
    "mode": "crew"
  }'
```

### 5. Get Conversation History
```bash
curl http://localhost:8000/conversation/user_002
```

### 6. Session Statistics
```bash
curl http://localhost:8000/session/user_002/stats
```

## Test Cases

### Test 1: Intent Detection
**Query**: "Compare Islamic platinum cards"
**Expected**: 
- Intent: comparison
- Banking Type: islami
- Tier: platinum

### Test 2: Multi-Agent Pipeline
**Query**: "I'm salaried. Can I get a Mastercard Platinum?"
**Expected Agents**:
1. IntentClassifier → eligibility_check intent
2. ProductRetriever → Islamic cards
3. EligibilityAnalyzer → Check salaried compatibility
4. ResponseFormatter

### Test 3: Comparison Feature
**Query**: "How does Visa Gold compare to Mastercard Gold?"
**Expected Agents**:
1. IntentClassifier → comparison intent
2. ProductRetriever → Both cards
3. FeatureComparator → Generate comparison table
4. ResponseFormatter

### Test 4: Fallback Handling
**Query**: "Show me debit cards" (when only credit cards in KB)
**Expected**: Clarification prompt asking for more details

### Test 5: Session Persistence
**Turn 1**: "Islamic cards"
**Turn 2**: "Show me gold" → Should remember "islamic" preference

## File Structure

```
backend/
├── app.py                  # FastAPI main app (NEW: CrewAI routes)
├── crew_tools.py          # Tool definitions (NEW)
├── crew_agents.py         # Agent implementations (NEW)
├── crew_pipeline.py       # Orchestration + session mgmt (NEW)
├── vector_db.py           # Vector DB (UPDATED: metadata filters)
├── chunker.py             # Chunking (UPDATED: hierarchy metadata)
├── rag_pipeline.py        # Traditional RAG (existing)
├── config.yaml            # Configuration
├── requirements.txt       # Dependencies (UPDATED: +CrewAI)
└── frontend.html          # Web UI
```

## Monitoring

### Check Vector DB Stats
```bash
curl http://localhost:8000/stats
```

### Check Server Health
```bash
curl http://localhost:8000/health
```

### Monitor Agent Performance
Watch the terminal logs for agent chain output:
```
[Intent Classifier]
  Query: Tell me about Visa Gold
  Intent: product_info
  Banking Type: Not specified

[Product Retriever]
  Search Query: Tell me about Visa Gold
  Metadata Filters: {}
  Results Found: 2
    - Visa Gold Credit Card
    - Mastercard Gold Credit Card

[Response Formatter]
  Products Formatted: 2
  Included Comparison: No
  Citations Added: Yes
```

## Troubleshooting

### Issue: "Service not initialized"
**Solution**: Ensure Ollama is running and vector DB loaded
```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Re-run server
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

### Issue: Empty or no products found
**Solution**: Check knowledge base structure
```bash
# Verify MD files exist
find ../knowledge_base -name "*.md" | wc -l  # Should be 8

# Check metadata extraction
python -c "from chunker import process_knowledge_base; chunks = process_knowledge_base('../knowledge_base', {'chunking': {}}); print(f'Found {len(chunks)} chunks')"
```

### Issue: Slow responses (>60s)
**Solution**: Check Ollama model is loaded
```bash
# Check running models
ollama list
ollama show qwen:1.7b-q4

# If slow, restart with more CPU cores
OLLAMA_NUM_THREAD=8 ollama serve
```

### Issue: Memory errors
**Solution**: Reduce session window size
Edit `crew_pipeline.py`:
```python
self.max_messages = 5  # Reduce from 10 to 5
```

## API Documentation

**Interactive Docs**: http://localhost:8000/docs

**Key Endpoints**:
- `POST /chat` - Send query (supports crew/rag mode)
- `GET /health` - Health check
- `GET /stats` - System stats
- `GET /conversation/{session_id}` - Get history
- `GET /session/{session_id}/stats` - Session info
- `DELETE /session/{session_id}` - Clear session

## Next Steps

1. **Test with Real Queries**: Use frontend to test with actual users
2. **Monitor Performance**: Track response times and agent usage
3. **Optimize Parameters**: Adjust `top_k`, `chunk_size`, session TTL
4. **Add Custom Agents**: Create specialized agents for specific tasks
5. **Scale Sessions**: Move from in-memory to Redis for multi-server setup

## Architecture References

- **CrewAI Framework**: [docs/CREWAI_ARCHITECTURE.md](CREWAI_ARCHITECTURE.md)
- **Chunking Strategy**: Knowledge base split into semantic chunks with metadata
- **Multi-Agent Pattern**: Hierarchical Manager orchestration model
- **Session Management**: In-memory store with 30-minute TTL
